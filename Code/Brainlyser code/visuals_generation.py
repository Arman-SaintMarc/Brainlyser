from __future__ import annotations

"""
Compute per‑class median images for two imaging modalities (structure & inflammation)
and generate inter‑class difference map :

*Coloured heat‑map*    (signed, diverging) →  <root>/difference_heatmap/<A>_vs_<B>/<slice>

The script expects a JSON mapping brain→{registered‑file→atlas‑slice}.  Per‑class
medians are written to <root>/median/<class>/{structure|inflammation}/<slice>.
"""

import itertools
import json
import os
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
from matplotlib import colormaps
import matplotlib.colors as mcolors

# ─────────────────────────────────────────────────────────────────────────────
# New helper ─ draws an on‑image colour‑bar legend (top‑right)
# ─────────────────────────────────────────────────────────────────────────────
def overlay_colorbar(
    img: np.ndarray,
    vmin: float,
    vmax: float,
    cmap_name: str = "coolwarm",
    bar_h_px: int | None = None,
    bar_w_px: int = 20,
    margin_right: int = 10,
    margin_top: int = 10,
    y_offset: int = 20,          # ← was 15 … move a touch lower
    font_scale: float = 0.4,
    thickness: int = 1,
) -> np.ndarray:
    h, w = img.shape[:2]
    if h < 64 or w < 64:
        return img.copy()
    bar_h_px = min(bar_h_px or int(h * 0.6), h - margin_top - y_offset - 16)

    # build coloured bar (vmax ▾ vmin)
    grad = np.linspace(vmax, vmin, bar_h_px, dtype=np.float32)[:, None]
    cmap = colormaps[cmap_name]
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    bar_bgr = cv2.cvtColor(
        (cmap(norm(grad))[:, :, :3] * 255).astype(np.uint8),
        cv2.COLOR_RGB2BGR,
    )
    bar_bgr = cv2.resize(bar_bgr, (bar_w_px, bar_h_px), cv2.INTER_AREA)

    out = img.copy()
    x0 = w - bar_w_px - margin_right
    y0 = margin_top + y_offset                # ← label now guaranteed inside

    out[y0:y0 + bar_h_px, x0:x0 + bar_w_px] = bar_bgr

    # numeric labels
    cv2.putText(out, f"{vmax:.0f}", (x0, y0 - 3),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale,
                (255, 255, 255), thickness, cv2.LINE_AA)
    cv2.putText(out, f"{vmin:.0f}", (x0, y0 + bar_h_px + 13),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale,
                (255, 255, 255), thickness, cv2.LINE_AA)
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Basic helpers
# ──────────────────────────────────────────────────────────────────────────────

