# align_d55_to_atlas_fixed.py
"""Brain slice alignment (D55 → Atlas)

This version fixes the signature mismatches and ref‑directory discovery bugs that
caused the previous script to crash.  It also cleans up duplicate constant
declarations and harmonises the public API so that it can be called directly
from your pipeline like::

    from align_d55_to_atlas_fixed import main as align_all_brains
    assignments_json = align_all_brains(output_dir)

The function returns the absolute path of the newly‑created
``atlas_to_brain.json`` file inside *output_dir*.
"""
from __future__ import annotations
import sys, logging, io, pathlib
from pathlib import Path
import os
import hashlib



if getattr(sys, "frozen", False):                           # only when frozen
    # Create a writable dev-null *in binary*, then wrap it with a UTF-8 text layer.
    devnull_bin = open(os.devnull, "wb", buffering=0)
    devnull_txt = io.TextIOWrapper(devnull_bin,
                                   encoding="utf-8",
                                   write_through=True)      # immediate flush
    sys.stdout = sys.stdout or devnull_txt
    sys.stderr = sys.stderr or devnull_txt


import glob
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Sequence, Tuple


import cv2
import numpy as np
import torch
from scipy.spatial.distance import cdist
from torchvision import transforms

# ─────────────────────────── Global configuration ────────────────────────────
# Basename of the reference stack *folder* that lives somewhere inside the
# dataset root.  We do **not** embed any ".." sequences here; instead we search
# for a matching directory within *root_dir* at runtime.
DEFAULT_REF_BASENAME = Path(__file__).resolve().parent / "assets/20230320 D55"

MODEL_NAME: str = "dinov2_vits14_reg"
IMAGE_SIZE: int = 224
BATCH_SIZE: int = 8
GAP_PENALTY: float = 0.0

NUM_CPU_THREADS: int = min(4, os.cpu_count() or 1)
MAX_WORKERS: int = 1

OUTPUT_JSON: str = "d55_to_brain.json"   # kept for backwards compatibility
OUTPUT_ATLAS_JSON: str = "atlas_to_brain.json"

# ---------------------------------------------------------------------------
# D55 slice index → Atlas slice index  (manually curated look‑up table)
# ---------------------------------------------------------------------------
DEFAULT_REF_ATLAS_PAIRS: Sequence[Tuple[int, int]] = [
    (10, 5), (11, 6), (12, 7), (13, 8), (14, 9), (15, 10), (16, 11),
    (17, 12), (18, 13), (19, 14), (20, 15), (21, 17), (22, 19), (23, 21),
    (24, 23), (25, 25), (26, 27), (27, 29), (28, 31), (29, 32), (30, 34),
    (31, 35), (32, 37), (33, 38), (34, 40), (35, 41), (36, 43), (37, 44),
    (38, 46), (39, 47), (40, 49), (41, 50), (42, 52), (43, 53), (44, 55),
    (45, 56), (46, 58), (47, 59), (48, 61), (49, 62), (50, 63), (51, 64),
    (52, 65), (53, 66), (54, 67), (55, 68), (56, 69), (57, 70), (58, 71),
    (59, 72), (60, 73), (61, 74), (62, 75), (63, 76), (64, 77), (65, 78),
    (66, 79), (67, 81), (68, 82), (69, 83), (70, 85), (71, 87), (72, 89),
    (73, 91), (74, 92), (75, 94), (76, 95), (77, 97), (78, 98), (79, 99),
    (80, 100), (81, 102), (82, 104), (83, 106), (84, 107), (85, 109),
    (86, 110), (87, 112), (88, 113), (89, 114), (90, 115), (91, 117),
    (92, 118), (93, 120), (94, 121), (95, 122), (96, 123), (97, 124),
    (98, 125), (99, 126), (102, 127), (103, 128), (104, 129), (105, 130),
    (106, 131), (107, 133), (108, 134), (109, 136), (110, 137), (111, 139),
    (112, 140), (113, 142), (114, 143), (115, 144), (116, 146), (117, 147),
    (118, 149), (119, 150), (120, 153), (121, 154), (122, 156), (123, 157),
    (124, 160), (125, 161), (126, 163), (127, 164), (128, 166), (129, 167),
    (130, 169), (131, 170), (132, 173), (133, 174), (134, 175), (135, 176),
    (136, 177), (137, 178), (138, 179), (139, 180), (140, 181), (141, 182),
    (142, 183), (143, 184), (144, 186), (146, 187), (147, 188), (148, 189),
    (149, 190), (150, 192), (151, 193), (152, 194), (153, 195), (154, 197),
    (155, 198), (156, 200), (157, 201), (158, 203), (159, 204), (160, 206),
    (161, 207), (162, 209), (163, 210), (164, 212), (165, 213), (166, 215),
    (167, 216), (168, 218), (169, 219), (170, 220),
]

