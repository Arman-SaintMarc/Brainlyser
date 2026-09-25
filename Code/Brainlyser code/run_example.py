"""Run the supplied D55 example without the manual-review window."""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from time import perf_counter


def main():
    app = Path(__file__).resolve().parent
    os.chdir(app)
    example = app.parent.parent / "examples"
    with (example / "classes.csv").open(newline="", encoding="utf-8") as stream:
        classes = {row["Brain"]: row["Class"] for row in csv.DictReader(stream)}

    import yolo_processor as detector
    import dino_brains_alignment as aligner
    from brains_registration import main as register
    from extract_stats import main as quantify
    from visuals_generation import main as visualize

    started = perf_counter()
    output = app / "data" / datetime.now().strftime("processed_data_example_%Y%m%d_%H%M%S_%f")
    output.mkdir(parents=True, exist_ok=False)
    detector.main(example / "raw", output)
    assignments_path = aligner.main(output)
    register(output, assignments_path)
    quantify(output, classes, assignments_path)
    visualize(output, classes, assignments_path)

    with (output / "brain_slice_data.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    crop_count = sum(len(list((output / brain / "structure").glob("*.jpg"))) for brain in classes)
    region_count = sum(len(json.loads(row["region_stats_json"])) for row in rows)
    if crop_count != 3 or len(rows) != 3 or region_count == 0:
        raise RuntimeError(f"Example failed: crops={crop_count}, rows={len(rows)}, regions={region_count}. See {output}")

    summary = {
        "example": "D55 three-image inference demonstration",
        "processed_images": crop_count,
        "quantified_slices": len(rows),
        "region_entries": region_count,
        "assignments": json.loads(Path(assignments_path).read_text()),
        "elapsed_seconds": round(perf_counter() - started, 2),
        "review": "automatic assignments accepted for installation testing only",
    }
    (output / "example_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    last_path = "../data/" + output.name
    (app / "interface/js/last_path.js").write_text(f"const lastPath = {json.dumps(last_path)};\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"PASS: example results in {output}")
    print(f"Dashboard: {(app / 'interface/index.html').as_uri()}")


if __name__ == "__main__":
    main()
