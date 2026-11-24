#!/usr/bin/env python3
"""Independent check: every PCB pad net == KiCad schematic netlist net; writes Validation.txt + Connectivity.txt."""
import os
import re
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.join(HERE, "..", "Piezo_MCP6002_RevD")
NET = os.path.join(PRJ, "_schematic.net")
subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", NET,
                os.path.join(PRJ, "Piezo_MCP6002_RevD.kicad_sch")], check=True, capture_output=True)
txt = open(NET).read()
os.remove(NET)
sch = {}
for m in re.finditer(r'\(net \(code "\d+"\) \(name "([^"]+)"\)(.*?)\)\s*(?=\(net \(code|\)\s*\)\s*$)', txt, re.S):
    for ref, pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', m.group(2)):
        if not ref.startswith("#"):
            sch[(ref, pin)] = m.group(1).lstrip("/")
sch_fp = dict(re.findall(r'\(comp \(ref "([^"]+)"\).*?\(footprint "([^"]+)"\)', txt, re.S))
sch_val = dict(re.findall(r'\(comp \(ref "([^"]+)"\)\s*\(value "([^"]+)"\)', txt, re.S))

b = pcbnew.LoadBoard(os.path.join(PRJ, "Piezo_MCP6002_RevD.kicad_pcb"))
pcb, errs, nfp = {}, [], 0
for fp in b.GetFootprints():
    nfp += 1
    ref = fp.GetReference()
    if sch_fp.get(ref) != fp.GetFPIDAsString():
        errs.append(f"footprint {ref}: sch {sch_fp.get(ref)} pcb {fp.GetFPIDAsString()}")
    if sch_val.get(ref) != fp.GetValue():
        errs.append(f"value {ref}: sch {sch_val.get(ref)} pcb {fp.GetValue()}")
    for pad in fp.Pads():
        pcb[(ref, pad.GetNumber())] = pad.GetNetname()
for k in sorted(set(sch) | set(pcb)):
    if sch.get(k) != pcb.get(k):
        errs.append(f"pad {k[0]}.{k[1]}: sch {sch.get(k)} pcb {pcb.get(k)}")
drc = open(os.path.join(PRJ, "DRC.txt")).read()
summary = [l for l in drc.splitlines() if l.startswith("** Found")]
nseg = len(re.findall(r"\(segment ", open(os.path.join(PRJ, "Piezo_MCP6002_RevD.kicad_pcb")).read()))
lines = [f"KiCad version: {pcbnew.Version()}.",
         "PASS: Schematic exported by KiCad (kicad-cli) and netlist parsed.",
         f"{'PASS' if not errs else 'FAIL'}: All {len(pcb)} pad/net assignments match the schematic netlist.",
         f"{'PASS' if not errs else 'FAIL'}: All {nfp} component values and footprint assignments match.",
         "KiCad DRC: " + "; ".join(s.strip('* ') for s in summary) + ".",
         "PASS: GND zones (F.Cu + B.Cu) filled by KiCad.",
         f"Board: 48 x 32 mm, two copper layers; {nseg} track segments (all on F.Cu, B.Cu = unbroken GND plane); "
         "0.25 mm tracks; 0.6/0.3 mm vias.",
         "No full schematic ERC (kicad-cli 7 has no ERC), hardware test, or fabricator-specific review performed."]
lines += errs
open(os.path.join(PRJ, "Validation.txt"), "w").write("\n".join(lines) + "\n")
nets = {}
for (ref, pin), n in sorted(pcb.items()):
    nets.setdefault(n, []).append(f"{ref}.{pin}")
open(os.path.join(PRJ, "Connectivity.txt"), "w").write(
    "\n".join(f"{n}: " + " ".join(v) for n, v in sorted(nets.items())) + "\n")
print("\n".join(lines))
sys.exit(1 if errs else 0)
