import unittest
import numpy as np
from lauff.activity import ActivityMap

class ActivityTests(unittest.TestCase):
    def test_region_activity_includes_inactive_cells_and_correct_ids(self):
        view=ActivityMap.__new__(ActivityMap)
        view.mapped=np.array([0,1,2,3]);view.region_index=np.array([0,0,1,1])
        view.region_size=np.array([2,2]);view.cloud=np.array([1,3])
        view.nodes=np.array([0,2]);view.node_ids=np.array(['a','b'])
        result=view.summarize(np.array([10,0,30,0,50]))
        self.assertEqual(result['region_mean_hz'],[5,15])
        self.assertEqual(result['region_active_fraction'],[.5,.5])
        self.assertEqual(result['cloud_rates_hz'],[0,0])
        self.assertEqual(result['rates_by_id'],{'a':10,'b':30})
        self.assertEqual(result['active_neurons'],3)
        zero=view.summarize(np.zeros(5))
        self.assertEqual(zero['region_mean_hz'],[0,0])
        self.assertEqual(zero['active_neurons'],0)
