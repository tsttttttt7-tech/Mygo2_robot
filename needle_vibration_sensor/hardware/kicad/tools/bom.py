#!/usr/bin/env python3
"""Write BOM.csv for Rev D with Baghdad sources."""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from design import PARTS  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "Piezo_MCP6002_RevD", "BOM.csv")
NOTE = {"DIP8": "DIP-8, 7.62 mm rows; socket optional", "Header_1x02": "2.54 mm 2-pin header",
        "BAV99_SOT23": "SOT-23; pin 3 = IN, pins 1+2 = VREF", "SolderJumper_2": "solder bridge = gain 11, open = gain 44",
        "C1206": "1206 SMD", "R1206": "1206 SMD 1 %"}
KIT_R = "Ardunic resistor kit ARD-065066 (1206, 33 values, IQD 7,500)"
KIT_C = "Ardunic capacitor kit ARD-065072 (1206, 16 values, IQD 7,000)"


def source(ref, val):
    if ref.startswith("R"):
        return KIT_R
    if ref.startswith("C"):
        return KIT_C
    if val.startswith("MCP6002") or val == "BAV99":
        return "Al-Hekmh Electronics, Tahrir Sq. (alhekmh.com)"
    if ref.startswith("JP"):
        return "PCB pads, no part"
    return "any component shop"


def key(p):
    return (p[0].rstrip("0123456789"), int("".join(c for c in p[0] if c.isdigit())))


with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Reference", "Value", "Footprint", "Package note", "Baghdad source"])
    for ref, val, sym, fp, pins in sorted(PARTS, key=key):
        w.writerow([ref, val, "Piezo_PCB:" + fp, NOTE[fp], source(ref, val)])
print("BOM written:", OUT)
