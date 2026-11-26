#!/usr/bin/env python3
"""DairyNexus generic weighing-scale bridge.

Reads text/number output from USB/RS232 serial scales, detects stable weight,
and emits one JSON event per weighing. This is a generic bridge; scale-specific
protocols may require an adapter/parser.

Examples:
  python tools/weighing_scale_bridge.py --list-ports
  python tools/weighing_scale_bridge.py --port COM3 --raw
  python tools/weighing_scale_bridge.py --port COM3 --baud 9600 --unit kg

JSON events are printed to stdout. Diagnostics go to stderr.
"""
import argparse
import json
import re
import sys
import time
from collections import deque

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("Missing pyserial. Install with: pip install pyserial", file=sys.stderr)
    raise SystemExit(2)

NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:[.,]\d*)?|[.,]\d+)")


def list_serial_ports():
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports detected.")
        return
    for p in ports:
        print(f"{p.device}\t{p.description}\t{p.hwid}")


def parse_weight(line: str):
    """Extract weight from common scale text such as 'ST,GS, 12.34 kg' or '12,34'."""
    text = line.strip()
    if not text:
        return None
    # Prefer number followed by an explicit kg/g/lb unit.
    match = re.search(r"([-+]?(?:\d+(?:[.,]\d*)?|[.,]\d+))\s*(kg|kgs|g|lb|lbs)", text, re.I)
    if match:
        value = float(match.group(1).replace(",", "."))
        unit = match.group(2).lower()
        if unit in {"g"}:
            value /= 1000.0
        elif unit in {"lb", "lbs"}:
            value *= 0.45359237
        return value
    # Otherwise use the last numeric token, allowing comma decimals.
    numbers = NUMBER_RE.findall(text)
    if not numbers:
        return None
    try:
        return float(numbers[-1].replace(",", "."))
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser(description="DairyNexus weighing scale bridge")
    parser.add_argument("--list-ports", action="store_true")
    parser.add_argument("--port")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--unit", choices=["kg", "g", "lb"], default="kg",
                      help="Unit for numeric readings without unit labels")
    parser.add_argument("--stable-seconds", type=float, default=2.0,
                      help="How long readings must remain stable before capture")
    parser.add_argument("--tolerance-kg", type=float, default=0.03,
                      help="Maximum range within stability window, in kg")
    parser.add_argument("--min-weight-kg", type=float, default=0.05)
    parser.add_argument("--rearm-kg", type=float, default=0.02,
                      help="Scale must return near zero before another capture")
    parser.add_argument("--raw", action="store_true", help="Include raw serial lines in JSON events")
    args = parser.parse_args()

    if args.list_ports:
        list_serial_ports()
        return
    if not args.port:
        parser.error("Use --list-ports or specify --port COMx")

    window = deque()
    last_weight = None
    captured = False
    zero_since = None
    print(f"Connecting to {args.port} ({args.baud} baud)...", file=sys.stderr)

    try:
        with serial.Serial(args.port, args.baud, timeout=args.timeout) as ser:
            print("Connected. Waiting for stable weight; Ctrl+C to stop.", file=sys.stderr)
            while True:
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                weight = parse_weight(line)
                if weight is None:
                    if args.raw:
                        print(json.dumps({"type": "scale_raw", "port": args.port, "line": line}))
                    continue

                # Convert bare numeric values to kg. Explicit-unit values were normalized in parse_weight.
                if not re.search(r"\b(kg|kgs|g|lb|lbs)\b", line, re.I):
                    if args.unit == "g":
                        weight /= 1000.0
                    elif args.unit == "lb":
                        weight *= 0.45359237

                now = time.monotonic()
                last_weight = weight
                if abs(weight) <= args.rearm_kg:
                    window.clear()
                    zero_since = now
                    captured = False
                    continue
                zero_since = None
                if weight < args.min_weight_kg:
                    window.clear()
                    continue

                window.append((now, weight, line))
                while window and now - window[0][0] > max(args.stable_seconds * 2, 4.0):
                    window.popleft()

                if len(window) < 2:
                    continue
                values = [item[1] for item in window]
                if max(values) - min(values) > args.tolerance_kg:
                    continue
                if now - window[0][0] < args.stable_seconds or captured:
                    continue

                stable_kg = sum(values) / len(values)
                event = {
                    "type": "milk_weight_captured",
                    "timestamp": time.time(),
                    "port": args.port,
                    "weight_kg": round(stable_kg, 3),
                    "unit": "kg",
                    "stable": True,
                    "source": "serial_scale",
                }
                if args.raw:
                    event["raw_line"] = line
                print(json.dumps(event, ensure_ascii=False), flush=True)
                print(f"Captured stable weight: {stable_kg:.3f} kg. Remove container to re-arm.", file=sys.stderr)
                captured = True
                window.clear()

    except serial.SerialException as exc:
        print(f"Serial connection error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nScale bridge stopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
