import ctypes, json, socket
from ctypes import wintypes as w
from aiohttp import web, WSMsgType
import os

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()
SW, SH = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

import threading, tkinter as tk

pos = [0, 0]  # latest pen position in pixels

CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tablet_config.json")
cfg = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0, "lock": True, "aspect": None}
try:
    with open(CFG_PATH) as f:
        cfg.update(json.load(f))
except Exception:
    pass

def save_cfg():
    try:
        with open(CFG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print("Could not save config:", e)

def open_config(root):
    PAD, CW = 20, 560
    CH = int(CW * SH / SW)
    win = tk.Toplevel(root)
    win.title("Phone area")
    win.attributes("-topmost", True)
    win.protocol("WM_DELETE_WINDOW", win.iconify)   # closing just minimizes
    cv = tk.Canvas(win, width=CW + 2*PAD, height=CH + 2*PAD, bg="#1e1e1e", highlightthickness=0)
    cv.pack()
    lock = tk.BooleanVar(value=cfg["lock"])
    state = {"mode": None, "start": None, "mouse": None, "aspect": cfg["aspect"]}

    def ratio():  # rect height / width in normalized units for the phone's shape
        return SW / ((cfg["aspect"] or 2.0) * SH)

    def to_canvas():
        return (PAD + cfg["x"]*CW, PAD + cfg["y"]*CH,
                PAD + (cfg["x"]+cfg["w"])*CW, PAD + (cfg["y"]+cfg["h"])*CH)

    def redraw():
        cv.delete("all")
        cv.create_rectangle(PAD, PAD, PAD+CW, PAD+CH, fill="#3a3a3a", outline="#888")
        cv.create_text(PAD+8, PAD+8, anchor="nw", fill="#999", text="Laptop screen")
        x0, y0, x1, y1 = to_canvas()
        cv.create_rectangle(x0, y0, x1, y1, fill="#2f7fd8", outline="white", width=2)
        cv.create_text((x0+x1)/2, (y0+y1)/2, fill="white", text="Phone")
        for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            cv.create_rectangle(cx-5, cy-5, cx+5, cy+5, fill="white", outline="#2f7fd8")

    def apply_aspect():
        r = ratio()
        w = min(cfg["w"], 1.0, 1.0 / r)
        h = w * r
        cfg["w"], cfg["h"] = w, h
        cfg["x"], cfg["y"] = min(cfg["x"], 1 - w), min(cfg["y"], 1 - h)

    def press(e):
        x0, y0, x1, y1 = to_canvas()
        corners = {(0, 0): (x0, y0), (1, 0): (x1, y0), (0, 1): (x0, y1), (1, 1): (x1, y1)}
        state["mode"] = None
        for (cx, cy), (px_, py_) in corners.items():
            if abs(e.x - px_) <= 9 and abs(e.y - py_) <= 9:
                state["mode"] = ("corner", cx, cy)
                break
        else:
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                state["mode"] = ("move",)
        state["start"] = (cfg["x"], cfg["y"], cfg["w"], cfg["h"])
        state["mouse"] = ((e.x - PAD) / CW, (e.y - PAD) / CH)

    def drag(e):
        m = state["mode"]
        if not m:
            return
        mx, my = (e.x - PAD) / CW, (e.y - PAD) / CH
        sx, sy, sw, sh = state["start"]
        if m[0] == "move":
            cfg["x"] = min(max(sx + mx - state["mouse"][0], 0), 1 - sw)
            cfg["y"] = min(max(sy + my - state["mouse"][1], 0), 1 - sh)
        else:
            _, cx, cy = m
            ax, ay = sx + (1-cx)*sw, sy + (1-cy)*sh      # opposite corner stays fixed
            w = max(0.03, (mx - ax) if cx else (ax - mx))
            h = max(0.03, (my - ay) if cy else (ay - my))
            maxw = (1 - ax) if cx else ax
            maxh = (1 - ay) if cy else ay
            if lock.get():
                r = ratio()
                w = min(max(w, h / r), maxw, maxh / r)
                h = w * r
            else:
                w, h = min(w, maxw), min(h, maxh)
            cfg["x"] = ax if cx else ax - w
            cfg["y"] = ay if cy else ay - h
            cfg["w"], cfg["h"] = w, h
        redraw()

    cv.bind("<Button-1>", press)
    cv.bind("<B1-Motion>", drag)
    cv.bind("<ButtonRelease-1>", lambda e: save_cfg())

    def on_lock():
        cfg["lock"] = lock.get()
        if lock.get():
            apply_aspect()
        redraw(); save_cfg()

    def fit():
        r = ratio()
        w = min(1.0, 1.0 / r)
        cfg.update(w=w, h=w*r, x=(1-w)/2, y=(1-w*r)/2)
        redraw(); save_cfg()

    def full():
        cfg.update(x=0.0, y=0.0, w=1.0, h=1.0, lock=False)
        lock.set(False)
        redraw(); save_cfg()

    bar = tk.Frame(win); bar.pack(fill="x", pady=4)
    tk.Checkbutton(bar, text="Lock phone aspect ratio", variable=lock, command=on_lock).pack(side="left", padx=6)
    tk.Button(bar, text="Full screen (stretch)", command=full).pack(side="right", padx=6)
    tk.Button(bar, text="Fit", command=fit).pack(side="right")
    info = tk.Label(win, anchor="w")
    info.pack(fill="x", padx=6, pady=(0, 6))

    def update_info():
        a = cfg["aspect"]
        info.config(text=f"Phone aspect ratio: {a:.2f}" if a else "Open the page on your phone to detect its aspect ratio")

    def poll():
        if cfg["aspect"] != state["aspect"]:
            state["aspect"] = cfg["aspect"]
            if lock.get():
                apply_aspect()
            redraw(); save_cfg()
        update_info()
        win.after(300, poll)

    if lock.get():
        apply_aspect()
    redraw(); poll()

def cursor_overlay():
    R = 10
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-transparentcolor", "black")
    root.geometry(f"{2*R}x{2*R}+0+0")
    c = tk.Canvas(root, width=2*R, height=2*R, bg="black", highlightthickness=0)
    c.pack()
    c.create_oval(2, 2, 2*R-2, 2*R-2, outline="white", width=2)
    c.create_oval(R-2, R-2, R+2, R+2, fill="red", outline="")
    root.update_idletasks()
    # click-through, no focus stealing, hidden from Alt-Tab
    hwnd = user32.GetParent(root.winfo_id())
    style = user32.GetWindowLongW(hwnd, -20)
    user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20 | 0x80 | 0x08000000)

    def tick():
        root.geometry(f"+{pos[0]-R}+{pos[1]-R}")
        root.after(8, tick)
    tick()
    open_config(root)
    root.mainloop()
    root.mainloop()

