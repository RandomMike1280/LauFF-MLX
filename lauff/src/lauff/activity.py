"""Read-only visualization telemetry from actual full-network spike counts."""
from importlib.resources import files
import numpy as np


class ActivityMap:
    def __init__(self, pack):
        path=files('lauff').joinpath('web/brain-layout.npz')
        with np.load(path, allow_pickle=False) as layout:
            if not np.array_equal(layout['neuron_ids'], np.asarray(pack.neuron_ids).astype(str)):
                raise ValueError('visual activity layout differs from the model neuron ordering')
            self.mapped=layout['mapped_indices']
            self.region_index=layout['region_index']
            self.cloud=layout['cloud_indices']
            self.nodes=layout['node_indices']
            self.node_ids=layout['node_ids']
        self.region_size=np.bincount(self.region_index)

    def summarize(self, spike_counts, duration_s=1.0):
        counts=np.asarray(spike_counts)
        rates=counts/duration_s
        mapped=rates[self.mapped]
        # Every soma-mapped model neuron contributes, including inactive ones.
        region_mean=np.bincount(self.region_index, weights=mapped)/self.region_size
        region_fraction=np.bincount(self.region_index, weights=(mapped>0))/self.region_size
        return {
            'duration_s':duration_s, 'source':'measured model spike counts',
            'cloud_rates_hz':rates[self.cloud].tolist(),
            'rates_by_id':{str(k):float(v) for k,v in zip(self.node_ids,rates[self.nodes])},
            'region_mean_hz':region_mean.round(4).tolist(),
            'region_active_fraction':region_fraction.round(6).tolist(),
            'active_neurons':int((counts>0).sum()), 'total_neurons':len(counts),
            'mapped_neurons':len(self.mapped), 'max_hz':float(rates.max()),
        }
