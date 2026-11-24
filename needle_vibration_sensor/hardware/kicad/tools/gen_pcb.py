#!/usr/bin/env python3
"""Build the Rev D PCB with KiCad's pcbnew API: place, route (2-layer grid router), GND pours, DRC.

    python3 tools/place.py      # (optional) re-run placement -> tools/placement.json
    python3 tools/gen_pcb.py    # -> Piezo_MCP6002_RevD/Piezo_MCP6002_RevD.kicad_pcb + DRC.txt
"""
import heapq
import re
import json
import math
import os
import random
import sys

import numpy as np
import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
from design import PARTS  # noqa: E402
from place import BW, BH  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.join(HERE, "..", "Piezo_MCP6002_RevD")
PCB = os.path.join(PRJ, "Piezo_MCP6002_RevD.kicad_pcb")
LIB = os.path.join(PRJ, "Piezo_PCB.pretty")

OX, OY = 100.0, 100.0          # board origin on the KiCad page (mm)
G = 0.25                        # routing grid (mm)
TW, CLR = 0.25, 0.2             # track width, clearance
VIA_D, VIA_DRILL = 0.6, 0.3
NX, NY = int(round(BW / G)) + 1, int(round(BH / G)) + 1
mm = pcbnew.FromMM


def V(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


# ------------------------------------------------------------------ board construction
def build_board(placement):
    board = pcbnew.BOARD()
    nets = {}

    def net(name):
        if name not in nets:
            ni = pcbnew.NETINFO_ITEM(board, name)
            board.Add(ni)
            nets[name] = ni
        return nets[name]

    for ref, value, sym, fpname, pins in PARTS:
        fp = pcbnew.FootprintLoad(LIB, fpname)
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.SetFPID(pcbnew.LIB_ID("Piezo_PCB", fpname))
        x, y, r = placement[ref]
        fp.SetPosition(V(x, y))
        fp.SetOrientationDegrees(r)
        for t in (fp.Reference(),):
            t.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
            t.SetTextThickness(mm(0.12))
        fp.Value().SetVisible(False)
        for pad in fp.Pads():
            pad.SetNet(net(pins[pad.GetNumber()]))
        board.Add(fp)
    # outline
    rect = pcbnew.PCB_SHAPE(board)
    rect.SetShape(pcbnew.SHAPE_T_RECT)
    rect.SetStart(V(0, 0))
    rect.SetEnd(V(BW, BH))
    rect.SetLayer(pcbnew.Edge_Cuts)
    rect.SetWidth(mm(0.1))
    board.Add(rect)
    return board, nets


def pad_table(board):
    pads = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            x0, y0 = pcbnew.ToMM(bb.GetX()) - OX, pcbnew.ToMM(bb.GetY()) - OY
            x1, y1 = x0 + pcbnew.ToMM(bb.GetWidth()), y0 + pcbnew.ToMM(bb.GetHeight())
            layers = [l for l, kl in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)) if pad.IsOnLayer(kl)]
            round_ = pad.GetShape() in (pcbnew.PAD_SHAPE_CIRCLE, pcbnew.PAD_SHAPE_OVAL)
            pads.append(dict(ref=fp.GetReference(), num=pad.GetNumber(), net=pad.GetNetname(),
                             rect=(x0, y0, x1, y1), layers=layers, round=round_))
    return pads


