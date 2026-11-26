"""ESP32 camera viewer with a 'Capture to e-paper' button.
Usage: python gui_viewer.py [COM9]"""
import sys, struct, threading, time
import tkinter as tk
from tkinter import ttk
import serial, numpy as np, cv2
from PIL import Image, ImageOps, ImageEnhance, ImageTk

EPD_W, EPD_H = 416, 240
PORT = sys.argv[1] if len(sys.argv) > 1 else "COM9"
AUTO_TARGET = 0.35   # default median brightness the auto mode aims for (0 = black, 1 = white); lower = darker
GAMMA_MIN = 0.8      # auto mode never brightens beyond this gamma (1.0 = never brighten; lower = lifts dark scenes more)
MAGIC = b"\xaa\x55\xaa\x55"

ser = serial.Serial(PORT, 4000000, timeout=0.2)
ser.dtr = False; ser.rts = False

latest = {"img": None, "fps": 0.0}      # written by reader thread, read by the GUI
events = []                              # text lines from the board
lock = threading.Lock()


def reader():
    buf = bytearray(); frames, t0 = 0, time.time()
    while True:
        try:
            buf += ser.read(max(1, ser.in_waiting))
        except serial.SerialException:
            return
        while True:
            i = buf.find(MAGIC)
            if i < 0:
                if b"\n" in buf:
                    line, _, rest = bytes(buf).rpartition(b"\n")
                    take_text(line); buf = bytearray(rest)
                del buf[:-1024]
                break
            if i > 0:
                take_text(bytes(buf[:i])); del buf[:i]
            if len(buf) < 8: break
            n = struct.unpack("<I", buf[4:8])[0]
            if n > 500000: del buf[:4]; continue
            if len(buf) < 8 + n: break
            jpg = bytes(buf[8:8+n]); del buf[:8+n]
            if jpg[:2] != b"\xff\xd8" or jpg[-2:] != b"\xff\xd9": continue
            img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
            if img is None: continue
            frames += 1
            with lock:
                latest["img"] = img
                if time.time() - t0 >= 1:
                    latest["fps"] = frames / (time.time() - t0); frames, t0 = 0, time.time()


def take_text(raw):
    for l in raw.split(b"\n"):
        t = l.decode(errors="replace").strip()
        if t.startswith(("EPD_", "CAMERA", "CAPTURE")):
            with lock: events.append(t)


def rotate(bgr, deg):
    code = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}.get(deg)
    return cv2.rotate(bgr, code) if code is not None else bgr


def to_epaper(bgr, contrast, gamma, auto=False, target=AUTO_TARGET):
    """Returns (1-bit PIL image, packed bytes, description of what was applied)."""
    im = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    s = max(EPD_W / im.width, EPD_H / im.height)             # cover-crop, centred
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    left, top = (im.width - EPD_W) // 2, (im.height - EPD_H) // 2
    im = im.crop((left, top, left + EPD_W, top + EPD_H))
    g = ImageOps.autocontrast(im.convert("L"), cutoff=1)
    if auto:
        # Local contrast equalisation (works for dim and harsh lighting alike), then pick
        # the gamma that moves the median brightness to a mid tone so the dither has
        # something to work with.
        a = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(4, 4)).apply(np.array(g))
        m = float(np.clip(np.median(a) / 255.0, 0.05, 0.95))
        gamma = float(np.clip(np.log(target) / np.log(m), GAMMA_MIN, 2.6))
        g = Image.fromarray(a)
        note = f"auto: gamma {gamma:.2f} (median brightness {m:.2f})"
    else:
        g = ImageEnhance.Contrast(g).enhance(contrast)
        note = f"manual: contrast {contrast:.2f}, gamma {gamma:.2f}"
    g = g.point(lambda p: round(255 * (p / 255) ** gamma))
    bw = g.convert("1", dither=Image.FLOYDSTEINBERG)          # 0 = black
    return bw, np.packbits(np.array(bw) == 0, axis=1).tobytes(), note


