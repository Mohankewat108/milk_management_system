#!/usr/bin/env python3
"""Local DairyNexus weighing-scale HTTP bridge (localhost only).

Start: .venv\\Scripts\\python.exe tools\\weighing_scale_api.py --serial COM3
Browser endpoints: GET /status, GET /latest
"""
import argparse, json, re, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
try:
    import serial
except ImportError:
    print("Install pyserial in the project virtualenv first.")
    raise SystemExit(2)

state = {"connected": False, "port": None, "live_kg": None, "captured_kg": None,
         "stable": False, "updated_at": None, "error": None}
lock = threading.Lock()

def serial_worker(args):
    pattern = re.compile(r"([-+]?(?:\\d+(?:[.,]\\d*)?|[.,]\\d+))\\s*(kg|kgs|g|lb|lbs)?", re.I)
    try:
        with serial.Serial(args.serial, args.baud, timeout=1) as ser:
            with lock:
                state.update(connected=True, port=args.serial, error=None)
            history = []
            captured = False
            while True:
                raw = ser.readline()
                if not raw: continue
                line = raw.decode("utf-8", errors="replace").strip()
                m = pattern.search(line)
                if not m: continue
                value = float(m.group(1).replace(",", "."))
                unit = (m.group(2) or args.unit).lower()
                if unit == "g": value /= 1000
                elif unit in ("lb", "lbs"): value *= 0.45359237
                now = time.monotonic()
                history.append((now, value))
                history = [(t,v) for t,v in history if now-t <= max(args.stable_seconds*2,4)]
                stable = len(history)>=2 and now-history[0][0]>=args.stable_seconds and max(v for _,v in history)-min(v for _,v in history)<=args.tolerance
                with lock: state.update(live_kg=round(value,3), stable=stable, updated_at=time.time())
                if value <= args.rearm:
                    history.clear(); captured=False
                    with lock: state.update(captured_kg=None, stable=False)
                elif stable and value >= args.minimum and not captured:
                    avg=sum(v for _,v in history)/len(history)
                    with lock: state.update(captured_kg=round(avg,3), stable=True)
                    captured=True
    except Exception as e:
        with lock: state.update(connected=False, error=str(e))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/status", "/latest"):
            self.send_response(404); self.end_headers(); return
        with lock: payload=dict(state)
        body=json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        origin = self.headers.get("Origin", "")
        if origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1"):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Private-Network","true")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def log_message(self, fmt, *args): pass

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--serial", required=True, help="COM port, e.g. COM3")
    p.add_argument("--baud", type=int, default=9600)
    p.add_argument("--unit", choices=["kg","g","lb"], default="kg")
    p.add_argument("--stable-seconds", type=float, default=2)
    p.add_argument("--tolerance", type=float, default=0.03)
    p.add_argument("--minimum", type=float, default=0.05)
    p.add_argument("--rearm", type=float, default=0.02)
    p.add_argument("--http-port", type=int, default=8765)
    args=p.parse_args()
    threading.Thread(target=serial_worker,args=(args,),daemon=True).start()
    print(f"Scale API listening on http://127.0.0.1:{args.http_port} (serial {args.serial})")
    HTTPServer(("127.0.0.1",args.http_port),Handler).serve_forever()

if __name__=="__main__": main()
