# Changelog

## 1.0.0 — 2026-09-25 (first public release)

- Code identical to source snapshot 2026.09.24 below.
- The GitHub repository contains the complete software, including the YOLO
  detector, DINOv2 code and weights, atlas and D55 reference; the AD and JEV
  datasets are distributed as two separate archives. Added
  `ASSETS_CHECKSUMS.sha256`.
- Reduced the bundled DINOv2 repository to the files needed to load the
  ViT-S/14-reg4 backbone (175 → 26 files).
- Rewrote the README (installation, example, paper datasets, outputs,
  method, licences, citation, troubleshooting); added `docs/DATASETS.md`;
  extended the CC BY 4.0 data licence to the AD and JEV datasets; updated
  third-party notices and `CITATION.cff`.

## Source snapshot 2026.09.24

- Fixed macOS native CSV/Excel file chooser crashes and tested real Cocoa panels.
- Bounded YOLO/DINO memory and streamed class medians/difference images.
- Resolved assets independently of the working/output directory.
- Restricted processing to specimens in the class table; reject invalid tables,
  missing assigned images, and write failures with explicit errors.
- Added source-image traceability, run/exclusion summaries, initial assignments,
  and saved registration parameters and optimizer status.
- Fixed macOS scrolling and comparator widget/cache accumulation when switching
  specimens; corrected upward minimal-shift assignment editing.
- Resized the desktop window to show all controls and protected against concurrent runs.
- Fixed dashboard atlas level 220, initial image paths, difference outlines,
  and empty-data displays.
- Added native-dialog, GUI AD/CT, output-integrity, numerical, and browser tests.

## Source snapshot 2026.09.08

- Standardized the software name to Brainlyser.
- Supplied installation, example, method, and redistribution documentation.
- Added AGPL-3.0 software licensing, D55 data licensing, third-party notices,
  provenance, and distribution checksums.
- Loaded the bundled DINOv2 implementation and verified local weights instead
  of retrieving a changing upstream implementation during analysis.
- Bounded heatmap export to the supplied atlas levels 1–220, including 220.
- Updated placeholder text rendering for current Pillow versions and bound
  Ctrl-click to assignment deletion on macOS.
- Scheduled the manual comparator on the Tk main thread for macOS compatibility.

The existing Windows executable predates these source changes. It is not
included in this source release and has not been rebuilt or verified against it.
