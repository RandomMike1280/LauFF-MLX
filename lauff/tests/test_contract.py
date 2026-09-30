import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from lauff.protocol import observation, command_text, parse_command
from lauff.neural import fit_threshold, calibrate, load_calibration
from lauff.worker import decide

ROOT = Path(__file__).resolve().parents[1]

def obs():
    return dict(v=1, session='12345678-abcd-abcd-abcd-123456789abc', seq=1, x=0, z=0,
                can_harvest=True, fruit_count=0, fruit_capacity=10, previous_outcome='NONE',
                tiles=[dict(x=x, z=z, known=True, plant='Apple', has_fruit=True, fruit_percent=100)
                       for x,z in [(0,0),(0,-1),(1,0),(0,1),(-1,0)]])

class GamePackagingTests(unittest.TestCase):
    def test_live_imports_fit_five_file_limit(self):
        import re
        pending=['client.lau']
        seen=set()
        while pending:
            name=pending.pop()
            if name in seen:
                continue
            seen.add(name)
            path=ROOT/'game'/name
            if name == 'LauFFConfig.laum':
                path=ROOT/'game/LauFFConfig.example.laum'
            self.assertTrue(path.is_file(), name)
            pending.extend(re.findall(r'req\("([^"\n]+)"\)', path.read_text()))
        self.assertEqual(len(seen), 5, seen)

    def test_no_inline_conditionals(self):
        import re
        for path in (ROOT/'game').iterdir():
            if path.suffix in ('.lau', '.laum'):
                for number,line in enumerate(path.read_text().splitlines(),1):
                    code=re.sub(r'"(?:\\.|[^"\\])*"', '""', line).split('--',1)[0]
                    with self.subTest(file=path.name,line=number):
                        self.assertNotRegex(code, r'\bthen\s+\S')

    def test_game_files_below_engine_limit(self):
        for path in (ROOT/'game').iterdir():
            if path.suffix in ('.lau', '.laum'):
                with self.subTest(file=path.name):
                    self.assertLess(path.stat().st_size, 5000)

class ProtocolTests(unittest.TestCase):
    def test_roundtrip(self):
        o=obs()
        self.assertEqual(parse_command(command_text(o,'HARVEST',10000),o,age_s=2,roundtrip_s=1),'HARVEST')

    def test_reject_stale_malformed_and_late(self):
        o=obs(); good=command_text(o,'HARVEST',10000)
        for value in [good+'|extra', good.replace('HARVEST','SELL'), good.replace('|1|0|0|','|2|0|0|'),
                      good.replace('|1|0|0|','|1|1|0|'),good.replace('|10000|','|nan|')]:
            with self.subTest(value=value), self.assertRaises(ValueError): parse_command(value,o,age_s=2)
        for age,rtt in [(45,0),(1,10)]:
            with self.assertRaises(ValueError): parse_command(good,o,age_s=age,roundtrip_s=rtt)

    def test_invalid_observations(self):
        for key,val in [('seq',True),('can_harvest',1),('fruit_capacity',0),('tiles',[]),('x',float('nan'))]:
            o=obs();o[key]=val
            with self.subTest(key=key), self.assertRaises(ValueError): observation(o)
        o=obs();o['tiles'][1]['x']=99
        with self.assertRaises(ValueError): observation(o)

    def test_neural_requirement_and_capacity(self):
        o=obs()
        self.assertEqual(decide(o,{'score_hz':0},10),'WAIT')
        self.assertEqual(decide(o,{'score_hz':30},10),'HARVEST')
        o['fruit_count']=10
        self.assertEqual(decide(o,{'score_hz':30},10),'WAIT')
        o['fruit_count']=0;o['can_harvest']=False
        self.assertEqual(decide(o,{'score_hz':30},10),'WAIT')

