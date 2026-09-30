"""Offline neural steering assay. Does not connect to the game or relay."""
import argparse
from pathlib import Path
from lauff.cli import private_json
from lauff.neural import MaleCNS
from lauff.steering import SteeringAssay, validate

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--trials', type=int, default=10)
p.add_argument('--output', type=Path, default=Path('outputs/navigation/steering-validation.json'))
a = p.parse_args()
upstream = Path('vendor/drosophila-brain-mlx')
private_json(a.output, {'passed':False, 'status':'starting', 'autonomous_navigation_enabled':False})
brain = MaleCNS(upstream, upstream/'data/pack/male_cns_v1')
assay = SteeringAssay(brain)
report = validate(assay, a.trials, checkpoint=lambda r: private_json(a.output, r),
                  progress=lambda line: print(line, flush=True))
print('Circuit assay:', 'PASS' if report['passed'] else 'FAIL', flush=True)
print('Sensory navigation and autonomous movement remain unvalidated.', flush=True)
raise SystemExit(0 if report['passed'] else 1)
