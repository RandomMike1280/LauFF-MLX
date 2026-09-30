import json
from pathlib import Path
import unittest

class BrainVisualTests(unittest.TestCase):
    def test_embedded_graph_and_anatomy_are_bounded(self):
        page=(Path(__file__).resolve().parents[1]/'src/lauff/web/index.html').read_text()
        data=json.loads(page.split('<script id="brain-data" type="application/json">',1)[1].split('</script>',1)[0])
        self.assertEqual(len(data['cloud']),6000)
        self.assertGreater(data['somas_available'],len(data['cloud']))
        self.assertEqual(len(data['cloud_ids']),len(data['cloud']))
        self.assertEqual(sum(r['neurons'] for r in data['regions']),data['somas_available'])
        self.assertGreater(len(data['regions']),20)
        self.assertTrue(all(len(p)==3 and all(-1<=x<=1 for x in p) for p in data['cloud']))
        ids={n['id'] for n in data['nodes']}
        self.assertEqual(len(ids),len(data['nodes']))
        for edge in data['edges']:
            self.assertIn(edge['source'],ids)
            self.assertIn(edge['target'],ids)
            self.assertIsInstance(edge['weight'],int)
        self.assertEqual(sum(n['group']=='taste' for n in data['nodes']),17)
        self.assertEqual(sum(n['group']=='feeding' for n in data['nodes']),2)
        self.assertEqual(sum(n['group']=='relay' for n in data['nodes']),15)