# ------------------------------------------------------------------ router
class Router:
    def __init__(self, pads, netnames):
        self.pads = pads
        self.nid = {n: i for i, n in enumerate(netnames)}
        self.reset()

    def reset(self):
        self.keep = np.full((2, NY, NX), -1, np.int16)      # -1 free, net id, -2 blocked
        self.copper = np.full((2, NY, NX), -1, np.int16)    # copper centre cells
        self.padvia = np.full((2, NY, NX), -1, np.int16)    # pad keepout for via centres
        self.vias = []                                      # (x, y, net)
        self._vcache = {}
        self.tracks = []                                    # (layer, [(ix, iy), ...], net)
        ys, xs = np.mgrid[0:NY, 0:NX]
        self.X, self.Y = xs * G, ys * G
        edge = (self.X < 0.65) | (self.Y < 0.65) | (self.X > BW - 0.65) | (self.Y > BH - 0.65)
        self.keep[:, edge] = -2
        self.via_edge = (self.X < 0.95) | (self.Y < 0.95) | (self.X > BW - 0.95) | (self.Y > BH - 0.95)
        self.core = {}
        self.padcore = np.zeros((NY, NX), bool)
        for i, p in enumerate(self.pads):
            n = self.nid[p["net"]]
            x0, y0, x1, y1 = p["rect"]
            for l in p["layers"]:
                self._mark(self.keep[l], (self.X > x0 - 0.42) & (self.X < x1 + 0.42) & (self.Y > y0 - 0.42) & (self.Y < y1 + 0.42), n)
                self._mark(self.padvia[l], (self.X > x0 - 0.52) & (self.X < x1 + 0.52) & (self.Y > y0 - 0.52) & (self.Y < y1 + 0.52), n)
            if p.get("round"):
                cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 - 0.1, (y1 - y0) / 2 - 0.1
                m = ((self.X - cx) / rx) ** 2 + ((self.Y - cy) / ry) ** 2 < 1.0
            else:
                m = (self.X > x0 + 0.02) & (self.X < x1 - 0.02) & (self.Y > y0 + 0.02) & (self.Y < y1 - 0.02)
            cells = list(zip(*np.nonzero(m)))
            if not cells:   # very small pad: nearest cell
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                cells = [(int(round(cy / G)), int(round(cx / G)))]
            self.core[i] = [(l, int(y), int(x)) for l in p["layers"] for (y, x) in cells]
            self.padcore[(self.X > x0 - 0.35) & (self.X < x1 + 0.35) & (self.Y > y0 - 0.35) & (self.Y < y1 + 0.35)] = True
            for l, y, x in self.core[i]:
                self.copper[l, y, x] = n

    @staticmethod
    def _mark(arr, mask, n):
        sub = arr[mask]
        sub = np.where(sub == -1, n, np.where(sub == n, n, -2))
        arr[mask] = sub

    def via_ok(self, y, x, n):
        key = (y, x, n, len(self.vias), len(self.tracks))
        c = self._vcache.get(key)
        if c is None:
            c = self._via_ok(y, x, n)
            self._vcache[key] = c
        return c

    def _via_ok(self, y, x, n):
        if self.via_edge[y, x] or self.padcore[y, x]:
            return False
        r = 3
        y0, y1, x0, x1 = max(0, y - r), min(NY, y + r + 1), max(0, x - r), min(NX, x + r + 1)
        for l in (0, 1):
            pv = self.padvia[l, y, x]
            if pv not in (-1, n):
                return False
            k = self.keep[l, y, x]
            if k not in (-1, n):
                return False
            win = self.copper[l, y0:y1, x0:x1]
            dy, dx = np.mgrid[y0 - y:y1 - y, x0 - x:x1 - x]
            near = (dy * dy + dx * dx) * G * G < 0.65 ** 2
            if np.any((win != -1) & (win != n) & near):
                return False
        px, py = x * G, y * G
        for vx, vy, vn in self.vias:
            d = math.hypot(vx - px, vy - py)
            if (vn != n and d < VIA_D + CLR + 0.01) or (vn == n and d < VIA_D + 0.05):
                return False
        return True

    def commit(self, path, n):
        """path: list of (l, y, x); vias where consecutive cells change layer."""
        seg, cur_l = [], None
        for i, (l, y, x) in enumerate(path):
            if cur_l is not None and l != cur_l:
                if len(seg) > 1:
                    self.tracks.append((cur_l, seg, n))
                py, px = path[i - 1][1], path[i - 1][2]
                self.add_via(py, px, n)
                seg = []
            seg.append((x, y))
            cur_l = l
            self.copper[l, y, x] = n
            self._mark(self.keep[l], self._disc(y, x, 1.5), n)
        if len(seg) > 1:
            self.tracks.append((cur_l, seg, n))

    def _disc(self, y, x, rc):
        m = np.zeros((NY, NX), bool)
        r = int(math.ceil(rc))
        y0, y1, x0, x1 = max(0, y - r), min(NY, y + r + 1), max(0, x - r), min(NX, x + r + 1)
        dy, dx = np.mgrid[y0 - y:y1 - y, x0 - x:x1 - x]
        m[y0:y1, x0:x1] = (dy * dy + dx * dx) <= rc * rc
        return m

    def add_via(self, y, x, n):
        self.vias.append((x * G, y * G, n))
        for l in (0, 1):
            self.copper[l, y, x] = n
            self._mark(self.keep[l], self._disc(y, x, 0.65 / G), n)

    def astar(self, sources, targets, n, bottom_cost=2.0, via_cost=12.0):
        tset = set(targets)
        if not tset:
            return None
        ty = [t[1] for t in tset]
        tx = [t[2] for t in tset]
        bx0, bx1, by0, by1 = min(tx), max(tx), min(ty), max(ty)

        def h(y, x):
            dx = max(bx0 - x, 0, x - bx1)
            dy = max(by0 - y, 0, y - by1)
            return (max(dx, dy) + 0.414 * min(dx, dy))

        keep = self.keep
        openh, g, parent = [], {}, {}
        for s in sources:
            g[s] = 0.0
            parent[s] = None
            heapq.heappush(openh, (h(s[1], s[2]), 0.0, s))
        dirs = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
                (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)]
        while openh:
            f, gc, s = heapq.heappop(openh)
            if gc > g.get(s, 1e18):
                continue
            if s in tset:
                path = []
                while s is not None:
                    path.append(s)
                    s = parent[s]
                return path[::-1]
            l, y, x = s
            mult = bottom_cost if l == 1 else 1.0
            for dy, dx, c in dirs:
                yy, xx = y + dy, x + dx
                if not (0 <= yy < NY and 0 <= xx < NX):
                    continue
                k = keep[l, yy, xx]
                ns = (l, yy, xx)
                if k != -1 and k != n and ns not in tset:
                    continue
                cp = self.copper[l, yy, xx]
                if cp != -1 and cp != n:
                    continue
                ng = gc + c * mult
                if ng < g.get(ns, 1e18):
                    g[ns] = ng
                    parent[ns] = s
                    heapq.heappush(openh, (ng + h(yy, xx), ng, ns))
            ns = (1 - l, y, x)
            if self.copper[l, y, x] in (-1, n) and self.via_ok(y, x, n) or ns in tset and self.via_ok(y, x, n):
                ng = gc + via_cost
                if ng < g.get(ns, 1e18):
                    g[ns] = ng
                    parent[ns] = s
                    heapq.heappush(openh, (ng + h(y, x), ng, ns))
        return None

    def route_net(self, name):
        n = self.nid[name]
        idx = [i for i, p in enumerate(self.pads) if p["net"] == name]
        if len(idx) < 2:
            return True
        cent = {i: ((self.pads[i]["rect"][0] + self.pads[i]["rect"][2]) / 2,
                    (self.pads[i]["rect"][1] + self.pads[i]["rect"][3]) / 2) for i in idx}
        tree_pads = [idx[0]]
        tree = set(self.core[idx[0]])
        rest = idx[1:]
        while rest:
            # nearest remaining pad to the tree
            rest.sort(key=lambda i: min(math.dist(cent[i], cent[j]) for j in tree_pads))
            i = rest.pop(0)
            src = [c for c in self.core[i]]
            path = self.astar(src, list(tree), n)
            if path is None:
                return False
            self.commit(path, n)
            tree |= set(path) | set(self.core[i])
            tree_pads.append(i)
        return True

    def gnd_vias(self, name="GND", maxlen=40):
        """Connect every SMD GND pad to a via (pours on both layers do the rest)."""
        n = self.nid[name]
        fails = []
        for i, p in enumerate(self.pads):
            if p["net"] != name or 1 in p["layers"]:
                continue
            # Dijkstra on the top layer to the nearest cell where a via fits
            src = self.core[i]
            dist = {s: 0.0 for s in src}
            parent = {s: None for s in src}
            hq = [(0.0, s) for s in src]
            found = None
            while hq:
                d, s = heapq.heappop(hq)
                if d > maxlen:
                    break
                l, y, x = s
                if self.via_ok(y, x, n):
                    found = s
                    break
                for dy, dx, c in ((-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)):
                    yy, xx = y + dy, x + dx
                    if not (0 <= yy < NY and 0 <= xx < NX):
                        continue
                    if self.keep[0, yy, xx] not in (-1, n) or self.copper[0, yy, xx] not in (-1, n):
                        continue
                    ns = (0, yy, xx)
                    if d + c < dist.get(ns, 1e18):
                        dist[ns] = d + c
                        parent[ns] = s
                        heapq.heappush(hq, (d + c, ns))
            if found is None:
                fails.append(f'{p["ref"]}.{p["num"]}')
                continue
            path = []
            s = found
            while s is not None:
                path.append(s)
                s = parent[s]
            path = path[::-1]
            if len(path) > 1:
                self.commit(path, n)
            self.add_via(found[1], found[2], n)
        return fails

    def stitch(self, name="GND", pitch=3.0):
        n = self.nid[name]
        k = 0
        for y in np.arange(1.5, BH - 1.0, pitch):
            for x in np.arange(1.5, BW - 1.0, pitch):
                iy, ix = int(round(y / G)), int(round(x / G))
                if self.keep[0, iy, ix] == -1 and self.keep[1, iy, ix] == -1 and self.via_ok(iy, ix, n):
                    self.add_via(iy, ix, n)
                    k += 1
        return k


