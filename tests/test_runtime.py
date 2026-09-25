"""Focused regression tests for the macOS and full-dataset fixes."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

APP = Path(__file__).resolve().parents[1] / "Code/Brainlyser code"
sys.path.insert(0, str(APP))
import index
import visuals_generation as visuals
import yolo_processor as yolo
from alignment_software import minimal_reorder_indices


class RuntimeTests(unittest.TestCase):
    def test_pipeline_failure_is_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'raw/brain').mkdir(parents=True)
            output = root / 'output'
            output.mkdir()
            table = root / 'classes.csv'
            table.write_text('Brain,Class\nbrain,AD-F\n')
            with patch.object(index, 'create_processed_data_dir', return_value=output), patch.object(index, 'process_all_brains', side_effect=RuntimeError('simulated failure')):
                with self.assertRaisesRegex(RuntimeError, 'simulated failure'):
                    index.run_pipeline(root / 'raw', table, review=False, open_browser=False)
            status = json.loads((output / 'run_status.json').read_text())
            self.assertEqual(status['stage'], 'Failed')
            self.assertEqual(status['failed_stage'], 'Detection and cropping')
            self.assertIn('simulated failure', (output / 'error.log').read_text())

    def test_invalid_reference_tables(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'reference.csv'
            for content in ['REF,ATLAS\n1,221\n', 'REF,ATLAS\n1.5,10\n',
                            'REF,ATLAS\n1,10\n2,10\n', 'REF,ATLAS\n1,\n']:
                path.write_text(content)
                with self.assertRaises(ValueError):
                    index.load_ref_atlas_pairs(path)

    def test_invalid_assignment_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for mappings in [{}, {'unknown':{}}, {'brain':{'../bad.jpg':'slice0001.jpg'}},
                             {'brain':{'slice0000.jpg':'slice0221.jpg'}}]:
                with self.assertRaises(ValueError):
                    index.validate_assignments(mappings, root, {'brain':'AD-F'})

    def test_manual_reorder_both_directions_and_gaps(self):
        positions = {f"slice{i:04d}.jpg": p for i, p in enumerate([4, 5, 6, 20])}
        moved = minimal_reorder_indices(positions, "slice0002.jpg", 4)
        self.assertEqual(list(moved.values()), [2, 3, 4, 20])
        moved = minimal_reorder_indices(positions, "slice0000.jpg", 6)
        self.assertEqual(list(moved.values()), [6, 7, 8, 20])

    def test_native_table_filter_uses_extension_list(self):
        self.assertEqual(index.TABLE_FILETYPES[0][1], ("*.csv", "*.xlsx", "*.xls"))

    def test_invalid_class_tables(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "classes.csv"
            for content in ["Brain,Class\nA,AD-F\nA,CT-F\n", "Brain,Class\nA,\n",
                            "Brain,Class\n../A,AD-F\n", "Brain,Class\nA,../AD\n"]:
                with self.subTest(content=content):
                    path.write_text(content)
                    with self.assertRaises(ValueError):
                        index.load_mapping_file(path)
            path.write_text("Brain,Class\n A , AD-F \n")
            self.assertEqual(index.load_mapping_file(path), {"A": "AD-F"})

    def test_small_differences_are_white_without_warnings(self):
        for maximum in (0, 1, 2, 3):
            diff = np.full((10, 10), min(maximum, 2), np.float32)
            with np.errstate(all="raise"):
                result = visuals.apply_diverging_colormap(diff, -maximum, maximum)
            np.testing.assert_array_equal(result, np.full((10, 10, 3), 255, np.uint8))

    def test_streamed_medians_and_both_difference_directions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            assignments = {}
            classes = {"a1": "AD-F", "a2": "AD-F", "ct": "CT-F"}
            for brain, value in [("a1", 10), ("a2", 30), ("ct", 5)]:
                assignments[brain] = {"slice0000.jpg": "slice0220.jpg"}
                for modality in ("structure", "inflammation"):
                    dest = root / brain / (modality + "_registered")
                    dest.mkdir(parents=True)
                    cv2.imwrite(str(dest / "slice0000.jpg"), np.full((80, 100), value, np.uint8))
            (root / "atlas_to_brain.json").write_text(json.dumps(assignments))
            visuals.main(root, classes)
            median = cv2.imread(str(root / "median/AD-F/inflammation/slice0220.jpg"), 0)
            self.assertTrue(np.all(median == 20))
            for label in ("AD-F_vs_CT-F", "CT-F_vs_AD-F"):
                self.assertTrue((root / "difference_heatmap" / label / "slice0220.jpg").is_file())

    def test_unreadable_detection_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            brain = root / "raw/brain"
            brain.mkdir(parents=True)
            (brain / "bad.jpg").write_bytes(b"not an image")
            with patch.object(yolo, "_load_model", return_value=object()):
                self.assertEqual(yolo.main(root / "raw", root / "out"), (0, 1))
            with (root / "out/detection_manifest.csv").open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["status"], "unreadable")


if __name__ == "__main__":
    unittest.main()
