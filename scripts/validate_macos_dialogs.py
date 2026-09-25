"""Exercise real Cocoa/Tk file dialogs and cancel them automatically (macOS)."""
import ctypes
import sys
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Code/Brainlyser code"))
from index import TABLE_FILETYPES

if sys.platform != "darwin":
    raise SystemExit("This native-dialog test requires macOS.")

objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
objc.objc_getClass.argtypes = [ctypes.c_char_p]
objc.objc_getClass.restype = ctypes.c_void_p
objc.sel_registerName.argtypes = [ctypes.c_char_p]
objc.sel_registerName.restype = ctypes.c_void_p
objc.object_getClassName.argtypes = [ctypes.c_void_p]
objc.object_getClassName.restype = ctypes.c_char_p
send = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(('objc_msgSend', objc))
send_index = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)(('objc_msgSend', objc))
cancel = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(('objc_msgSend', objc))
send_object = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(('objc_msgSend', objc))
send_two = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(('objc_msgSend', objc))

root = tk.Tk()
root.title("Brainlyser native dialog validation")
root.geometry("420x120")
root.update()
seen = []


def dismiss(*_):
    app = send(objc.objc_getClass(b"NSApplication"), objc.sel_registerName(b"sharedApplication"))
    windows = send(app, objc.sel_registerName(b"windows"))
    count = send(windows, objc.sel_registerName(b"count")) or 0
    for index in range(count):
        window = send_index(windows, objc.sel_registerName(b"objectAtIndex:"), index)
        name = objc.object_getClassName(window).decode()
        if ("OpenPanel" in name or "SavePanel" in name) and send(window, objc.sel_registerName(b"isVisible")):
            seen.append(name)
            cancel(window, objc.sel_registerName(b"cancel:"), None)
            return
    raise RuntimeError("No native open panel found")


# Tk's after callbacks need not run inside Cocoa's modal loop. A Cocoa timer
# registered in its modal mode does; the callback remains on the GUI thread.
objc.objc_allocateClassPair.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
objc.objc_allocateClassPair.restype = ctypes.c_void_p
objc.class_addMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
objc.objc_registerClassPair.argtypes = [ctypes.c_void_p]
callback = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(dismiss)
timer_class = objc.objc_allocateClassPair(objc.objc_getClass(b"NSObject"), b"BrainlyserDialogTestTimer", 0)
objc.class_addMethod(timer_class, objc.sel_registerName(b"fire:"), ctypes.cast(callback, ctypes.c_void_p), b"v@:@")
objc.objc_registerClassPair(timer_class)
target = send(send(timer_class, objc.sel_registerName(b"alloc")), objc.sel_registerName(b"init"))
make_timer = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_double,
                             ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)(('objc_msgSend', objc))
make_string = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)(('objc_msgSend', objc))


def schedule_dismiss():
    timer = make_timer(objc.objc_getClass(b"NSTimer"), objc.sel_registerName(b"timerWithTimeInterval:target:selector:userInfo:repeats:"),
                       1.0, target, objc.sel_registerName(b"fire:"), None, False)
    loop = send(objc.objc_getClass(b"NSRunLoop"), objc.sel_registerName(b"currentRunLoop"))
    for name in (b"NSModalPanelRunLoopMode", b"NSRunLoopCommonModes"):
        mode = make_string(objc.objc_getClass(b"NSString"), objc.sel_registerName(b"stringWithUTF8String:"), name)
        send_two(loop, objc.sel_registerName(b"addTimer:forMode:"), timer, mode)


for label, types in [("Class table", TABLE_FILETYPES), ("Reference table", TABLE_FILETYPES),
                     ("Assignments", [("JSON", "*.json"), ("All files", "*")])]:
    schedule_dismiss()
    result = filedialog.askopenfilename(parent=root, title=label,
                                       initialdir=ROOT / "Datasets", filetypes=types)
    assert not result
    print(f"PASS native {label}: {seen[-1]}", flush=True)
schedule_dismiss()
assert not filedialog.askdirectory(parent=root, initialdir=ROOT / "Datasets")
print(f"PASS native directory: {seen[-1]}", flush=True)
root.destroy()
