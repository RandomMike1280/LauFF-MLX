"""Compare the optimized full-graph simulator against its independent baseline.
Run from the project root with .venv/bin/python scripts/verify_neural.py.
"""
import json
from pathlib import Path
import numpy as np
from lif import core, engine_fused, engine_naive
from lauff.neural import MaleCNS

root = Path(__file__).resolve().parents[1]
brain = MaleCNS(root/'vendor/drosophila-brain-mlx', root/'vendor/drosophila-brain-mlx/data/pack/male_cns_v1')
stim = core.make_stimulus_for(brain.pack, brain.targets, 100.0, n_ticks=1000, seed=77)
results = []
for silenced in (False, True):
    mask = None
    if silenced:
        mask = np.zeros(brain.pack.n_neurons, dtype=bool)
        mask[brain.targets] = True
    print(f'Checking full graph, 100 ms, silenced={silenced}', flush=True)
    ref = engine_naive.run(brain.pack, stim, silenced=mask, warmup=0)
    got = engine_fused.run(brain.pack, stim, silenced=mask, warmup=0, chunk=32, edge_split=8)
    checks = {name: bool(np.array_equal(getattr(ref,name),getattr(got,name)))
              for name in ('spike_counts','v_final','g_final')}
    results.append({'silenced':silenced,'checks':checks,'spikes':int(got.spike_counts.sum()),
                    'baseline_seconds':ref.seconds,'fused_seconds':got.seconds})
    print(results[-1], flush=True)
report = {'fingerprint':brain.fingerprint,'provenance':brain.provenance,'seed':77,'n_ticks':1000,
          'results':results,'passed':all(all(r['checks'].values()) for r in results)}
(root/'outputs').mkdir(exist_ok=True)
(root/'outputs/engine-parity.json').write_text(json.dumps(report,indent=2)+'\n')
if not report['passed']:
    raise SystemExit('Engine parity FAILED')
