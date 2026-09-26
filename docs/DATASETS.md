# Alzheimer (AD) dataset of the FastHisto paper

The raw photograph series analysed in the paper is too large for GitHub. It is
distributed as a single ZIP archive:

| File | Download | Size | Specimens | Photographs |
|---|---|---|---|---|
| `Dataset Alzheimer.zip` | <https://drive.proton.me/urls/WHDT0T9W84#4lpTiiRHADI6> | 18.6 GB | 39 | 4 257 |

The dataset is not needed to install or test Brainlyser; the 3-image example
in `examples/` is enough for that.

To check the download (macOS / Linux):

```bash
shasum -a 256 "Dataset Alzheimer.zip"
```

Expected SHA-256: `09540532ed5e49d4348ce053da9f08f420abffbb219be4ac531f9f57f8bdfaa5`

## Installation

The archive contains the class table and the image folder at its root:

```text
Dataset Alzheimer.zip
├── AD vs CT.csv
└── raw_data_AD/
    ├── 20230320 D45/   DSC02161.JPG …
    └── …               (39 specimen folders)
```

It also contains macOS metadata (`__MACOSX/`, `.DS_Store`) and Windows
thumbnail files (`Thumbs.db`); they are not needed and are ignored by
Brainlyser.

Extract it into a `Datasets/` folder at the **root of the Brainlyser
repository** (the folder containing `README.md` and `Code/`):

```bash
cd Brainlyser
mkdir -p Datasets
unzip "/path/to/Dataset Alzheimer.zip" -d Datasets -x "__MACOSX/*"
```

Result:

```text
Brainlyser/
└── Datasets/
    ├── AD vs CT.csv
    └── raw_data_AD/
        ├── 20230320 D45/
        └── …
```

With a graphical unzip tool, extract the archive, create `Brainlyser/Datasets/`
and move `AD vs CT.csv` and `raw_data_AD/` into it.

Keep the folder and file names unchanged: the class table refers to the
specimen folder names, and `scripts/validate_ad_ct.py` uses these paths. For
analyses through the graphical interface only, the dataset can be extracted
anywhere.

## Running the analysis

Start `python index.py` from `Code/Brainlyser code/` and select:

| Field | Selection |
|---|---|
| Data Folder | `Datasets/raw_data_AD/` |
| Brain class (.csv/.xlsx) | `Datasets/AD vs CT.csv` |

Leave the optional fields empty, review the assignments of every specimen in
Brain Comparator, and close it to continue. See the main
[README](../README.md) for the outputs.

A non-interactive run (automatic assignments, no manual review), for software
verification only:

```bash
python scripts/validate_ad_ct.py        # from the repository root
```

## Image format

- RGB JPEG photographs, 6000 × 4000 px, one blockface of the brain per
  photograph, taken during serial sectioning.
- One folder per specimen; the camera file names (`DSC#####.JPG`) give the
  acquisition order.
- Green channel (inverted by the software): structural signal. Red channel:
  reporter fluorescence.
- Images are the original camera files, not re-encoded.

## Specimens and classes

Alzheimer's-disease model mice and controls, both sexes.

| Class | Meaning | Specimens |
|---|---|---|
| `AD-F` | AD model, female | 11 |
| `AD-M` | AD model, male | 12 |
| `CT-F` | control, female | 11 |
| `CT-M` | control, male | 5 |

Folder names are `<acquisition date YYYYMMDD> <specimen ID>`, e.g.
`20230320 D55`. The class table has the two columns `Brain`, `Class`.
Because the classes follow the `<disease>-F/-M` and `CT-F/-M` convention, the
dashboard's disease-vs-control heatmap is produced for this dataset.

Specimen `20230320 D55` is also the reference stack used for atlas
assignment (`Code/Brainlyser code/assets/20230320 D55/`); results for this
specimen are therefore not independent of the reference.

## Licence and citation

The dataset is released by the FastHisto project team under **CC BY 4.0**
(see [licenses/DATA-LICENSE.md](../licenses/DATA-LICENSE.md)). Please cite
the FastHisto article when reusing it. Experimental procedures, animal-ethics
approvals and acquisition settings are described in the article.