class CalibrationTests(unittest.TestCase):
    class Brain:
        fingerprint='unit-test-fixture';provenance={'fixture':True}
        def trial(self,sweet,seed,silenced=False):
            return dict(sweet=sweet,seed=seed,silenced=silenced,score_hz=50 if sweet and not silenced else 0)
    def test_separate_held_out_and_model_identity(self):
        b=self.Brain();r=calibrate(b,3,progress=lambda _:None)
        self.assertTrue(r['passed']);self.assertEqual(r['threshold_hz'],25)
        self.assertFalse({t['seed'] for t in r['training']} & {t['seed'] for t in r['held_out']})
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'calibration.json';p.write_text(json.dumps(r));load_calibration(p,b)
            r['fingerprint']='changed';p.write_text(json.dumps(r))
            with self.assertRaises(ValueError):load_calibration(p,b)
    def test_failure_has_no_scripted_fallback(self):
        b=self.Brain()
        b.trial=lambda sweet,seed,silenced=False:dict(sweet=sweet,seed=seed,silenced=silenced,score_hz=0)
        with self.assertRaises(ValueError):calibrate(b,3,progress=lambda _:None)

@unittest.skipUnless(shutil.which('lau'), 'desktop Lau interpreter unavailable')
class LauActionTests(unittest.TestCase):
    def run_case(self, setup, response, expected, calls=0, moves=0):
        source=(ROOT/'game/client.lau').read_text()
        source=source.replace('varol cfg = req("LauFFConfig.laum")','varol cfg = {"https://example.invalid", "test-token", true, -1, 1, -1, 1}')
        source=source.replace('gardenModule[2](s, player)', '')
        source=source[:source.index('\nprint("LauFF paused.')]
        source=source.replace('varol actions = actionModule[1]',
            'net[1] = func(data) outcome = data.outcome return "OK" end\nvarol actions = actionModule[1]')
        # Import actual modules and execute command checks against deterministic game stubs.
        pre='''
varol garden = {}
varol moved, blockMove = 0, false
varol Enum = {["Direction"] = {["North"] = "North", ["East"] = "East", ["South"] = "South", ["West"] = "West"}}
varol now, harvested, outcome, ripe = 1, 0, "NONE", true
varol px, pz, count, cap = 0, 0, 0, 10
varol task = {["clock"] = func() return now end, ["wait"] = func(n) now += n end}
varol player = {["alert"] = func(s) return end, ["getFruitCount"] = func() return count end, ["getFruitCapacity"] = func() return cap end}
varol drone = {["getPosition"] = func() return px, pz end, ["canHarvest"] = func() return ripe end, ["harvest"] = func() harvested += 1 ripe = false end}
'''
        pre+='''
drone.move = func(direction)
    moved += 1
    if blockMove then
        return
    end
    if direction == "North" then
        pz -= 1
    end
    if direction == "South" then
        pz += 1
    end
    if direction == "East" then
        px += 1
    end
    if direction == "West" then
        px -= 1
    end
end
'''
        post='''
s.running = true
s.session = "12345678-abcd-abcd-abcd-123456789abc"
s.seq = 1
s.sampledAt = 0
s.pending = {["x"] = 0, ["z"] = 0}
'''+setup+'\nprocessCommand('+json.dumps(response)+', 0)\nprint("RESULT", harvested, outcome, s.running)\nprint("MOVES", moved)\n'
        with tempfile.TemporaryDirectory() as d:
            for module in (ROOT/'game').glob('LauFF*.laum'):
                shutil.copy(module,d)
            p=Path(d)/'case.lau';p.write_text(pre+source+post)
            r=subprocess.run(['lau','run',str(p),'--virtual-time','--max-statements','10000'],text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn(f'MOVES\t{moves}',r.stdout.replace(' ', '\t'))
        self.assertIn(f'RESULT\t{calls}\t{expected}',r.stdout.replace(' ', '\t'))

    def test_harvest_and_duplicate(self):
        c=command_text(obs(),'HARVEST',40000)
        self.run_case('',c,'HARVEST_CONFIRMED',1)
        self.run_case('s.lastHandled = 1',c,'NONE')
    def test_movement_pause_capacity_and_stale(self):
        c=command_text(obs(),'HARVEST',40000)
        for setup,result in [('s.running = false','REJECTED'),('s.moveRequest = "North"','REJECTED'),
                             ('px = 1','REJECTED'),('count = 10','CAPACITY'),('ripe = false','REJECTED'),
                             ('now = 46','NONE')]:
            with self.subTest(setup=setup):self.run_case(setup,c,result)
    def test_malformed(self):
        c=command_text(obs(),'HARVEST',40000)
        for bad in [c+'|extra',c.replace('HARVEST','CROP'),c.replace('|40000|','|nan|')]:
            with self.subTest(bad=bad):self.run_case('',bad,'NONE')

    def test_neural_moves_and_guards(self):
        o=obs();o['autonomous']=True;o['can_harvest']=False
        setup='s.autonomous = true\ns.pending.autonomous = true\ns.pending.tiles = {{["known"] = true}, {["known"] = true}, {["known"] = true}, {["known"] = true}, {["known"] = true}}\nripe = false\n'
        for direction in ('NORTH','EAST','SOUTH','WEST'):
            command=command_text(o,'MOVE_'+direction,40000)
            with self.subTest(direction=direction):
                self.run_case(setup,command,'MOVED',moves=1)
        command=command_text(o,'MOVE_EAST',40000)
        for guard,outcome in [('s.autonomous = false','REJECTED'),('s.pending.autonomous = false','REJECTED'),
                              ('s.pending.tiles[3].known = false','REJECTED'),('cfg[5] = 0','REJECTED'),
                              ('px = 1','REJECTED'),('count = 10','CAPACITY'),('s.running = false','REJECTED'),
                              ('s.moveRequest = "West"','REJECTED'),('ripe = true','REJECTED'),
                              ('now = 46','NONE'),('s.lastHandled = 1','NONE')]:
            with self.subTest(guard=guard):self.run_case(setup+guard,command,outcome)
        self.run_case(setup+'blockMove = true',command,'MOVE_UNCONFIRMED',moves=1)
        # Disabling the rectangle applies to all four directions, with other guards intact.
        for direction in ('NORTH','EAST','SOUTH','WEST'):
            self.run_case(setup+'cfg[4] = 0\ncfg[5] = 0\ncfg[6] = 0\ncfg[7] = 0\ncfg[8] = true',
                          command_text(o,'MOVE_'+direction,40000),'MOVED',moves=1)
        self.run_case(setup+'cfg[8] = true\ns.pending.tiles[3].known = false',command,'REJECTED')

    def test_get_payload_encoding(self):
        from urllib.parse import quote, unquote
        client=(ROOT/'game/LauFFNet.laum').read_text()
        encoder=client[client.index('func encodeQuery('):client.index('func request(')]
        probe=(ROOT/'game/probe_http.lau').read_text()
        normalized = lambda text: '\n'.join(line.lstrip() for line in text.strip().splitlines())
        self.assertIn(normalized(encoder), normalized(probe))
        payload=json.dumps(dict(op='observe',token='test-token',observation=obs(),
                               extra=''.join(chr(n) for n in range(32,127))))
        code=encoder+'\nprint(encodeQuery('+json.dumps(payload)+'))\n'
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'encode.lau';path.write_text(code)
            result=subprocess.run(['lau','run',str(path),'--virtual-time'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        encoded=result.stdout.strip()
        self.assertEqual(encoded,quote(payload,safe='-._~'))
        self.assertEqual(json.loads(unquote(encoded))['observation'],obs())

    def test_tile_response_shapes(self):
        functions='varol module = req("LauFFGarden.laum")\nvarol api = module[1](cfg, garden)\nvarol tile = api[2]\n'
        cases=[
            ('{["0,0"] = {["PlantName"] = "LemonTree", ["HasFruit"] = false, ["PlantPercent"] = 100}}', 'true LemonTree false -1'),
            ('{["0,0"] = {["PlantName"] = "LemonTree", ["HasFruit"] = true, ["FruitPercent"] = 100}}', 'true LemonTree true 100'),
            ('{["PlantName"] = "Apple", ["HasFruit"] = false, ["FruitPercent"] = 45}', 'true Apple false 45'),
            ('null', 'true EMPTY false -1'),
            ('{}', 'false EMPTY false -1'),
            ('{["9,9"] = {["PlantName"] = "WrongTile"}}', 'false EMPTY false -1'),
            ('"unexpected"', 'false EMPTY false -1'),
        ]
        for payload,expected in cases:
            code='varol cfg = {"", "", false, -1, 1, -1, 1}\nvarol garden = {["getPlantPosition"] = func(x,z) return '+payload+' end}\n'+functions+'\nvarol t = tile(0,0)\nif t.plant == "" then t.plant = "EMPTY" end\nprint(t.known,t.plant,t.has_fruit,t.fruit_percent)\n'
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as d:
                shutil.copy(ROOT/'game/LauFFGarden.laum',d)
                path=Path(d)/'tile.lau';path.write_text(code)
                result=subprocess.run(['lau','run',str(path),'--virtual-time'],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(' '.join(result.stdout.split()),expected)


class WorkerTests(unittest.TestCase):
    def test_end_to_end_worker_and_outcome(self):
        import threading
        from lauff.worker import Evidence, run_worker
        class Stop:
            done=False
            def is_set(self):return self.done
            def wait(self,_):return self.done
        stop=Stop(); o=obs()
        class Brain(CalibrationTests.Brain):
            calls=0
            def trial(self,sweet,seed,silenced=False):
                self.calls+=1
                return super().trial(sweet,seed,silenced)
        brain=Brain()
        class Relay:
            polls=0
            results=[]
            def call(self,op,**values):
                if op=='worker_result':
                    self.results.append(values)
                    return 'OK'
                self.polls+=1
                if self.polls<3:
                    return json.dumps({'observation':{'observation':o,'created_ms':1000,'deadline_ms':46000}})
                stop.done=True
                return json.dumps({'observation':None,'ack':{'session':o['session'],'seq':1,'outcome':'HARVEST_CONFIRMED'}})
        relay=Relay()
        with tempfile.TemporaryDirectory() as d:
            e=Evidence(Path(d));run_worker(relay,brain,{'threshold_hz':25},e,stop)
            events=[json.loads(line) for line in e.path.read_text().splitlines()]
        self.assertEqual(brain.calls,1)
        self.assertEqual([r['action'] for r in relay.results],['HARVEST','HARVEST'])
        self.assertEqual([x['kind'] for x in events],['start','neural_decision','game_outcome'])

class ConfigureTests(unittest.TestCase):
    def test_private_stable_credentials_and_lau_module(self):
        import contextlib, io
        from lauff.cli import main
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'config.json'
            args=['configure','--relay-url','https://script.google.com/macros/s/test/exec',
                  '--bounds','-1','1','-1','1','--config',str(path)]
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                main(args)
                initial=json.loads(path.read_text())
                main(args+['--capabilities-verified'])
            updated=json.loads(path.read_text())
            self.assertEqual(initial['game_token'],updated['game_token'])
            self.assertNotEqual(updated['game_token'],updated['worker_token'])
            self.assertTrue(updated['capabilities_verified'])
            self.assertNotIn(updated['game_token'],stdout.getvalue())
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            with contextlib.redirect_stdout(io.StringIO()):
                main(args[:3]+['--unbounded','--config',str(path),'--capabilities-verified'])
            unbounded=json.loads(path.read_text())
            self.assertTrue(unbounded['unbounded'])
            self.assertEqual(updated['game_token'],unbounded['game_token'])
            self.assertTrue((path.parent/'LauFFConfig.laum').read_text().endswith(', true}\n'))
            self.assertFalse(updated['unbounded'])
            if shutil.which('lau'):
                subprocess.run(['lau','check',str(path.parent/'LauFFConfig.laum')],check=True,capture_output=True)

if __name__ == "__main__":
    unittest.main()
