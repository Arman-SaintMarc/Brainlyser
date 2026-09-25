import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Optional

import cv2
import numpy as np
from scipy.optimize import minimize


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
ATLAS_FOLDER_NAME = Path(__file__).resolve().parent / "assets/atlas"
ALIGN_JSON_FILENAME = "atlas_to_brain.json"
MAX_WORKERS: int = min(4, os.cpu_count() or 1)


def transform_image(img: np.ndarray, angle: float, tx: float, ty: float, scale: float) -> np.ndarray:
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, scale)
    M[0, 2] += tx
    M[1, 2] += ty
    return cv2.warpAffine(img, M, (w, h))


def cost_function(params: tuple[float, float, float, float], ref_bin: np.ndarray, mov_small: np.ndarray) -> float:
    angle, tx, ty, scale = params
    if not (-5 <= angle <= 5 and 0.85 <= scale <= 1.3):
        return 1e15
    diff_img = transform_image(mov_small, angle, tx, ty, scale)
    _, diff_bin = cv2.threshold(diff_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return float(cv2.countNonZero(cv2.absdiff(ref_bin, diff_bin)))


def get_transformation_matrix(shape: tuple[int, int], angle: float, tx: float, ty: float, scale: float) -> np.ndarray:
    h, w = shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, scale)
    M[0, 2] += tx
    M[1, 2] += ty
    return M


def invert_affine_transform(M: np.ndarray) -> np.ndarray:
    M_full = np.vstack([M, [0, 0, 1]])
    return np.linalg.inv(M_full)[:2, :]


# ───────────────────────────────────────────────────────────────
# Single‑slice registration
# ───────────────────────────────────────────────────────────────

def _process_single_slice(
    query_file: str,
    assignments: Dict[str, str],
    atlas_structure_folder: Path,
    query_structure_folder: Path,
    query_infl_folder: Optional[Path],
    out_structure_folder: Path,
    out_infl_folder: Optional[Path],
) -> Optional[Dict[str, Dict[str, list[float]]]]:
    atlas_path = atlas_structure_folder / assignments[query_file]

    ref_full = cv2.imread(atlas_path.as_posix(), cv2.IMREAD_GRAYSCALE)
    mov_full = cv2.imread((query_structure_folder / query_file).as_posix(), cv2.IMREAD_GRAYSCALE)
    if ref_full is None or mov_full is None:
        raise ValueError(f"Unreadable registration image: {atlas_path} or {query_structure_folder / query_file}")

    if ref_full.shape != mov_full.shape:
        mov_full = cv2.resize(mov_full, (ref_full.shape[1], ref_full.shape[0]))

    ref_small = ref_full
    mov_small = mov_full
    _, ref_bin = cv2.threshold(ref_small, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    res = minimize(
        cost_function,
        x0=(0.0, 0.0, 0.0, 1.0),
        args=(ref_bin, mov_small),
        method="Powell",
        options={"disp": False},
    )
    ang, tx, ty, sc = res.x

    registered_struct = transform_image(mov_full, ang, tx, ty, sc)
    out_structure_folder.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite((out_structure_folder / query_file).as_posix(), registered_struct):
        raise OSError(f"Cannot save registered structure: {query_file}")

    atlas_mask_path = atlas_structure_folder.parent / "mask" / f"{atlas_path.stem}.png"
    atlas_mask = cv2.imread(atlas_mask_path.as_posix(), cv2.IMREAD_GRAYSCALE)
    if atlas_mask is not None:
        M_inv = invert_affine_transform(get_transformation_matrix(mov_full.shape, ang, tx, ty, sc))
        mask_out = cv2.warpAffine(atlas_mask, M_inv, (mov_full.shape[1], mov_full.shape[0]), flags=cv2.INTER_NEAREST)
        mask_dir = query_structure_folder.parent / "mask"
        mask_dir.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite((mask_dir / f"{Path(query_file).stem}.png").as_posix(), mask_out):
            raise OSError(f"Cannot save mask: {query_file}")
    else:
        raise ValueError(f"Unreadable atlas mask: {atlas_mask_path}")

    if query_infl_folder and out_infl_folder:
        infl_full = cv2.imread((query_infl_folder / query_file).as_posix(), cv2.IMREAD_GRAYSCALE)
        if infl_full is not None:
            if infl_full.shape != ref_full.shape:
                infl_full = cv2.resize(infl_full, (ref_full.shape[1], ref_full.shape[0]))
            registered_infl = transform_image(infl_full, ang, tx, ty, sc)
            out_infl_folder.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite((out_infl_folder / query_file).as_posix(), registered_infl):
                raise OSError(f"Cannot save registered inflammation: {query_file}")
        else:
            raise ValueError(f"Unreadable inflammation image: {query_infl_folder / query_file}")

    return {query_file: {"params": [float(ang), float(tx), float(ty), float(sc)],
                         "optimizer_success": bool(res.success), "cost": float(res.fun)}}


# ───────────────────────────────────────────────────────────────
# Per‑brain wrapper
# ───────────────────────────────────────────────────────────────

def _register_one_brain(
    brain_path: Path,
    assignment_map: Dict[str, str],
    atlas_structure_folder: Path,
) -> Dict[str, Dict[str, list[float]]]:
    qs_folder = brain_path / "structure"
    qi_folder = brain_path / "inflammation" if (brain_path / "inflammation").is_dir() else None
    out_s_folder = brain_path / "structure_registered"
    out_i_folder = brain_path / "inflammation_registered" if qi_folder else None

    results: Dict[str, Dict[str, list[float]]] = {}
    for qf in sorted(os.listdir(qs_folder)):
        if qf not in assignment_map:
            continue
        res = _process_single_slice(
            qf,
            assignment_map,
            atlas_structure_folder,
            qs_folder,
            qi_folder,
            out_s_folder,
            out_i_folder,
        )
        if res:
            results.update(res)
    return results


# ───────────────────────────────────────────────────────────────
# Master orchestrator
# ───────────────────────────────────────────────────────────────

def main(root_dir: str, assignment_file: str | None = None) -> None:
    """Run registration on every subdirectory inside *root_dir*."""
    root_dir = Path(root_dir)
    json_path = ""
    if assignment_file:
        json_path = Path(assignment_file)
    else: 
        json_path = Path(root_dir) / ALIGN_JSON_FILENAME

    if not json_path.is_file():
        raise FileNotFoundError(f"Missing alignment JSON: {json_path}")
    atlas_to_brain = json.loads(json_path.read_text(encoding="utf-8"))

    atlas_structure_folder = (root_dir / ATLAS_FOLDER_NAME / "structure").resolve()
    if not atlas_structure_folder.is_dir():
        raise FileNotFoundError(f"Atlas structure folder not found: {atlas_structure_folder}")


    brains = [d for d in root_dir.iterdir() if d.is_dir()]


    all_results: Dict[str, Dict] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(
                _register_one_brain,
                brain,
                atlas_to_brain.get(brain.name, {}),
                atlas_structure_folder,
            ): brain for brain in brains if atlas_to_brain.get(brain.name)
        }
        for fut in as_completed(futures):
            brain_path = futures[fut]
            all_results[brain_path.name] = fut.result()
            print(f"[register] {brain_path.name}: {len(all_results[brain_path.name])} slices", flush=True)
    (root_dir / "registration_parameters.json").write_text(json.dumps(all_results, indent=2), encoding="utf-8")