class POINTER_INFO(ctypes.Structure):
    _fields_ = [("pointerType", w.DWORD), ("pointerId", ctypes.c_uint32),
                ("frameId", ctypes.c_uint32), ("pointerFlags", w.DWORD),
                ("sourceDevice", w.HANDLE), ("hwndTarget", w.HWND),
                ("ptPixelLocation", w.POINT), ("ptHimetricLocation", w.POINT),
                ("ptPixelLocationRaw", w.POINT), ("ptHimetricLocationRaw", w.POINT),
                ("dwTime", w.DWORD), ("historyCount", ctypes.c_uint32),
                ("InputData", ctypes.c_int32), ("dwKeyStates", w.DWORD),
                ("PerformanceCount", ctypes.c_uint64), ("ButtonChangeType", w.DWORD)]

class POINTER_PEN_INFO(ctypes.Structure):
    _fields_ = [("pointerInfo", POINTER_INFO), ("penFlags", ctypes.c_uint32),
                ("penMask", ctypes.c_uint32), ("pressure", ctypes.c_uint32),
                ("rotation", ctypes.c_uint32), ("tiltX", ctypes.c_int32),
                ("tiltY", ctypes.c_int32)]

class POINTER_TOUCH_INFO(ctypes.Structure):  # only here so the union is the right size
    _fields_ = [("pointerInfo", POINTER_INFO), ("touchFlags", ctypes.c_uint32),
                ("touchMask", ctypes.c_uint32), ("rcContact", w.RECT),
                ("rcContactRaw", w.RECT), ("orientation", ctypes.c_uint32),
                ("pressure", ctypes.c_uint32)]

