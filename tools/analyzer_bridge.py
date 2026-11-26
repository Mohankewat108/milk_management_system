#!/usr/bin/env python3
"""
DairyNexus Milk Analyzer Bridge
==============================

Purpose
-------
Read milk analyzer measurements through USB/RS232 serial connections and
convert incoming analyzer fields into DairyNexus standard field names.

Supported connection types
------------------------
- USB-to-serial adapters
- RS232 serial connections
- COM ports on Windows
- Serial devices on Linux

IMPORTANT
--------
Milk analyzer communication protocols vary by manufacturer and model.

This bridge provides:
1. Serial connection handling
2. Port discovery
3. Basic text parsing
4. Analyzer field mapping
5. Basic measurement validation
6. JSON output

A model-specific protocol decoder may still be required for a real analyzer.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

import argparse
import json
import re
import sys
import time
from typing import Dict, Optional, Any

try:
    import serial
    from serial.tools import list_ports

except ImportError:
    print(
        "Missing dependency: pyserial\n"
        "Install it using:\n"
        "pip install pyserial",
        file=sys.stderr,
    )
    raise SystemExit(2)


# ============================================================
# 2. DAIRYNEXUS FIELD MAPPING
# ============================================================
#
# Analyzer devices may use different field names for the same
# measurement.
#
# This section converts analyzer field names into standardized
# DairyNexus field names.
#
# Example:
#
#   FAT=4.2;SNF=8.7;LAC=4.8
#
# Becomes:
#
#   {
#       "fat": 4.2,
#       "snf": 8.7,
#       "lactose": 4.8
#   }
#
# Keys are normalized to lowercase before mapping.
# ============================================================

FIELD_ALIASES = {

    # --------------------------------------------------------
    # Milk quantity / volume
    # --------------------------------------------------------
    "litres": "quantity_litres",
    "liters": "quantity_litres",
    "litre": "quantity_litres",
    "liter": "quantity_litres",
    "volume": "quantity_litres",
    "qty": "quantity_litres",
    "quantity": "quantity_litres",

    # --------------------------------------------------------
    # Fat
    # --------------------------------------------------------
    "fat": "fat",
    "f": "fat",

    # --------------------------------------------------------
    # SNF - Solids Not Fat
    # --------------------------------------------------------
    "snf": "snf",
    "solidsnotfat": "snf",

    # --------------------------------------------------------
    # Lactose
    # --------------------------------------------------------
    "lac": "lactose",
    "lact": "lactose",
    "lactose": "lactose",

    # --------------------------------------------------------
    # Protein
    # --------------------------------------------------------
    "pro": "protein",
    "prot": "protein",
    "protein": "protein",

    # --------------------------------------------------------
    # Density
    # --------------------------------------------------------
    "den": "density",
    "dens": "density",
    "density": "density",

    # --------------------------------------------------------
    # Temperature
    # --------------------------------------------------------
    "temp": "temperature",
    "temperature": "temperature",
    "t": "temperature",

    # --------------------------------------------------------
    # Water
    # --------------------------------------------------------
    "water": "water",
    "addedwater": "water",

    # --------------------------------------------------------
    # Freezing point
    # --------------------------------------------------------
    "fp": "freezing_point",
    "freezingpoint": "freezing_point",
}


# ============================================================
# 3. REQUIRED DAIRYNEXUS MEASUREMENTS
# ============================================================
#
# A valid milk analyzer reading must contain at least:
#
# - Fat
# - SNF
#
# Other measurements are optional because analyzer models may
# provide different data.
# ============================================================

REQUIRED_FIELDS = {
    "fat",
    "snf",
}


# ============================================================
# 4. MEASUREMENT VALIDATION RULES
# ============================================================
#
# These are basic sanity limits.
#
# They are NOT official milk quality limits or laboratory
# calibration standards.
# ============================================================

VALIDATION_RANGES = {

    "fat": (0.0, 15.0),
    "snf": (0.0, 20.0),
    "lactose": (0.0, 15.0),
    "protein": (0.0, 15.0),
    "density": (0.0, 2.0),
    "temperature": (-10.0, 100.0),
    "quantity_litres": (0.0, 10000.0),
    "water": (0.0, 100.0),
}


# ============================================================
# 5. SERIAL PORT DISCOVERY
# ============================================================

def list_serial_ports() -> None:
    """
    Detect and display available serial ports.

    Example output:
        COM3    USB Serial Device
        COM6    Bluetooth Serial Port
    """

    ports = list(list_ports.comports())

    if not ports:
        print("No serial ports detected.")
        return

    print("\nAvailable Serial Ports")
    print("=" * 70)

    for port in ports:
        print(f"Port        : {port.device}")
        print(f"Description : {port.description}")
        print(f"Hardware ID: {port.hwid}")
        print("-" * 70)


# ============================================================
# 6. FIELD NAME NORMALIZATION
# ============================================================

def normalize_field_name(field_name: str) -> str:
    """
    Normalize an analyzer field name.

    Examples:
        FAT       -> fat
        SNF       -> snf
        Lactose   -> lactose
        Added Water -> addedwater
    """

    return re.sub(
        r"[^a-z]",
        "",
        field_name.lower().strip()
    )


# ============================================================
# 7. VALUE CONVERSION
# ============================================================

def convert_numeric_value(value: str) -> Optional[float]:
    """
    Convert analyzer text into a floating-point number.

    Supports:
        4.2
        4,2

    Returns:
        float or None
    """

    try:
        value = value.strip().replace(",", ".")
        return float(value)

    except (ValueError, TypeError):
        return None


# ============================================================
# 8. ANALYZER DATA PARSER
# ============================================================
#
# Supported example formats:
#
#   FAT=4.2;SNF=8.7;LAC=4.8
#
#   FAT:4.2,SNF:8.7,LAC:4.8
#
#   FAT=4.2 | SNF=8.7 | LAC=4.8
#
# This is a generic text parser.
# Actual analyzer protocols may use binary data or other formats.
# ============================================================

def parse_analyzer_line(line: str) -> Dict[str, float]:
    """
    Parse one analyzer output line and map fields to DairyNexus.

    Parameters:
        line:
            Raw serial output from the analyzer.

    Returns:
        Dictionary containing mapped DairyNexus measurements.
    """

    measurements = {}

    # Split incoming data by common delimiters.
    items = re.split(r"[;,|\t]+", line.strip())

    for item in items:

        item = item.strip()

        if not item:
            continue

        # Accept KEY=VALUE or KEY:VALUE.
        if "=" not in item and ":" not in item:
            continue

        try:

            field_name, raw_value = re.split(
                r"[=:]",
                item,
                maxsplit=1
            )

        except ValueError:
            continue

        # Normalize analyzer field name.
        normalized_key = normalize_field_name(field_name)

        # Ignore unknown fields.
        if normalized_key not in FIELD_ALIASES:
            continue

        # Map analyzer field to DairyNexus field.
        dairy_field = FIELD_ALIASES[normalized_key]

        # Convert value to numeric.
        numeric_value = convert_numeric_value(raw_value)

        if numeric_value is None:
            continue

        measurements[dairy_field] = numeric_value

    return measurements


# ============================================================
# 9. MEASUREMENT VALIDATION
# ============================================================

def validate_measurements(
    measurements: Dict[str, float]
) -> bool:
    """
    Validate analyzer measurements.

    Required:
        fat
        snf

    Optional:
        lactose
        protein
        density
        temperature
        quantity_litres
        water

    Returns:
        True if the measurement passes basic validation.
    """

    # --------------------------------------------------------
    # Check required fields
    # --------------------------------------------------------

    if not REQUIRED_FIELDS.issubset(measurements.keys()):
        return False

    # --------------------------------------------------------
    # Validate numeric ranges
    # --------------------------------------------------------

    for field, value in measurements.items():

        if field not in VALIDATION_RANGES:
            continue

        minimum, maximum = VALIDATION_RANGES[field]

        if not minimum <= value <= maximum:
            return False

    return True


# ============================================================
# 10. JSON OUTPUT
# ============================================================

def create_reading(
    port: str,
    measurements: Dict[str, float]
) -> Dict[str, Any]:
    """
    Create a standardized DairyNexus analyzer reading.

    Example:

    {
        "type": "milk_analyzer_reading",
        "timestamp": 1234567890,
        "port": "COM3",
        "data": {
            "fat": 4.2,
            "snf": 8.7,
            "lactose": 4.8
        }
    }
    """

    return {
        "type": "milk_analyzer_reading",
        "timestamp": time.time(),
        "port": port,
        "data": measurements,
    }


# ============================================================
# 11. SERIAL READER
# ============================================================

def run_serial_reader(args) -> None:
    """
    Connect to the analyzer and continuously read serial data.
    """

    # --------------------------------------------------------
    # Configure parity
    # --------------------------------------------------------

    parity_mapping = {
        "N": serial.PARITY_NONE,
        "E": serial.PARITY_EVEN,
        "O": serial.PARITY_ODD,
    }

    parity = parity_mapping[args.parity]

    # --------------------------------------------------------
    # Connect to serial port
    # --------------------------------------------------------

    try:

        with serial.Serial(
            port=args.port,
            baudrate=args.baud,
            bytesize=args.bytesize,
            parity=parity,
            stopbits=args.stopbits,
            timeout=args.timeout,
        ) as connection:

            print(
                f"\nConnected to {args.port} "
                f"at {args.baud} baud."
            )

            print("Waiting for analyzer data...")
            print("Press CTRL+C to stop.\n")

            # ------------------------------------------------
            # Continuous reading loop
            # ------------------------------------------------

            while True:

                raw_data = connection.readline()

                if not raw_data:
                    continue

                line = raw_data.decode(
                    "utf-8",
                    errors="replace"
                ).strip()

                if not line:
                    continue

                # Parse and map analyzer fields.
                measurements = parse_analyzer_line(line)

                # Validate mapped measurements.
                if validate_measurements(measurements):

                    reading = create_reading(
                        port=args.port,
                        measurements=measurements
                    )

                    print(
                        json.dumps(
                            reading,
                            ensure_ascii=False
                        )
                    )

                # ------------------------------------------------
                # Raw mode
                # ------------------------------------------------

                elif args.raw:

                    print(
                        json.dumps(
                            {
                                "type": "raw",
                                "port": args.port,
                                "line": line,
                            },
                            ensure_ascii=False
                        )
                    )

                else:

                    print(
                        "Unrecognized or invalid analyzer data."
                        " Use --raw to inspect the output."
                    )

    except serial.SerialException as error:

        print(
            f"Serial connection error: {error}",
            file=sys.stderr
        )

        raise SystemExit(1)


# ============================================================
# 12. COMMAND LINE ARGUMENTS
# ============================================================

def build_argument_parser() -> argparse.ArgumentParser:
    """
    Create command-line configuration.
    """

    parser = argparse.ArgumentParser(
        description=(
            "DairyNexus Milk Analyzer Bridge - "
            "USB/RS232 Serial Reader"
        )
    )

    # Port selection
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="Display available COM/serial ports"
    )

    parser.add_argument(
        "--port",
        help="Serial port, e.g. COM3"
    )

    # Serial communication settings
    parser.add_argument(
        "--baud",
        type=int,
        default=9600,
        help="Baud rate (default: 9600)"
    )

    parser.add_argument(
        "--bytesize",
        type=int,
        choices=[5, 6, 7, 8],
        default=8,
        help="Data bits"
    )

    parser.add_argument(
        "--parity",
        choices=["N", "E", "O"],
        default="N",
        help="Parity: None, Even, Odd"
    )

    parser.add_argument(
        "--stopbits",
        type=float,
        choices=[1, 1.5, 2],
        default=1,
        help="Stop bits"
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="Serial read timeout"
    )

    # Raw output mode
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Display unrecognized analyzer output"
    )

    return parser


# ============================================================
# 13. MAIN ENTRY POINT
# ============================================================

def main() -> None:
    """
    Main program entry point.
    """

    parser = build_argument_parser()

    args = parser.parse_args()

    # Port discovery
    if args.list_ports:
        list_serial_ports()
        return

    # Require port selection
    if not args.port:
        parser.error(
            "Specify --list-ports or --port COM3"
        )

    # Start analyzer connection
    run_serial_reader(args)


# ============================================================
# 14. EXECUTION
# ============================================================

if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print("\nAnalyzer bridge stopped.")