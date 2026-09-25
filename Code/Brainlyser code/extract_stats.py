from __future__ import annotations

"""
Generate per‑slice reporter statistics **and** bulk CSV exports used by the web
visualisation:

| File | Purpose |
|------|---------|
| `brain_slice_data.json` | Nested JSON for in‑app data. |
| `brain_slice_data.js`   | `const imageData = …` wrapper. |
| `brain_slice_data.csv`  | Slice‑level table — one row per *atlas slice*. |
| `outlier_scatter_data.csv` | Aggregated stats per *brain × region* for the scatter plot. |
| `heatmap_diff_data.csv` | **NEW** — Δ reporter (disease − control) for every *region × slice* pair, raw & interpolated. |
"""

import json
import csv
import re
from pathlib import Path
from typing import Dict, List, Any, DefaultDict

import numpy as np
from PIL import Image
from collections import defaultdict

# ──────────────────────────────────────────────────────────────────────────────
# Constants & mappings (must mirror the JS)
# ──────────────────────────────────────────────────────────────────────────────

REGION_MAPPING: Dict[str, str] = {
    "9": "1065_HB",
    "8": "1089_HPF",
    "7": "1097_HY",
    "6": "313_MB",
    "5": "315_Isocortex",
    "4": "512_CB",
    "3": "549_TH",
    "2": "623_CNU",
    "1": "698_OLF",
}

MAX_SLICES = 220  # supplied atlas filenames are slice0001 ... slice0220
SLICE_RE = re.compile(r"slice(\d+)", re.IGNORECASE)

# ──────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ──────────────────────────────────────────────────────────────────────────────

def compute_stats_from_array(arr: np.ndarray) -> Dict[str, float] | None:
    nonzero = arr[arr != 0]
    if nonzero.size == 0:
        return None
    return {
        "median": float(np.median(nonzero)),
        "mean":   float(np.mean(nonzero)),
        "std":    float(np.std(nonzero)),
        "min":    float(np.min(nonzero)),
        "max":    float(np.max(nonzero)),
    }


def load_image_as_array(path: Path, mode: str = "F") -> np.ndarray | None:
    try:
        with Image.open(path) as img:
            return np.array(img.convert(mode))
    except (FileNotFoundError, OSError):
        return None


def extract_slice_number(filename: str | None) -> int | None:
    if not filename:
        return None
    m = SLICE_RE.search(filename)
    if m:
        return int(m.group(1))
    return None


def interpolate_gaps(row: List[float]) -> List[float]:
    """Linearly interpolate NaNs in *row* (length MAX_SLICES)."""
    result = row.copy()
    last_valid = None
    for i, val in enumerate(result):
        if not np.isnan(val):
            if last_valid is not None and i > last_valid + 1:
                y1, y2 = result[last_valid], val
                for j in range(last_valid + 1, i):
                    result[j] = y1 + (y2 - y1) * (j - last_valid) / (i - last_valid)
            last_valid = i
    return result

# ──────────────────────────────────────────────────────────────────────────────
# Core processing helpers
# ──────────────────────────────────────────────────────────────────────────────

def build_brain_slice_data(
    root_dir: Path,
    assignments: Dict[str, Dict[str, str]],
    brain_to_class: Dict[str, str],
) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []

    for brain, slice_map in assignments.items():
        if brain not in brain_to_class:
            continue

        images_dict: Dict[str, Any] = {}
        infl_folder = root_dir / brain / "inflammation"
        mask_folder = root_dir / brain / "mask"

        for brain_slice, atlas_slice in slice_map.items():
            if not atlas_slice:
                continue
            infl_path = infl_folder / brain_slice
            mask_path = mask_folder / f"{Path(brain_slice).stem}.png"
            if not mask_path.exists():
                raise FileNotFoundError(f"Missing registered mask: {mask_path}")
            infl_arr = load_image_as_array(infl_path, "F")
            mask_arr = load_image_as_array(mask_path, "L")
            if infl_arr is None or mask_arr is None or infl_arr.shape != mask_arr.shape:
                raise ValueError(f"Unreadable images or unequal image/mask dimensions: {infl_path}, {mask_path}")

            global_stats = compute_stats_from_array(infl_arr.flatten())
            regions_stats: Dict[str, Any] = {}
            for region_id in np.unique(mask_arr):
                if region_id == 0:
                    continue
                region_vals = infl_arr[mask_arr == region_id]
                stat = compute_stats_from_array(region_vals)
                regions_stats[f"brainRegion{int(region_id)}"] = stat

            images_dict[brain_slice] = {
                "atlas": atlas_slice,
                "global": global_stats,
                **regions_stats,
            }

        if images_dict:
            output.append({
                brain: [{
                    "class": brain_to_class[brain],
                    "images": images_dict,
                }]
            })
    return output

