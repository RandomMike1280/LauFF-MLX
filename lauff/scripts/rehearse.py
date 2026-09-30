"""Real neural inference on explicit synthetic garden observations; no network/game actions."""
import json
from pathlib import Path
from lauff.neural import MaleCNS, load_calibration
from lauff.protocol import command_text, parse_command
from lauff.worker import decide

root=Path(__file__).resolve().parents[1]
brain=MaleCNS(root/'vendor/drosophila-brain-mlx',root/'vendor/drosophila-brain-mlx/data/pack/male_cns_v1')
cal=load_calibration(root/'outputs/calibration.json',brain)
results=[]
for seq,(sweet,silenced) in enumerate(((True,False),(False,False),(True,True)),1):
    obs=dict(v=1,session='offline-no-game',seq=seq,x=0,z=0,can_harvest=sweet,
             fruit_count=0,fruit_capacity=10,previous_outcome='NONE',
             tiles=[dict(x=x,z=z,known=True,plant='Apple' if (x,z)==(0,0) else '',
                         has_fruit=sweet and (x,z)==(0,0),fruit_percent=-1)
                    for x,z in [(0,0),(0,-1),(1,0),(0,1),(-1,0)]])
    trial=brain.trial(sweet,2000000,silenced)
    action=decide(obs,trial,cal['threshold_hz'])
    wire=command_text(obs,action,30000)
    assert parse_command(wire,obs,age_s=2,roundtrip_s=1)==action
    assert action==('HARVEST' if sweet and not silenced else 'WAIT')
    results.append(dict(observation=obs,trial=trial,action=action,wire=wire))
    print(f'Offline synthetic observation: sweet={sweet}, silenced={silenced}, MN9={trial["score_hz"]} Hz -> {action}',flush=True)
(root/'outputs/offline-rehearsal.json').write_text(json.dumps({'synthetic_game_observations':True,
    'real_neural_model':True,'game_actions_executed':False,'fingerprint':brain.fingerprint,'results':results},indent=2)+'\n')
