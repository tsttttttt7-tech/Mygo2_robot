#!/usr/bin/env python3
"""Generate the Rev D KiCad 7 schematic (label-based, same style as Rev C) from design.py."""
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(__file__))
from design import PARTS, UNIT_PINS  # noqa: E402

PRJ = "Piezo_MCP6002_RevD"
OUT = os.path.join(os.path.dirname(__file__), "..", PRJ)
LIB = os.path.join(OUT, "Piezo_Local.kicad_sym")
ROOT = str(uuid.uuid4())
G = 2.54

SJ_SYMBOL = '''  (symbol "SJ_H" (pin_names (offset 0.508) hide) (in_bom yes) (on_board yes) (property "Reference" "JP" (at 0 0 0) (effects (font (size 1.7780 1.7780)) )) (property "Value" "SJ_H" (at 0 0 0) (effects (font (size 1.7780 1.7780)) )) (symbol "SJ_H_1_1" (arc (start -0.2540 1.2700) (mid -1.5240 0) (end -0.2540 -1.2700) (stroke (width 0.254) (type default)) (fill (type outline)))(polyline (pts (xy -0.2540 1.2700)(xy -0.2540 -1.2700)) (stroke (width 0.254) (type default)) (fill (type none)))(arc (start 0.2540 -1.2700) (mid 1.5240 0) (end 0.2540 1.2700) (stroke (width 0.254) (type default)) (fill (type outline)))(polyline (pts (xy 0.2540 1.2700)(xy 0.2540 -1.2700)) (stroke (width 0.254) (type default)) (fill (type none)))(pin passive line (at -5.0800 0.0000 0) (length 3.5560) (name "~" (effects (font (size 1.4224 1.4224)) )) (number "1" (effects (font (size 1.4224 1.4224)) )))(pin passive line (at 5.0800 0.0000 180) (length 3.5560) (name "~" (effects (font (size 1.4224 1.4224)) )) (number "2" (effects (font (size 1.4224 1.4224)) )))))
'''


def u():
    return str(uuid.uuid4())


def snap(v):
    return round(v / G) * G


def lib_text():
    s = open(LIB).read()
    if '(symbol "SJ_H"' not in s:
        s = s.rstrip()
        assert s.endswith(")")
        s = s[:-1] + SJ_SYMBOL + ")\n"
        open(LIB, "w").write(s)
    return s