# ───────────────────── Torch / DINO helpers ─────────────────────────────────


MODEL_NAME  = "dinov2_vits14_reg"
CACHE_SUB   = "dinov2_repo"

def _asset_path(*parts: str) -> Path:
    """Resolve data files both frozen and unfrozen."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base.joinpath(*parts)

def _load_dino_model(root_dir: Path) -> torch.nn.Module:
    """Load the bundled, checksum-verified DINOv2 model without a download."""
    # 1  Pick a device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        torch.set_num_threads(NUM_CPU_THREADS)

    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    repo = base / "assets" / "dinov2_repo"
    weights = repo / "models" / "dinov2_vits14_reg4_pretrain.pth"
    if not (repo / "hubconf.py").is_file() or not weights.is_file():
        raise FileNotFoundError("DINOv2 assets missing. Extract the complete Brainlyser package, including assets/dinov2_repo.")
    digest = hashlib.sha256()
    with weights.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != "f433177089a681826f849f194ece3bb48f4d63fb38d32fc837e3dc7a4e5641fb":
        raise ValueError("DINOv2 weight checksum mismatch. Restore the supplied model file.")
    model = torch.hub.load(str(repo), MODEL_NAME, source="local", pretrained=False)
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True), strict=True)
    return model.eval().to(device)


_TFM = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize(IMAGE_SIZE, interpolation=transforms.InterpolationMode.BICUBIC),
    transforms.CenterCrop(IMAGE_SIZE),
    transforms.ToTensor(),
    transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
])


def _to_rgb(img: np.ndarray) -> np.ndarray:
    """Ensure a H×W×3 uint8 RGB image (duplicate greys if necessary)."""
    if img.ndim == 2:
        return np.stack([img] * 3, -1)
    if img.ndim == 3 and img.shape[2] == 1:
        return np.repeat(img, 3, -1)
    if img.ndim == 3 and img.shape[2] == 3:
        return img
    raise ValueError(f"Unexpected image shape {img.shape}")


def _compute_embeddings(imgs: Sequence[np.ndarray], model: torch.nn.Module) -> np.ndarray:
    """Forward all images through DINO and return ℓ²‑normalised feature vectors."""
    device = next(model.parameters()).device
    vecs: List[np.ndarray] = []
    for start in range(0, len(imgs), BATCH_SIZE):
        batch_rgb = [_to_rgb(g) for g in imgs[start : start + BATCH_SIZE]]
        x = torch.stack([_TFM(im) for im in batch_rgb]).to(device)
        with torch.inference_mode():
            feats = model.forward_features(x)["x_norm_clstoken"].cpu().numpy()
        feats /= np.linalg.norm(feats, axis=1, keepdims=True)  # ℓ² normalise
        vecs.append(feats)
    return np.vstack(vecs)

# ───────────────────────── Dynamic Time Warping ─────────────────────────────

def _sequence_align(sim: np.ndarray) -> List[Tuple[int, int]]:
    """Needleman–Wunsch‑style global alignment with constant gap penalty."""
    N, M = sim.shape
    score = np.full((N + 1, M + 1), -np.inf, dtype=np.float32)
    ptr   = np.zeros((N + 1, M + 1, 2), dtype=int)  # back‑pointers

    score[0, 0] = 0.0
    for i in range(1, N + 1):
        score[i, 0] = score[i - 1, 0] + GAP_PENALTY
        ptr[i, 0]   = (i - 1, 0)
    for j in range(1, M + 1):
        score[0, j] = score[0, j - 1] + GAP_PENALTY
        ptr[0, j]   = (0, j - 1)

    for i in range(1, N + 1):
        for j in range(1, M + 1):
            match = score[i - 1, j - 1] + sim[i - 1, j - 1]
            delete = score[i - 1, j] + GAP_PENALTY
            insert = score[i, j - 1] + GAP_PENALTY
            best = max(match, delete, insert)
            score[i, j] = best
            if best == match:
                ptr[i, j] = (i - 1, j - 1)
            elif best == delete:
                ptr[i, j] = (i - 1, j)
            else:
                ptr[i, j] = (i, j - 1)

    # back‑trace
    pairs: List[Tuple[int, int]] = []
    i, j = N, M
    while (i, j) != (0, 0):
        pi, pj = ptr[i, j]
        if (i - 1, j - 1) == (pi, pj):  # diagonal ⇒ real match
            pairs.append((i - 1, j - 1))
        i, j = pi, pj
    pairs.reverse()
    return pairs

# ──────────────────────── Image IO helpers ──────────────────────────────────

def _load_gray_series(folder: Path) -> Tuple[List[str], List[np.ndarray]]:
    """Return (file_names, grayscale_images) sorted numerically."""
    files = sorted(
        glob.glob(str(folder / "*.png"))
        + glob.glob(str(folder / "*.jpg"))
        + glob.glob(str(folder / "*.jpeg"))
        + glob.glob(str(folder / "*.tif")),
        key=lambda p: int("".join(filter(str.isdigit, Path(p).stem)) or -1),
    )
    if not files:
        raise FileNotFoundError(f"No slice images found in {folder!s}")
    names = [Path(f).name for f in files]
    imgs  = [cv2.imread(f, cv2.IMREAD_GRAYSCALE) for f in files]
    for name, img in zip(names, imgs):
        if img is None:
            raise ValueError(f"Unreadable image: {folder / name}")
    return names, imgs

# ───────────────────────── Single‑stack worker ─────────────────────────────

def _process_stack(stack_dir: Path, ref_emb: np.ndarray, ref_names: List[str],
                   model: torch.nn.Module) -> Tuple[str, Dict[str, str]]:
    """Align *one* brain stack and return its mapping dict."""
    slice_dir = stack_dir / "structure"
    test_names, test_imgs = _load_gray_series(slice_dir)
    test_emb = _compute_embeddings(test_imgs, model)

    sim = 1.0 - cdist(test_emb, ref_emb, metric="cosine")  # similarity matrix
    matches = _sequence_align(sim)

    mapping = {test_names[t]: ref_names[r] for t, r in matches}
    print(f"  • {stack_dir.name:<30} ↔ {len(matches):3d} pairs")
    return stack_dir.name, mapping

# ─────────────────────────────── Public API ────────────────────────────────

def main(
    root_dir: str | Path,
    *,
    ref_dir: str | Path | None = None,
    ref_atlas_pairs: Sequence[Tuple[int, int]] | None = None,
) -> Path:
    """
    Align all stacks found in *root_dir* to a reference stack.

    Parameters
    ----------
    root_dir : Path
        The pipeline's output directory (contains per-brain sub-folders).
    ref_dir : Path, optional
        Folder holding the reference stack images (default = D55 stack).
    ref_atlas_pairs : list[(ref_idx, atlas_idx)], optional
        Slice-index mapping. Defaults to the built-in D55 mapping.
    """
    root_dir = Path(root_dir)

    # 1. Decide which reference stack & mapping to use ---------------------
    if ref_dir is None:
        ref_dir = root_dir / DEFAULT_REF_BASENAME
    else:
        ref_dir = Path(ref_dir)

    if ref_atlas_pairs is None:
        ref_atlas_pairs = DEFAULT_REF_ATLAS_PAIRS

    REF_TO_ATLAS_IDX = {ref: atl for ref, atl in ref_atlas_pairs}

    # 2. Pre-compute reference embeddings ---------------------------------
    model = _load_dino_model(root_dir / "../../assets" / "dinov2_repo")
    ref_names, ref_imgs = _load_gray_series(ref_dir / "structure")
    ref_emb = _compute_embeddings(ref_imgs, model)
    del ref_imgs

    # 3. Align every other sub-stack ---------------------------------------
    atlas_map: Dict[str, Dict[str, str]] = {}
    work_dirs = sorted(d for d in root_dir.iterdir() if (d / "structure").is_dir()
                       and any((d / "structure").glob("*.jpg")) and d != ref_dir)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_process_stack, d, ref_emb, ref_names, model): d
            for d in work_dirs
        }
        for fut in as_completed(futures):
            brain_name, mapping_ref = fut.result()
            # convert ref-slice names → atlas-slice names
            mapping_atlas: Dict[str, str] = {}
            for test_slice, ref_slice in mapping_ref.items():
                idx = int("".join(filter(str.isdigit, ref_slice)))
                if idx in REF_TO_ATLAS_IDX:
                    atlas_idx = REF_TO_ATLAS_IDX[idx]
                    mapping_atlas[test_slice] = f"slice{atlas_idx:04d}.jpg"
            atlas_map[brain_name] = mapping_atlas

    # 4. Write JSON and return path ----------------------------------------
    atlas_json_path = root_dir / OUTPUT_ATLAS_JSON
    atlas_json_path.write_text(json.dumps(atlas_map, indent=2), encoding="utf-8")
    print(f"[align] Saved → {atlas_json_path}")
    return atlas_json_path


if __name__ == "__main__":  # pragma: no cover
    import argparse

    ap = argparse.ArgumentParser(description="Align D55 brain slices to Atlas coordinates.")
    ap.add_argument("root", type=Path, help="Root folder produced by the pipeline (contains per‑brain subdirs)")
    ns = ap.parse_args()
    main(ns.root)
