import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, font as tkfont, filedialog, messagebox
from PIL import Image, ImageTk
import pandas as pd
import shutil
import json
import logging
import re
import csv
import traceback
from functools import wraps

TABLE_FILETYPES = [("CSV / Excel", ("*.csv", "*.xlsx", "*.xls")), ("All files", "*")]
is_processing = False

# ──────────────────────────────────────────────────────────────────────────────
#  Domain‑specific processors (unchanged)
# ──────────────────────────────────────────────────────────────────────────────
from yolo_processor import main as process_all_brains
from dino_brains_alignment import main as align_all_brains
from brains_registration import main as register_all_brains
from extract_stats import main as extract_stats
from visuals_generation import main as generate_visuals
import utils
from alignment_software import run_brain_comparator

# ──────────────────────────────────────────────────────────────────────────────
#  Paths & global state
# ──────────────────────────────────────────────────────────────────────────────

def get_executable_path() -> Path:
    """Return the path to the running executable or script."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return Path(__file__).resolve()

EXE_PATH = get_executable_path()
BASE_DIR = EXE_PATH.parent
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
INTERFACE_DIR = os.path.join(BASE_DIR, "interface")
UI_ASSETS_DIR = os.path.join(ASSETS_DIR, "ui")
D55_PARENT_DIR = os.path.join(ASSETS_DIR, "20230320 D55")
D55_STRUCTURE_DIR = os.path.join(D55_PARENT_DIR, "structure")

# ──────────────────────────────────────────────────────────────────────────────
#  UI colour palette
# ──────────────────────────────────────────────────────────────────────────────
LIGHT_BG_COLOR       = "#F8FAFC"
FRAME_BG_COLOR       = "#FFFFFF"
PRIMARY_COLOR        = "#2563EB"
PRIMARY_HOVER        = "#1D4ED8"
PRIMARY_ACTIVE       = "#1E40AF"
DARK_FG_COLOR        = "#0F172A"
MEDIUM_FG_COLOR      = "#475569"
PLACEHOLDER_FG_COLOR = "#94A3B8"
PROGRESS_BAR_COLOR   = PRIMARY_COLOR

# ──────────────────────────────────────────────────────────────────────────────
#  Global input paths (required & optional)
# ──────────────────────────────────────────────────────────────────────────────
brain_to_class: dict[str, str] = {}
ref_to_atlas = {}

# Required
mapping_file_path: str | None = None  # Atlas → Reference-brain CSV/XLSX

# Optional
assignments_file_path: str | None = None  # atlas_to_brain.json
extra_csv_path: str | None = None        # any additional CSV/XLSX (optional)
extra_folder_path: str | None = None     # any additional folder (optional)

# REF⇄ATLAS mapping created from optional CSV/XLSX
REF_ATLAS_PAIRS: list[tuple[int, int]] | None = None
ATLAS_TO_REF: dict[int, int] | None = None
REF_TO_ATLAS: dict[int, int] | None = None

progress_bar = None  # set in main_ui()


# ──────────────────────────────────────────────────────────────────────────────
#  Helper – timestamped output directory
# ──────────────────────────────────────────────────────────────────────────────

def create_processed_data_dir(base_path: str | Path = "data") -> Path:
    base_path = Path(base_path)
    base_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out_dir = base_path / f"processed_data_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    return out_dir

# ──────────────────────────────────────────────────────────────────────────────
#  CSV loader – REF↔ATLAS pairs
# ──────────────────────────────────────────────────────────────────────────────

def load_ref_atlas_pairs(path: str | Path) -> None:
    """Populate REF_ATLAS_PAIRS, ATLAS_TO_REF, REF_TO_ATLAS global vars."""
    global REF_ATLAS_PAIRS, ATLAS_TO_REF, REF_TO_ATLAS

    df = pd.read_csv(path) if Path(path).suffix.lower() == ".csv" else pd.read_excel(path)
    required_cols = {"REF", "ATLAS"}
    if not required_cols.issubset(df.columns):
        raise KeyError(f"CSV/XLSX must have columns: {', '.join(required_cols)}")

    if df.empty or df[["REF", "ATLAS"]].isna().any().any():
        raise ValueError("The reference table must contain nonempty integer REF and ATLAS values.")
    for column in ("REF", "ATLAS"):
        values = pd.to_numeric(df[column], errors="raise")
        if (values % 1 != 0).any() or values.duplicated().any():
            raise ValueError(f"{column} values must be distinct integers.")
        if column == "ATLAS" and not values.between(1, 220).all():
            raise ValueError("ATLAS levels must be between 1 and 220.")
        if column == "REF" and (values < 0).any():
            raise ValueError("REF values cannot be negative.")
    REF_ATLAS_PAIRS = [(int(r), int(a)) for r, a in zip(df["REF"], df["ATLAS"])]
    ATLAS_TO_REF = {a: d for d, a in REF_ATLAS_PAIRS}
    REF_TO_ATLAS = {d: a for d, a in REF_ATLAS_PAIRS}

# ──────────────────────────────────────────────────────────────────────────────
#  Core pipeline
# ──────────────────────────────────────────────────────────────────────────────

def validate_assignments(assignments, output_dir, classes):
    if not isinstance(assignments, dict) or not any(assignments.values()):
        raise ValueError("No usable atlas assignments were produced.")
    for brain, slices in assignments.items():
        if brain not in classes or not isinstance(slices, dict):
            raise ValueError(f"Assignment specimen missing from class table, or invalid mapping: {brain}")
        for query, atlas in slices.items():
            if not isinstance(query, str) or not re.fullmatch(r"slice\d{4}\.jpg", query):
                raise ValueError(f"Invalid crop filename in assignments: {query}")
            if not isinstance(atlas, str) or not re.fullmatch(r"slice\d{4}\.jpg", atlas):
                raise ValueError(f"Invalid atlas filename in assignments: {atlas}")
            for required in (output_dir / brain / "structure" / query, BASE_DIR / "assets/atlas/structure" / atlas):
                if not required.is_file():
                    raise ValueError(f"Assignment references a missing image: {required}")


def _record_failure(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        state = {}
        try:
            return function(*args, _run_state=state, **kwargs)
        except Exception as exc:
            output = state.get("output")
            if output is not None:
                status_file = output / "run_status.json"
                status = json.loads(status_file.read_text()) if status_file.exists() else {}
                status.update({"failed_stage": status.get("stage"), "stage": "Failed", "error": str(exc)})
                try:
                    status_file.write_text(json.dumps(status, indent=2))
                    (output / "error.log").write_text(traceback.format_exc())
                except OSError:
                    logging.exception("Unable to write the failure report")
            raise
    return guarded


@_record_failure
def run_pipeline(
    raw_data_dir: str | Path,
    mapping_file: str | Path,
    assignment_file: str | Path | None = None,
    *,
    extra_csv: str | Path | None = None,
    extra_folder: str | Path | None = None,
    review: bool = True,
    open_browser: bool = True,
    progress=None,
    _run_state=None,
) -> Path:
    """Run full Brainlyser workflow and return output directory."""

    raw_data_dir = Path(raw_data_dir).resolve()
    mapping_file = Path(mapping_file)
    classes = load_mapping_file(mapping_file)
    if not raw_data_dir.is_dir():
        raise ValueError(f"Image directory does not exist: {raw_data_dir}")
    missing = [brain for brain in classes if not (raw_data_dir / brain).is_dir()]
    if missing:
        raise ValueError(f"Specimen directories missing from the selected image folder: {', '.join(missing)}")
    if bool(extra_folder) != bool(extra_csv):
        raise ValueError("Provide both the custom reference folder and its REF/ATLAS table.")
    if assignment_file and not Path(assignment_file).is_file():
        raise ValueError(f"Assignment file not found: {assignment_file}")

    if extra_csv:
        load_ref_atlas_pairs(extra_csv)
    ref_atlas_pairs_local = REF_ATLAS_PAIRS if extra_csv else None

    output_dir = create_processed_data_dir(BASE_DIR / "data")
    if _run_state is not None:
        _run_state["output"] = output_dir
    shutil.copy2(mapping_file, output_dir / ("classes" + mapping_file.suffix.lower()))
    def report(stage):
        logging.info("%s: %s", output_dir.name, stage)
        (output_dir / "run_status.json").write_text(json.dumps({"stage": stage, "raw_data_dir": str(raw_data_dir), "specimens": len(classes)}, indent=2))
        if progress:
            progress(stage)

    # 1 — Detection / cropping
    report("Detection and cropping")
    processed, failed = process_all_brains(raw_data_dir, output_dir, specimen_names=classes)
    if not processed:
        raise ValueError("No valid brain crops were detected. See detection_manifest.csv in the output directory.")

    # 2 — Alignment
    if assignment_file is None:
        report("DINOv2 assignment")
        assignment_file = align_all_brains(
            output_dir,
            ref_dir=Path(extra_folder) if extra_folder else None,
            ref_atlas_pairs=ref_atlas_pairs_local,
        )
    else:
        assignment_copy = output_dir / "atlas_to_brain.json"
        shutil.copy2(Path(assignment_file), assignment_copy)
        assignment_file = assignment_copy
    assignments = json.loads(Path(assignment_file).read_text())
    validate_assignments(assignments, output_dir, classes)
    shutil.copy2(assignment_file, output_dir / "atlas_to_brain_initial.json")

    # Tk windows must be constructed on the main thread (especially on macOS).
    review_done = threading.Event()
    review_errors = []

    def review_assignments():
        try:
            run_brain_comparator(
                root, assignment_file, output_dir, D55_STRUCTURE_DIR,
                extra_csv=extra_csv, extra_folder=extra_folder,
            )
        except Exception as exc:
            review_errors.append(exc)
        finally:
            review_done.set()

    if not review:
        review_done.set()
    elif threading.current_thread() is threading.main_thread():
        review_assignments()
    else:
        root.after(0, review_assignments)
        review_done.wait()
    if review_errors:
        raise review_errors[0]
    assignments = json.loads(Path(assignment_file).read_text())
    validate_assignments(assignments, output_dir, classes)

    # 4 — Registration → stats → visuals
    report("Registration")
    register_all_brains(output_dir, assignment_file)
    report("Regional quantification")
    extract_stats(output_dir, classes, assignment_file)
    report("Class medians and difference maps")
    generate_visuals(output_dir, classes, assignment_file)
    quantified = json.loads((output_dir / "brain_slice_data.json").read_text())
    analyzed = {name: len(rows[0]["images"]) for item in quantified for name, rows in item.items()}
    summary = {"specimens_requested": len(classes), "specimens_quantified": len(analyzed),
               "crops_detected": processed, "photos_rejected": failed,
               "slices_assigned": sum(map(len, assignments.values())),
               "unassigned_crops": processed - sum(map(len, assignments.values())),
               "slices_quantified": sum(analyzed.values()),
               "specimens_without_measurements": sorted(set(classes) - set(analyzed)),
               "manual_review_opened": review}
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2))
    with (output_dir / "detection_manifest.csv").open() as source, (output_dir / "image_coverage.csv").open("w", newline="") as dest:
        writer = csv.DictWriter(dest, fieldnames=["brain", "source_image", "crop_image", "atlas_image", "outcome"])
        writer.writeheader()
        for row in csv.DictReader(source):
            atlas = assignments.get(row["brain"], {}).get(row["crop_image"], "")
            writer.writerow({"brain": row["brain"], "source_image": row["source_image"], "crop_image": row["crop_image"],
                             "atlas_image": atlas, "outcome": "quantified" if atlas else
                             "unassigned_crop" if row["status"] == "processed" else row["status"]})

    # 5 — Persist optional artefacts
    if extra_csv:
        shutil.copy2(extra_csv, output_dir / Path(extra_csv).name)
    if extra_folder:
        shutil.copytree(extra_folder, output_dir / "extra_folder", dirs_exist_ok=True)

    # 6 — Update web interface
    INTERFACE_DIR = Path(BASE_DIR) / "interface"     # Path object
    last_js       = INTERFACE_DIR / "js" / "last_path.js"        # ← str / str → TypeError
    rel = os.path.relpath(output_dir, last_js.parent).replace(os.sep, "/")
    if rel.startswith("../"):
        rel = rel[3:]
    last_js.write_text(f'const lastPath = "{rel}";\n', encoding="utf-8")

    report("Complete")
    if open_browser:
        utils.open_interface_in_browser(INTERFACE_DIR)
    return output_dir

# ──────────────────────────────────────────────────────────────────────────────
#  Background worker and UI‑thread callbacks
# ──────────────────────────────────────────────────────────────────────────────

def _process_in_background(raw_dir, mapping_file, assignments_file, extra_csv, extra_folder):
    try:
        out_dir = run_pipeline(
            raw_dir,
            mapping_file,
            assignments_file,
            extra_csv=extra_csv,
            extra_folder=extra_folder,
            progress=lambda stage: root.after(0, lambda: status_label.config(text=stage)),
        )
        root.after(0, _on_success, out_dir)
    except Exception as exc:
        logging.exception("Brainlyser pipeline failed")
        root.after(0, _on_error, exc)


def _on_success(out_dir):
    global is_processing
    is_processing = False
    status_label.config(text=f"Done! Output at {out_dir}")
    summary_file = out_dir / "run_summary.json"
    if summary_file.is_file():
        summary = json.loads(summary_file.read_text())
        status_label.config(text=f"Done: {summary['specimens_quantified']} specimens, {summary['slices_quantified']} slices. Results: {out_dir.name}")
        if summary["photos_rejected"] or summary["unassigned_crops"] or summary["specimens_without_measurements"]:
            messagebox.showwarning("Analysis completed with exclusions",
                f"Rejected photographs: {summary['photos_rejected']}\n"
                f"Crops without an atlas assignment: {summary['unassigned_crops']}\n"
                f"Specimens without measurements: {summary['specimens_without_measurements']}\n\n"
                "See detection_manifest.csv and run_summary.json in the output directory.")
    progress_bar.stop()
    progress_bar["value"] = 0
    update_start_button_state()


def _on_error(exc):
    global is_processing
    is_processing = False
    status_label.config(text="Error during processing")
    progress_bar.stop()
    progress_bar["value"] = 0
    messagebox.showerror("Error", str(exc))
    update_start_button_state()

# ──────────────────────────────────────────────────────────────────────────────
#  Icon loader (unchanged)
# ──────────────────────────────────────────────────────────────────────────────

def load_icons():
    global file_icon, folder_icon, start_icon
    folder_img = Image.open(os.path.join(UI_ASSETS_DIR, "folder-open.png")).resize((16, 16), Image.Resampling.LANCZOS)
    file_img   = Image.open(os.path.join(UI_ASSETS_DIR, "file-text.png")).resize((16, 16), Image.Resampling.LANCZOS)
    start_img  = Image.open(os.path.join(UI_ASSETS_DIR, "play-circle.png")).resize((16, 16), Image.Resampling.LANCZOS)
    folder_icon = ImageTk.PhotoImage(folder_img)
    file_icon   = ImageTk.PhotoImage(file_img)
    start_icon  = ImageTk.PhotoImage(start_img)

# ──────────────────────────────────────────────────────────────────────────────
#  File‑selection helpers
# ──────────────────────────────────────────────────────────────────────────────

def select_raw_folder():
    if is_processing:
        return
    folder = filedialog.askdirectory(title="Select Data Folder")
    if folder:
        raw_folder_display_label.config(text=folder)
    update_start_button_state()


def load_mapping_file(path: str | Path) -> dict[str, str]:
    """Return a dict mapping the 'Brain' column to the 'Class' column."""
    ext = Path(path).suffix.lower()
    if ext in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    elif ext == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported file type: {ext!r}")

    expected = {"Brain", "Class"}
    if not expected.issubset(df.columns):
        raise KeyError(f"Missing column(s): {', '.join(expected - set(df.columns))}")

    if df.empty or df[["Brain", "Class"]].isna().any().any():
        raise ValueError("The class table must contain nonempty Brain and Class values.")
    for col in ("Brain", "Class"):
        df[col] = df[col].astype(str).str.strip()
        if df[col].eq("").any() or df[col].str.contains(r"[/\\]").any() or df[col].isin([".", ".."]).any():
            raise ValueError(f"Invalid {col}: use a nonempty name without path separators.")
    if df["Brain"].duplicated().any():
        raise ValueError("Each specimen must occur only once in the class table.")
    return dict(zip(df["Brain"], df["Class"]))


def select_mapping_file():
    global mapping_file_path, brain_to_class
    if is_processing:
        return
    initial_dir = os.path.dirname(mapping_file_path) if mapping_file_path else BASE_DIR
    filepath = filedialog.askopenfilename(
        parent=root,
        title="Select brain class table (CSV or Excel)",
        initialdir=initial_dir,
        filetypes=TABLE_FILETYPES,
    )
    if not filepath:
        return

    mapping_file_path = filepath
    mapping_file_display_label.config(text=os.path.basename(filepath))
    try:
        brain_to_class.clear()
        brain_to_class.update(load_mapping_file(filepath))
    except Exception as e:
        messagebox.showerror("Error loading mapping file", f"{filepath}\n\n{e}")
        mapping_file_path = None
        mapping_file_display_label.config(text="(No file selected)")
    update_start_button_state()


def select_assignments_file():
    global assignments_file_path
    if is_processing:
        return
    initial_dir = os.path.dirname(assignments_file_path) if assignments_file_path else BASE_DIR
    filepath = filedialog.askopenfilename(
        title="Select atlas_to_brain.json (Optional)",
        initialdir=initial_dir,
        parent=root,
        filetypes=[("JSON", "*.json"), ("All files", "*")],
    )
    if filepath:
        assignments_file_path = filepath
        assignments_file_display_label.config(text=os.path.basename(filepath))


def select_extra_csv_file() -> None:
    global extra_csv_path
    if is_processing:
        return

    initial_dir = os.path.dirname(extra_csv_path) if extra_csv_path else BASE_DIR

    filepath = filedialog.askopenfilename(
        title="Select REF→ATLAS CSV/XLSX (Optional)",
        initialdir=initial_dir,
        parent=root,
        filetypes=TABLE_FILETYPES,
    )

    if not filepath:
        return

    try:
        load_ref_atlas_pairs(filepath)
    except Exception as e:
        messagebox.showerror(
            "Invalid mapping file",
            f"Could not load REF→ATLAS pairs:\n{filepath}\n\n{e}"
        )
        return

    extra_csv_path = filepath
    extra_csv_display_label.config(text=os.path.basename(filepath))




def select_extra_folder():
    """Optional: select any additional folder."""
    global extra_folder_path
    if is_processing:
        return
    folder = filedialog.askdirectory(title="Select Additional Folder (Optional)")
    if folder:
        extra_folder_path = folder
        extra_folder_display_label.config(text=folder)

# ──────────────────────────────────────────────────────────────────────────────
#  UI‑state helpers
# ──────────────────────────────────────────────────────────────────────────────

def update_start_button_state():
    ready = (
        not is_processing and raw_folder_display_label.cget("text") != "(No folder selected)" and
        mapping_file_display_label.cget("text") != "(No file selected)"
    )
    start_button.config(state=tk.NORMAL if ready else tk.DISABLED)


def start_processing():
    global is_processing
    if is_processing:
        return
    is_processing = True
    raw_dir = raw_folder_display_label.cget("text")
    start_button.config(state=tk.DISABLED)
    status_label.config(text="Processing…")
    progress_bar.start(8)
    root.update_idletasks()

    thread = threading.Thread(
        target=_process_in_background,
        args=(
            raw_dir,
            mapping_file_path,
            assignments_file_path,
            extra_csv_path,
            extra_folder_path,
        ),
        daemon=True,
    )
    thread.start()

# ──────────────────────────────────────────────────────────────────────────────
#  Minimalist GUI
# ──────────────────────────────────────────────────────────────────────────────

def main_ui():
    global root, raw_folder_display_label, mapping_file_display_label
    global assignments_file_display_label, extra_csv_display_label, extra_folder_display_label
    global start_button, status_label, progress_bar

    root = tk.Tk()
    root.title("Brainlyser")
    root.geometry("820x650")
    root.configure(bg=LIGHT_BG_COLOR)
    root.resizable(True, True)
    root.minsize(780, 620)
    def close_window():
        if is_processing and not messagebox.askyesno(
            "Stop Brainlyser?", "An analysis is running. Closing Brainlyser stops it and leaves an incomplete output directory. Stop now?",
            parent=root):
            return
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", close_window)

    load_icons()

    # ── fonts ────────────────────────────────────────────────────────────
    base_family = (
        "Segoe UI" if "Segoe UI" in tkfont.families() else tkfont.nametofont("TkDefaultFont").actual()["family"]
    )
    default_font = tkfont.nametofont("TkDefaultFont")
    default_font.configure(family=base_family, size=10)

    title_font    = tkfont.Font(family=base_family, size=16, weight="bold")
    subtitle_font = tkfont.Font(family=base_family, size=10)
    label_font    = tkfont.Font(family=base_family, size=9, weight="bold")
    button_font   = tkfont.Font(family=base_family, size=9, weight="bold")
    path_font     = tkfont.Font(family=base_family, size=9)
    status_font   = tkfont.Font(family=base_family, size=9)

    # ── ttk styling (same as before, minor tweaks) ───────────────────────
    style = ttk.Style()
    style.theme_use("clam")

    style.configure(".", background=LIGHT_BG_COLOR, foreground=DARK_FG_COLOR, font=default_font)
    style.configure("TFrame", background=LIGHT_BG_COLOR)
    style.configure("Input.TFrame", background=FRAME_BG_COLOR, padding=(12, 10))
    style.configure("Title.TLabel", background=LIGHT_BG_COLOR, foreground=DARK_FG_COLOR, font=title_font, padding=(0, 0, 0, 6))
    style.configure("Subtitle.TLabel", background=LIGHT_BG_COLOR, foreground=MEDIUM_FG_COLOR, font=subtitle_font, padding=(0, 0, 0, 18))
    style.configure("TLabel", background=FRAME_BG_COLOR, foreground=MEDIUM_FG_COLOR, font=label_font)
    style.configure("PathDisplay.TLabel", background=FRAME_BG_COLOR, foreground=PLACEHOLDER_FG_COLOR, font=path_font, padding=(10, 6), anchor=tk.W)
    style.configure("Flat.TButton", font=button_font, padding=(14, 8), background=PRIMARY_COLOR, foreground="#FFFFFF", relief=tk.FLAT, borderwidth=0)
    style.map("Flat.TButton", background=[("active", PRIMARY_HOVER), ("pressed", PRIMARY_ACTIVE)], foreground=[("disabled", "#FFFFFF")])
    style.configure("Ghost.TButton", font=button_font, padding=(10, 7), background=FRAME_BG_COLOR, foreground=PRIMARY_COLOR, relief=tk.FLAT, borderwidth=0)
    style.map("Ghost.TButton", foreground=[("active", PRIMARY_HOVER), ("pressed", PRIMARY_ACTIVE)])
    style.configure("Primary.Horizontal.TProgressbar", troughcolor=FRAME_BG_COLOR, background=PRIMARY_COLOR, thickness=6, borderwidth=0, relief=tk.FLAT)

    # ── layout containers ────────────────────────────────────────────────
    outer = tk.Frame(root, bg=LIGHT_BG_COLOR, highlightthickness=0)
    outer.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

    main = ttk.Frame(outer)
    main.pack(expand=True, fill=tk.BOTH)
    for r in range(2, 10):
        main.rowconfigure(r, pad=8)
    main.columnconfigure(1, weight=1)

    # ── title / subtitle ─────────────────────────────────────────────────
    ttk.Label(main, text="Brainlyser", style="Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="ew")
    ttk.Label(main, text="Select required inputs, then add any optional artefacts.", style="Subtitle.TLabel").grid(row=1, column=0, columnspan=3, sticky="ew")

    # ── REQUIRED INPUTS ──────────────────────────────────────────────────
    df_frame = ttk.Frame(main, style="Input.TFrame")
    df_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
    df_frame.columnconfigure(1, weight=1)

    ttk.Label(df_frame, text="Data Folder*:", background=FRAME_BG_COLOR, font=label_font).grid(row=0, column=0, padx=(0, 12))
    raw_folder_display_label = ttk.Label(df_frame, text="(No folder selected)", style="PathDisplay.TLabel")
    raw_folder_display_label.grid(row=0, column=1, sticky="ew")
    ttk.Button(df_frame, text="Browse", image=folder_icon, compound=tk.LEFT, style="Ghost.TButton", command=select_raw_folder).grid(row=0, column=2, padx=(12, 0))

    mf_frame = ttk.Frame(main, style="Input.TFrame")
    mf_frame.grid(row=3, column=0, columnspan=3, sticky="ew")
    mf_frame.columnconfigure(1, weight=1)

    ttk.Label(mf_frame, text="Brain class (.csv/.xlsx)*:", background=FRAME_BG_COLOR, font=label_font).grid(row=0, column=0, padx=(0, 12))
    mapping_file_display_label = ttk.Label(mf_frame, text="(No file selected)", style="PathDisplay.TLabel")
    mapping_file_display_label.grid(row=0, column=1, sticky="ew")
    ttk.Button(mf_frame, text="Browse", image=file_icon, compound=tk.LEFT, style="Ghost.TButton", command=select_mapping_file).grid(row=0, column=2, padx=(12, 0))

    # ── OPTIONAL INPUTS ─────────────────────────────────────────────────
    opt_label = ttk.Label(main, text="Optional Inputs", style="Subtitle.TLabel")
    opt_label.grid(row=4, column=0, columnspan=3, sticky="w", pady=(12, 0))

    af_frame = ttk.Frame(main, style="Input.TFrame")
    af_frame.grid(row=5, column=0, columnspan=3, sticky="ew")
    af_frame.columnconfigure(1, weight=1)
    ttk.Label(af_frame, text="atlas_to_brain.json:", background=FRAME_BG_COLOR, font=label_font).grid(row=0, column=0, padx=(0, 12))
    assignments_file_display_label = ttk.Label(af_frame, text="(No file selected)", style="PathDisplay.TLabel")
    assignments_file_display_label.grid(row=0, column=1, sticky="ew")
    ttk.Button(af_frame, text="Browse", image=file_icon, compound=tk.LEFT, style="Ghost.TButton", command=select_assignments_file).grid(row=0, column=2, padx=(12, 0))

    ec_frame = ttk.Frame(main, style="Input.TFrame")
    ec_frame.grid(row=6, column=0, columnspan=3, sticky="ew")
    ec_frame.columnconfigure(1, weight=1)
    ttk.Label(ec_frame, text="Custom REF->ATLAS CSV/XLSX:", background=FRAME_BG_COLOR, font=label_font).grid(row=0, column=0, padx=(0, 12))
    extra_csv_display_label = ttk.Label(ec_frame, text="(No file selected)", style="PathDisplay.TLabel")
    extra_csv_display_label.grid(row=0, column=1, sticky="ew")
    ttk.Button(ec_frame, text="Browse", image=file_icon, compound=tk.LEFT, style="Ghost.TButton", command=select_extra_csv_file).grid(row=0, column=2, padx=(12, 0))

    ef_frame = ttk.Frame(main, style="Input.TFrame")
    ef_frame.grid(row=7, column=0, columnspan=3, sticky="ew")
    ef_frame.columnconfigure(1, weight=1)
    ttk.Label(ef_frame, text="Custom REF Folder:", background=FRAME_BG_COLOR, font=label_font).grid(row=0, column=0, padx=(0, 12))
    extra_folder_display_label = ttk.Label(ef_frame, text="(No folder selected)", style="PathDisplay.TLabel")
    extra_folder_display_label.grid(row=0, column=1, sticky="ew")
    ttk.Button(ef_frame, text="Browse", image=folder_icon, compound=tk.LEFT, style="Ghost.TButton", command=select_extra_folder).grid(row=0, column=2, padx=(12, 0))

    # ── START / STATUS / PROGRESS ───────────────────────────────────────
    start_button = ttk.Button(main, text="Start Processing Pipeline", image=start_icon, compound=tk.LEFT, style="Flat.TButton", state=tk.DISABLED, command=start_processing)
    start_button.grid(row=8, column=0, columnspan=3, pady=(20, 12))

    progress_bar = ttk.Progressbar(main, orient="horizontal", length=500, mode="indeterminate", style="Primary.Horizontal.TProgressbar")
    progress_bar.grid(row=9, column=0, columnspan=3, sticky="ew")

    status_label = ttk.Label(main, text="Select required inputs and click Start.", background=LIGHT_BG_COLOR, foreground=MEDIUM_FG_COLOR, font=status_font, wraplength=740)
    status_label.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(6, 0))

    root.mainloop()

# ──────────────────────────────────────────────────────────────────────────────
#  Entrypoint
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main_ui()
