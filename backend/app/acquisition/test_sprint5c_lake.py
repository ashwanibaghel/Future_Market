import os
import json
import unittest

from app.acquisition.replay_indexer import ReplayIndexBuilder, REPLAY_INDEX_DIR
from app.research_os.governance.simulation_schema import ensure_simulation_storage_structure, SIMULATION_STORAGE_DIR
from app.research_os.governance.ai_dataset_schema import ensure_ai_storage_structure, AI_DATASETS_DIR
from app.acquisition.sprint5c_data_lake_builder import run_sprint5c_pipeline, FINAL_REPORT_JSON


class TestSprint5CLake(unittest.TestCase):
    """Unit test suite for Sprint 5C: Historical Data Lake Construction."""

    def test_01_replay_indexer(self):
        builder = ReplayIndexBuilder()
        res = builder.build_index_for_lake()
        self.assertIn("total_partitions_indexed", res)
        self.assertTrue(os.path.exists(res["index_json"]))

    def test_02_simulation_schema(self):
        sim_dir = ensure_simulation_storage_structure()
        self.assertTrue(os.path.exists(sim_dir))
        self.assertEqual(sim_dir, SIMULATION_STORAGE_DIR)

    def test_03_ai_dataset_schema(self):
        dirs = ensure_ai_storage_structure()
        self.assertTrue(os.path.exists(dirs["root"]))
        self.assertTrue(os.path.exists(dirs["features"]))
        self.assertTrue(os.path.exists(dirs["labels"]))

    def test_04_master_sprint5c_runner(self):
        report = run_sprint5c_pipeline()
        self.assertEqual(report["sprint"], "5C")
        self.assertIn(report["deliverables"]["11_final_status"], ["PASS", "FAIL"])
        self.assertTrue(os.path.exists(FINAL_REPORT_JSON))


if __name__ == "__main__":
    unittest.main()
