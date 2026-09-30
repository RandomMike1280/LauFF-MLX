"""Execute the real Lau transport against deterministic network failures."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which('lau'), 'desktop Lau interpreter unavailable')
class TransportTests(unittest.TestCase):
    def test_retry_failure_pause_and_expiry(self):
        cases = [
            ('transient', 'if calls == 1 then\nmissingFunction()\nend', 'RESULT\t2\tPENDING\ttrue'),
            ('ready', 'if calls == 1 then\nmissingFunction()\nend\nreturn "C|test|1|0|0|20000|WAIT"', 'RESULT\t2\tC|test|1|0|0|20000|WAIT\ttrue'),
            ('not_received', 'if calls == 1 then\nmissingFunction()\nend\nreturn "ERROR|SEQUENCE"', 'RESULT\t2\tnull\tfalse'),
            ('persistent', 'missingFunction()', 'RESULT\t2\tnull\tfalse'),
            ('pause', 's.controlVersion += 1\ns.running = false\nmissingFunction()', 'RESULT\t1\tnull\tfalse'),
            ('expiry', 'now = 45\nmissingFunction()', 'RESULT\t1\tnull\tfalse'),
            ('relay_error', 'return "ERROR|SESSION"', 'RESULT\t1\tnull\tfalse'),
        ]
        for name, behavior, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                shutil.copy(ROOT/'game/LauFFNet.laum', d)
                code = '''
varol now, calls = 0, 0
varol s = {["running"] = true, ["controlVersion"] = 0, ["lastHttp"] = -100, ["pending"] = {}, ["sampledAt"] = 0}
varol task = {["clock"] = func() return now end, ["wait"] = func(n) now += n end}
varol encodedOp = ""
varol http = {["jsonEncode"] = func(data) encodedOp = data.op return "{}" end}
http.get = func(url)
    calls += 1
    if calls == 2 AND encodedOp ~= "poll" then
        return "ERROR|REUPLOADED"
    end
    if calls > 1 AND now < 3 then
        return "ERROR|TOO_FAST"
    end
'''+behavior+'''
    return "PENDING"
end
varol module = req("LauFFNet.laum")
varol net = module[1](s, {"https://example.invalid", "SECRET"}, task, {}, http)
varol result = net[1]({["op"] = "observe", ["session"] = "test", ["observation"] = {["seq"] = 1}})
print("RESULT", calls, result, s.running)
'''
                p=Path(d)/'test.lau'; p.write_text(code)
                r=subprocess.run(['lau','run',str(p),'--virtual-time'], text=True, capture_output=True)
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertIn(expected,r.stdout.replace(' ', '\t'))
                self.assertNotIn('SECRET',r.stdout)
                self.assertLessEqual(r.stdout.count('LauFF paused:'),1)
