#!/usr/bin/env python3
"""Compare a KiCad-exported netlist (kicadsexpr) with design.py, pin by pin."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from design import PARTS, netmap  # noqa: E402

txt = open(sys.argv[1]).read()
got = {}
for m in re.finditer(r'\(net \(code "\d+"\) \(name "([^"]+)"\)(.*?)\)\s*(?=\(net \(code|\)\s*\)\s*$)', txt, re.S):
    name = m.group(1).lstrip("/")
    nodes = set(re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', m.group(2)))
    nodes = {n for n in nodes if not n[0].startswith("#")}
    if nodes:
        got[name] = nodes
want = netmap()
ok = True
for n, nodes in want.items():
    if got.get(n) != nodes:
        ok = False
        print("MISMATCH", n, "want", sorted(nodes), "got", sorted(got.get(n, [])))
for n in got:
    if n not in want:
        ok = False
        print("EXTRA NET", n, sorted(got[n]))
comps = set(re.findall(r'\(comp \(ref "([^"#][^"]*)"\)', txt))
fps = dict(re.findall(r'\(comp \(ref "([^"]+)"\).*?\(footprint "([^"]+)"\)', txt, re.S))
for ref, val, sym, fp, pins in PARTS:
    if ref not in comps:
        ok = False; print("MISSING COMPONENT", ref)
    elif fps.get(ref) != "Piezo_PCB:" + fp:
        ok = False; print("FOOTPRINT", ref, fps.get(ref))
print(f"{len(want)} nets, {sum(len(v) for v in want.values())} pins, {len(PARTS)} parts:", "MATCH" if ok else "ERRORS")
