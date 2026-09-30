"""Exploratory cue response sweep; does not enable or control the game."""
from pathlib import Path
import json
from lauff.neural import MaleCNS
from lauff.navigation import Navigation
from lauff.cli import private_json
p=Path('vendor/drosophila-brain-mlx');brain=MaleCNS(p,p/'data/pack/male_cns_v1');nav=Navigation(brain)
report={'fingerprint':nav.fingerprint,'provenance':nav.provenance,'trials':[],'passed':False}
conditions=[[int(i==j) for i in range(4)] for j in range(4)]+[[.2]*4,[1]*4,[0]*4]
conditions += [[1 if i==j else .2 for i in range(4)] for j in range(4)]
for n,cues in enumerate(conditions):
 for silenced in (False,True):
  t=nav.trial(cues,500000+n,silenced);report['trials'].append(t)
  private_json(Path('outputs/navigation/cue-probe.json'),report)
  print(cues,silenced,t['scores_hz'],flush=True)
