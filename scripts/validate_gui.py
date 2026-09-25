"""Exercise the GUI pipeline on the example, accepting automatic assignments."""
import os
import sys
import tkinter as tk
import tempfile
import csv
import json
import copy
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Code/Brainlyser code"
os.chdir(APP)
sys.path.insert(0, str(APP))

import index as app
from alignment_software import BrainComparator

outcome = []
original_loop = tk.Tk.mainloop
fixture = None
raw = ROOT / "examples/raw"
mapping = ROOT / "examples/classes.csv"
if "--ad-ct" in sys.argv:
    fixture = tempfile.TemporaryDirectory(prefix="brainlyser-gui-ad-ct-")
    raw = Path(fixture.name) / "raw"
    raw.mkdir()
    selected = {}
    for brain, group in app.load_mapping_file(ROOT / "Datasets/AD vs CT.csv").items():
        selected.setdefault(group, brain)
    mapping = Path(fixture.name) / "classes.csv"
    with mapping.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Brain", "Class"])
        for group, brain in selected.items():
            writer.writerow([brain, group])
            images = sorted((ROOT / "Datasets/raw_data_AD" / brain).glob("*.JPG"))
            dest = raw / brain
            dest.mkdir()
            middle = len(images) // 2
            for image in images[middle-5:middle+5]:
                (dest / image.name).symlink_to(image)


def begin():
    app.root.update_idletasks()
    for widget in (app.start_button, app.status_label):
        assert widget.winfo_rooty() + widget.winfo_height() <= app.root.winfo_rooty() + app.root.winfo_height(), 'Control clipped below the window'
    app.raw_folder_display_label.config(text=str(raw))
    app.mapping_file_path = str(mapping)
    app.brain_to_class.update(app.load_mapping_file(app.mapping_file_path))
    app.mapping_file_display_label.config(text="classes.csv")
    app.start_processing()
    app.root.after(250, watch)


def watch():
    for child in app.root.winfo_children():
        if isinstance(child, BrainComparator):
            # Exercise specimen switching and small macOS wheel events.
            from types import SimpleNamespace
            for specimen in child.datasets:
                child.ds_var.set(specimen)
                child._rebuild_rows()
                child._scroll(SimpleNamespace(delta=-1))
                child.update_idletasks()
                assert len(child.text.winfo_children()) == len(child.ref_files)
            original = copy.deepcopy(child.assignments)
            specimen = child.datasets[0]
            child.ds_var.set(specimen)
            child._rebuild_rows()
            filename = next(iter(child.assignments[specimen]))
            with patch('alignment_software.messagebox.askyesno', return_value=True):
                child._delete_assignment(specimen, filename)
            assert filename not in json.loads(Path(child._data_json).read_text())[specimen]
            # Keep pipeline results comparable to the automatic baseline.
            child.assignments = original
            child._save_json(original)
            child.destroy()
    app.root.after(250, watch)


def success(output):
    app.is_processing = False
    app.update_start_button_state()
    assert str(app.start_button.cget('state')) == 'normal'
    outcome.append((True, str(output)))
    app.root.destroy()


def failure(error):
    outcome.append((False, str(error)))
    app.root.destroy()


def event_loop(self, *args, **kwargs):
    self.report_callback_exception = lambda kind, error, trace: failure(error)
    self.after(100, begin)
    self.after(900000, lambda: failure("GUI pipeline timed out"))
    return original_loop(self, *args, **kwargs)


app._on_success = success
app._on_error = failure
app.utils.open_interface_in_browser = lambda _: None
tk.Tk.mainloop = event_loop
app.main_ui()
if not outcome or not outcome[0][0]:
    raise RuntimeError(f"GUI validation failed: {outcome}")
print("PASS: full GUI pipeline, comparator accepted, output:", outcome[0][1])
if fixture:
    fixture.cleanup()
