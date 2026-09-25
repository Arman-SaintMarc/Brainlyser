# brain_comparator.py
# ------------------------------------------------------------
# Brain Comparator – DnD   v8.1
# 2025-08-06
#   • Bulk-shift vs local-insert modes
#   • Right-click to delete an assignment
# ------------------------------------------------------------
import os, re, json, logging, tkinter as tk
from pathlib import Path
import pandas as pd
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw

# ------------------------------------------------------------
# Default mapping (used when GUI does **not** pass a CSV/XLSX)
# ------------------------------------------------------------
DEFAULT_REF_ATLAS_PAIRS = [
    (10, 5), (11, 6), (12, 7), (13, 8), (14, 9), (15, 10), (16, 11),
    (17, 12), (18, 13), (19, 14), (20, 15), (21, 17), (22, 19), (23, 21),
    (24, 23), (25, 25), (26, 27), (27, 29), (28, 31), (29, 32), (30, 34),
    (31, 35), (32, 37), (33, 38), (34, 40), (35, 41), (36, 43), (37, 44),
    (38, 46), (39, 47), (40, 49), (41, 50), (42, 52), (43, 53), (44, 55),
    (45, 56), (46, 58), (47, 59), (48, 61), (49, 62), (50, 63), (51, 64),
    (52, 65), (53, 66), (54, 67), (55, 68), (56, 69), (57, 70), (58, 71),
    (59, 72), (60, 73), (61, 74), (62, 75), (63, 76), (64, 77), (65, 78),
    (66, 79), (67, 81), (68, 82), (69, 83), (70, 85), (71, 87), (72, 89),
    (73, 91), (74, 92), (75, 94), (76, 95), (77, 97), (78, 98), (79, 99),
    (80, 100), (81, 102), (82, 104), (83, 106), (84, 107), (85, 109), (86, 110),
    (87, 112), (88, 113), (89, 114), (90, 115), (91, 117), (92, 118), (93, 120),
    (94, 121), (95, 122), (96, 123), (97, 124), (98, 125), (99, 126), (102, 127),
    (103, 128), (104, 129), (105, 130), (106, 131), (107, 133), (108, 134),
    (109, 136), (110, 137), (111, 139), (112, 140), (113, 142), (114, 143),
    (115, 144), (116, 146), (117, 147), (118, 149), (119, 150), (120, 153),
    (121, 154), (122, 156), (123, 157), (124, 160), (125, 161), (126, 163),
    (127, 164), (128, 166), (129, 167), (130, 169), (131, 170), (132, 173),
    (133, 174), (134, 175), (135, 176), (136, 177), (137, 178), (138, 179),
    (139, 180), (140, 181), (141, 182), (142, 183), (143, 184), (144, 186),
    (146, 187), (147, 188), (148, 189), (149, 190), (150, 192), (151, 193),
    (152, 194), (153, 195), (154, 197), (155, 198), (156, 200), (157, 201),
    (158, 203), (159, 204), (160, 206), (161, 207), (162, 209), (163, 210),
    (164, 212), (165, 213), (166, 215), (167, 216), (168, 218), (169, 219),
    (170, 220)
]
REF_ATLAS_PAIRS = DEFAULT_REF_ATLAS_PAIRS.copy()
ATLAS_TO_REF    = {a: r for r, a in REF_ATLAS_PAIRS}
REF_TO_ATLAS    = {r: a for r, a in REF_ATLAS_PAIRS}

# ---------- tiny helpers ------------------------------------
_num   = lambda s: int(re.search(r"\d+", str(s)).group()) if re.search(r"\d+", str(s)) else None
_atlas = lambda n: f"slice{n:04d}.jpg" if n is not None else None