class _U(ctypes.Union):
    _fields_ = [("penInfo", POINTER_PEN_INFO), ("touchInfo", POINTER_TOUCH_INFO)]

class POINTER_TYPE_INFO(ctypes.Structure):
    _fields_ = [("type", w.DWORD), ("u", _U)]

user32.CreateSyntheticPointerDevice.restype = ctypes.c_void_p
user32.CreateSyntheticPointerDevice.argtypes = [w.DWORD, ctypes.c_ulong, w.DWORD]
user32.InjectSyntheticPointerInput.argtypes = [ctypes.c_void_p, ctypes.c_void_p, w.DWORD]



PT_PEN = 3
dev = user32.CreateSyntheticPointerDevice(PT_PEN, 1, 1)
assert dev, "Could not create pen device (needs Windows 10 1809+)"

NEW, INRANGE, INCONTACT, BTN1 = 0x1, 0x2, 0x4, 0x10
DOWN, UPDATE, UP = 0x10000, 0x20000, 0x40000

def inject(flags, x, y, pressure):
    px = int((cfg["x"] + min(max(x, 0), 1) * cfg["w"]) * SW)
    py = int((cfg["y"] + min(max(y, 0), 1) * cfg["h"]) * SH)
    pos[0], pos[1] = px, py            # <-- feeds the overlay
    info = POINTER_TYPE_INFO()
    info.type = PT_PEN
    pi = info.u.penInfo
    pi.pointerInfo.pointerType = PT_PEN
    pi.pointerInfo.pointerId = 0
    pi.pointerInfo.pointerFlags = flags
    pi.pointerInfo.ptPixelLocation.x = px  # <-- use the same values
    pi.pointerInfo.ptPixelLocation.y = py
    pi.penMask = 0x1
    pi.pressure = int(max(0, min(1, pressure)) * 1024)
    user32.InjectSyntheticPointerInput(dev, ctypes.byref(info), 1)
async def index(req):
    return web.FileResponse("index.html")

async def ws_handler(req):
    ws = web.WebSocketResponse()
    await ws.prepare(req)
    last = (0, 0)
    down = False
    inrange = False
    async for msg in ws:
        if msg.type != WSMsgType.TEXT:
            continue
        d = json.loads(msg.data)
        if d["type"] == "size":
            cfg["aspect"] = d["w"] / d["h"]
            continue
        x, y, p, t = d["x"], d["y"], d["p"], d["type"]
        last = (x, y)

        if t == "hover":
            inject(INRANGE | UPDATE | (0 if inrange else NEW), x, y, 0)
            inrange = True
        elif t == "down":
            flags = INRANGE | INCONTACT | BTN1 | DOWN | (0 if inrange else NEW)
            inject(flags, x, y, p)
            down = inrange = True
        elif t == "move" and down:
            inject(INRANGE | INCONTACT | BTN1 | UPDATE, x, y, p)
        elif t == "up" and down:
            inject(INRANGE | UP, x, y, 0)
            down = False
            if not d.get("pen"):               # finger: lift means gone
                inject(UPDATE, x, y, 0); inrange = False
        elif t == "leave" and inrange and not down:
            inject(UPDATE, x, y, 0)            # no INRANGE flag = pen left
            inrange = False

    if down:                                    # phone disconnected mid-stroke
        inject(INRANGE | UP, *last, 0)
    if inrange:
        inject(UPDATE, *last, 0)
    return ws

def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    return s.getsockname()[0]

app = web.Application()
app.add_routes([web.get("/", index), web.get("/ws", ws_handler)])
print(f"Open on your phone: http://{local_ip()}:8000")

threading.Thread(target=cursor_overlay, daemon=True).start()
web.run_app(app, host="0.0.0.0", port=8000, print=None)

web.run_app(app, host="0.0.0.0", port=8000, print=None)