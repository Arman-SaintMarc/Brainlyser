"""Regression checks for release fixes; run using python -m unittest discover."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Code/Brainlyser code"))
from extract_stats import build_heatmap_diff_rows


def specimen(name, group, level, median):
    return {name: [{"class": group, "images": {
        "slice0000.jpg": {"atlas": f"slice{level:04d}.jpg", "brainRegion1": {"median": median}}
    }}]}


class AtlasEndpointTests(unittest.TestCase):
    def test_first_and_last_levels_are_preserved(self):
        for level in (1, 220):
            with self.subTest(level=level):
                rows = build_heatmap_diff_rows([
                    specimen("control", "CT-F", level, 5),
                    specimen("disease", "AD-F", level, 8),
                ])
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["slice_idx"], level)
                self.assertEqual(rows[0]["diff_raw"], 3)
                self.assertEqual(rows[0]["n_slices_control"], 1)

    def test_levels_outside_supplied_atlas_are_ignored(self):
        for level in (0, 221):
            self.assertEqual(build_heatmap_diff_rows([
                specimen("control", "CT-F", level, 5),
                specimen("disease", "AD-F", level, 8),
            ]), [])


if __name__ == "__main__":
    unittest.main()
