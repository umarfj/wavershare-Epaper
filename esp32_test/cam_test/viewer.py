"""Live view of the ESP32 camera. Press SPACE to capture the current frame and show it
on the e-paper. Press q to quit.   Usage: python viewer.py [COM9]"""
import sys, struct, time
import serial, numpy as np, cv2
from PIL import Image, ImageOps, ImageEnhance

EPD_W, EPD_H = 416, 240      # landscape, matches the firmware
CONTRAST = 1.5               # >1 = punchier
GAMMA = 1.3                  # >1 = darker midtones

port = sys.argv[1] if len(sys.argv) > 1 else "COM9"
ser = serial.Serial(port, 4000000, timeout=1)
ser.dtr = False; ser.rts = False
MAGIC = b"\xaa\x55\xaa\x55"


def to_epaper(bgr):
    """BGR camera frame -> (1-bit PIL image, packed bytes) for the 416x240 panel."""
    im = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    s = max(EPD_W / im.width, EPD_H / im.height)            # cover-crop, centred
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    left, top = (im.width - EPD_W) // 2, (im.height - EPD_H) // 2
    im = im.crop((left, top, left + EPD_W, top + EPD_H))
    g = ImageOps.autocontrast(im.convert("L"), cutoff=1)
    g = ImageEnhance.Contrast(g).enhance(CONTRAST)
    g = g.point(lambda p: round(255 * (p / 255) ** GAMMA))
    bw = g.convert("1", dither=Image.FLOYDSTEINBERG)         # 0 = black
    black = (np.array(bw) == 0)                              # True where black
    return bw, np.packbits(black, axis=1).tobytes()         # MSB first, 1 = black


def report(txt):
    if txt and txt.isprintable(): print("board:", txt)


buf = bytearray()
last = None
frames, t0 = 0, time.time()
print("SPACE = show on e-paper (takes ~2 s), q = quit.")
while True:
    buf += ser.read(max(1, ser.in_waiting))
    while True:
        i = buf.find(MAGIC)
        if i < 0:
            if b"\n" in buf:
                line, _, rest = bytes(buf).rpartition(b"\n")
                for l in line.split(b"\n"): report(l.decode(errors="replace").strip())
                buf = bytearray(rest)
            buf = buf[-1024:]
            break
        if i > 0:
            for l in bytes(buf[:i]).split(b"\n"): report(l.decode(errors="replace").strip())
            del buf[:i]
        if len(buf) < 8: break
        n = struct.unpack("<I", buf[4:8])[0]
        if n > 500000: del buf[:4]; continue
        if len(buf) < 8 + n: break
        jpg = bytes(buf[8:8+n]); del buf[:8+n]
        if jpg[:2] != b'\xff\xd8' or jpg[-2:] != b'\xff\xd9': continue
        img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
        if img is None: continue
        last = img
        frames += 1
        if time.time() - t0 >= 1:
            cv2.setWindowTitle("ESP32 camera", f"ESP32 camera - {frames} fps  (SPACE = e-paper)")
            frames, t0 = 0, time.time()
        cv2.imshow("ESP32 camera", img)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"): sys.exit()
        if key == ord(" ") and last is not None:
            bw, data = to_epaper(last)
            cv2.imshow("e-paper preview", cv2.cvtColor(np.array(bw.convert("L")), cv2.COLOR_GRAY2BGR))
            ser.write(b"EPD!" + data)
            print(f"sent {len(data)} bytes to e-paper...")
