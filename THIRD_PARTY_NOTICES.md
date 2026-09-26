# Third-party notices and redistribution

Applies to Brainlyser 1.0.0 (source snapshot 2026.09.24) and its separately
distributed Alzheimer (AD) dataset archive. Each component retains its
own copyright and licence. A software licence does not relicense adjacent
research data.

## Brainlyser and Ultralytics YOLO

The original Brainlyser Python code, application interface, and documentation
are offered under GNU Affero General Public License version 3 (AGPL-3.0-only),
except where another licence is explicitly identified. The complete licence is
in [LICENSE](LICENSE). Copyright remains with the respective contributors.

`Code/Brainlyser code/assets/best.pt` is the supplied custom YOLO11n detector
for the `brain` class; the checkpoint identifies Ultralytics 8.3.153. It is
distributed under the AGPL-3.0 route described by Ultralytics. The environment
installs `ultralytics==8.3.153`; it does not bundle an installed Python runtime.

Preserve attribution and licence notices when sharing source or weights.
Redistributed modified covered software must meet AGPL requirements, including
corresponding source. Network deployment of modified covered software carries
the AGPL's source-access obligations. Nonprofit status does not remove these
conditions, and the AGPL itself does not prohibit commercial use.

Sources: [Ultralytics licensing](https://www.ultralytics.com/license),
[YOLO11](https://docs.ultralytics.com/models/yolo11/).

The detector is provided for inference. Its original annotated training dataset
and complete training procedure are not included, so this release does not claim
to reproduce detector training.

## DINOv2

Component: Meta's base DINOv2 ViT-S/14 with four register tokens.
Architecture entry point: `dinov2_vits14_reg`.
Weights: `dinov2_vits14_reg4_pretrain.pth`.
Repository base commit: `592541c8d842042bb5ab29a49433f73b544522d5`.

Copyright (c) Meta Platforms, Inc. and affiliates. Code and these base model
weights are Apache-2.0; the full text is in
[licenses/Apache-2.0-DINOv2.txt](licenses/Apache-2.0-DINOv2.txt) and in
`Code/Brainlyser code/assets/dinov2_repo/LICENSE`.

`assets/dinov2_repo/` is a **subset** of the upstream repository: only the
files needed to build and run `dinov2_vits14_reg` through `torch.hub` are
included (`hubconf.py`, `dinov2/__init__.py`, `dinov2/hub/`, `dinov2/layers/`,
`dinov2/models/`), together with the upstream `LICENSE` and `MODEL_CARD.md`
and the weights in `models/`. Training, evaluation, notebooks, documentation,
packaging files and the third-party CLIP tokenizer were removed; the included
files are unmodified apart from line endings (no semantic difference from the
recorded commit in a whitespace-insensitive comparison). The weights were
added separately from Meta's official download.

The Brainlyser loader uses this local implementation and verifies the weight
hash. This licence statement does not apply to other, newer DINO variants with
different terms.

Upstream: [DINOv2](https://github.com/facebookresearch/dinov2).
Cite Oquab et al. (2024) and Darcet et al. (2024), as linked in the README.

## Allen mouse-brain atlas

`assets/atlas/` contains 220 image levels in each of `structure/`, `mask/`,
`colored_mask/`, and `outline/`. These are derived Allen Institute brain
atlas resources. Attribution: **Allen Institute for Brain Science,
Allen Brain Atlas resources, https://brain-map.org/**.

Allen's terms permit research/noncommercial copying, redistribution, and
derivatives subject to their conditions, including citation and the provisions
on improvements. Commercial redistribution requires written permission.
These files and derivatives remain under Allen's terms; the project's AGPL and
D55 CC BY licence do not override them.

The exact original atlas release, source image identifiers, physical spacing,
and conversion pipeline are not recorded in the supplied assets. File hashes
identify this local derivative; they do not establish upstream provenance.
No specific CCF version or atlas-publication attribution is asserted.

Governing documents:
[Terms of Use](https://alleninstitute.org/legal/terms-of-use),
[Citation Policy](https://alleninstitute.org/legal/citation-policy).
Questions outside those terms may be addressed to `terms@alleninstitute.org`.

## FastHisto image data (D55 reference, example, AD dataset)

The D55 reference stack, the three example photographs, and the Alzheimer (AD)
dataset belong to the FastHisto project team and are distributed under
CC BY 4.0; the scope and attribution are in
[licenses/DATA-LICENSE.md](licenses/DATA-LICENSE.md). The AD dataset is not
part of the Git repository; it is distributed as a separate archive
(see [docs/DATASETS.md](docs/DATASETS.md)).

## Where each component is distributed

| Component | GitHub repository | AD dataset ZIP |
|---|---|---|
| Brainlyser code, dashboard, docs (AGPL-3.0) | yes | — |
| YOLO detector `best.pt` (AGPL-3.0) | yes | — |
| Plotly.js (MIT) | yes | — |
| DINOv2 code and weights (Apache-2.0) | yes | — |
| Allen-derived atlas (Allen terms) | yes | — |
| D55 reference stack (CC BY 4.0) | yes | — |
| D55 example photographs (CC BY 4.0) | yes | — |
| AD dataset (CC BY 4.0) | — | yes |

## Plotly, dashboard resources, and Python dependencies

The supplied `interface/js/plotly.js` identifies version 3.0.1 and carries the
Plotly copyright header. Its MIT licence is included at
[licenses/MIT-Plotly.txt](licenses/MIT-Plotly.txt). Preserve both that licence
and third-party notices embedded in the distributed JavaScript.

The dashboard links to Font Awesome Free 6.4.0 on cdnjs and Inter on Google
Fonts. Those remote files are not included in this distribution. Font Awesome
uses separate icon, font, and code licences; Inter uses SIL OFL. If you vendor
them for offline use, retain the applicable upstream notices.

Python, Tk, NumPy, SciPy, pandas, scikit-learn, matplotlib, Pillow, PyTorch,
torchvision, OpenCV, openpyxl, xlrd, and transitive dependencies retain their
respective licences. Conda/pip obtain them during installation. Redistributing
an installed environment or executable requires the notices for the exact
bundled builds, beyond the notices for this source-only distribution.
