"""Offline navigation interface calibration. No relay connection or game actions."""
from pathlib import Path
from lauff.neural import MaleCNS
from lauff.navigation import Navigation,calibrate_navigation
from lauff.cli import private_json
p=Path('vendor/drosophila-brain-mlx');out=Path('outputs/navigation/calibration.json')
private_json(out,{'passed':False,'status':'starting'})
b=MaleCNS(p,p/'data/pack/male_cns_v1');nav=Navigation(b)
r=calibrate_navigation(nav,checkpoint=lambda r:private_json(out,r),progress=lambda s:print(s,flush=True))
print('PASS' if r['passed'] else 'FAIL',r['failures'],flush=True)
raise SystemExit(0 if r['passed'] else 1)
