"""Closed-loop synthetic garden with real connectome trials; no relay or game calls."""
from pathlib import Path
from lauff.neural import MaleCNS,load_calibration
from lauff.navigation import Navigation,load_navigation,cues_from_observation,decode,DIRECTIONS
from lauff.worker import decide
from lauff.protocol import OFFSETS,observation,command_text,parse_command
from lauff.cli import private_json
p=Path('vendor/drosophila-brain-mlx');b=MaleCNS(p,p/'data/pack/male_cns_v1');nav=Navigation(b)
feeding=load_calibration('outputs/calibration.json',b)
cal=load_navigation('outputs/navigation/calibration.json',nav)
episodes=[];seed=900000
scenarios=[(name,{delta},False) for name,delta in zip(DIRECTIONS,OFFSETS[1:])]
scenarios += [('garden',{(x,z) for x in range(-1,2) for z in range(-1,2) if (x,z)!=(0,0)},False),
              ('silenced',{(x,z) for x in range(-1,2) for z in range(-1,2) if (x,z)!=(0,0)},True)]
for name,fruit,silenced in scenarios:
 position=(0,0);events=[];harvests=0
 for seq in range(1,25):
  seed+=1;x,z=position
  o=observation(dict(v=1,session='offline-navigation',seq=seq,x=x,z=z,autonomous=True,
    can_harvest=position in fruit,fruit_count=harvests,fruit_capacity=200,previous_outcome='NONE',
    tiles=[dict(x=x+dx,z=z+dz,known=abs(x+dx)<=1 and abs(z+dz)<=1,plant='SyntheticFruit',
           has_fruit=(x+dx,z+dz) in fruit,fruit_percent=100 if (x+dx,z+dz) in fruit else -1) for dx,dz in OFFSETS]))
  feed=b.trial(o['can_harvest'],seed,silenced);action=decide(o,feed,feeding['threshold_hz']);t=None
  if not o['can_harvest']:
   t=nav.trial(cues_from_observation(o),seed,silenced);action=decode(t,cal['decoder'])
  parse_command(command_text(o,action,40000),o,age_s=2,roundtrip_s=1)
  before=position
  if action.startswith('MOVE_'):
   dx,dz=OFFSETS[1+DIRECTIONS.index(action[5:])];position=(x+dx,z+dz)
   assert abs(position[0])<=1 and abs(position[1])<=1
  elif action=='HARVEST':fruit.remove(position);harvests+=1
  events.append({'observation':o,'feeding':feed,'navigation':t,'action':action,'after_position':position})
  print(name,seq,before,action,position,flush=True)
  if action=='WAIT' or not fruit:break
 episodes.append({'name':name,'silenced':silenced,'events':events,'simulated_harvests':harvests})
report={'kind':'real neural trials in synthetic closed-loop garden','navigation_fingerprint':nav.fingerprint,
        'episodes':episodes,'passed':all(e['simulated_harvests']==1 for e in episodes[:4]) and
        all(t['action']=='WAIT' for t in episodes[-1]['events'])}
private_json(Path('outputs/navigation/closed-loop.json'),report)
print('PASS' if report['passed'] else 'FAIL',flush=True)
raise SystemExit(0 if report['passed'] else 1)
