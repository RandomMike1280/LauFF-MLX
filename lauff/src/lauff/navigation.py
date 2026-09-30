"""Experimental allocentric FC2 -> PFL3 interface, not a biological walking model.

All four cues enter simultaneously. No destination is selected before simulation.
The cardinal naming of anatomical channel bands is an engineered interface.
"""
from __future__ import annotations
import json
import math
import re
import time
from pathlib import Path
from .neural import digest

DIRECTIONS = ('NORTH', 'EAST', 'SOUTH', 'WEST')
BASELINE = 0.2
RATE = 100.0


class Navigation:
    def __init__(self, brain):
        import pyarrow.parquet as pq
        b = self.brain = brain
        np = b.np
        rows = pq.read_table(b.pack.path/'names.parquet').to_pylist()
        self.inputs = [i for i,r in enumerate(rows) if r['type'] in ('FC2A','FC2B','FC2C')]
        self.outputs = [i for i,r in enumerate(rows) if r['type']=='PFL3']
        self.telemetry = self.outputs + [i for i,r in enumerate(rows) if r['type'] in ('DNa02','DNa03')]
        if not self.inputs or len(self.outputs)!=24:
            raise ValueError('missing navigation annotations')
        channels=[]
        for i in self.inputs:
            m=re.search(r'_C([1-9])_', rows[i]['instance'] or '')
            if not m: raise ValueError('unrecognized FC2 column')
            channels.append(min(3,(int(m[1])-1)//2))
        self.channels=np.array(channels)
        ptr=np.load(b.pack.path/'row_ptr.npy',mmap_mode='r')
        dst=np.load(b.pack.path/'destinations.npy',mmap_mode='r')
        weights=np.load(b.pack.path/'signed_counts.npy',mmap_mode='r')
        matrix=np.zeros((4,len(self.outputs)))
        for i,channel in zip(self.inputs,channels):
            d,w=dst[ptr[i]:ptr[i+1]],weights[ptr[i]:ptr[i+1]]
            for col,j in enumerate(self.outputs):matrix[channel,col]+=w[d==j].sum()
        self.output_channels=matrix.argmax(axis=0)
        if (matrix.max(axis=0)<=0).any() or len(set(self.output_channels))!=4:
            raise ValueError('ambiguous/missing downstream navigation channels')
        self.provenance={'model_fingerprint':b.fingerprint,'model':b.provenance,
            'interface':'artificial simultaneous world-cardinal local cues -> FC2 columns -> PFL3 population mean -> discrete step',
            'direction_labels':list(DIRECTIONS),'column_bands':[[1,2],[3,4],[5,6],[7,8,9]],
            'input_ids':[str(b.pack.neuron_ids[i]) for i in self.inputs], 'input_channels':channels,
            'output_ids':[str(b.pack.neuron_ids[i]) for i in self.outputs],
            'output_channels':[int(i) for i in self.output_channels],
            'selection':'each PFL3 assigned to strongest summed direct signed FC2 channel contacts',
            'selection_contacts':matrix.astype(int).tolist(),
            'rate_hz':RATE,'exploration_baseline':BASELINE,'duration_s':1,'reset_each_trial':True,
            'decoder':'largest calibrated downstream population activity; unique winner required',
            'scope':'local experimental neural foraging, not DNa02/heading or full biological locomotion'}
        self.fingerprint=digest(self.provenance)

    def trial(self,cues,seed,silenced=False):
        import mlx.core as mx
        b=self.brain; np=b.np
        cues=np.asarray(cues,dtype=float)
        if cues.shape!=(4,) or not np.isfinite(cues).all() or (cues<0).any() or (cues>1).any():
            raise ValueError('four finite cue strengths in [0,1] required')
        start=time.perf_counter();ticks=round(1000/b.core.DT)
        rates=RATE*cues[self.channels]
        draws=np.random.default_rng(seed).random((ticks,len(self.inputs))) < rates*b.core.DT/1000
        stimulus=b.core.Stimulus(np.array(self.inputs,dtype=np.int32),mx.array(draws),ticks,float('nan'),seed)
        mask=None
        if silenced:
            mask=np.zeros(b.pack.n_neurons,dtype=bool);mask[self.inputs]=True
        result=b.engine.run(b.pack,stimulus,silenced=mask,chunk=32,edge_split=8)
        spikes=result.spike_counts[self.outputs]
        scores=[float(spikes[self.output_channels==i].mean()) for i in range(4)]
        return {'seed':seed,'cues':cues.tolist(),'silenced':silenced,'scores_hz':scores,
                'pfl3_spikes':[int(x) for x in spikes],
                'visual_activity':b.visual.summarize(result.spike_counts) if getattr(b,'visual',None) else None,
                'rates_by_id':{str(b.pack.neuron_ids[i]):int(result.spike_counts[i]) for i in self.telemetry},'input_spikes':int(result.spike_counts[self.inputs].sum()),
                'stimulus_sha256':stimulus.sha256(),'wall_seconds':time.perf_counter()-start,
                'engine_seconds':result.seconds,'peak_bytes':result.peak_bytes}


def cues_from_observation(obs):
    # Unknown/outside cells have no cue. Every observed tile contributes independently.
    return [0.0 if not t['known'] else BASELINE+(1-BASELINE)*(
        min(100,max(0,t['fruit_percent']))/100 if t['has_fruit'] else 0)
        for t in obs['tiles'][1:]]


def decode(trial,calibration):
    raw=trial.get('scores_hz',[]);gains=calibration.get('gains',[])
    if (len(raw)!=4 or len(gains)!=4 or not all(math.isfinite(x) and x>=0 for x in raw)
        or not all(math.isfinite(x) and x>0 for x in gains)
        or not math.isfinite(calibration.get('threshold',float('nan'))) or calibration['threshold']<=0
        or not math.isfinite(calibration.get('margin',float('nan'))) or calibration['margin']<0):
        raise ValueError('invalid neural decoder or response')
    scores=[x/g for x,g in zip(trial['scores_hz'],calibration['gains'])]
    ranked=sorted(range(4),key=lambda i:scores[i],reverse=True)
    winner=ranked[0]
    if scores[winner]<calibration['threshold'] or scores[winner]-scores[ranked[1]]<=calibration['margin']:
        return 'WAIT'
    return 'MOVE_'+DIRECTIONS[winner]


def validation_cases():
    cases=[]
    for i in range(4):
        single=[float(j==i) for j in range(4)]
        cases.append((f'single_{i}',single,False,['MOVE_'+DIRECTIONS[i]]))
        cases.append((f'food_{i}',[1.0 if j==i else BASELINE for j in range(4)],False,['MOVE_'+DIRECTIONS[i]]))
        cases.append((f'contrast_{i}',[1.0 if j==i else .5 if j==(i+1)%4 else BASELINE for j in range(4)],False,['MOVE_'+DIRECTIONS[i]]))
        cases.append((f'blocked_{i}',single,True,['WAIT']))
    for i in range(4):
        for j in range(i+1,4):
            cases.append((f'pair_{i}_{j}',[1.0 if k in (i,j) else BASELINE for k in range(4)],False,
                          ['WAIT','MOVE_'+DIRECTIONS[i],'MOVE_'+DIRECTIONS[j]]))
    cases.extend([('zero',[0.0]*4,False,['WAIT']),('empty',[BASELINE]*4,False,['WAIT']),
                  ('equal',[1.0]*4,False,['WAIT']+['MOVE_'+d for d in DIRECTIONS]),
                  ('blocked_equal',[1.0]*4,True,['WAIT'])])
    return cases


def fit_decoder(training):
    import statistics
    gains=[statistics.mean(t['scores_hz'][i] for t in training if t['case']==f'single_{i}') for i in range(4)]
    if any(g<=0 for g in gains):raise ValueError('navigation channels failed to transmit')
    controls=[max(x/g for x,g in zip(t['scores_hz'],gains)) for t in training
              if t['case'] in ('zero','empty') or t['silenced']]
    return {'gains':gains,'threshold':max(controls)+.02,'margin':.03}


def calibrate_navigation(nav,count=3,checkpoint=lambda r:None,progress=print):
    if count<3:raise ValueError('at least 3 matched seeds per condition per split')
    r={'schema':1,'kind':'fc2_pfl3_cardinal_interface','fingerprint':nav.fingerprint,
       'provenance':nav.provenance,'training':[],'held_out':[],'passed':False}
    checkpoint(r)
    for split,start in (('training',600000),('held_out',700000)):
        for i in range(count):
            for name,cues,silenced,allowed in validation_cases():
                trial=nav.trial(cues,start+i,silenced)
                trial.update(case=name,allowed_actions=allowed)
                r[split].append(trial)
                checkpoint(r)
                progress(f"{split} {start+i} {name}: {trial['scores_hz']}")
        if split=='training':
            r['decoder']=fit_decoder(r['training'])
    failures=[]
    for split in ('training','held_out'):
        for t in r[split]:
            t['action']=decode(t,r['decoder'])
            if t['action'] not in t['allowed_actions']:
                failures.append({'split':split,'seed':t['seed'],'case':t['case'],'action':t['action']})
    r['failures']=failures;r['passed']=not failures
    checkpoint(r)
    return r


def load_navigation(path,nav):
    r=json.loads(Path(path).read_text())
    if r.get('passed') is not True or r.get('fingerprint')!=nav.fingerprint:
        raise ValueError('passing navigation validation for this exact interface required')
    cases={name:(cues,silenced,allowed) for name,cues,silenced,allowed in validation_cases()}
    seeds=[]
    for split in ('training','held_out'):
        groups={name:set() for name in cases}
        for t in r.get(split,[]):
            spec=cases.get(t.get('case'))
            if not spec or (t.get('cues'),t.get('silenced'),t.get('allowed_actions'))!=spec:
                raise ValueError('invalid navigation validation case')
            import math
            if len(t.get('scores_hz',[]))!=4 or not all(math.isfinite(v) and v>=0 for v in t['scores_hz']):
                raise ValueError('invalid navigation scores')
            if t['seed'] in groups[t['case']]:raise ValueError('duplicate navigation seed')
            groups[t['case']].add(t['seed'])
            if decode(t,r['decoder']) not in spec[2]:raise ValueError('navigation gate failed')
        if any(len(x)<3 for x in groups.values()) or len({tuple(sorted(x)) for x in groups.values()})!=1:
            raise ValueError('missing matched navigation controls')
        seeds.append(set.union(*groups.values()))
    if seeds[0]&seeds[1] or fit_decoder(r['training'])!=r['decoder']:
        raise ValueError('navigation decoder or validation split mismatch')
    return r
