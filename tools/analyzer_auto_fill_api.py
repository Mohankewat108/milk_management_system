#!/usr/bin/env python3
"""Local DairyNexus milk analyzer bridge. Reads text serial data and serves latest reading on localhost."""
import argparse, json, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
try:
    import serial
except ImportError:
    raise SystemExit("Install pyserial in the project virtualenv.")

# Reuse the project's generic analyzer parser and validation.
from analyzer_bridge import parse_analyzer_line

state={"connected":False,"port":None,"data":{},"updated_at":None,"raw":None,"error":None}
lock=threading.Lock()

def serial_worker(args):
    try:
        with serial.Serial(args.serial,args.baud,timeout=1) as ser:
            with lock: state.update(connected=True,port=args.serial,error=None)
            while True:
                raw=ser.readline()
                if not raw: continue
                line=raw.decode("utf-8",errors="replace").strip()
                if not line: continue
                data=parse_analyzer_line(line)
                # Analyzer auto-fill accepts whichever quality values are present.
                if any(k in data for k in ("fat","snf","lactose")):
                    with lock: state.update(connected=True,data=data,updated_at=time.time(),raw=line,error=None)
    except Exception as e:
        with lock: state.update(connected=False,error=str(e))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/latest","/status"):
            self.send_response(404);self.end_headers();return
        with lock: payload=dict(state)
        body=json.dumps(payload).encode()
        self.send_response(200);self.send_header("Content-Type","application/json")
        origin=self.headers.get("Origin","")
        if origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1"):
            self.send_header("Access-Control-Allow-Origin",origin);self.send_header("Vary","Origin")
        self.send_header("Access-Control-Allow-Private-Network","true")
        self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(body)))
        self.end_headers();self.wfile.write(body)
    def log_message(self,*args): pass

def main():
    p=argparse.ArgumentParser(description="DairyNexus analyzer auto-fill bridge")
    p.add_argument("--serial",required=True,help="COM port, e.g. COM4")
    p.add_argument("--baud",type=int,default=9600)
    p.add_argument("--http-port",type=int,default=8766)
    args=p.parse_args()
    threading.Thread(target=serial_worker,args=(args,),daemon=True).start()
    print(f"Analyzer API listening at http://127.0.0.1:{args.http_port} (serial {args.serial})")
    HTTPServer(("127.0.0.1",args.http_port),Handler).serve_forever()
if __name__=="__main__": main()
