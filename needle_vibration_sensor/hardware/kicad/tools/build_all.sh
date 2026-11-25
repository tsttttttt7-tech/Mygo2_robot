#!/usr/bin/env bash
# Regenerate the complete Rev D KiCad project: schematic, PCB (placement optional), DRC, validation, outputs.
#   bash tools/build_all.sh            # keep tools/placement.json
#   bash tools/build_all.sh --place    # re-run simulated-annealing placement first
set -euo pipefail
cd "$(dirname "$0")/.."
P=Piezo_MCP6002_RevD
[[ "${1:-}" == "--place" ]] && python3 tools/place.py
python3 tools/gen_sch.py
python3 tools/gen_pcb.py | grep -E "attempt|Found|failed|F.Fab"
python3 tools/validate.py
python3 tools/bom.py
cd $P
kicad-cli sch export pdf -o Schematic.pdf $P.kicad_sch >/dev/null
kicad-cli pcb export pdf --layers F.Cu,F.SilkS,Edge.Cuts -o PCB_top_preview.pdf $P.kicad_pcb >/dev/null
kicad-cli pcb export pdf --layers B.Cu,Edge.Cuts --mirror -o PCB_bottom_preview.pdf $P.kicad_pcb >/dev/null
kicad-cli pcb export pdf --layers F.Fab,F.SilkS,Edge.Cuts -o PCB_assembly.pdf $P.kicad_pcb >/dev/null
rm -rf gerbers Gerbers_$P.zip && mkdir gerbers
kicad-cli pcb export gerbers --layers F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,F.Paste,Edge.Cuts -o gerbers/ $P.kicad_pcb >/dev/null
kicad-cli pcb export drill --format excellon -o gerbers/ $P.kicad_pcb >/dev/null
(cd gerbers && zip -q ../Gerbers_$P.zip *)
python3 - <<'PY'
import subprocess, pcbnew
from PIL import Image
P = "Piezo_MCP6002_RevD"
b = pcbnew.LoadBoard(P + ".kicad_pcb")
for z in list(b.Zones()):
    b.Remove(z)
pcbnew.SaveBoard("/tmp/_nozone.kicad_pcb", b)
subprocess.run(["kicad-cli", "pcb", "export", "pdf", "--layers", "F.Cu,B.Cu,F.SilkS,Edge.Cuts", "-o", "/tmp/_routing.pdf",
                "/tmp/_nozone.kicad_pcb"], check=True, capture_output=True)
for src, dst, mirror in (("PCB_top_preview.pdf", "PCB_top_preview", 0), ("PCB_bottom_preview.pdf", "PCB_bottom_preview", 1),
                         ("PCB_assembly.pdf", "PCB_assembly", 0), ("/tmp/_routing.pdf", "PCB_routing_preview", 0)):
    subprocess.run(["pdftoppm", "-r", "600", "-png", "-singlefile", src, "/tmp/_" + dst], check=True)
    from PIL import ImageOps
    im = Image.open("/tmp/_" + dst + ".png").convert("RGB")
    bb = ImageOps.invert(im).getbbox()                      # content bounding box
    pad = 40
    im.crop((max(0, bb[0] - pad), max(0, bb[1] - pad), bb[2] + pad, bb[3] + pad)).save(dst + ".png")
PY
echo "build complete"