def top_symbols(s):
    """name -> block text of each top-level symbol in a .kicad_sym file."""
    starts = [(m.start(), m.group(1)) for m in re.finditer(r'\(symbol "([^"]+)"', s)
              if not re.search(r"_\d+_\d+$", m.group(1))]
    out = {}
    for i, (pos, name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(s)
        blk = s[pos:end].rstrip()
        out[name] = blk[:-1].rstrip() if i + 1 == len(starts) else blk   # drop the library's closing paren
    return out


def pins_of(block):
    pins = {}
    for m in re.finditer(r'\(symbol "[^"]+_(\d+)_\d+"(.*?)(?=\(symbol "|$)', block, re.S):
        unit = int(m.group(1))
        for p in re.finditer(r'\(pin \w+ \w+ \(at ([-\d.]+) ([-\d.]+) (\d+)\).*?\(number "([^"]+)"', m.group(2)):
            pins[(unit, p.group(4))] = (float(p.group(1)), float(p.group(2)), int(p.group(3)))
    return pins


def main():
    s = lib_text()
    syms = top_symbols(s)
    needed = sorted({p[2] for p in PARTS} | {"PWR_FLAG"})
    lib_syms = []
    for n in needed:
        blk = syms[n]
        lib_syms.append(blk.replace(f'(symbol "{n}"', f'(symbol "Piezo_Local:{n}"', 1))
    pinpos = {n: pins_of(syms[n]) for n in needed}

    items = []

    def text(t, x, y, size=2.3114):
        items.append(f'(text "{t}" (at {x:.4f} {y:.4f} 0) (effects (font (size {size} {size})) (justify left top)) (uuid "{u()}"))')

    def place(ref, value, sym, fp, pins, unit, x, y, unit_pins=None):
        x, y = snap(x), snap(y)
        items.append(
            f'(symbol (lib_id "Piezo_Local:{sym}") (at {x:.4f} {y:.4f} 0) (unit {unit})\n'
            f' (in_bom yes) (on_board yes) (dnp no) (uuid "{u()}")\n'
            f' (property "Reference" "{ref}" (at {x:.4f} {y - 7.62:.4f} 0) (effects (font (size 1.6002 1.6002)) ))\n'
            f' (property "Value" "{value}" (at {x:.4f} {y + 10.16:.4f} 0) (effects (font (size 1.5113 1.5113)) ))\n'
            f' (property "Footprint" "{("Piezo_PCB:" + fp) if fp else ""}" (at {x:.4f} {y:.4f} 0) (effects (font (size 1.7780 1.7780)) hide))\n'
            f' (instances (project "{PRJ}" (path "/{ROOT}" (reference "{ref}") (unit {unit})))))')
        for pn in (unit_pins or pins.keys()):
            px, py, ang = pinpos[sym][(unit, pn)]
            ex, ey = x + px, y - py                       # schematic Y points down
            dx, dy = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[ang]
            lx, ly = ex + dx * G, ey + dy * G
            items.append(f'(wire (pts (xy {ex:.4f} {ey:.4f}) (xy {lx:.4f} {ly:.4f})) (stroke (width 0) (type default)) (uuid "{u()}"))')
            rot, just = {(-1, 0): (180, "right bottom"), (1, 0): (0, "left bottom"),
                         (0, -1): (90, "left bottom"), (0, 1): (270, "right bottom")}[(dx, dy)]
            items.append(f'(label "{pins[pn]}" (at {lx:.4f} {ly:.4f} {rot}) (effects (font (size 1.5113 1.5113)) (justify {just})) (uuid "{u()}"))')

    P = {p[0]: p for p in PARTS}
    layout = [
        ("1   PIEZO INPUT, PROTECTION AND GAIN (gain 11 with JP1 closed, 48 with JP1 open)", 30, 45,
         [("J1", 1, 40, 70), ("R1", 1, 70, 70), ("R2", 1, 100, 72), ("D1", 1, 125, 72), ("D1", 2, 145, 72),
          ("U1", 1, 185, 70), ("R4", 1, 225, 72), ("R3", 1, 255, 70), ("R14", 1, 290, 70), ("JP1", 1, 325, 70),
          ("C5", 1, 360, 70)]),
        ("2   HALF-SUPPLY REFERENCE (VREF = AVDD/2)", 30, 100,
         [("R5", 1, 45, 125), ("R6", 1, 75, 125), ("C4", 1, 105, 125), ("U1", 2, 145, 125)]),
        ("3   4TH-ORDER BUTTERWORTH LOW-PASS ~15 kHz (stage 1 Q=0.55 f0=16.0k, stage 2 Q=1.30 f0=15.7k)", 190, 100,
         [("R8", 1, 205, 125), ("R9", 1, 240, 125), ("C8", 1, 275, 125), ("C9", 1, 305, 127), ("U2", 1, 345, 125)]),
        ("", 30, 155,
         [("R10", 1, 45, 175), ("R11", 1, 80, 175), ("C10", 1, 115, 175), ("C11", 1, 145, 177), ("U2", 2, 185, 175)]),
        ("4   OUTPUTS: J3 DC-coupled to ESP32-S3 GPIO1 (ADC1_CH0); J4 AC-coupled to PCM1808 L input", 230, 155,
         [("R7", 1, 245, 175), ("C6", 1, 275, 177), ("J3", 1, 300, 175), ("C7", 1, 330, 175), ("R13", 1, 360, 175),
          ("J4", 1, 390, 175)]),
        ("5   POWER: regulated 3.3 V from the ESP32 board; R12/C3 filter; C2/C12 at pin 8 of U1/U2", 30, 205,
         [("J2", 1, 40, 228), ("R12", 1, 70, 228), ("C3", 1, 100, 230), ("C2", 1, 125, 230), ("C12", 1, 150, 230),
          ("U1", 3, 185, 230), ("U2", 3, 215, 230)]),
    ]
    for title, tx, ty, plist in layout:
        if title:
            text(title, tx, ty)
        for ref, unit, x, y in plist:
            r, val, sym, fp, pins = P[ref]
            up = UNIT_PINS.get(sym, {}).get(unit)
            place(ref, val, sym, fp, pins, unit, x, y, up)
    # power flags
    for i, (net, x) in enumerate((("V33", 255), ("GND", 285), ("AVDD", 315))):
        place(f"#FLG0{i + 1}", "PWR_FLAG", "PWR_FLAG", "", {"1": net}, 1, x, 235)

    text("PIEZO VIBRATION FRONT END  /  REV D", 15.24, 12.7, 3.556)
    text("3.3 V  |  one piezo  |  gain 11/48 (JP1)  |  4-pole Butterworth ~15 kHz  |  ESP32-S3 ADC 80 kS/s or PCM1808 48 kS/s",
         15.24, 22.86, 1.9558)
    text("Rev D vs Rev C: C1 removed (piezo blocks DC); BAV199 -> BAV99 (available in Baghdad); E24 filter values; "
         "R14 + JP1 gain select; C5 47p; separate DC (J3) and AC (J4) outputs.", 15.24, 270, 1.9558)
    text("DESIGN STATUS: calculated prototype, not bench-validated. All filter capacitors C0G/NP0 or film.", 15.24, 280, 1.9558)

    sch = (f'(kicad_sch (version 20230121) (generator eeschema) (uuid "{ROOT}") (paper "User" 420 297) '
           f'(title_block (title "Piezo front end | MCP6002 | Rev D") (date "2026-11-24") (rev "D") '
           f'(comment 1 "Two dual op-amps; gain 11/48; 4-pole 15 kHz low-pass; verify on bench"))\n'
           f'(lib_symbols\n' + "\n".join(lib_syms) + '\n)\n' + "\n".join(items) + '\n)\n')
    open(os.path.join(OUT, f"{PRJ}.kicad_sch"), "w").write(sch)
    print("schematic written,", len(items), "items")


if __name__ == "__main__":
    main()
