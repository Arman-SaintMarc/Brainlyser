# Datasets of the FastHisto paper

The raw photograph series analysed in the paper are too large for GitHub
(≈ 28 GB in total). They are distributed as two separate ZIP archives in the
data archive referenced by the paper. Neither is needed to install or test
Brainlyser; the 3-image example in `examples/` is enough for that.

| Archive | Size | Specimens | Photographs | Extracts to |
|---|---|---|---|---|
| `Brainlyser-dataset-AD.zip` | ≈ 18 GB | 39 | 4 257 | `Datasets/raw_data_AD/`, `Datasets/AD vs CT.csv` |
| `Brainlyser-dataset-JEV.zip` | ≈ 10 GB | 22 | 2 804 | `Datasets/raw data JEV/`, `Datasets/JEVvs CT.csv` |

Each archive also contains a copy of this file (`Datasets/README-AD.md` or
`Datasets/README-JEV.md`), the data licence (`Datasets/LICENSE-AD/`,
`Datasets/LICENSE-JEV/`) and the SHA-256 checksums of its images
(`Datasets/CHECKSUMS-AD.sha256`, `Datasets/CHECKSUMS-JEV.sha256`). File
names differ between the two archives, so both can be extracted into the same
folder without conflicts.

## Installation

Extract the archives into the **root of the Brainlyser repository** (the
folder containing `README.md` and `Code/`):

```bash
cd Brainlyser
unzip /path/to/Brainlyser-dataset-AD.zip
unzip /path/to/Brainlyser-dataset-JEV.zip
```

Result:

```text
Brainlyser/
└── Datasets/
    ├── AD vs CT.csv
    ├── JEVvs CT.csv
    ├── raw_data_AD/
    │   ├── 20230320 D45/   DSC02161.JPG …
    │   └── …               (39 specimen folders)
    └── raw data JEV/
        ├── H145/           DSC09273.JPG …
        └── …               (22 specimen folders)
```

Keep the folder and file names unchanged: the class tables refer to the
specimen folder names, and `scripts/validate_ad_ct.py` uses these paths.

To verify the extracted files (macOS / Linux), from `Brainlyser/`:

```bash
shasum -a 256 -c Datasets/CHECKSUMS-AD.sha256
shasum -a 256 -c Datasets/CHECKSUMS-JEV.sha256
```

## Running the analyses

Start `python index.py` from `Code/Brainlyser code/` and select:

| Dataset | Data Folder | Brain class (.csv/.xlsx) |
|---|---|---|
| AD | `Datasets/raw_data_AD/` | `Datasets/AD vs CT.csv` |
| JEV | `Datasets/raw data JEV/` | `Datasets/JEVvs CT.csv` |

Leave the optional fields empty, review the assignments of every specimen in
Brain Comparator, and close it to continue. See the main
[README](../README.md) for the outputs.

## Image format (both datasets)

- RGB JPEG photographs, 6000 × 4000 px, one blockface of the brain per
  photograph, taken during serial sectioning.
- One folder per specimen; the camera file names (`DSC#####.JPG`) give the
  acquisition order.
- Green channel (inverted by the software): structural signal. Red channel:
  reporter fluorescence.
- Images are the original camera files, not re-encoded.

## AD dataset — `raw_data_AD/`, `AD vs CT.csv`

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

## JEV dataset — `raw data JEV/`, `JEVvs CT.csv`

Mice infected with Japanese encephalitis virus (JEV) at three doses, and
uninfected controls.

| Class | Meaning | Specimens |
|---|---|---|
| `Group1-CTRL` | control | 5 |
| `Group 2` | JEV, 10⁴ pfu/mL | 5 |
| `Group 4` | JEV, 10⁶ pfu/mL | 6 |
| `Group 5` | JEV, 10⁷ pfu/mL | 6 |

Folder names are the specimen IDs (`H145`, …). Besides `Brain` and `Class`,
the table has informational columns ignored by the software: `Order`
(acquisition order), `Issues` (acquisition notes such as *Inverted*,
*Partial out of focus*, *Damaged brain*), `Date` (acquisition date,
DD/MM/YYYY) and a free-text notation of the group. Check the `Issues`
column before interpreting individual specimens.

The class names do not follow the `-F`/`-M` convention, so the dedicated
disease-vs-control heatmap is not produced; all other exports, class
medians and pairwise class difference images are.

## Licence and citation

The datasets are released by the FastHisto project team under
**CC BY 4.0** (see [licenses/DATA-LICENSE.md](../licenses/DATA-LICENSE.md)).
Please cite the FastHisto article and the data archive when reusing them.
Experimental procedures, animal-ethics approvals and acquisition settings are
described in the article.