def place_refs(board):
    """Put each reference designator where it does not touch pads, other labels or the board edge."""
    def bb(item, grow=0.0):
        b = item.GetBoundingBox(False, False) if isinstance(item, pcbnew.FOOTPRINT) else item.GetBoundingBox()
        x0, y0 = pcbnew.ToMM(b.GetX()), pcbnew.ToMM(b.GetY())
        return (x0 - grow, y0 - grow, x0 + pcbnew.ToMM(b.GetWidth()) + grow, y0 + pcbnew.ToMM(b.GetHeight()) + grow)

    def hit(a, c):
        return not (a[2] <= c[0] or c[2] <= a[0] or a[3] <= c[1] or c[3] <= a[1])

    pads = [bb(p, 0.15) for fp in board.GetFootprints() for p in fp.Pads()]
    taken = [bb(g, 0.1) for fp in board.GetFootprints() for g in fp.GraphicalItems() if g.GetLayer() == pcbnew.F_SilkS]
    taken += [bb(d, 0.1) for d in board.GetDrawings() if d.GetLayer() == pcbnew.F_SilkS]
    inside = (OX + 0.6, OY + 0.6, OX + BW - 0.6, OY + BH - 0.6)
    for fp in sorted(board.GetFootprints(), key=lambda f: f.GetReference()):
        t = fp.Reference()
        c = bb(fp)
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        cands = [(cx, cy)] if fp.GetFPIDAsString().endswith("DIP8") else []
        for d in (0.9, 1.4, 2.0, 2.8):
            cands += [(cx, c[1] - d * 0.6), (cx, c[3] + d * 0.6), (c[0] - d, cy), (c[2] + d, cy)]
        for d in (0.8, 1.5):
            cands += [(c[0] - d, c[1] - d * 0.6), (c[2] + d, c[1] - d * 0.6), (c[0] - d, c[3] + d * 0.6), (c[2] + d, c[3] + d * 0.6)]
        ok = False
        for sz, r_ in ((0.8, 0), (0.8, 90)):
            t.SetTextSize(pcbnew.VECTOR2I(mm(sz), mm(sz)))
            t.SetTextThickness(mm(0.12 if sz > 0.7 else 0.1))
            for x, y in cands:
                t.SetTextAngle(pcbnew.EDA_ANGLE(r_, pcbnew.DEGREES_T))
                t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
                tb = bb(t, 0.05)
                if (tb[0] < inside[0] or tb[1] < inside[1] or tb[2] > inside[2] or tb[3] > inside[3]):
                    continue
                if any(hit(tb, p) for p in pads) or any(hit(tb, q) for q in taken):
                    continue
                taken.append(tb)
                ok = True
                break
            if ok:
                break
        if not ok:
            t.SetLayer(pcbnew.F_Fab)      # no free spot: keep it on the fab layer only, centred on the part
            t.SetTextAngle(pcbnew.EDA_ANGLE(0, pcbnew.DEGREES_T))
            t.SetPosition(pcbnew.VECTOR2I(mm(cx), mm(cy)))
            print("reference moved to F.Fab:", fp.GetReference())


