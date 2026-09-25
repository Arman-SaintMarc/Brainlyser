"""
Batch image processor with YOLO object detection.

Folder layout
-------------
```
RAW_DATA_DIR/
    brainA/
        img001.jpg
        img002.jpg
    brainB/
        ...
```
The script rebuilds the same hierarchy under `processed_data_dir`, writing two
cropped brain single-channel outputs: structure (green channel) and inflammation (red channel with CRIMSON dye) for each source image.

Brains are processed sequentially with one shared model and small image batches
to bound memory consumption on desktop machines.
"""

import os
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Tuple

import cv2
import torch
from ultralytics import YOLO

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
MODEL_PATH           = Path(__file__).resolve().parent / "assets/best.pt"
BBOX_SIZE            : Tuple[int, int] = (1140, 800)
CONFIDENCE_THRESHOLD = 0.75
IMG_SIZE             = 640
BATCH_SIZE           = 2
GROUP_WORKERS        = 1
NUM_SAVE_WORKERS     = 8
DEVICE               = "cuda" if torch.cuda.is_available() else "cpu"
_VALID_EXTS          = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

torch.backends.cudnn.benchmark = True
cv2.setNumThreads(0)
torch.set_num_threads(min(4, os.cpu_count() or 1))


def _collect_images(group_dir: Path):
    return sorted(p for p in group_dir.iterdir() if p.is_file() and p.suffix.lower() in _VALID_EXTS)


def _ensure_out_dirs(processed_data_dir: Path, group_name: str):
    struct_dir = processed_data_dir / group_name / "structure"
    infl_dir = processed_data_dir / group_name / "inflammation"
    struct_dir.mkdir(parents=True, exist_ok=True)
    infl_dir.mkdir(parents=True, exist_ok=True)
    return struct_dir, infl_dir


def _load_model() -> YOLO:
    m = YOLO(MODEL_PATH, verbose=False)
    m.fuse()
    if DEVICE.startswith("cuda") and torch.cuda.is_available():
        m.model.half().to(DEVICE)
    else:
        m.to(DEVICE)
    return m


def _process_group(group_dir: Path, processed_data_dir: Path, model=None, manifest=None) -> Tuple[int, int]:
    struct_dir, infl_dir = _ensure_out_dirs(processed_data_dir, group_dir.name)
    img_paths = _collect_images(group_dir)
    if not img_paths:
        return 0, 0

    model = model if model is not None else _load_model()
    processed = failed = 0
    slice_idx = 0

    for i in range(0, len(img_paths), BATCH_SIZE):
        batch = [cv2.imread(str(p)) for p in img_paths[i : i + BATCH_SIZE]]
        valid = [(im, p) for im, p in zip(batch, img_paths[i : i + BATCH_SIZE]) if im is not None]
        for im, path in zip(batch, img_paths[i : i + BATCH_SIZE]):
            if im is None:
                failed += 1
                if manifest is not None:
                    manifest.writerow([group_dir.name, path.name, "", "unreadable"])
        if not valid:
            continue

        imgs, paths = zip(*valid)
        results = model.predict(imgs, conf=CONFIDENCE_THRESHOLD, imgsz=IMG_SIZE, verbose=False)
        jobs = []

        for path, res in zip(paths, results):
            orig = res.orig_img
            boxes = res.boxes.xyxy.cpu().numpy()
            if boxes.size == 0:
                failed += 1
                if manifest is not None:
                    manifest.writerow([group_dir.name, path.name, "", "no_detection"])
                continue

            areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
            x1, y1, x2, y2 = boxes[areas.argmax()].astype(int)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            crop_w, crop_h = BBOX_SIZE
            xb, yb = max(0, cx - crop_w // 2), max(0, cy - crop_h // 2)
            crop = orig[yb : yb + crop_h, xb : xb + crop_w]

            if crop.shape[:2] != (crop_h, crop_w):
                failed += 1
                if manifest is not None:
                    manifest.writerow([group_dir.name, path.name, "", "incomplete_crop"])
                continue

            struct_img = cv2.bitwise_not(crop[:, :, 1])
            infl_img = crop[:, :, 2]
            fname = f"slice{slice_idx:04d}.jpg"
            jobs.append((struct_dir / fname, struct_img))
            jobs.append((infl_dir / fname, infl_img))
            slice_idx += 1
            processed += 1
            if manifest is not None:
                manifest.writerow([group_dir.name, path.name, fname, "processed"])

        if jobs:
            with ThreadPoolExecutor(max_workers=NUM_SAVE_WORKERS) as executor:
                futures = [executor.submit(cv2.imwrite, str(path), img) for path, img in jobs]
                for future in as_completed(futures):
                    if not future.result():
                        raise OSError(f"Could not save crop in {struct_dir.parent}")

    return processed, failed


@torch.no_grad()
def main(raw_data_dir: Path, processed_data_dir: Path, specimen_names=None) -> Tuple[int, int]:
    """Process all subfolders under raw_data_dir into processed_data_dir."""
    raw_data_dir, processed_data_dir = Path(raw_data_dir), Path(processed_data_dir)
    processed_data_dir.mkdir(parents=True, exist_ok=True)
    groups = sorted(d for d in raw_data_dir.iterdir() if d.is_dir() and
                    (specimen_names is None or d.name in specimen_names))
    if not groups:
        raise ValueError(f"No specimen directories found in {raw_data_dir}")

    total_processed = 0
    total_failed = 0
    model = _load_model()
    with (processed_data_dir / "detection_manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        manifest = csv.writer(stream)
        manifest.writerow(["brain", "source_image", "crop_image", "status"])
        for group in groups:
            proc, fail = _process_group(group, processed_data_dir, model, manifest)
            total_processed += proc
            total_failed += fail
            stream.flush()
            print(f"[detect] {group.name}: {proc} processed, {fail} rejected", flush=True)

    return total_processed, total_failed