# ──────────────────────────────────────────────────────────────────────────────
# CSV helpers
# ──────────────────────────────────────────────────────────────────────────────

def write_csv(rows: List[Dict[str, Any]], csv_path: Path) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def flatten_results_for_csv(result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for brain_entry in result:
        for brain, class_list in brain_entry.items():
            cls_info = class_list[0]
            cls = cls_info["class"]
            for brain_slice, stats in cls_info["images"].items():
                row: Dict[str, Any] = {
                    "brain": brain,
                    "class": cls,
                    "brain_slice": brain_slice,
                    "atlas_slice": stats.get("atlas"),
                }
                global_stats = stats.get("global") or {}
                for key in ("median", "mean", "std", "min", "max"):
                    row[f"global_{key}"] = global_stats.get(key)
                region_stats = {k: v for k, v in stats.items() if k not in ("atlas", "global")}
                row["region_stats_json"] = json.dumps(region_stats, separators=(',', ':')) or None
                rows.append(row)
    return rows


def build_outlier_rows(result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for brain_entry in result:
        for brain, class_list in brain_entry.items():
            cls_info = class_list[0]
            cls = cls_info["class"]
            images_dict = cls_info["images"]
            region_vals: Dict[str, List[float]] = {}
            for slice_stats in images_dict.values():
                for key, metrics in slice_stats.items():
                    if key in ("atlas", "global"):
                        continue
                    if metrics and isinstance(metrics, dict) and metrics.get("median") is not None:
                        region_vals.setdefault(key, []).append(metrics["median"])
            for region_key, med_list in region_vals.items():
                mean_val = float(np.mean(med_list))
                std_val = float(np.std(med_list))
                region_num = region_key.replace("brainRegion", "") if region_key.startswith("brainRegion") else ""
                region_name = REGION_MAPPING.get(region_num, region_key)
                rows.append({
                    "brain": brain,
                    "class": cls,
                    "region": region_name,
                    "region_id": region_num,
                    "aggregated_mean": mean_val,
                    "aggregated_std": std_val,
                    "n_slices": len(med_list),
                })
    return rows

# ──────────────────────────────────────────────────────────────────────────────
# Heat‑map difference helper
# ──────────────────────────────────────────────────────────────────────────────

def build_heatmap_diff_rows(result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compute Δ reporter per region × slice and include **per‑slice counts**.

    n_slices_disease / n_slices_control = number of individual slice‑measurements
    (from different brains) that contributed to the mean at this *slice_idx*.
    """

    # 1) Aggregate raw per‑class values (retain full lists → we can count them)
    class_region_slice_vals: Dict[str, Dict[str, DefaultDict[int, List[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for brain_entry in result:
        for brain, class_list in brain_entry.items():
            cls_info = class_list[0]
            cls = cls_info["class"]
            images_dict = cls_info["images"]
            for brain_slice, stats in images_dict.items():
                slice_idx = extract_slice_number(stats.get("atlas"))
                if slice_idx is None or not 1 <= slice_idx <= MAX_SLICES:
                    continue
                for region_key, metrics in stats.items():
                    if region_key in ("atlas", "global"):
                        continue
                    if metrics and isinstance(metrics, dict) and metrics.get("median") is not None:
                        region_num = region_key.replace("brainRegion", "") if region_key.startswith("brainRegion") else ""
                        region_name = REGION_MAPPING.get(region_num, region_key)
                        class_region_slice_vals[cls][region_name][slice_idx].append(metrics["median"])

    # 2) Compute mean matrices (needed for Δ) and keep counts
    class_heatmaps_raw: Dict[str, Dict[str, List[float]]] = {}
    class_heatmaps_counts: Dict[str, Dict[str, List[int]]] = {}

    for cls, region_map in class_region_slice_vals.items():
        region_rows_mean: Dict[str, List[float]] = {}
        region_rows_cnt: Dict[str, List[int]] = {}
        for region_name, slice_map in region_map.items():
            mean_row = [np.nan] * (MAX_SLICES + 1)
            cnt_row  = [0] * (MAX_SLICES + 1)
            for sidx, vals in slice_map.items():
                mean_row[sidx] = float(np.mean(vals))
                cnt_row[sidx]  = len(vals)
            region_rows_mean[region_name] = mean_row
            region_rows_cnt[region_name]  = cnt_row
        class_heatmaps_raw[cls] = region_rows_mean
        class_heatmaps_counts[cls] = region_rows_cnt

    # 3) Interpolated means (for smoothing view) — counts stay raw
    class_heatmaps_interp: Dict[str, Dict[str, List[float]]] = {
        cls: {region: interpolate_gaps(row) for region, row in region_map.items()}
        for cls, region_map in class_heatmaps_raw.items()
    }

    # 4) Build diff rows with per‑slice counts
    diff_rows: List[Dict[str, Any]] = []
    for cls in class_heatmaps_raw:
        if cls.startswith("CT-"):
            continue  # controls are subtrahend only
        gender_suffix = "-F" if cls.endswith("-F") else "-M" if cls.endswith("-M") else None
        if not gender_suffix:
            continue
        ctrl_cls = f"CT{gender_suffix}"
        if ctrl_cls not in class_heatmaps_raw:
            continue
        for region_name in REGION_MAPPING.values():
            mean_d   = class_heatmaps_raw[cls].get(region_name, [np.nan] * (MAX_SLICES + 1))
            mean_c   = class_heatmaps_raw[ctrl_cls].get(region_name, [np.nan] * (MAX_SLICES + 1))
            mean_d_i = class_heatmaps_interp[cls].get(region_name, [np.nan] * (MAX_SLICES + 1))
            mean_c_i = class_heatmaps_interp[ctrl_cls].get(region_name, [np.nan] * (MAX_SLICES + 1))
            cnt_d    = class_heatmaps_counts[cls].get(region_name, [0] * (MAX_SLICES + 1))
            cnt_c    = class_heatmaps_counts[ctrl_cls].get(region_name, [0] * (MAX_SLICES + 1))

            for s in range(1, MAX_SLICES + 1):
                diff_raw   = mean_d[s] - mean_c[s]   if not (np.isnan(mean_d[s])   or np.isnan(mean_c[s]))   else ''
                diff_interp = mean_d_i[s] - mean_c_i[s] if not (np.isnan(mean_d_i[s]) or np.isnan(mean_c_i[s])) else ''

                if diff_raw == '' and diff_interp == '':
                    continue  # nothing to export

                diff_rows.append({
                    "disease_class": cls,
                    "control_class": ctrl_cls,
                    "region": region_name,
                    "slice_idx": s,
                    "n_slices_disease": cnt_d[s],
                    "n_slices_control": cnt_c[s],
                    "diff_raw": diff_raw,
                    "diff_interpolated": diff_interp,
                })
    return diff_rows

# ──────────────────────────────────────────────────────────────────────────────
# JSON → JS helper
# ──────────────────────────────────────────────────────────────────────────────

def json_to_js(json_path: Path, js_path: Path, var_name: str = "imageData") -> None:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    js_path.write_text(f"const {var_name} = {json.dumps(data, indent=2)};", encoding="utf-8")

# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main(root_dir: Path, brain_to_class: Dict[str, str], assignment_file: str | None = None) -> None:
    assignments_path = Path(assignment_file) if assignment_file else root_dir / "atlas_to_brain.json"
    if not assignments_path.is_file():
        raise FileNotFoundError(f"Assignments JSON not found: {assignments_path}")
    assignments = json.loads(assignments_path.read_text(encoding="utf-8"))

    # Build core structure
    result = build_brain_slice_data(root_dir, assignments, brain_to_class)

    # JSON + JS
    json_out = root_dir / "brain_slice_data.json"
    json_out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    json_to_js(json_out, root_dir / "brain_slice_data.js")

    # CSVs
    write_csv(flatten_results_for_csv(result), root_dir / "brain_slice_data.csv")
    write_csv(build_outlier_rows(result), root_dir / "outlier_scatter_data.csv")
    write_csv(build_heatmap_diff_rows(result), root_dir / "heatmap_diff_data.csv")

