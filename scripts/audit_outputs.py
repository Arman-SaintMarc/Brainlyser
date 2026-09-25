"""Check run completeness, images, and independently recompute sampled statistics.

Usage: python scripts/audit_outputs.py path/to/processed_data_directory
The report is a software consistency check, not an anatomical validation.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np


def audit(root):
    root = Path(root).resolve()
    assignments = json.loads((root / "atlas_to_brain.json").read_text())
    data = json.loads((root / "brain_slice_data.json").read_text())
    measured = {name: rows[0] for item in data for name, rows in item.items()}
    registration = json.loads((root / "registration_parameters.json").read_text())
    with (root / "detection_manifest.csv").open() as stream:
        detections = list(csv.DictReader(stream))
    assert len({(row['brain'], row['source_image']) for row in detections}) == len(detections)
    assigned_count = sum(len(mapping) for mapping in assignments.values())
    quantified_count = sum(len(row['images']) for row in measured.values())
    assert assigned_count == quantified_count, (assigned_count, quantified_count)
    checked_images = checked_metrics = 0
    optimization_failures = []
    for brain, mapping in assignments.items():
        assert set(mapping) == set(measured.get(brain, {}).get('images', {}))
        assert set(mapping) == set(registration.get(brain, {}))
        middle = sorted(mapping)[len(mapping)//2] if mapping else None
        for filename, atlas in mapping.items():
            assert 1 <= int(Path(atlas).stem[5:]) <= 220
            for folder in ('structure', 'inflammation', 'structure_registered', 'inflammation_registered', 'mask'):
                image_path = root / brain / folder / (Path(filename).with_suffix('.png') if folder == 'mask' else filename)
                image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
                assert image is not None and image.shape == (800,1140), str(image_path)
                if folder == 'mask':
                    assert set(np.unique(image)).issubset(set(range(10)))
                checked_images += 1
            params = registration[brain][filename]
            assert np.isfinite(params['params']).all() and np.isfinite(params['cost'])
            if not params['optimizer_success']:
                optimization_failures.append([brain, filename])
            if filename == middle:
                image = cv2.imread(str(root / brain / 'inflammation' / filename), 0).astype(np.float32)
                mask = cv2.imread(str(root / brain / 'mask' / Path(filename).with_suffix('.png')), 0)
                for key, metrics in measured[brain]['images'][filename].items():
                    if key == 'atlas':
                        continue
                    pixels = image.ravel() if key == 'global' else image[mask == int(key.replace('brainRegion',''))]
                    pixels = pixels[pixels != 0]
                    if not len(pixels):
                        assert metrics is None
                        continue
                    expected = {'median':np.median(pixels), 'mean':np.mean(pixels), 'std':np.std(pixels),
                                'min':np.min(pixels), 'max':np.max(pixels)}
                    for statistic, value in expected.items():
                        assert np.isclose(metrics[statistic], value, rtol=1e-6), (brain,key,statistic)
                        checked_metrics += 1
    with (root / 'brain_slice_data.csv').open() as stream:
        assert len(list(csv.DictReader(stream))) == quantified_count
    result = {'output':str(root), 'source_photos':len(detections),
              'detection_statuses':dict(Counter(row['status'] for row in detections)),
              'specimens':len(measured), 'class_specimens':dict(Counter(row['class'] for row in measured.values())),
              'assigned_slices':assigned_count, 'quantified_slices':quantified_count,
              'unassigned_crops':sum(row['status'] == 'processed' for row in detections) - assigned_count,
              'image_checks':checked_images, 'independent_statistic_checks':checked_metrics,
              'optimizer_failures':optimization_failures,
              'scope':'Execution and internal consistency only; automatic assignments not independently anatomically validated.'}
    (root / 'validation_audit.json').write_text(json.dumps(result, indent=2))
    with (root / 'image_coverage.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['brain','source_image','crop_image','atlas_image','outcome'])
        writer.writeheader()
        for row in detections:
            atlas = assignments.get(row['brain'], {}).get(row['crop_image'], '')
            writer.writerow({'brain':row['brain'], 'source_image':row['source_image'], 'crop_image':row['crop_image'],
                             'atlas_image':atlas, 'outcome':'quantified' if atlas else
                             'unassigned_crop' if row['status'] == 'processed' else row['status']})
    print(json.dumps(result, indent=2), flush=True)
    return result


if __name__ == '__main__':
    audit(sys.argv[1])
