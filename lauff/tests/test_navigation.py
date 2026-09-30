import copy,json,tempfile,unittest
from pathlib import Path
from lauff.navigation import decode,cues_from_observation,calibrate_navigation,load_navigation
from test_contract import obs

class Fixture:
    fingerprint='test';provenance={'fixture':True}
    def trial(self,cues,seed,silenced=False):
        return dict(cues=cues,seed=seed,silenced=silenced,scores_hz=[0 if silenced else x*100 for x in cues])

class NavigationTests(unittest.TestCase):
    def test_cues_are_simultaneous_and_unknown_is_zero(self):
        o=obs();o['tiles'][1]['known']=False;o['tiles'][2]['fruit_percent']=50
        for value,expected in zip(cues_from_observation(o),[0,.6,1,1]):
            self.assertAlmostEqual(value,expected)
    def test_decoder_has_no_tie_or_zero_fallback(self):
        c={'gains':[1]*4,'threshold':2,'margin':.1}
        self.assertEqual(decode({'scores_hz':[0]*4},c),'WAIT')
        self.assertEqual(decode({'scores_hz':[3,3,0,0]},c),'WAIT')
        for i,name in enumerate(('NORTH','EAST','SOUTH','WEST')):
            self.assertEqual(decode({'scores_hz':[4 if j==i else 0 for j in range(4)]},c),'MOVE_'+name)
        with self.assertRaises(ValueError):decode({'scores_hz':[0]*4},{**c,'gains':[0]*4})
    def test_validation_loader_rejects_tampering(self):
        nav=Fixture();r=calibrate_navigation(nav,progress=lambda _:None)
        self.assertTrue(r['passed'])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'gate.json';p.write_text(json.dumps(r));load_navigation(p,nav)
            for field in ('seed','scores_hz'):
                bad=copy.deepcopy(r)
                if field=='seed':bad['held_out'][0][field]=bad['training'][0][field]
                else:bad['held_out'][0][field]=[0]*4
                p.write_text(json.dumps(bad))
                with self.subTest(field=field),self.assertRaises(ValueError):load_navigation(p,nav)

class AutonomousWorkerTests(unittest.TestCase):
    def test_worker_publishes_neural_move_and_reuses_duplicate(self):
        from lauff.worker import run_worker,Evidence
        class Stop:
            done=False
            def is_set(self):return self.done
            def wait(self,_):return self.done
        stop=Stop();o=obs();o.update(autonomous=True,can_harvest=False)
        for t in o['tiles'][1:]:t['has_fruit']=False
        o['tiles'][2]['has_fruit']=True
        class Brain:
            fingerprint='fixture';provenance={}
            def trial(self,*args):return {'score_hz':0,'visual_activity':{'active_neurons':1}}
        class Nav(Fixture):
            calls=0
            def trial(self,*args):
                self.calls+=1
                result=super().trial(*args)
                result['visual_activity']={'active_neurons':2}
                return result
        nav=Nav()
        class Relay:
            polls=0;results=[]
            def call(self,op,**values):
                if op=='worker_result':self.results.append(values['action']);return 'OK'
                self.polls+=1
                if self.polls<3:return json.dumps({'observation':{'observation':o,'created_ms':0,'deadline_ms':45000}})
                stop.done=True
                return json.dumps({'observation':None,'ack':{'session':o['session'],'seq':1,'outcome':'MOVED'}})
        relay=Relay()
        with tempfile.TemporaryDirectory() as d:
            e=Evidence(Path(d))
            run_worker(relay,Brain(),{'threshold_hz':19},e,stop,navigation=nav,
                       navigation_calibration={'decoder':{'gains':[100]*4,'threshold':.3,'margin':.03}})
            self.assertEqual(e.snapshot()['latest']['trial']['navigation']['action'],'MOVE_EAST')
            self.assertEqual(e.snapshot()['ack']['outcome'],'MOVED')
            self.assertEqual(e.snapshot()['brain_activity']['phase'],'navigation')
            self.assertEqual(e.snapshot()['brain_activity']['active_neurons'],2)
            self.assertEqual(e.snapshot()['brain_activity']['seq'],1)
        self.assertEqual(nav.calls,1)
        self.assertEqual(relay.results,['MOVE_EAST','MOVE_EAST'])
