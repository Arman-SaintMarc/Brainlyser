# Validation record

This record was written for source snapshot 2026.09.08. Snapshot 2026.09.24
(released as version 1.0.0) adds the tests listed in `CHANGELOG.md`; the
commands below apply unchanged. Paths are relative to the repository root.

Tests were performed on macOS with an Intel Core i5-1038NG7 CPU (2.00 GHz)
in the existing `brainlyser` Conda
environment. Exact principal package versions are recorded in
`VALIDATED_ENVIRONMENT.json`.

## Checks completed

- All application modules import successfully. `python -m pip check` reports
  no broken requirements.
- The custom YOLO checkpoint loads and reports the single class `brain`.
- The local DINOv2 model loads with its SHA-256 verified. A forward pass
  produces a normalized 384-component feature vector.
- The main Brainlyser Tk window opens and closes on macOS.
- The comparator opens with the three assignments, renders its missing-image
  placeholder with the installed Pillow version, and closes successfully.
- `scripts/validate_gui.py` exercises the complete GUI pipeline: automatic
  input selection, worker-thread processing, main-thread comparator creation,
  acceptance of the three assignments, registration, quantification, and
  successful completion. It accepts the matches automatically for this test.
- The full command-line example detects three D55 crops, assigns them to atlas
  levels 69, 70, and 71, registers them, and exports three quantified slices
  with twelve regional entries. Processing took 29.73 seconds after imports on
  the test machine; this is one observed run, not a minimum hardware or speed
  guarantee.
- Regression tests cover atlas levels 1 and 220 and reject out-of-range levels
  0 and 221. This guards the export correction without changing intensity
  definitions.
- The expected outputs are retained in `examples/expected/`.

Run the regression checks from the package root with the environment activated:

```bash
python -m unittest discover -s tests -v
```

Run the end-to-end example from `Code/Brainlyser code/`:

```bash
python run_example.py
```

The command-line example automatically accepts DINOv2 matches. It does not
replace manual review, validate anatomical accuracy, or establish independence
from the reference specimen. No disease-control comparison is possible with
this single specimen. Windows and Apple Silicon source execution have not been
tested here. The older Windows binary is not covered by this validation.