class App:
    def __init__(self, root):
        self.root = root
        root.title("ESP32 camera -> e-paper")
        left = ttk.Frame(root, padding=8); left.grid(row=0, column=0)
        right = ttk.Frame(root, padding=8); right.grid(row=0, column=1, sticky="n")

        self.video = ttk.Label(left); self.video.pack()
        self.fps = ttk.Label(left, text="waiting for camera..."); self.fps.pack(anchor="w")

        self.btn = ttk.Button(right, text="Capture to e-paper", command=self.capture)
        self.btn.pack(fill="x", ipady=10)
        self.status = ttk.Label(right, text="Ready", wraplength=300); self.status.pack(anchor="w", pady=6)

        ttk.Label(right, text="Rotate").pack(anchor="w")
        self.rot = tk.StringVar(value="0")
        ttk.Combobox(right, textvariable=self.rot, values=["0", "90", "180", "270"],
                     state="readonly", width=6).pack(anchor="w")
        self.auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text="Auto contrast / gamma (adapts to lighting)",
                        variable=self.auto, command=self.toggle_auto).pack(anchor="w", pady=(8, 0))
        self.target = tk.DoubleVar(value=AUTO_TARGET)
        ttk.Label(right, text="Auto brightness target (left = darker, right = lighter)").pack(anchor="w")
        ttk.Scale(right, from_=0.15, to=0.7, variable=self.target, length=300).pack()
        self.contrast = tk.DoubleVar(value=1.5); self.gamma = tk.DoubleVar(value=1.3)
        ttk.Label(right, text="Contrast (manual)").pack(anchor="w")
        self.s_contrast = ttk.Scale(right, from_=0.8, to=3.0, variable=self.contrast, length=300)
        self.s_contrast.pack()
        ttk.Label(right, text="Gamma (manual, higher = darker)").pack(anchor="w")
        self.s_gamma = ttk.Scale(right, from_=0.6, to=2.5, variable=self.gamma, length=300)
        self.s_gamma.pack()
        self.toggle_auto()

        ttk.Label(right, text="Sent to e-paper:").pack(anchor="w", pady=(10, 0))
        self.preview = ttk.Label(right); self.preview.pack()
        self.busy_until = 0
        self.tick()

    def toggle_auto(self):
        st = "disabled" if self.auto.get() else "!disabled"
        self.s_contrast.state([st]); self.s_gamma.state([st])

    def current(self):
        with lock: img = latest["img"]
        return None if img is None else rotate(img, int(self.rot.get()))

    def capture(self):
        img = self.current()
        if img is None:
            self.status.config(text="No camera frame yet."); return
        bw, data, note = to_epaper(img, self.contrast.get(), self.gamma.get(), self.auto.get(), self.target.get())
        self.pv = ImageTk.PhotoImage(bw.convert("L"))
        self.preview.config(image=self.pv)
        ser.write(b"EPD!" + data)
        self.btn.state(["disabled"]); self.busy_until = time.time() + 15
        self.status.config(text=f"Sent ({note}). Refreshing e-paper (~3 s, video pauses)...")

    def tick(self):
        img = self.current()
        if img is not None:
            self.tk_img = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
            self.video.config(image=self.tk_img)
        with lock:
            fps = latest["fps"]; ev = events[:]; events.clear()
        self.fps.config(text=f"{fps:.0f} fps")
        for e in ev:
            if e.startswith("EPD_DONE"):
                self.status.config(text="Done - image is on the e-paper."); self.btn.state(["!disabled"])
            elif e.startswith("EPD_ERROR"):
                self.status.config(text=e); self.btn.state(["!disabled"])
            elif e.startswith("CAMERA_INIT_FAILED"):
                self.status.config(text=e)
        if self.busy_until and time.time() > self.busy_until:
            self.busy_until = 0; self.btn.state(["!disabled"])
            self.status.config(text="No reply from the board (timed out).")
        self.root.after(15, self.tick)


threading.Thread(target=reader, daemon=True).start()
root = tk.Tk()
App(root)
root.mainloop()