def read_and_align_registered_images(
    brain: str,
    modality_folder: str,
    assignments: Dict[str, Dict[str, str]],
    root_dir: Path,
) -> Dict[str, List[np.ndarray]]:
    """Return {final_atlas_slice: [registered images…]} for *brain*/*modality*."""
    images: Dict[str, List[np.ndarray]] = {}
    folder = root_dir / brain / modality_folder
    if not folder.is_dir() or brain not in assignments:
        return images

    try:
        for query_file in os.listdir(folder):
            final_atlas = assignments[brain].get(query_file)
            if not final_atlas:
                continue
            img = cv2.imread(str(folder / query_file), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                if img.ndim == 3 and img.shape[2] == 1:   # grey stored as H×W×1
                    img = img[:, :, 0]
                elif img.ndim == 4 and img.shape[2] == 1:
                    img = img[:, :, 0]
                images.setdefault(final_atlas, []).append(img)
    except OSError:
        pass  # ignore unreadable folders
    return images


def compute_median_image(image_list: List[np.ndarray]) -> np.ndarray | None:
    """Return the pixel‑wise median of *image_list* if shapes are consistent."""
    if not image_list:
        return None
    first_shape = image_list[0].shape
    stack = [im for im in image_list if im.shape == first_shape]
    if not stack:
        return None
    return np.uint8(np.median(np.stack(stack, axis=0), axis=0))


def apply_diverging_colormap(
    diff: np.ndarray,
    vmin: float,
    vmax: float,
    base1: np.ndarray | None = None,
    base2: np.ndarray | None = None,
    cmap_name: str = "coolwarm",
    bg_threshold: int = 5,
    diff_threshold: float = 2.0,      # |diff| ≤ threshold → just white
) -> np.ndarray:
    """
    · Outside brain          → black
    · Brain canvas           → white
    · |diff| > threshold     → red/blue overlay (opacity ∝ |diff|)
    """
    if vmin >= vmax:
        vmin, vmax = -1.0, 1.0

    # Foreground mask (brain)
    if (
        base1 is None or base2 is None or
        base1.shape != diff.shape or base2.shape != diff.shape
    ):
        mask_fg = np.ones_like(diff, dtype=bool)
    else:
        mask_fg = (base1 > bg_threshold) | (base2 > bg_threshold)

    h, w = diff.shape
    out = np.zeros((h, w, 3), np.uint8)      # start all‑black
    out[mask_fg] = 255                       # brain → white

    # Colourise *entire* diff once (RGB → BGR)
    cmap = colormaps[cmap_name]
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    bgr_full = cv2.cvtColor(
        (cmap(norm(diff))[:, :, :3] * 255).astype(np.uint8),
        cv2.COLOR_RGB2BGR,
    )

    # Per‑pixel opacity α  (H×W×1)  — smooth ramp beyond threshold
    alpha = np.clip(
        (np.abs(diff) - diff_threshold) / max(max(abs(vmin), abs(vmax)) - diff_threshold, 1e-6),
        0, 1,
    )[..., None]                              # broadcast channel‑wise

    # Blend *vectorised* → no boolean‑index shape clash
    overlay = (alpha * bgr_full.astype(np.float32) +
               (1 - alpha) * 255).astype(np.uint8)

    # Only inside brain
    out = np.where(mask_fg[..., None], overlay, out)

    return out


# ──────────────────────────────────────────────────────────────────────────────
# Main generator
# ──────────────────────────────────────────────────────────────────────────────

def main(
    root_dir: Path,
    brain_to_class: Dict[str, str],
    assignment_file: str | None = None,
) -> None:
    """Compute per‑class medians and save difference maps in BW & colour."""

    # ─── Load assignments JSON ───────────────────────────────────────────────
    assignments_path: Path
    if assignment_file:
        assignments_path = Path(assignment_file)
    else:
        assignments_path = root_dir / "atlas_to_brain.json"
    if not assignments_path.is_file():
        raise FileNotFoundError(f"Assignments JSON not found: {assignments_path}")

    assignments: Dict[str, Dict[str, str]] = json.loads(assignments_path.read_text(encoding="utf-8"))

    median_root   = root_dir / "median"
    diff_root     = root_dir / "difference_heatmap"  # coloured, diverging

    for p in (median_root, diff_root):
        p.mkdir(parents=True, exist_ok=True)

    # ─── 1) Collect registered images by class → modality → final atlas slice ─
    # Keep paths, not thousands of full-resolution arrays, in memory.
    aggregator = {}
    valid_brains = set(assignments) & set(brain_to_class)

    for brain in valid_brains:
        cls = brain_to_class[brain]
        agg_cls = aggregator.setdefault(cls, {"structure": {}, "inflammation": {}})

        for modality_folder, key in (("structure_registered", "structure"),
                                     ("inflammation_registered", "inflammation")):
            for query_file, atlas_slice in assignments[brain].items():
                path = root_dir / brain / modality_folder / query_file
                if not path.is_file():
                    raise FileNotFoundError(f"Missing registered image: {path}")
                agg_cls[key].setdefault(atlas_slice, []).append(path)

    # ─── 2) Compute medians and save ─────────────────────────────────────────
    medians: Dict[str, Dict[str, Dict[str, np.ndarray]]] = {}
    for cls, mod_dict in aggregator.items():
        for mod_key, slice_map in mod_dict.items():
            out_dir = median_root / cls / mod_key
            out_dir.mkdir(parents=True, exist_ok=True)
            for atlas_slice, paths in slice_map.items():
                imgs = [cv2.imread(str(path), cv2.IMREAD_GRAYSCALE) for path in paths]
                if any(img is None for img in imgs):
                    raise ValueError(f"Unreadable registered image for {cls}/{atlas_slice}")
                med = compute_median_image(imgs)
                if med is not None:
                    if not cv2.imwrite(str(out_dir / atlas_slice), med):
                        raise OSError(f"Cannot save median: {out_dir / atlas_slice}")
                    medians.setdefault(cls, {}).setdefault(mod_key, {})[atlas_slice] = out_dir / atlas_slice
                del imgs, med
        print(f"[visuals] Medians: {cls}", flush=True)

    # ─── 3) Signed and magnitude differences for every ordered pair of classes ──
    class_labels = list(medians)
    if len(class_labels) < 2:
        print("⚠ Only one class with data – skipping difference maps.")
        return

    global_max = 0.0
    pairs = []
    for a, b in itertools.permutations(class_labels, 2):
        label = f"{a}_vs_{b}"
        common_slices = sorted(set(medians[a].get("inflammation", {})) & set(medians[b].get("inflammation", {})))
        pairs.append((a, b, common_slices))
        for slc in common_slices:
            img_a = cv2.imread(str(medians[a]["inflammation"][slc]), cv2.IMREAD_GRAYSCALE)
            img_b = cv2.imread(str(medians[b]["inflammation"][slc]), cv2.IMREAD_GRAYSCALE)
            diff = img_a.astype(np.float32) - img_b.astype(np.float32)
            global_max = max(global_max, np.max(np.abs(diff)))

    if global_max == 0:
        global_max = 1.0  # prevent division‑by‑zero in degenerate case

    vmin, vmax = -global_max, global_max
    for a_label, b_label, slices in pairs:
        label = f"{a_label}_vs_{b_label}"
        coloured_dir = diff_root / label
        coloured_dir.mkdir(parents=True, exist_ok=True)

        for slc in slices:
            # ── 3a. Diverging colour map (signed) ────────────────────────────
            base_a = cv2.imread(str(medians[a_label]["inflammation"][slc]), cv2.IMREAD_GRAYSCALE)
            base_b = cv2.imread(str(medians[b_label]["inflammation"][slc]), cv2.IMREAD_GRAYSCALE)
            diff_f = base_a.astype(np.float32) - base_b.astype(np.float32)
            coloured = apply_diverging_colormap(diff_f, vmin, vmax, base_a, base_b)
            coloured = overlay_colorbar(coloured, vmin, vmax)
            if not cv2.imwrite(str(coloured_dir / slc), coloured):
                raise OSError(f"Cannot save difference map: {coloured_dir / slc}")
        print(f"[visuals] Difference maps: {label} ({len(slices)} levels)", flush=True)



