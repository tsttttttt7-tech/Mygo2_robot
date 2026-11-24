#!/usr/bin/env python3
"""Parametric 3-D printable housing for the piezo needle sensor -> STL files.

    pip install manifold3d trimesh numpy
    python make_stl.py                      # 20 mm piezo, 30 x 20 mm SMD amplifier PCB
    python make_stl.py --piezo 27 --pcb 40x25   # 27 mm piezo, DIP version of the PCB

Parts (print in PETG or PLA, 0.2 mm layers, 100 % infill for the body = best vibration transfer):
  sensor_body.stl    piezo pocket on top, amplifier-PCB cavity underneath, cable exit
  sensor_lid.stl     clamp: needle groove + pocket for a rubber pad that presses the needle on the piezo
  sensor_bottom.stl  bottom cover with 2 x M3 pilot holes for mounting on the robot
Coordinate system: X = needle axis, Z = up. Units: mm.
"""
import argparse
import os

import numpy as np
import trimesh
from manifold3d import Manifold

SEG = 96


def box(sx, sy, sz, x=0, y=0, z=0):
    """Box with its bottom-centre at (x, y, z)."""
    return Manifold.cube([sx, sy, sz], center=True).translate([x, y, z + sz / 2])


def cyl(d, h, x=0, y=0, z=0, d2=None):
    return Manifold.cylinder(h, d / 2, (d2 if d2 is not None else d) / 2, SEG).translate([x, y, z])


def save(m, path):
    mesh = m.to_mesh()
    t = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts))
    t.export(path)
    return t


def build(piezo=20.0, ceramic=None, pcb=(30.0, 20.0), pcb_h=8.5, needle=1.27, ball=2.0, foam=0.5, pad=2.5):
    ceramic = ceramic or (14.0 if piezo <= 20 else 20.0)
    wall, roof = 4.0, 5.5
    L = max(40.0, pcb[0] + 2 * wall + 2, piezo + 20)          # length along the needle
    W = max(30.0, pcb[1] + 2 * wall + 2, piezo + 10)          # width
    H = pcb_h + roof                                          # body height
    cav = (L - 2 * wall, W - 2 * wall)

    # ---------------- body ----------------
    body = box(L, W, H)
    body -= box(cav[0], cav[1], pcb_h + 0.01, z=-0.01)                      # PCB cavity (open at bottom)
    rec_depth = foam + 0.2 + 0.1                                            # foam tape + brass + clearance
    body -= cyl(piezo + 0.6, rec_depth + 0.01, z=H - rec_depth)             # piezo pocket (brass rests on rim)
    body -= cyl(ceramic + 1.0, H, z=pcb_h - 0.5)                            # free space under ceramic + wire path
    body -= Manifold.cylinder(2 * wall + 2, 2.1, 2.1, SEG).rotate([0, 90, 0]) \
        .translate([-L / 2 - 1, 0, pcb_h / 2])                               # cable exit, 4.2 mm
    top_holes = [(sx * (cav[0] / 2 - 3), sy * (W / 2 - 2.8)) for sx in (-1, 1) for sy in (-1, 1)]
    bot_holes = [(sx * (L / 2 - 2.2), sy * (W / 2 - 2.2)) for sx in (-1, 1) for sy in (-1, 1)]
    for x, y in top_holes:
        body -= cyl(1.7, 5.0, x, y, H - 5.0)                                 # M2 pilot, lid (stays in the 5.5 mm roof)
    for x, y in bot_holes:
        body -= cyl(1.7, 6.0, x, y, -0.01)                                   # M2 pilot, bottom cover

    # needle height: brass top -> steel ball (or glue dot) -> needle
    brass_top = H - rec_depth + foam + 0.2
    needle_bot = brass_top + ball
    needle_top = needle_bot + needle

    # ---------------- lid ----------------
    LT = 6.0
    lid = box(L, W, LT, z=H)
    groove_w, groove_d = 3.2, needle_top - H + 0.6
    lid -= box(L + 2, groove_w, groove_d + 0.01, z=H - 0.01)                # needle clearance groove
    pocket_d = needle_top - H + pad - 0.9                                    # rubber pad pre-compressed ~0.9 mm
    lid -= cyl(7.0, pocket_d + 0.01, z=H - 0.01)                             # rubber pad pocket over piezo centre
    for x, y in top_holes:
        lid -= cyl(2.4, LT + 1, x, y, H - 0.5)                               # M2 clearance
        lid -= cyl(4.0, 2.0, x, y, H + LT - 2.0)                             # counterbore for M2 head

    # ---------------- bottom cover ----------------
    BT = 3.0
    bottom = box(L, W, BT, z=-BT)
    bottom += box(cav[0] - 0.4, cav[1] - 0.4, 1.0, z=0) - box(cav[0] - 2.4, cav[1] - 2.4, 1.02, z=-0.01)  # locating lip
    for x, y in bot_holes:
        bottom -= cyl(2.4, BT + 2, x, y, -BT - 1)
        bottom -= cyl(3.8, 1.2, x, y, -BT - 0.01, d2=2.4)                    # countersink, M2 flat head
    for x in (-10.0, 10.0):
        bottom -= cyl(2.5, 2.5, x, 0, -BT - 0.01)                            # M3 self-tap pilot, robot mount

    info = dict(L=L, W=W, H=H, lid=LT, bottom=BT, cavity=cav, pcb_h=pcb_h, brass_top=brass_top,
                needle_axis=needle_bot + needle / 2, pad_pocket_depth=pocket_d, groove_depth=groove_d)
    return body, lid, bottom, info


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--piezo", type=float, default=20.0, help="piezo brass diameter (mm)")
    p.add_argument("--ceramic", type=float, default=None, help="ceramic diameter (mm), default 14 (20 mm disc) / 20 (27 mm)")
    p.add_argument("--pcb", default="30x20", help="amplifier PCB size, e.g. 30x20 (SMD) or 40x25 (DIP)")
    p.add_argument("--needle", type=float, default=1.27, help="needle outer diameter (18G = 1.27 mm)")
    p.add_argument("--pcb-h", type=float, default=8.5, help="free height above the PCB cavity floor (DIP board: 10)")
    p.add_argument("--out", default=os.path.dirname(os.path.abspath(__file__)))

    a = p.parse_args()
    pcb = tuple(float(v) for v in a.pcb.lower().split("x"))
    body, lid, bottom, info = build(a.piezo, a.ceramic, pcb, pcb_h=a.pcb_h, needle=a.needle)
    meshes = {}
    for name, m in (("sensor_body", body), ("sensor_lid", lid), ("sensor_bottom", bottom)):
        t = save(m, os.path.join(a.out, f"{name}.stl"))
        meshes[name] = t
        print(f"{name}.stl  {t.extents.round(1)} mm  watertight={t.is_watertight}  volume={t.volume/1000:.1f} cm3")
    for k, v in info.items():
        print(f"  {k}: {np.round(v, 2) if not isinstance(v, tuple) else tuple(round(x, 1) for x in v)}")
    return meshes, info


if __name__ == "__main__":
    main()
