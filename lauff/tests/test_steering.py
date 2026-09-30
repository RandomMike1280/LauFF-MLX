import unittest
from lauff.steering import CONDITIONS, fit_steering_gate, validate

class Assay:
    fingerprint='fixture'
    provenance={'fixture':True}
    def trial(self, condition, seed):
        return {'condition':condition,'seed':seed,
                'difference_hz':{'left':-60,'right':70}.get(condition,0)}

class SteeringGateTests(unittest.TestCase):
    def test_signed_controls_and_disjoint_seeds(self):
        report=validate(Assay(),3,progress=lambda _:None)
        self.assertTrue(report['passed'])
        self.assertFalse(report['autonomous_navigation_enabled'])
        self.assertEqual(report['threshold_hz'],30)
        self.assertFalse({t['seed'] for t in report['training']} & {t['seed'] for t in report['held_out']})
        for split in ('training','held_out'):
            for c in CONDITIONS:
                self.assertEqual(sum(t['condition']==c for t in report[split]),3)

    def test_reject_reversed_or_noncausal_response(self):
        base=[Assay().trial(c,1) for c in CONDITIONS]
        for changed,value in [('left',60),('right',-70),('left_silenced',60),('right_silenced',70),('zero',float('nan'))]:
            rows=[dict(t) for t in base]
            next(t for t in rows if t['condition']==changed)['difference_hz']=value
            with self.subTest(changed=changed),self.assertRaises(ValueError):fit_steering_gate(rows)

    def test_held_out_failure_stays_disabled(self):
        class BadHeldOut(Assay):
            def trial(self,condition,seed):
                t=super().trial(condition,seed)
                if seed>=400_000:t['difference_hz']=0
                return t
        r=validate(BadHeldOut(),3,progress=lambda _:None)
        self.assertFalse(r['passed'])
        self.assertFalse(r['autonomous_navigation_enabled'])
        self.assertIn('failure',r)
