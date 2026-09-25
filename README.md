# Brainlyser

**Atlas-indexed analysis of serial mouse-brain blockface fluorescence photographs.**

Brainlyser is the image-analysis software of the FastHisto project. From a
folder of RGB photographs taken while a mouse brain is sectioned, it:

1. **detects and crops** the brain in every photograph (custom YOLO11n model);
2. **assigns** each crop to a level of a 220-level mouse-brain atlas
   (DINOv2 features + ordered sequence alignment);
3. lets you **review and correct** those assignments in a graphical editor;
4. **registers** each section to its atlas level (2D similarity transform);
5. **measures** reporter fluorescence in nine broad brain regions and exports
   tables, class-median images, difference maps, and an interactive dashboard.

Brainlyser performs serial atlas-indexed **2D** analysis, not deformable 3D
reconstruction. It is research software, not a clinical diagnostic tool.

- **Version:** 1.0.0 (code identical to source snapshot 2026.09.24; see [CHANGELOG.md](CHANGELOG.md))
- **Licence:** AGPL-3.0 for the code; separate terms for models, atlas and data (see [Licences](#licences))
- **Citation:** see [How to cite](#how-to-cite) and [CITATION.cff](CITATION.cff)

---

## Contents

- [What is distributed where](#what-is-distributed-where)
- [Installation](#installation)
- [Quick test with the included example](#quick-test-with-the-included-example)
- [Reproducing the analyses of the paper](#reproducing-the-analyses-of-the-paper)
- [Analysing your own data](#analysing-your-own-data)
- [Reviewing the atlas assignments](#reviewing-the-atlas-assignments)
- [Outputs](#outputs)
- [Method](#method)
- [Limitations and interpretation](#limitations-and-interpretation)
- [Tests](#tests)
- [Repository layout](#repository-layout)
- [Licences](#licences)
- [How to cite](#how-to-cite)
- [Troubleshooting and support](#troubleshooting-and-support)

---

## What is distributed where

| Part | Where | Size | Contents |
|---|---|---|---|
| **Software** | this GitHub repository | ≈ 200 MB | Python application, dashboard, Conda environment, YOLO detector (`best.pt`), DINOv2 code and weights, 220-level atlas, D55 reference stack, 3-image example with expected outputs, tests, documentation, licences |
| **Paper datasets** *(optional)* | `Brainlyser-dataset-AD.zip` and `Brainlyser-dataset-JEV.zip`, in the data archive cited in the paper | ≈ 18 GB and ≈ 10 GB | The complete raw photograph series and class tables analysed in the paper |

The repository alone is enough to install and run Brainlyser: every model and
reference file is included. The datasets are only needed to reproduce the
analyses of the paper; they are extracted into the repository root:

```text
Brainlyser/                              ← root of this repository
├── Code/Brainlyser code/
│   ├── index.py  …
│   └── assets/
│       ├── best.pt                      YOLO11n brain detector
│       ├── dinov2_repo/                 DINOv2 code + weights
│       ├── atlas/                       220-level atlas
│       ├── 20230320 D55/                D55 reference stack
│       └── ui/                          interface icons
└── Datasets/                            ← dataset ZIPs (optional)
    ├── raw_data_AD/     + AD vs CT.csv
    └── raw data JEV/    + JEVvs CT.csv
```

The integrity of the model and reference files can be checked from the
repository root:

```bash
shasum -a 256 -c ASSETS_CHECKSUMS.sha256
```

---

## Installation

### Requirements

- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or Anaconda.
- A desktop session (the application opens a window).
- ≈ 3 GB of disk for the Conda environment, plus room for results
  (a complete run on the AD dataset writes a few GB).
- An internet connection during installation only.
- A GPU is **not** required. CUDA is used automatically when available;
  otherwise everything runs on the CPU.

Tested platform: Intel macOS, Python 3.10, PyTorch 2.6.0, torchvision 0.21.0,
Ultralytics 8.3.153, OpenCV 4.11.0 (exact versions in
[docs/VALIDATED_ENVIRONMENT.json](docs/VALIDATED_ENVIRONMENT.json)).
Windows, Linux and Apple Silicon should work through the same Conda
environment but were not tested for this release.

### Step by step

**1. Get the code.** Either clone the repository

```bash
git clone https://github.com/Arman-SaintMarc/Brainlyser.git
```

or download the release source ZIP from GitHub (*Code → Download ZIP* or the
v1.0.0 release) and extract it; in that case rename the extracted folder to
`Brainlyser` (or use its name in the commands below). All models, the atlas
and the reference are included; nothing else needs to be downloaded.

**2. Create the Conda environment** (once):

```bash
cd "Brainlyser/Code/Brainlyser code"
conda env create -f environment.yml
```

On older Conda versions, add `--solver libmamba` if solving is slow.
To update an existing environment:
`conda env update -n brainlyser -f environment.yml`.

**3. Start Brainlyser:**

```bash
conda activate brainlyser
python index.py
```

For later sessions, only `conda activate brainlyser` and `python index.py`
are needed, from `Code/Brainlyser code/`.

Analysis runs locally; no image is uploaded anywhere. The dashboard loads its
fonts and icons from public CDNs and simply displays without them offline.

---

## Quick test with the included example

`examples/raw/D55/` holds three consecutive photographs of specimen D55. This
checks that the installation works (≈ 30 s of processing on a laptop CPU).

**Command line** (automatic assignments are accepted, no window):

```bash
cd "Code/Brainlyser code"
conda activate brainlyser
python run_example.py
```

It ends with `PASS: example results in …` and prints the dashboard address.
Compare with the reference results in `examples/expected/`
(3 crops, atlas levels 69–71, 3 quantified slices, 12 regional entries).
Small numerical differences across platforms are expected.

**Graphical interface:**

1. `python index.py`
2. **Data Folder** → select `examples/raw/`.
3. **Brain class (.csv/.xlsx)** → select `examples/classes.csv`.
4. Leave the optional fields empty and click **Start Processing Pipeline**.
5. When **Brain Comparator** opens, inspect the assignments, then close it to
   continue. The dashboard opens in your browser at the end.

D55 is also the reference specimen, so this example validates the
installation, not the accuracy of the method. See [examples/README.md](examples/README.md).

---

## Reproducing the analyses of the paper

The two complete datasets of the paper are distributed separately as ZIP archives.
Their content and provenance are described in [docs/DATASETS.md](docs/DATASETS.md).

| Archive | Experiment | Specimens | Photographs | Class table |
|---|---|---|---|---|
| `Brainlyser-dataset-AD.zip` | Alzheimer's-disease model (AD) vs control (CT), females and males | 39 | 4 257 | `AD vs CT.csv` (classes `AD-F`, `AD-M`, `CT-F`, `CT-M`) |
| `Brainlyser-dataset-JEV.zip` | Japanese encephalitis virus (JEV) infection at three doses vs control | 22 | 2 804 | `JEVvs CT.csv` (classes `Group1-CTRL`, `Group 2`, `Group 4`, `Group 5`) |

1. Extract the archive(s) into the repository root, producing
   `Brainlyser/Datasets/`.
2. Start `python index.py` and select:

   | Dataset | Data Folder | Brain class |
   |---|---|---|
   | AD | `Datasets/raw_data_AD/` | `Datasets/AD vs CT.csv` |
   | JEV | `Datasets/raw data JEV/` | `Datasets/JEVvs CT.csv` |

3. Review the assignments of each specimen in Brain Comparator, then close it.

A full dataset (about 70–110 photographs per specimen) can take several hours
on a CPU; a CUDA GPU shortens detection and assignment.

A non-interactive run of the AD dataset (automatic assignments, no manual
review) is available for software verification:

```bash
conda activate brainlyser
python scripts/validate_ad_ct.py        # from the repository root
```

Results of the paper were obtained **after manual review** of the
assignments; an automatic run is not expected to reproduce them exactly.

---

## Analysing your own data

### Images

- RGB photographs, **one brain blockface per image**.
- The **green** channel (inverted) is used as the structural signal and the
  **red** channel as the reporter signal. Brainlyser is not configured for
  arbitrary multichannel microscopy.
- Accepted formats: `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`, `.bmp`.
- One subfolder per specimen; images are ordered **alphabetically**, so use
  zero-padded or camera-sequential names. Multi-page TIFFs are not read as a
  series. Only images directly inside each specimen folder are read.

```text
my_experiment/
├── brain_001/
│   ├── image_0001.jpg
│   └── image_0002.jpg
└── brain_002/
    ├── image_0001.jpg
    └── image_0002.jpg
```

### Class table

A CSV or Excel file with exactly these two column headers (extra columns are
ignored):

```csv
Brain,Class
brain_001,CT-F
brain_002,AD-F
```

- `Brain` must match the specimen folder name exactly (spaces included).
  Only specimens listed in the table are processed.
- Class names are free. The **disease-vs-control heatmap** of the dashboard is
  produced only for classes ending in `-F` or `-M` with a matching control
  `CT-F` or `CT-M`. Class-median images and pairwise difference images are
  produced for any set of two or more classes.

### Optional inputs

| Field | Use |
|---|---|
| `atlas_to_brain.json` | Reuse existing assignments and skip automatic DINOv2 matching (for example the file saved by a previous, reviewed run). Keys are specimen names, then processed crop names (`slice0000.jpg`, …), mapped to atlas files (`slice0001.jpg` … `slice0220.jpg`). |
| Custom REF→ATLAS CSV/XLSX | Integer columns `REF` and `ATLAS`, mapping a custom reference stack to the supplied atlas (see `examples/ref_to_atlas_example.csv`). |
| Custom REF Folder | Folder containing the custom reference's `structure/` images. Must be used together with the REF→ATLAS table. |

A custom reference changes only how crops are matched; it does not replace
the atlas or its region definitions.

---

## Reviewing the atlas assignments

Brain Comparator opens automatically after DINOv2 matching.

- Select a specimen in the list.
- Drag an image from the right column onto the appropriate reference row.
- The *shift* checkbox controls whether the following assignments move
  together.
- Right-click (Ctrl-click on macOS) removes a match.
- Changes are saved immediately in the run's `atlas_to_brain.json`.
- **Closing the window accepts the assignments** and continues the pipeline.

Always check doubtful matches and the registration overlays before
interpreting measurements.

---

## Outputs

Each run creates a new folder
`Code/Brainlyser code/data/processed_data_YYYYMMDD_HHMMSS_ffffff/`.
Keep it: the dashboard and later analyses read from it.

| File / folder | Contents |
|---|---|
| `classes.csv` / `.xlsx` | Copy of the class table used. |
| `atlas_to_brain_initial.json` | Automatic assignments, before manual review. |
| `atlas_to_brain.json` | Final assignments after review. |
| `detection_manifest.csv` | Every source photograph, its crop name if accepted, or the rejection reason. |
| `image_coverage.csv` | Source photograph → crop → atlas level → included / excluded. |
| `run_status.json`, `run_summary.json` | Current stage, final counts, rejected photographs, unassigned crops. |
| `error.log` | Only if the run failed; `run_status.json` names the failed stage. Do not use incomplete runs. |
| `registration_parameters.json` | Per-slice transform, optimizer status and final mismatch cost. |
| `<specimen>/structure/`, `<specimen>/inflammation/` | Cropped structural and reporter images (*inflammation* is a historical name for the reporter channel). |
| `<specimen>/mask/` | Atlas region labels mapped into specimen coordinates. |
| `<specimen>/structure_registered/`, `inflammation_registered/` | Images transformed to atlas coordinates. |
| `brain_slice_data.csv` | One row per analysed slice: global statistics and per-region statistics (JSON column). |
| `brain_slice_data.json`, `.js` | Same measurements, for the dashboard. |
| `outlier_scatter_data.csv` | Mean and SD of slice medians per specimen and region. |
| `heatmap_diff_data.csv` | Disease − control regional differences by atlas level (when matching classes exist). |
| `median/`, `difference_heatmap/` | Class-median images and pairwise class differences. |

The dashboard is `Code/Brainlyser code/interface/index.html`; it opens at the
end of a run and always shows the **latest** run.

---

## Method

| Stage | Implementation |
|---|---|
| Detection | Custom one-class (`brain`) YOLO11n; confidence ≥ 0.75; input size 640; largest box kept. |
| Cropping | Fixed 1140 × 800 px window of the original photograph, centred on the detection. |
| Atlas assignment | DINOv2 ViT-S/14 with 4 register tokens; 224 × 224 input; L2-normalised 384-d CLS features; cosine similarity to the D55 reference; ordered global (Needleman–Wunsch-type) alignment, gap penalty 0; reference levels mapped to atlas levels. |
| Review | Manual editing in Brain Comparator. |
| Registration | Independent 2D similarity transform per slice (translation, rotation −5° to +5°, isotropic scale 0.85–1.30), minimising the mismatch of Otsu silhouettes with Powell's method. |
| Quantification | Mean, median, SD, min and max of reporter (red-channel) intensity in nine regions. |

Regions: 1 olfactory areas · 2 cerebral nuclei · 3 thalamus · 4 cerebellum ·
5 isocortex · 6 midbrain · 7 hypothalamus · 8 hippocampal formation ·
9 hindbrain.

---

## Limitations and interpretation

- Statistics **exclude pixels equal to zero**. A region with only zero pixels
  is reported as missing (`null`), not as zero signal.
- The global statistics cover the non-zero pixels of the crop, not only the
  brain mask.
- Values are fluorescence intensities, not cell counts. Crops are saved as
  JPEG; no radiometric calibration or between-experiment normalisation is
  applied.
- Rejected photographs are skipped and accepted crops renumbered
  consecutively; `detection_manifest.csv` keeps the original names. Do not
  infer physical spacing from crop numbers.
- Linear interpolation in the dashboard heatmaps is for display only.
- The atlas is a legacy derivative of Allen Institute mouse-brain resources;
  its exact upstream release, voxel spacing and conversion history are not
  recorded. No specific CCF version is claimed.
- D55 is both the reference specimen and part of the AD dataset.
- Detection, assignment and registration should be checked on your own
  imaging conditions; the included example is not an accuracy benchmark.

---

## Tests

From the repository root, with the environment activated:

```bash
python -m unittest discover -s tests -v    # unit / regression tests
python "Code/Brainlyser code/run_example.py"   # end-to-end example
python scripts/audit_outputs.py "Code/Brainlyser code/data/<run folder>"   # consistency check of a run
```

Additional scripts in `scripts/`: `validate_gui.py` (full GUI pipeline on the
example), `validate_ad_ct.py` (full AD dataset, needs the AD dataset ZIP),
`validate_macos_dialogs.py` (macOS file dialogs), `validate_dashboard.cjs`
(browser test; needs Node.js and Playwright). What was validated and how is
recorded in [docs/VALIDATION.md](docs/VALIDATION.md).

---

## Repository layout

```text
Brainlyser/
├── README.md                  this file
├── LICENSE                    GNU AGPL-3.0 (code)
├── THIRD_PARTY_NOTICES.md     third-party components and their terms
├── CITATION.cff               machine-readable citation
├── CHANGELOG.md
├── MODEL_CHECKSUMS.sha256     SHA-256 of the YOLO and DINOv2 weights
├── ASSETS_CHECKSUMS.sha256    SHA-256 of every file in Code/Brainlyser code/assets/
├── RUNTIME_PROVENANCE.json    provenance of models, atlas and reference
├── licenses/                  full licence texts; data licence
├── docs/                      datasets, validation record, tested environment
├── examples/                  3-image D55 example + expected outputs
├── tests/                     unit / regression tests
├── scripts/                   validation and audit scripts
└── Code/Brainlyser code/
    ├── index.py               application (GUI + pipeline)
    ├── yolo_processor.py      detection and cropping
    ├── dino_brains_alignment.py   DINOv2 atlas assignment
    ├── alignment_software.py  Brain Comparator (manual review)
    ├── brains_registration.py 2D registration
    ├── extract_stats.py       regional statistics and exports
    ├── visuals_generation.py  class medians and difference maps
    ├── run_example.py         command-line example
    ├── utils.py
    ├── environment.yml        Conda environment
    ├── Brainlyser.spec, .ico  PyInstaller starting point (no validated executable is distributed)
    ├── interface/             HTML dashboard (Plotly.js bundled)
    └── assets/                best.pt, dinov2_repo/, atlas/, 20230320 D55/, ui/
```

---

## Licences

Each component keeps its own licence. In short:

| Component | Licence |
|---|---|
| Brainlyser code, dashboard, documentation, YOLO detector `best.pt` | **GNU AGPL-3.0** ([LICENSE](LICENSE)) |
| Ultralytics YOLO (installed dependency) | AGPL-3.0 |
| DINOv2 code and weights (`assets/dinov2_repo/`) | Apache-2.0 ([licenses/Apache-2.0-DINOv2.txt](licenses/Apache-2.0-DINOv2.txt)) |
| Atlas images and masks (`assets/atlas/`) | Allen Institute [Terms of Use](https://alleninstitute.org/legal/terms-of-use) — research / non-commercial redistribution; commercial redistribution needs Allen's permission |
| D55 reference, example photographs, AD and JEV datasets | **CC BY 4.0** ([licenses/DATA-LICENSE.md](licenses/DATA-LICENSE.md)) |
| Plotly.js (bundled in the dashboard) | MIT ([licenses/MIT-Plotly.txt](licenses/MIT-Plotly.txt)) |
| Other Python dependencies | Their own licences; installed by Conda/pip, not redistributed here |

AGPL-3.0 allows use, modification and redistribution, including commercial
use, provided that source code of distributed or network-served modified
versions is made available under the same licence. Full details, attributions
and redistribution conditions: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

## How to cite

If you use Brainlyser, please cite:

1. **The FastHisto article** (reference to be completed upon publication).
2. **This software:** FastHisto project team. *Brainlyser: the FastHisto
   brain-image analysis software*, version 1.0.0 (2026). See
   [CITATION.cff](CITATION.cff); GitHub's "Cite this repository" button
   uses it.
3. **The datasets**, if you reuse them: FastHisto project team, *Brainlyser
   AD and JEV blockface datasets* (see [docs/DATASETS.md](docs/DATASETS.md)).

and the methods Brainlyser builds on:

- Jocher, G. & Qiu, J. *Ultralytics YOLO11* (2024). <https://docs.ultralytics.com/models/yolo11/>
- Oquab, M. et al. DINOv2: Learning Robust Visual Features without Supervision. *TMLR* (2024). <https://openreview.net/forum?id=a68SUt6zFt>
- Darcet, T. et al. Vision Transformers Need Registers. *ICLR* (2024). <https://openreview.net/forum?id=2dnO3LLiJ1>
- Allen Institute for Brain Science. Allen Brain Atlas resources. <https://brain-map.org/> — see the [citation policy](https://alleninstitute.org/legal/citation-policy).

---

## Troubleshooting and support

| Problem | Solution |
|---|---|
| `DINOv2 assets missing` or missing atlas / reference images | `Code/Brainlyser code/assets/` is incomplete (e.g. files moved, or a partial download). Clone or download the repository again and run `shasum -a 256 -c ASSETS_CHECKSUMS.sha256`. |
| Weight hash error | The DINOv2 weight file is incomplete or modified; download the repository again and verify it with `ASSETS_CHECKSUMS.sha256`. |
| `Specimen directories missing from the selected image folder` | The `Brain` names of the class table do not match the folder names exactly (check spaces), or the wrong parent folder was selected. |
| `Missing column(s)` | The class table needs the headers `Brain` and `Class` (case-sensitive). |
| No window appears / Tk error | Check Tk with `python -m tkinter`; run from a desktop session, not a headless server. |
| Warnings about xFormers | Expected on CPU; they do not affect results. |
| Run finished "with exclusions" | Some photographs had no detected brain or some crops no assignment; see `detection_manifest.csv` and `run_summary.json`. |

For help, open an issue on this repository with the Brainlyser version, your
operating system, the full error message, `run_status.json` / `error.log` of
the run, and the output of `conda list`.
