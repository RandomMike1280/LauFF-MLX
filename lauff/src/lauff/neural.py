"""MaleCNS adapter. No game-policy or mock fallback exists in this module."""
from __future__ import annotations
import hashlib
import json
import math
import importlib.metadata
from pathlib import Path
import subprocess
import time

PIN = "e417b33616513ef350b1b1c3cdf2b5b7a1799c8e"
DRIVE = ("LB3b_R", "LB3c_R")
READOUT = ("MN9_L", "MN9_R")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class MaleCNS:
    def __init__(self, upstream: Path, pack: Path):
        import numpy as np
        from lif import core, engine_fused, names
        import lif
        upstream = upstream.resolve()
        if not Path(lif.__file__).resolve().is_relative_to(upstream):
            raise ValueError("lif must be installed from the pinned upstream checkout")
        revision = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(["git", "-C", str(upstream), "status", "--porcelain", "--untracked-files=no"], text=True)
        if revision != PIN or dirty.strip():
            raise ValueError("upstream revision differs from lock or has tracked modifications")
        self.np, self.core, self.engine = np, core, engine_fused
        self.pack = core.load_pack(pack)
        if "male" not in str(self.pack.manifest.get("dataset", "")).lower():
            raise ValueError("MaleCNS pack required")
        labels = names.load(self.pack)
        if labels is None:
            raise ValueError("verified annotation sidecar required")
        populations = {name: labels.select(name) for name in DRIVE + READOUT}
        if any(not indices for indices in populations.values()):
            raise ValueError("missing sweet-taste or MN9 annotations")
        self.targets = np.array(sorted({i for name in DRIVE for i in populations[name]}), dtype=np.int32)
        self.readouts = {name: populations[name] for name in READOUT}
        self.provenance = {
            "upstream_commit": revision, "manifest_sha256": digest(self.pack.manifest),
            "dataset": self.pack.manifest["dataset"], "neurons": self.pack.n_neurons,
            "edges": self.pack.n_edges, "populations": {
                name: [str(self.pack.neuron_ids[i]) for i in indices] for name, indices in populations.items()},
            "dt_ms": core.DT, "duration_s": 1, "sweet_rate_hz": 100,
            "refractory_ms": core.T_RFC, "delay_ms": core.T_DLY,
            "membrane_tau_ms": core.T_MBR, "synapse_tau_ms": core.TAU,
            "reset_each_trial": True, "readout": "max of left/right MN9 population mean rates",
            "engine": "fused", "chunk": 32, "edge_split": 8,
            "constants": {k: float(v) for k, v in core.constants_f32().items()},
            "packages": {name: importlib.metadata.version(name) for name in ("mlx", "mlx-metal", "numpy", "pyarrow")},
        }
        self.fingerprint = digest(self.provenance)

    def trial(self, sweet: bool, seed: int, silenced=False):
        started = time.perf_counter()
        stimulus = self.core.make_stimulus_for(self.pack, self.targets, 100.0 if sweet else 0.0,
                                                n_ticks=round(1000 / self.core.DT), seed=seed)
        mask = None
        if silenced:
            mask = self.np.zeros(self.pack.n_neurons, dtype=bool)
            mask[self.targets] = True  # block outgoing transmission; inputs still spike
        result = self.engine.run(self.pack, stimulus, silenced=mask, chunk=32, edge_split=8)
        rates = {name: float(result.spike_counts[indices].mean()) for name, indices in self.readouts.items()}
        return {"seed": seed, "sweet": sweet, "silenced": silenced, "rates_hz": rates,
                "score_hz": max(rates.values()), "total_spikes": int(result.spike_counts.sum()),
                "input_spikes": int(result.spike_counts[self.targets].sum()),
                "visual_activity": self.visual.summarize(result.spike_counts) if getattr(self, "visual", None) else None,
                "stimulus_sha256": stimulus.sha256(), "wall_seconds": time.perf_counter() - started,
                "engine_seconds": result.seconds, "peak_bytes": result.peak_bytes}


def fit_threshold(trials):
    positive = [t["score_hz"] for t in trials if t["sweet"] and not t["silenced"]]
    negative = [t["score_hz"] for t in trials if not t["sweet"] or t["silenced"]]
    if not positive or not negative or not all(math.isfinite(x) for x in positive + negative):
        raise ValueError("incomplete or nonfinite calibration")
    if min(positive) <= max(negative):
        raise ValueError("neural validation failed: sweet and control responses overlap")
    return (min(positive) + max(negative)) / 2


def calibrate(brain, count=10, progress=print, checkpoint=lambda result: None):
    if count < 3:
        raise ValueError("at least three trials per condition and split required")
    result = {"schema": 1, "fingerprint": brain.fingerprint, "provenance": brain.provenance,
              "training": [], "held_out": [], "passed": False}
    for split, first in (("training", 1000), ("held_out", 100000)):
        for index in range(count):
            for sweet, silenced in ((False, False), (True, False), (True, True)):
                trial = brain.trial(sweet, first + index, silenced)
                result[split].append(trial)
                checkpoint(result)
                progress(f"{split} seed={first + index} sweet={sweet} silenced={silenced} MN9={trial['score_hz']:.1f} Hz")
        if split == "training":
            result["threshold_hz"] = fit_threshold(result[split])
    threshold = result["threshold_hz"]
    result["passed"] = all((t["score_hz"] >= threshold) == (t["sweet"] and not t["silenced"])
                           for t in result["held_out"])
    if not result["passed"]:
        raise ValueError("held-out neural controls failed; live control disabled")
    return result


def load_calibration(path, brain):
    report = json.loads(Path(path).read_text())
    if report.get("passed") is not True or report.get("fingerprint") != brain.fingerprint:
        raise ValueError("passing calibration for this exact model required")
    for split in ("training", "held_out"):
        trials = report.get(split, [])
        groups = {(False, False): [], (True, False): [], (True, True): []}
        for trial in trials:
            condition = (trial.get("sweet"), trial.get("silenced"))
            if condition not in groups or not math.isfinite(trial.get("score_hz", float("nan"))):
                raise ValueError("invalid calibration trial")
            groups[condition].append(trial["seed"])
        if any(len(seeds) < 3 or len(set(seeds)) != len(seeds) for seeds in groups.values()):
            raise ValueError("incomplete calibration controls")
        if len({tuple(sorted(seeds)) for seeds in groups.values()}) != 1:
            raise ValueError("calibration controls must use matched seeds")
    if {t["seed"] for t in report["training"]} & {t["seed"] for t in report["held_out"]}:
        raise ValueError("calibration and held-out seeds overlap")
    threshold = fit_threshold(report["training"])
    if threshold != report.get("threshold_hz") or not report.get("held_out") or not all(
        (t["score_hz"] >= threshold) == (t["sweet"] and not t["silenced"]) for t in report["held_out"]):
        raise ValueError("invalid calibration evidence")
    return report