def minimal_reorder_indices(original, dragged, target):
    """Move only the contiguous conflicting neighbours, in either direction."""
    positions = dict(original)
    source = positions[dragged]
    positions[dragged] = target
    ordered = sorted(positions, key=_num)
    pivot = ordered.index(dragged)
    if target > source:
        previous = target
        for name in ordered[pivot + 1:]:
            positions[name] = max(positions[name], previous + 1)
            previous = positions[name]
    else:
        following = target
        for name in reversed(ordered[:pivot]):
            positions[name] = min(positions[name], following - 1)
            following = positions[name]
    return positions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")


class BrainComparator(tk.Toplevel):
    """Drag-and-drop GUI for reviewing atlas–dataset slice assignments."""
    def __init__(self, data_json: str, data_root: str, ref_root: str,
                 ref_size: tuple[int, int] = (250, 250),
                 assigned_size: tuple[int, int] = (250, 250)):
        super().__init__()
        self._data_json, self._data_root, self._ref_root = data_json, data_root, ref_root
        self._ref_size, self._assigned_size = tuple(ref_size), tuple(assigned_size)

        self.title("Brain Comparator – DnD")
        self.geometry("800x700")
        self.maxsize(800, self.winfo_screenheight())
        self.configure(bg="#fafafa")

        self._thumb_cache, self._ph_cache = {}, {}
        self.assignments = self._load_json()
        self.datasets = sorted(self.assignments)
        self.ref_files = sorted([f for f in os.listdir(self._ref_root) if _num(f)], key=_num)

        self._row_widgets = {}
        self._drag_fname = self._drag_img = self._source_rf = None
        self._press_pos = self._ghost = None

        self._build_gui()
        if self.datasets:
            self.ds_var.set(self.datasets[0])
            self._rebuild_rows()
        self.after_idle(self._show_tutorial)

    # ======================================================================
    # GUI
    # ======================================================================
    def _build_gui(self):
        top = ttk.Frame(self, padding=10); top.pack(fill="x")
        ttk.Label(top, text="Dataset:").pack(side="left")
        self.ds_var = tk.StringVar()
        cmb = ttk.Combobox(top, textvariable=self.ds_var, state="readonly",
                           width=40, values=self.datasets)
        cmb.pack(side="left", padx=6)
        cmb.bind("<<ComboboxSelected>>", lambda *_: self._rebuild_rows())
        ttk.Button(top, text="Finish", command=self.destroy).pack(side="right")

        self.shift_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Shift entire dataset", variable=self.shift_var
                        ).pack(side="left", padx=6)

        wrap = ttk.Frame(self); wrap.pack(fill="both", expand=True)
        self.text = tk.Text(wrap, wrap="none", bg="#fafafa",
                            bd=0, highlightthickness=0)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=vsb.set)
        self.text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.bind("<MouseWheel>", self._scroll)
        self.text.bind("<Configure>", self._sync_row_widths)

    def _scroll(self, event):
        if event.delta:
            units = event.delta if self.tk.call("tk", "windowingsystem") == "aqua" else event.delta / 120
            self.text.yview_scroll(-int(units or (1 if event.delta > 0 else -1)), "units")
        return "break"

    def _sync_row_widths(self, ev):
        for _, row in self._row_widgets.values():
            row.configure(width=ev.width)

    # ======================================================================
    # ROWS
    # ======================================================================
    def _rebuild_rows(self, *, keep_view: bool = False):
        """
        Re-create the two-column list.

        Parameters
        ----------
        keep_view : bool
            When True, restore the Text widget’s vertical scroll position
            so the user does not lose their place.
        """
        # record current vertical position *before* clearing the widget
        saved_frac = self.text.yview()[0] if keep_view else 0.0

        for _, row in self._row_widgets.values():
            row.destroy()
        self.text.delete("1.0", "end")
        self._row_widgets.clear()
        self._thumb_cache.clear()
        self._ph_cache.clear()

        ds        = self.ds_var.get()
        atlas_map = {v: k for k, v in self.assignments.get(ds, {}).items()}
        mapping   = {rf: _atlas(REF_TO_ATLAS.get(_num(rf))) for rf in self.ref_files}

        for rf in self.ref_files:
            line_start = self.text.index("end-1c linestart")

            row = ttk.Frame(self.text)
            row.grid_columnconfigure(0, weight=1)
            row.grid_columnconfigure(1, weight=1)
            row.ref_file = rf

            # left column (reference)
            lf = ttk.Frame(row); lf.grid(row=0, column=0, padx=8, pady=12)
            ttk.Label(lf, image=self._thumb(os.path.join(self._ref_root, rf),
                                            self._ref_size)).pack()
            ttk.Label(lf, text=rf, wraplength=self._ref_size[0]).pack()

            # right column (assignment / drop target)
            rt = ttk.Frame(row); rt.grid(row=0, column=1, padx=8, pady=12)
            row.rt = rt
            assigned = atlas_map.get(mapping[rf])
            if assigned:
                self._populate_rt(rt, ds, assigned)
            else:
                ttk.Label(rt, text="Drop here", foreground="#555",
                          width=20).pack(expand=True, fill="both")

            # insert row into Text widget
            self.text.window_create("end", window=row)
            self.text.insert("end", "\n")
            self._row_widgets[rf] = (int(float(line_start)), row)

        # restore scroll *after* geometry settles
        if keep_view:
            self.text.update_idletasks()
            self.text.yview_moveto(saved_frac)
        else:
            # initial build: show the very top
            self.text.see("1.0")


    # ------------------------------------------------------------------
    def _populate_rt(self, rt, ds, fname):
        for w in rt.winfo_children(): w.destroy()
        p = os.path.join(self._data_root, ds, "structure", fname)
        img = self._thumb(p, self._assigned_size)
        lbl = ttk.Label(rt, image=img, relief="solid", borderwidth=2,
                        cursor="hand2")
        lbl.image, lbl.fname = img, fname
        lbl.pack()
        ttk.Label(rt, text=fname, wraplength=self._assigned_size[0]).pack()

        lbl.bind("<ButtonPress-1>",  self._on_press)
        lbl.bind("<B1-Motion>",      self._on_motion)
        lbl.bind("<ButtonRelease-1>", self._on_release)

        for btn in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
            lbl.bind(btn, lambda e, d=ds, f=fname: self._delete_assignment(d, f))

    # ======================================================================
    # DRAG & DROP
    # ======================================================================
    def _on_press(self, ev):
        w = ev.widget
        self._source_rf, self._drag_fname = w.master.master.ref_file, w.fname
        self._drag_img, self._press_pos = w.image, (ev.x_root, ev.y_root)
        self._ghost = None

    def _on_motion(self, ev):
        if not self._drag_fname:
            return
        if self._ghost is None:
            dx, dy = abs(ev.x_root - self._press_pos[0]), abs(ev.y_root - self._press_pos[1])
            if dx < 4 and dy < 4:
                return
            self._ghost = tk.Toplevel(self, bd=0, bg="white")
            tk.Label(self._ghost, image=self._drag_img, bd=2, relief="raised").pack()
            self._ghost.overrideredirect(True)
        self._ghost.geometry(f"+{ev.x_root+8}+{ev.y_root+8}")

    def _on_release(self, ev):
        if self._ghost:
            self._ghost.destroy(); self._ghost = None
            x = ev.x_root - self.text.winfo_rootx()
            y = ev.y_root - self.text.winfo_rooty()
            try:
                line = int(float(self.text.index(f"@{x},{y}")))
            except tk.TclError:
                self._reset_drag_state(); return
            target_rf = next((rf for rf, (ln, _) in self._row_widgets.items() if ln == line), None)
            if target_rf and target_rf != self._source_rf:
                self._apply_assignment(target_rf)
        self._reset_drag_state()

    def _reset_drag_state(self):
        self._drag_fname = self._drag_img = self._source_rf = None
        self._press_pos = self._ghost = None

    # ======================================================================
    # ASSIGNMENT LOGIC
    # ======================================================================
    def _apply_assignment(self, target_rf: str) -> None:
        """
        Checkbox OFF → local minimal shift to restore ascending dataset order:
          • Drag ↓ : every slice with numeric > dragged that falls at or above
                     the target moves just enough to come after the dragged slice,
                     stopping once there’s a natural gap.
          • Drag ↑ : mirror behaviour for slices above.

        Checkbox ON  → bulk-shift (unchanged).
        """
        ds = self.ds_var.get()

        # 1) determine source & target atlas positions
        src_atlas = _atlas(REF_TO_ATLAS.get(_num(self._source_rf)))
        tgt_atlas = _atlas(REF_TO_ATLAS.get(_num(target_rf)))
        if src_atlas is None or tgt_atlas is None:
            return

        ordered = [_atlas(n) for n in sorted(REF_TO_ATLAS.values())]
        src_idx, tgt_idx = ordered.index(src_atlas), ordered.index(tgt_atlas)
        delta = tgt_idx - src_idx
        if delta == 0:
            return  # no move

        ds_map = self.assignments.setdefault(ds, {})
        # detach the dragged slice
        ds_map.pop(self._drag_fname, None)

        # ─── checkbox OFF: minimal reorder ───────────────────────────────────
        if not self.shift_var.get():
            # 2) capture original indices of remaining assignments
            orig_idx = {}
            for d, a in ds_map.items():
                try:
                    orig_idx[d] = ordered.index(a)
                except ValueError:
                    pass

            orig_idx[self._drag_fname] = src_idx
            new_idx = minimal_reorder_indices(orig_idx, self._drag_fname, tgt_idx)

            # 5) commit only in‐bounds assignments
            ds_map.clear()
            for d, idx in new_idx.items():
                if 0 <= idx < len(ordered):
                    ds_map[d] = ordered[idx]

            self._save_json(self.assignments)
            self._rebuild_rows(keep_view=True)
            return

        # ─── checkbox ON: bulk-shift (unchanged) ────────────────────────────
        for d, a in list(ds_map.items()):
            try:
                i = ordered.index(a)
            except ValueError:
                continue
            if delta > 0 and i > src_idx:
                ni = i + delta
            elif delta < 0 and i < src_idx:
                ni = i + delta
            else:
                continue

            if 0 <= ni < len(ordered):
                ds_map[d] = ordered[ni]
            else:
                ds_map.pop(d, None)

        ds_map[self._drag_fname] = tgt_atlas
        self._save_json(self.assignments)
        self._rebuild_rows(keep_view=True)







    # ------------------------------------------------------------------
    def _delete_assignment(self, ds: str, fname: str):
        if not messagebox.askyesno("Delete assignment",
                                   f"Remove the assignment for\n{fname}?"):
            return
        self.assignments.get(ds, {}).pop(fname, None)
        self._save_json(self.assignments)
        self._rebuild_rows(keep_view=True)

    # ======================================================================
    # UTILITIES
    # ======================================================================
    def _thumb(self, path: str, size: tuple[int, int]):
        key = (path, size)
        ph = self._thumb_cache.get(key)
        if ph is not None:
            try:
                if str(ph) in self.tk.call('image', 'names'):
                    return ph
            except tk.TclError:
                pass
        if not os.path.exists(path):
            ph = self._placeholder("Missing", size)
        else:
            try:
                with Image.open(path) as im:
                    im.thumbnail(size, Image.Resampling.LANCZOS)
                    ph = ImageTk.PhotoImage(im, master=self)
            except Exception as e:
                logging.error("thumb: %s", e, exc_info=True)
                ph = self._placeholder("Error", size)
        self._thumb_cache[key] = ph
        return ph

    def _placeholder(self, text: str, size: tuple[int, int]):
        key = (text, size)
        if key in self._ph_cache:
            return self._ph_cache[key]
        im = Image.new("RGB", size, "#d0d0d0")
        d = ImageDraw.Draw(im)
        left, top, right, bottom = d.textbbox((0, 0), text)
        w, h = right - left, bottom - top
        d.text(((size[0]-w)//2, (size[1]-h)//2), text, fill="#000")
        ph = ImageTk.PhotoImage(im); self._ph_cache[key] = ph
        return ph

    def _load_json(self) -> dict:
        return json.loads(Path(self._data_json).read_text(encoding="utf-8")) if os.path.exists(self._data_json) else {}

    def _save_json(self, j: dict):
        os.makedirs(os.path.dirname(self._data_json), exist_ok=True)
        Path(self._data_json).write_text(json.dumps(j, indent=2), encoding="utf-8")

    # ======================================================================
    # QUICK TUTORIAL
    # ======================================================================
    def _show_tutorial(self):
        """One-time pop-up explaining the basic controls."""
        top = tk.Toplevel(self)
        top.title("Brain Comparator – Quick tour")
        top.transient(self)          # stay on top of main window
        top.grab_set()               # modal

        # headline
        tk.Label(top,
                 text="How to use Brain Comparator",
                 font=("Arial", 14, "bold")
                ).pack(padx=20, pady=(15, 10))

        # instructions
        msg = (
            "• Drag a thumbnail in the right column and drop it on another row "
            "to reorder the slices.\n\n"

            "• Checkbox ON  → **bulk shift**:\n"
            "    All slices on the same side of the dragged one move by exactly "
            "the distance you skipped.\n\n"

            "• Checkbox OFF → **minimal shift**:\n"
            "    • Drag ↓ : only the contiguous block of slices below the dragged "
            "one is pushed down by the number of positions skipped, stopping as soon "
            "as a gap appears.\n"
            "    • Drag ↑ : same, but moves the contiguous block above up.\n\n"

            "• Right-click (or Ctrl-click) a thumbnail to delete its assignment.\n\n"

            "• The view will stay scrolled where you left it after each move.\n\n"

            "• Click “Got it!” to close this tour and start reordering."
        )
        tk.Label(top,
                 text=msg,
                 justify="left",
                 wraplength=440
                ).pack(padx=20, pady=10)

        ttk.Button(top,
                   text="Got it!",
                   command=top.destroy
                  ).pack(pady=(0, 15))



# ======================================================================
# PUBLIC ENTRY POINT
# ======================================================================
def run_brain_comparator(root: tk.Tk,
                         data_json: str,
                         data_root: str,
                         ref_root: str,
                         ref_size: tuple[int, int] = (250, 250),
                         assigned_size: tuple[int, int] = (250, 250),
                         *, extra_csv: str | None = None,
                         extra_folder: str | None = None) -> dict:

    global REF_ATLAS_PAIRS, ATLAS_TO_REF, REF_TO_ATLAS
    REF_ATLAS_PAIRS = DEFAULT_REF_ATLAS_PAIRS.copy()
    if extra_csv:
        df = (pd.read_csv(extra_csv) if Path(extra_csv).suffix.lower() == ".csv"
              else pd.read_excel(extra_csv))
        if not {"REF", "ATLAS"}.issubset(df.columns):
            raise ValueError("Mapping file must contain columns 'REF' and 'ATLAS'")
        REF_ATLAS_PAIRS = [(int(r), int(a)) for r, a in zip(df["REF"], df["ATLAS"])]
    ATLAS_TO_REF    = {a: r for r, a in REF_ATLAS_PAIRS}
    REF_TO_ATLAS    = {r: a for r, a in REF_ATLAS_PAIRS}

    if extra_folder:
        ref_root = os.path.join(extra_folder, "structure")

    for path, lbl in [(data_root, "DATA_ROOT"), (ref_root, "REF_ROOT")]:
        if not os.path.isdir(path):
            raise FileNotFoundError(f"missing {path}")

    dialog = BrainComparator(data_json=data_json, data_root=data_root,
                             ref_root=ref_root, ref_size=ref_size,
                             assigned_size=assigned_size)
    dialog.transient(root); dialog.grab_set()
    root.wait_window(dialog)
    return dialog.assignments

