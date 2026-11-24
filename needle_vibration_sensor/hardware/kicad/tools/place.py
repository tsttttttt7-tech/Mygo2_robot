#!/usr/bin/env python3
"""Placement for Rev D: fixed op-amps/connectors + simulated annealing for passives."""
import math
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from design import PARTS  # noqa: E402

BW, BH = 48.0, 32.0                      # board size (mm)
MARGIN = 0.7                              # free space kept around each courtyard for tracks

# footprint geometry (pad offsets at rotation 0, courtyard half sizes) - from Piezo_PCB.pretty
FP = {
    "R1206": ({"1": (-1.6, 0), "2": (1.6, 0)}, (2.6, 1.15)),
    "C1206": ({"1": (-1.6, 0), "2": (1.6, 0)}, (2.6, 1.15)),
    "C1210": ({"1": (-1.6, 0), "2": (1.6, 0)}, (2.6, 1.7)),
    "BAV99_SOT23": ({"1": (-0.95, 1), "2": (0.95, 1), "3": (0, -1)}, (1.75, 1.8)),
    "SolderJumper_2": ({"1": (-0.575, 0), "2": (0.575, 0)}, (1.65, 1.25)),
}
# fixed parts: ref -> (x, y, rot) of footprint origin (DIP / header origin = pin 1)
FIXED = {
    "U1": (15.0, 10.0, 0), "U2": (31.0, 10.0, 0),
    "J1": (2.5, 12.46, 0), "J2": (2.5, 25.0, 0),
    "J3": (45.5, 8.0, 0), "J4": (45.5, 20.0, 0),
}
DIP = {"1": (0, 0), "2": (0, 2.54), "3": (0, 5.08), "4": (0, 7.62),
       "8": (7.62, 0), "7": (7.62, 2.54), "6": (7.62, 5.08), "5": (7.62, 7.62)}
HDR = {"1": (0, 0), "2": (0, 2.54)}
FIXED_BOX = {"DIP8": (-1.1, -1.65, 8.72, 9.27), "Header_1x02": (-1.55, -1.55, 1.55, 4.09)}
WEIGHT = {"IN": 3, "PZ": 3, "FB": 2.5, "X": 2, "P1": 1.5, "P2": 1.5, "A1": 1.5, "A2": 1.5, "VDIV": 1, "GND": 0}


def rot(p, r):
    x, y = p
    for _ in range((r // 90) % 4):
        x, y = y, -x                       # KiCad: +90 deg rotation (y axis down)
    return x, y


def pad_positions(ref, fp, x, y, r):
    if fp == "DIP8":
        return {k: (x + a, y + b) for k, (a, b) in DIP.items()}
    if fp == "Header_1x02":
        return {k: (x + a, y + b) for k, (a, b) in HDR.items()}
    return {k: (x + a, y + b) for k, (a, b) in ((k, rot(v, r)) for k, v in FP[fp][0].items())}


def box(fp, x, y, r):
    if fp in FIXED_BOX:
        a, b, c, d = FIXED_BOX[fp]
        return (x + a, y + b, x + c, y + d)
    hx, hy = FP[fp][1]
    if r % 180:
        hx, hy = hy, hx
    return (x - hx, y - hy, x + hx, y + hy)


def anneal(seed=1, iters=60000):
    rng = random.Random(seed)
    info = {p[0]: p for p in PARTS}
    movable = [p[0] for p in PARTS if p[0] not in FIXED]
    state = dict(FIXED)
    for ref in movable:
        state[ref] = (rng.uniform(5, BW - 5), rng.uniform(4, BH - 4), rng.choice([0, 90, 180, 270]))

    def cost(st):
        pads = {}
        for ref, (x, y, r) in st.items():
            fp, pins = info[ref][3], info[ref][4]
            for k, pos in pad_positions(ref, fp, x, y, r).items():
                pads.setdefault(pins[k], []).append(pos)
        c = 0.0
        for net, pts in pads.items():
            w = WEIGHT.get(net, 1.0)
            if w and len(pts) > 1:
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                c += w * ((max(xs) - min(xs)) + (max(ys) - min(ys)))
        # decoupling caps right at the supply pins
        for cap, u in (("C2", "U1"), ("C12", "U2")):
            x, y, r = st[cap]
            pp = pad_positions(cap, "C1206", x, y, r)["1"]
            ux, uy = st[u][0] + 7.62, st[u][1]
            c += 4 * math.hypot(pp[0] - ux, pp[1] - uy)
        # overlaps + board edge
        boxes = {ref: box(info[ref][3], *st[ref]) for ref in st}
        refs = list(boxes)
        for i, a in enumerate(refs):
            ax0, ay0, ax1, ay1 = boxes[a]
            c += 200 * (max(0, 0.8 - ax0) + max(0, 0.8 - ay0) + max(0, ax1 - BW + 0.8) + max(0, ay1 - BH + 0.8))
            for b in refs[i + 1:]:
                if a in FIXED and b in FIXED:
                    continue
                bx0, by0, bx1, by1 = boxes[b]
                ox = min(ax1, bx1) - max(ax0, bx0) + MARGIN
                oy = min(ay1, by1) - max(ay0, by0) + MARGIN
                if ox > 0 and oy > 0:
                    c += 60 * min(ox, oy) + 20
        return c

    cur = cost(state)
    best, best_c = dict(state), cur
    T0, T1 = 30.0, 0.05
    for i in range(iters):
        T = T0 * (T1 / T0) ** (i / iters)
        ref = rng.choice(movable)
        old = state[ref]
        mv = rng.random()
        if mv < 0.7:
            s = max(0.25, 12 * T / T0)
            x = min(BW - 1, max(1, round((old[0] + rng.gauss(0, s)) * 4) / 4))
            y = min(BH - 1, max(1, round((old[1] + rng.gauss(0, s)) * 4) / 4))
            state[ref] = (x, y, old[2])
        elif mv < 0.85:
            state[ref] = (old[0], old[1], rng.choice([0, 90, 180, 270]))
        else:
            other = rng.choice(movable)
            state[ref], state[other] = (state[other][0], state[other][1], old[2]), (old[0], old[1], state[other][2])
        new = cost(state)
        if new < cur or rng.random() < math.exp((cur - new) / T):
            cur = new
            if cur < best_c:
                best, best_c = dict(state), cur
        else:
            if mv >= 0.85:
                state[ref], state[other] = old, (state[ref][0], state[ref][1], state[other][2])
            else:
                state[ref] = old
    return best, best_c, cost


if __name__ == "__main__":
    best = None
    for seed in range(1, 5):
        st, c, cost = anneal(seed)
        print("seed", seed, "cost", round(c, 1))
        if best is None or c < best[1]:
            best = (st, c)
    import json
    json.dump(best[0], open(os.path.join(os.path.dirname(__file__), "placement.json"), "w"), indent=1)
    print("best", round(best[1], 1))
