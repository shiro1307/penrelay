"""Phone Tablet Windows server with Tk control panel."""
import asyncio, ctypes, json, queue, socket, sys, threading
from ctypes import wintypes as w
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from aiohttp import web, WSMsgType

BASE = Path(__file__).resolve().parent
RESOURCE = Path(getattr(sys, "_MEIPASS", BASE))
PATH = (Path(sys.executable).parent if getattr(sys, "frozen", False) else BASE) / "tablet_config.json"
DEFAULT = {"x": 0., "y": 0., "w": 1., "h": 1., "lock": True,
           "aspect": None, "port": 8000}

class Settings:
    def __init__(self):
        self.lock = threading.RLock(); self.data = DEFAULT.copy()
        try: self.data.update(json.loads(PATH.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError): pass
    def get(self, key):
        with self.lock: return self.data[key]
    def copy(self):
        with self.lock: return self.data.copy()
    def update(self, **values):
        with self.lock:
            self.data.update(values)
            try: PATH.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
            except OSError: pass

class POINTER_INFO(ctypes.Structure):
    _fields_=[("pointerType",w.DWORD),("pointerId",ctypes.c_uint32),("frameId",ctypes.c_uint32),("pointerFlags",w.DWORD),("sourceDevice",w.HANDLE),("hwndTarget",w.HWND),("ptPixelLocation",w.POINT),("ptHimetricLocation",w.POINT),("ptPixelLocationRaw",w.POINT),("ptHimetricLocationRaw",w.POINT),("dwTime",w.DWORD),("historyCount",ctypes.c_uint32),("InputData",ctypes.c_int32),("dwKeyStates",w.DWORD),("PerformanceCount",ctypes.c_uint64),("ButtonChangeType",w.DWORD)]
class POINTER_PEN_INFO(ctypes.Structure):
    _fields_=[("pointerInfo",POINTER_INFO),("penFlags",ctypes.c_uint32),("penMask",ctypes.c_uint32),("pressure",ctypes.c_uint32),("rotation",ctypes.c_uint32),("tiltX",ctypes.c_int32),("tiltY",ctypes.c_int32)]
class POINTER_TOUCH_INFO(ctypes.Structure):
    _fields_=[("pointerInfo",POINTER_INFO),("touchFlags",ctypes.c_uint32),("touchMask",ctypes.c_uint32),("rcContact",w.RECT),("rcContactRaw",w.RECT),("orientation",ctypes.c_uint32),("pressure",ctypes.c_uint32)]
class UNION(ctypes.Union): _fields_=[("pen",POINTER_PEN_INFO),("touch",POINTER_TOUCH_INFO)]
class POINTER_TYPE_INFO(ctypes.Structure): _fields_=[("type",w.DWORD),("data",UNION)]

class Injector:
    PT=3; NEW=1; INRANGE=2; CONTACT=4; BTN1=16; DOWN=0x10000; UPDATE=0x20000; UP=0x40000
    def __init__(self, settings):
        self.settings = settings; self.u = ctypes.windll.user32
        self.u.SetProcessDPIAware(); self.sw=self.u.GetSystemMetrics(0); self.sh=self.u.GetSystemMetrics(1)
        self.u.CreateSyntheticPointerDevice.restype=ctypes.c_void_p
        self.u.CreateSyntheticPointerDevice.argtypes=[w.DWORD,ctypes.c_ulong,w.DWORD]
        self.u.InjectSyntheticPointerInput.argtypes=[ctypes.c_void_p,ctypes.c_void_p,w.DWORD]
        self.device=self.u.CreateSyntheticPointerDevice(self.PT,1,1)
        if not self.device: raise RuntimeError("Could not create pen device. Windows 10 1809+ required.")
    def inject(self, flags, x, y, pressure=0):
        c=self.settings.copy(); px=int((c["x"]+min(max(x,0),1)*c["w"])*self.sw); py=int((c["y"]+min(max(y,0),1)*c["h"])*self.sh)
        i=POINTER_TYPE_INFO(); i.type=self.PT; p=i.data.pen; p.pointerInfo.pointerType=self.PT; p.pointerInfo.pointerId=0; p.pointerInfo.pointerFlags=flags; p.pointerInfo.ptPixelLocation.x=px; p.pointerInfo.ptPixelLocation.y=py; p.penMask=1; p.pressure=int(max(0,min(1,pressure))*1024)
        self.u.InjectSyntheticPointerInput(self.device,ctypes.byref(i),1)

class Server:
    def __init__(self, settings, event): self.settings,self.event=settings,event; self.thread=self.loop=self.runner=self.pen=None; self.ready=threading.Event(); self.error=None
    @property
    def running(self): return bool(self.thread and self.thread.is_alive() and not self.error)
    def start(self):
        self.error=None; self.ready.clear(); self.thread=threading.Thread(target=self.run,daemon=True); self.thread.start(); self.ready.wait(4); return self.running
    def stop(self):
        if self.loop and self.thread and self.thread.is_alive(): self.loop.call_soon_threadsafe(self.loop.stop); self.thread.join(3)
        self.thread=self.loop=self.runner=self.pen=None
    def run(self):
        self.loop=asyncio.new_event_loop(); asyncio.set_event_loop(self.loop)
        try:
            self.pen=Injector(self.settings); app=web.Application(client_max_size=16384); app.router.add_get("/",self.index); app.router.add_get("/ws",self.ws)
            self.runner=web.AppRunner(app,access_log=None); self.loop.run_until_complete(self.runner.setup()); self.loop.run_until_complete(web.TCPSite(self.runner,"0.0.0.0",int(self.settings.get("port"))).start()); self.ready.set(); self.loop.run_forever()
        except Exception as exc: self.error=str(exc); self.event("error",self.error); self.ready.set()
        finally:
            if self.runner: self.loop.run_until_complete(self.runner.cleanup())
            self.loop.close(); self.event("stopped","")
    async def index(self, request): return web.FileResponse(RESOURCE / "index.html")
    async def ws(self, request):
        ws=web.WebSocketResponse(heartbeat=20); await ws.prepare(request); self.event("client","Phone connected"); last=(0,0); down=inrange=False
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT: continue
                try:
                    d=json.loads(msg.data); kind=d["type"]
                    if kind=="size":
                        aw,ah=float(d["w"]),float(d["h"])
                        if aw>0 and ah>0: self.settings.update(aspect=aw/ah); self.event("aspect","")
                        continue
                    x,y,p=float(d["x"]),float(d["y"]),float(d.get("p",0))
                except (KeyError,TypeError,ValueError,json.JSONDecodeError): continue
                last=(x,y); pen=self.pen
                if kind=="hover": pen.inject(pen.INRANGE|pen.UPDATE|(0 if inrange else pen.NEW),x,y); inrange=True
                elif kind=="down": pen.inject(pen.INRANGE|pen.CONTACT|pen.BTN1|pen.DOWN|(0 if inrange else pen.NEW),x,y,p); down=inrange=True
                elif kind=="move" and down: pen.inject(pen.INRANGE|pen.CONTACT|pen.BTN1|pen.UPDATE,x,y,p)
                elif kind=="up" and down:
                    pen.inject(pen.INRANGE|pen.UP,x,y); down=False
                    if not d.get("pen",False): pen.inject(pen.UPDATE,x,y); inrange=False
                elif kind=="leave" and inrange and not down: pen.inject(pen.UPDATE,x,y); inrange=False
        finally:
            if self.pen:
                if down: self.pen.inject(self.pen.INRANGE|self.pen.UP,*last)
                if inrange: self.pen.inject(self.pen.UPDATE,*last)
            self.event("client","Phone disconnected")
        return ws

class MapEditor:
    PAD=20; CW=560
    def __init__(self, app):
        self.app=app; self.s=app.settings; self.win=tk.Toplevel(app.root); self.win.title("Phone drawing area"); self.win.transient(app.root); self.ch=int(self.CW*app.sh/app.sw); self.canvas=tk.Canvas(self.win,width=self.CW+40,height=self.ch+40,bg="#1d2128",highlightthickness=0); self.canvas.pack(); self.lock=tk.BooleanVar(value=self.s.get("lock")); self.state={}
        bar=ttk.Frame(self.win,padding=8); bar.pack(fill="x"); ttk.Checkbutton(bar,text="Lock phone aspect ratio",variable=self.lock,command=self.toggle).pack(side="left"); ttk.Button(bar,text="Fit",command=self.fit).pack(side="right"); ttk.Button(bar,text="Full screen",command=self.full).pack(side="right",padx=6); self.info=ttk.Label(self.win,padding=(10,0,10,10)); self.info.pack(fill="x")
        self.canvas.bind("<Button-1>",self.press); self.canvas.bind("<B1-Motion>",self.drag); self.canvas.bind("<ButtonRelease-1>",lambda e:self.s.update()); self.draw(); self.refresh()
    def ratio(self): return self.app.sw/((self.s.get("aspect") or 2)*self.app.sh)
    def rect(self,c=None):
        c=c or self.s.copy(); return self.PAD+c["x"]*self.CW,self.PAD+c["y"]*self.ch,self.PAD+(c["x"]+c["w"])*self.CW,self.PAD+(c["y"]+c["h"])*self.ch
    def draw(self):
        self.canvas.delete("all"); p=self.PAD; self.canvas.create_rectangle(p,p,p+self.CW,p+self.ch,fill="#343b45",outline="#718096"); self.canvas.create_text(p+8,p+8,anchor="nw",fill="#b8c2cc",text="Desktop display"); x0,y0,x1,y1=self.rect(); self.canvas.create_rectangle(x0,y0,x1,y1,fill="#2677c9",outline="white",width=2); self.canvas.create_text((x0+x1)/2,(y0+y1)/2,fill="white",text="Phone drawing area")
        for x,y in ((x0,y0),(x1,y0),(x0,y1),(x1,y1)): self.canvas.create_rectangle(x-5,y-5,x+5,y+5,fill="white",outline="#2677c9")
    def press(self,e):
        x0,y0,x1,y1=self.rect(); self.state["mode"]=None
        for corner,(x,y) in { (0,0):(x0,y0),(1,0):(x1,y0),(0,1):(x0,y1),(1,1):(x1,y1)}.items():
            if abs(e.x-x)<=9 and abs(e.y-y)<=9: self.state["mode"]=("corner",*corner); break
        if not self.state["mode"] and x0<=e.x<=x1 and y0<=e.y<=y1: self.state["mode"]=("move",)
        self.state["start"]=self.s.copy(); self.state["mouse"]=((e.x-self.PAD)/self.CW,(e.y-self.PAD)/self.ch)
    def drag(self,e):
        m=self.state.get("mode")
        if not m:return
        mx,my=(e.x-self.PAD)/self.CW,(e.y-self.PAD)/self.ch; c=self.state["start"]; x,y,ww,hh=c["x"],c["y"],c["w"],c["h"]
        if m[0]=="move": v={"x":min(max(x+mx-self.state["mouse"][0],0),1-ww),"y":min(max(y+my-self.state["mouse"][1],0),1-hh)}
        else:
            _,cx,cy=m; ax,ay=x+(1-cx)*ww,y+(1-cy)*hh; ww=max(.03,(mx-ax) if cx else (ax-mx)); hh=max(.03,(my-ay) if cy else (ay-my)); maxw,maxh=((1-ax) if cx else ax),((1-ay) if cy else ay)
            if self.lock.get(): r=self.ratio(); ww=min(max(ww,hh/r),maxw,maxh/r); hh=ww*r
            else: ww,hh=min(ww,maxw),min(hh,maxh)
            v={"x":ax if cx else ax-ww,"y":ay if cy else ay-hh,"w":ww,"h":hh}
        self.s.update(**v); self.draw()
    def fit(self):
        r=self.ratio(); ww=min(1,1/r); self.s.update(w=ww,h=ww*r,x=(1-ww)/2,y=(1-ww*r)/2); self.draw()
    def full(self): self.lock.set(False); self.s.update(x=0,y=0,w=1,h=1,lock=False); self.draw()
    def toggle(self):
        self.s.update(lock=self.lock.get())
        if self.lock.get():
            c=self.s.copy(); r=self.ratio(); ww=min(c["w"],1,1/r); self.s.update(w=ww,h=ww*r,x=min(c["x"],1-ww),y=min(c["y"],1-ww*r))
        self.draw()
    def refresh(self):
        if not self.win.winfo_exists():return
        a=self.s.get("aspect"); self.info.config(text=f"Phone aspect ratio: {a:.2f}" if a else "Open phone page to detect aspect ratio"); self.win.after(400,self.refresh)

def local_ip():
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try: s.connect(("8.8.8.8",80)); return s.getsockname()[0]
    except OSError: return "127.0.0.1"
    finally: s.close()

class App:
    def __init__(self):
        self.settings=Settings(); self.events=queue.Queue(); self.root=tk.Tk(); self.root.title("Phone Tablet"); self.root.minsize(580,400); self.root.protocol("WM_DELETE_WINDOW",self.close); u=ctypes.windll.user32; u.SetProcessDPIAware(); self.sw,self.sh=u.GetSystemMetrics(0),u.GetSystemMetrics(1); self.server=Server(self.settings,self.event); self.build(); self.root.after(100,self.drain)
    def build(self):
        st=ttk.Style(self.root); st.configure("Title.TLabel",font=("Segoe UI",18,"bold")); st.configure("Muted.TLabel",foreground="#5d6773"); box=ttk.Frame(self.root,padding=24); box.pack(fill="both",expand=True); ttk.Label(box,text="Phone Tablet",style="Title.TLabel").pack(anchor="w"); ttk.Label(box,text="Use phone and S Pen as precise Windows pen input.",style="Muted.TLabel").pack(anchor="w",pady=(2,20))
        card=ttk.LabelFrame(box,text=" Server ",padding=16); card.pack(fill="x"); self.status=ttk.Label(card,text="● Stopped",foreground="#9b2c2c",font=("Segoe UI",11,"bold")); self.status.grid(row=0,column=0,sticky="w"); self.address=ttk.Label(card,text="Start server to get phone address",style="Muted.TLabel"); self.address.grid(row=1,column=0,sticky="w",pady=(6,0)); b=ttk.Frame(card); b.grid(row=0,column=1,rowspan=2,sticky="e"); self.start=ttk.Button(b,text="Start server",command=self.start_server); self.start.pack(side="left"); self.stop=ttk.Button(b,text="Stop",command=self.stop_server,state="disabled"); self.stop.pack(side="left",padx=(8,0)); card.columnconfigure(0,weight=1)
        setting=ttk.LabelFrame(box,text=" Settings ",padding=16); setting.pack(fill="x",pady=(16,0)); ttk.Button(setting,text="Set phone drawing area",command=lambda:MapEditor(self)).grid(row=0,column=0,sticky="w"); self.port=tk.StringVar(value=str(self.settings.get("port"))); ttk.Label(setting,text="Port").grid(row=0,column=1,sticky="e",padx=(30,8)); ttk.Entry(setting,textvariable=self.port,width=8).grid(row=0,column=2,sticky="w"); ttk.Label(setting,text="Change port before starting server.",style="Muted.TLabel").grid(row=1,column=1,columnspan=2,sticky="w",padx=(30,0)); ttk.Label(box,text="Phone and PC must use same Wi-Fi network.",style="Muted.TLabel").pack(anchor="w",pady=(20,0))
    def event(self,k,v): self.events.put((k,v))
    def drain(self):
        while True:
            try:k,v=self.events.get_nowait()
            except queue.Empty:break
            if k=="client" and self.server.running:self.status.config(text=f"● Running — {v}",foreground="#1f7a46")
            elif k=="error":self.status.config(text="● Could not start",foreground="#9b2c2c");self.address.config(text=v);self.start.config(state="normal");self.stop.config(state="disabled")
        self.root.after(100,self.drain)
    def start_server(self):
        try:
            p=int(self.port.get()); assert 1<=p<=65535
        except (ValueError,AssertionError): messagebox.showerror("Invalid port","Use port from 1 to 65535."); return
        self.settings.update(port=p); self.start.config(state="disabled"); self.status.config(text="● Starting…",foreground="#896a11"); self.root.update_idletasks()
        if self.server.start(): self.status.config(text="● Running — waiting for phone",foreground="#1f7a46"); self.address.config(text=f"Open on phone: http://{local_ip()}:{p}"); self.stop.config(state="normal")
        else:self.start.config(state="normal")
    def stop_server(self): self.stop.config(state="disabled"); self.server.stop(); self.status.config(text="● Stopped",foreground="#9b2c2c"); self.address.config(text="Start server to get phone address"); self.start.config(state="normal")
    def close(self): self.stop_server(); self.root.destroy()

if __name__=="__main__": App().root.mainloop()
