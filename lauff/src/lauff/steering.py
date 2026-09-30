"""Research-only PFL3 -> DNa02 assay; never emits a drone command.

Direct stimulation of central neurons is an intervention, not a validated
sensory interface, goal policy, or complete navigation controller.
"""
from __future__ import annotations
import json
from pathlib import Path
import time
from .neural import digest

STUDY = 'https://pmc.ncbi.nlm.nih.gov/articles/PMC10881397/'
CONDITIONS = ('zero', 'left', 'right', 'left_silenced', 'right_silenced')


class SteeringAssay:
    def __init__(self, brain):
        from lif import names
        self.brain = brain
        np = brain.np
        labels = names.load(brain.pack)
        self.outputs = {side: labels.select('DNa02_' + side) for side in ('L', 'R')}
        if any(len(v) != 1 for v in self.outputs.values()):
            raise ValueError('expected one DNa02 neuron per side')
        # PFL3 instance L/R labels describe PB anatomy, NOT motor output side.
        # Partition by actual direct excitatory contacts to DNa02, before trials.
        ptr = np.load(brain.pack.path / 'row_ptr.npy', mmap_mode='r')
        dst = np.load(brain.pack.path / 'destinations.npy', mmap_mode='r')
        weight = np.load(brain.pack.path / 'signed_counts.npy', mmap_mode='r')
        self.groups = {'left': [], 'right': []}
        evidence = []
        for i in labels.select('PFL3'):
            d, w = dst[ptr[i]:ptr[i+1]], weight[ptr[i]:ptr[i+1]]
            contacts = {side: int(w[d == indices[0]].sum()) for side, indices in self.outputs.items()}
            if contacts['L'] > 0 and contacts['R'] == 0:
                side = 'left'
            elif contacts['R'] > 0 and contacts['L'] == 0:
                side = 'right'
            else:
                raise ValueError('ambiguous PFL3 output laterality; manual anatomical review required')
            self.groups[side].append(i)
            evidence.append({'body_id': str(brain.pack.neuron_ids[i]), 'side': side,
                             'signed_direct_contacts': contacts})
        if any(not v for v in self.groups.values()):
            raise ValueError('missing PFL3 projection population')
        self.provenance = {
            'feeding_model_fingerprint': brain.fingerprint,
            'model': brain.provenance,
            'study': STUDY,
            'selection': 'PFL3 with positive direct signed contacts to only one DNa02 side',
            'selection_evidence': evidence,
            'outputs': {side: [str(brain.pack.neuron_ids[i]) for i in indices]
                        for side, indices in self.outputs.items()},
            'duration_s': 1, 'input_rate_hz': 100, 'reset_each_trial': True,
            'score': 'DNa02_R minus DNa02_L spikes / one second',
            'silencing': 'all outgoing synapses of BOTH PFL3 projection populations',
            'status': 'central-neuron perturbation assay; no sensory navigation claim',
        }
        self.fingerprint = digest(self.provenance)

    def trial(self, condition, seed):
        if condition not in CONDITIONS:
            raise ValueError('invalid assay condition')
        b = self.brain
        side = condition.split('_')[0]
        indices = self.groups.get(side, self.groups['left'] + self.groups['right'])
        started = time.perf_counter()
        stimulus = b.core.make_stimulus_for(b.pack, b.np.array(indices, dtype=b.np.int32),
            0.0 if condition == 'zero' else 100.0, n_ticks=round(1000 / b.core.DT), seed=seed)
        silenced = condition.endswith('_silenced')
        mask = None
        if silenced:
            mask = b.np.zeros(b.pack.n_neurons, dtype=bool)
            mask[self.groups['left'] + self.groups['right']] = True
        result = b.engine.run(b.pack, stimulus, silenced=mask, chunk=32, edge_split=8)
        rates = {side: float(result.spike_counts[ids].mean()) for side, ids in self.outputs.items()}
        return {'condition': condition, 'seed': seed, 'rates_hz': rates,
                'difference_hz': rates['R'] - rates['L'],
                'input_spikes': int(result.spike_counts[indices].sum()),
                'total_spikes': int(result.spike_counts.sum()),
                'stimulus_sha256': stimulus.sha256(), 'silenced': silenced,
                'wall_seconds': time.perf_counter() - started,
                'engine_seconds': result.seconds, 'peak_bytes': result.peak_bytes}


def fit_steering_gate(trials):
    groups = {c: [t for t in trials if t['condition'] == c] for c in CONDITIONS}
    if any(not values for values in groups.values()):
        raise ValueError('missing steering control condition')
    controls = [abs(t['difference_hz']) for c in ('zero','left_silenced','right_silenced') for t in groups[c]]
    positive = [t['difference_hz'] for t in groups['right']] + [-t['difference_hz'] for t in groups['left']]
    import math
    if not all(math.isfinite(x) for x in controls + positive) or min(positive) <= max(controls):
        raise ValueError('steering gate failed: sided responses do not separate from controls')
    return (min(positive) + max(controls)) / 2


def validate(assay, count=10, checkpoint=lambda result: None, progress=print):
    if count < 3:
        raise ValueError('at least three matched seeds per condition per split')
    report = {'schema':1, 'kind':'steering_circuit_perturbation', 'fingerprint':assay.fingerprint,
              'provenance':assay.provenance, 'training':[], 'held_out':[], 'passed':False,
              'autonomous_navigation_enabled':False}
    checkpoint(report)
    for split, start in (('training',300_000),('held_out',400_000)):
        for index in range(count):
            for condition in CONDITIONS:
                t = assay.trial(condition, start + index)
                report[split].append(t)
                checkpoint(report)
                progress(f"{split} seed={t['seed']} {condition}: R-L={t['difference_hz']:.1f} Hz")
        if split == 'training':
            try:
                report['threshold_hz'] = fit_steering_gate(report[split])
            except ValueError as error:
                report['failure'] = str(error)
                checkpoint(report)
                return report
    threshold = report['threshold_hz']
    def expected(t):
        score = t['difference_hz']
        if t['condition'] == 'right': return score >= threshold
        if t['condition'] == 'left': return score <= -threshold
        return abs(score) < threshold
    report['passed'] = all(expected(t) for t in report['held_out'])
    if not report['passed']:
        report['failure'] = 'held-out sided response or transmission control failed'
    checkpoint(report)
    return report