def simplify(cells):
    """Merge collinear grid steps into segments."""
    pts = [cells[0]]
    for i in range(1, len(cells) - 1):
        a, b, c = pts[-1], cells[i], cells[i + 1]
        d1 = (b[0] - a[0], b[1] - a[1])
        d2 = (c[0] - b[0], c[1] - b[1])
        if d1[0] * d2[1] - d1[1] * d2[0] != 0:
            pts.append(b)
    pts.append(cells[-1])
    return pts


def route_all(pads, netnames, order, attempts=25, seed=0):
    rng = random.Random(seed)
    best = None
    for a in range(attempts):
        r = Router(pads, netnames)
        failed = [nm for nm in order if not r.route_net(nm)]
        print(f"attempt {a + 1}: failed {failed}")
        if best is None or len(failed) < len(best[1]):
            best = (r, failed)
        if not failed:
            break
        order = failed + [n for n in order if n not in failed]
        if a > 2:
            rest = order[len(failed):]
            rng.shuffle(rest)
            order = failed + rest
    return best


def main():
    placement = {k: tuple(v) for k, v in json.load(open(os.path.join(HERE, "placement.json"))).items()}
    board, nets = build_board(placement)
    pads = pad_table(board)
    netnames = sorted({p["net"] for p in pads})

    def hpwl(nm):
        rs = [p["rect"] for p in pads if p["net"] == nm]
        xs = [(r[0] + r[2]) / 2 for r in rs]
        ys = [(r[1] + r[3]) / 2 for r in rs]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    signal = [n for n in netnames if n != "GND"]
    order = sorted(signal, key=hpwl)
    r, failed = route_all(pads, netnames, order)
    gfail = r.gnd_vias()
    nst = r.stitch()
    print("GND via failures:", gfail, " stitching vias:", nst)

    # ---- write copper
    for l, cells, n in r.tracks:
        pts = simplify(cells)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(V(x0 * G, y0 * G))
            t.SetEnd(V(x1 * G, y1 * G))
            t.SetWidth(mm(TW))
            t.SetLayer(pcbnew.F_Cu if l == 0 else pcbnew.B_Cu)
            t.SetNet(nets[netnames[n]])
            board.Add(t)
    for x, y, n in r.vias:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(V(x, y))
        v.SetWidth(mm(VIA_D))
        v.SetDrill(mm(VIA_DRILL))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetNet(nets[netnames[n]])
        board.Add(v)
    # ---- GND pours on both layers
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(nets["GND"])
        ol = z.Outline()
        ol.NewOutline()
        for x, y in ((0.3, 0.3), (BW - 0.3, 0.3), (BW - 0.3, BH - 0.3), (0.3, BH - 0.3)):
            ol.Append(mm(OX + x), mm(OY + y))
        z.SetLocalClearance(mm(0.3))
        z.SetMinThickness(mm(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(mm(0.3))
        z.SetThermalReliefSpokeWidth(mm(0.35))
        z.SetIsFilled(False)
        board.Add(z)
    # ---- silkscreen title
    txt = pcbnew.PCB_TEXT(board)
    txt.SetText("PIEZO / MCP6002 / REV D")
    txt.SetPosition(V(BW / 2, BH - 1.6))
    txt.SetLayer(pcbnew.F_SilkS)
    txt.SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
    txt.SetTextThickness(mm(0.15))
    board.Add(txt)
    pcbnew.SaveBoard(PCB, board)

    place_refs(board)
    pcbnew.SaveBoard(PCB, board)

    # reload so the project rules (.kicad_pro) apply, fill zones, run DRC
    rep = os.path.join(PRJ, "DRC.txt")
    solid = set()
    for _ in range(3):
        b = pcbnew.LoadBoard(PCB)
        for fp in b.GetFootprints():
            for pad in fp.Pads():
                if (fp.GetReference(), pad.GetNumber()) in solid:
                    pad.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        pcbnew.SaveBoard(PCB, b)
        pcbnew.WriteDRCReport(b, rep, pcbnew.EDA_UNITS_MILLIMETRES, True)
        txt = open(rep).read()
        starved = re.findall(r"starved_thermal.*?\n.*?\n.*?\n\s*@\([^)]*\): PTH pad (\S+) \[GND\] of (\S+)", txt)
        if not starved:
            break
        solid |= {(ref, num) for num, ref in starved}
        print("solid zone connection for", sorted(solid))
    print("\n".join(l for l in txt.splitlines() if l.startswith("**")))
    print("signal nets failed:", failed)


if __name__ == "__main__":
    main()
