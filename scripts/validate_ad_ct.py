"""Run the complete local AD/CT dataset without manual assignment edits.

This tests software execution, not anatomical accuracy. Original data are read-only.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Code/Brainlyser code"))
from index import run_pipeline

if __name__ == "__main__":
    started = time.time()
    output = run_pipeline(ROOT / "Datasets/raw_data_AD", ROOT / "Datasets/AD vs CT.csv",
                          review=False, open_browser=False, progress=lambda stage: print(stage, flush=True))
    report = {"output": str(output), "seconds": time.time() - started,
              "review": "Automatic assignments retained; not an anatomical validation."}
    (output / "validation_execution.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
