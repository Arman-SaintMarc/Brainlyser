# D55 installation example

This example contains three consecutive RGB blockface photographs from specimen
D55: `DSC02560.JPG`, `DSC02561.JPG`, and `DSC02562.JPG`. The originals are
6000 × 4000 pixels and are copied without re-encoding. The source specimen folder
is named `20230320 D55`. No sex, treatment, or acquisition calibration is
inferred from that name; `REFERENCE` is a demonstration label.

**This is an installation example, not an independent benchmark.** D55 is also
the supplied reference stack, and these three photographs do not support
population-level conclusions or claims of accuracy on new specimens.

## Run

From `Code/Brainlyser code/`, with `brainlyser` activated:

```bash
python run_example.py
```

Alternatively launch `python index.py`, choose `examples/raw/` and
`examples/classes.csv`, leave optional fields empty, and review the automatic
assignments in Brain Comparator before closing it.

## Expected results

A successful command-line test processes three crops, quantifies three slices,
and produces nonempty regional statistics. `expected/example_summary.json`
records the actual automatic assignments from the test machine, its runtime,
and the number of region entries. The corresponding CSV, JSON, registered
images, masks, and class median images are retained in `expected/`.

These outputs are reference software results, not manually certified anatomical
ground truth. Floating-point optimization and inference may differ across
platforms. Use the checksums to verify the delivered files; do not require every
new run to reproduce all image bytes exactly. Review registration quality and
numerical differences before reusing results.

There is one specimen and one class. Therefore no disease-control heatmap or
between-class difference image is expected. Empty comparison files may be absent.

## Files and rights

- `raw/D55/`: the three raw photographs.
- `classes.csv`: `Brain,Class` table with `D55,REFERENCE`.
- `expected/`: outputs from the documented test.
- `PROVENANCE.json`: input source names and SHA-256 hashes.
- Other `*_example.csv` and `*.example.json` files: format examples only;
  their specimen names do not match this D55 test.

Credit the FastHisto project team. The D55 input images are CC BY 4.0 as
specified in [the data licence](../licenses/DATA-LICENSE.md). Derived atlas
masks and any outputs incorporating Allen content also retain the Allen terms
described in [the third-party notices](../THIRD_PARTY_NOTICES.md).
