#!/usr/bin/env python3
"""Draws the piezo amplifier + filter schematic (Rev D) -> SVG, PNG, PDF.
    pip install schemdraw matplotlib
    python make_schematic.py
"""
import os
import schemdraw
import schemdraw.elements as elm

schemdraw.use('matplotlib')
OUT = os.path.dirname(os.path.abspath(__file__))
FS = 10


def vref(d, at, side='down'):
    """VREF net tag."""
    return d.add(elm.Line().at(at).length(0.01)) if False else \
        d.add(elm.Tag().at(at).down().label('VREF', fontsize=FS) if hasattr(elm, 'Tag') else
              elm.Label().at(at).label('VREF'))


def tag(d, at, name, direction='down'):
    t = getattr(elm.Tag(), direction)()
    return d.add(t.at(at).label(name, fontsize=FS))


with schemdraw.Drawing(show=False) as d:
    d.config(fontsize=FS, unit=2.2, lw=1.1)

    # ======================= INPUT + GAIN STAGE (U1A) =======================
    d.add(elm.Label().at((0, 7.2)).label('1) Piezo input + gain stage', fontsize=12, halign='left'))
    op1 = d.add(elm.Opamp(leads=True).at((9, 2.2)).anchor('in2')
                .label('U1A\nMCP6002', loc='center', ofst=(-0.35, 0), fontsize=8))
    # input chain
    d.add(elm.Line().at(op1.in2).left().length(1.0))
    n_in = d.add(elm.Dot().label('IN', loc='top', fontsize=8))
    r1 = d.add(elm.Resistor().left().label('R1\n18k', fontsize=FS))
    n_p = d.add(elm.Dot())
    pz = d.add(elm.Crystal().down().label('J1\nPiezo\n20 mm', loc='bottom', ofst=0.15, fontsize=FS))
    d.add(elm.Ground())
    d.add(elm.Label().at((n_p.center[0] - 1.6, n_p.center[1] + 0.35))
          .label('ceramic (+)', fontsize=7))
    d.add(elm.Label().at((n_p.center[0] - 1.5, pz.end[1] + 0.35)).label('brass (GND)', fontsize=7))
    # R2 and D1 from IN to VREF
    d.add(elm.Line().at(n_in.center).down().length(0.8))
    n_b = d.add(elm.Dot())
    r2 = d.add(elm.Resistor().down().at(n_b.center).label('R2\n1M', loc='bottom', fontsize=FS))
    tag(d, r2.end, 'VREF')
    d.add(elm.Line().at(n_b.center).right().length(2.4))
    dd = d.add(elm.Line().down().length(0.6))
    d.add(elm.Line().left().length(0.5).at(dd.end))
    da = d.add(elm.Diode().down().length(1.6))
    d.add(elm.Line().right().length(1.0))
    db = d.add(elm.Diode().up().length(1.6))
    d.add(elm.Line().left().length(0.5))
    d.add(elm.Line().at((da.end[0] + 0.5, da.end[1])).down().length(0.6))
    tag(d, d.here, 'VREF')
    d.add(elm.Label().at((da.start[0] + 1.7, da.center[1])).label('D1\nBAV99\npin3=IN\npin1,2=VREF', fontsize=7, halign='left'))

    # feedback network
    d.add(elm.Line().at(op1.in1).left().length(0.6))
    n_fb = d.add(elm.Dot().label('FB', loc='left', fontsize=8))
    d.add(elm.Line().at(n_fb.center).left().length(0.8))
    n_fb2 = d.add(elm.Dot())
    r4 = d.add(elm.Resistor().left().label('R4\n1k', fontsize=FS))
    tag(d, r4.end, 'VREF', 'left')
    d.add(elm.Line().at(n_fb.center).left().length(0.0001))
    # R3a + R3b(JP1) from FB to OUT, drawn above the opamp
    top_y = op1.in1[1] + 3.0
    d.add(elm.Line().at((n_fb.center[0] - 0.0, n_fb.center[1])).length(0.0001))
    d.add(elm.Line().at(n_fb2.center).up().toy(top_y))
    n_l = d.here
    r3a = d.add(elm.Resistor().right().label('R3 10k', fontsize=FS))
    n_x = d.add(elm.Dot().label('X', loc='bottom', fontsize=7))
    r3b = d.add(elm.Resistor().right().label('R14 33k', loc='bottom', fontsize=FS))
    d.add(elm.Line().right().tox(op1.out[0] + 0.6))
    n_r = d.here
    d.add(elm.Line().down().toy(op1.out[1]))
    d.add(elm.Line().left().tox(op1.out[0]))
    # JP1 across R3b
    d.add(elm.Line().at(n_x.center).up().length(1.2))
    d.add(elm.Switch().right().tox(r3b.end[0]).label('JP1 closed: gain 11 / open: gain 44', fontsize=7))
    d.add(elm.Line().down().toy(top_y))
    # C5 across whole feedback
    d.add(elm.Line().at(n_l).up().length(2.9))
    d.add(elm.Capacitor().right().tox(n_r[0]).label('C5 47p C0G', fontsize=FS))
    d.add(elm.Line().down().toy(n_r[1]))
    d.add(elm.Dot().at(n_r))
    d.add(elm.Dot().at(n_l))
    # output
    d.add(elm.Line().at(op1.out).right().length(1.0))
    d.add(elm.Dot())
    tag(d, d.here, 'AMP', 'right')

    # ======================= VREF (U1B) =======================
    X0, Y0 = 0, -6.5
    d.add(elm.Label().at((X0, Y0 + 2.6)).label('2) Half-supply reference', fontsize=12, halign='left'))
    d.add(elm.Vdd().at((X0 + 1.2, Y0 + 1.6)).label('AVDD', fontsize=FS))
    d.add(elm.Resistor().down().label('R5\n10k', loc='bottom', fontsize=FS))
    nd = d.add(elm.Dot().label('VDIV', loc='left', fontsize=8))
    d.add(elm.Resistor().down().label('R6\n10k', loc='bottom', fontsize=FS))
    d.add(elm.Ground())
    d.add(elm.Line().at(nd.center).right().length(1.4))
    nc = d.add(elm.Dot())
    d.add(elm.Capacitor().down().label('C4\n10µ', loc='bottom', fontsize=FS))
    d.add(elm.Ground())
    op2 = d.add(elm.Opamp(leads=True).at(nc.center).anchor('in2').right()
                .label('U1B', loc='center', ofst=(-0.35, 0), fontsize=8))
    d.add(elm.Line().at(nc.center).to(op2.in2))
    d.add(elm.Line().at(op2.in1).left().length(0.4))
    d.add(elm.Line().up().length(1.3))
    d.add(elm.Line().right().tox(op2.out[0] + 0.5))
    d.add(elm.Line().down().toy(op2.out[1]))
    d.add(elm.Dot())
    d.add(elm.Line().at(op2.out).right().length(1.3))
    tag(d, d.here, 'VREF', 'right')

    # ======================= POWER =======================
    PX, PY = 0, -14.5
    d.add(elm.Label().at((PX, PY + 2.6)).label('5) Power, connectors', fontsize=12, halign='left'))
    d.add(elm.Label().at((PX, PY + 1.2)).label('J2: 3V3 from ESP32', fontsize=FS, halign='left'))
    d.add(elm.Line().at((PX + 0.5, PY + 0.5)).right().length(0.5))
    d.add(elm.Resistor().right().label('R12 10Ω', fontsize=FS))
    na = d.add(elm.Dot())
    d.add(elm.Vdd().at(na.center).label('AVDD', fontsize=FS))
    for name in ['C3\n22µ', 'C2\n100n\n(U1 pin8)', 'C12\n100n\n(U2 pin8)']:
        d.add(elm.Line().at(na.center).right().length(1.6))
        na = d.add(elm.Dot())
        d.add(elm.Capacitor().down().at(na.center).label(name, loc='bottom', fontsize=FS))
        d.add(elm.Ground())
    d.add(elm.Label().at((PX, PY - 3.0)).label(
        'J3: OUT_DC → ESP32-S3 GPIO1 (ADC1_CH0)      J4: OUT_AC → PCM1808 "L"\n'
        'U1, U2 = MCP6002 (pin 8 = AVDD, pin 4 = GND)    values from Ardunic 1206 kits ARD-065066 / ARD-065072',
        fontsize=9, halign='left'))

    # ======================= FILTER (U2A, U2B) =======================
    FX, FY = 21, 2.2
    d.add(elm.Label().at((FX, 7.2)).label('3) 4th-order Butterworth low-pass, fc ≈ 15 kHz', fontsize=12, halign='left'))

    def sallen_key(x, y, rname, r1, r2, c1, c2, uname, inname, outname, q):
        tag(d, (x, y), inname, 'left')
        ra = d.add(elm.Resistor().at((x, y)).right().label(f'{rname[0]}\n{r1}', fontsize=FS))
        n1 = d.add(elm.Dot())
        rb = d.add(elm.Resistor().right().label(f'{rname[1]}\n{r2}', fontsize=FS))
        n2 = d.add(elm.Dot())
        cb = d.add(elm.Capacitor().down().at(n2.center).label(f'{c2[0]}\n{c2[1]}', loc='bottom', fontsize=FS))
        d.add(elm.Ground())
        op = d.add(elm.Opamp(leads=True).at(n2.center).anchor('in2').right()
                   .label(uname, loc='center', ofst=(-0.35, 0), fontsize=8))
        # follower feedback (output -> inverting input)
        xo = op.out[0] + 0.4
        yl = op.in1[1] + 1.0
        d.add(elm.Line().at(op.in1).to((op.in1[0] - 0.4, op.in1[1])))
        d.add(elm.Line().at((op.in1[0] - 0.4, op.in1[1])).to((op.in1[0] - 0.4, yl)))
        d.add(elm.Line().at((op.in1[0] - 0.4, yl)).to((xo, yl)))
        # feedback capacitor from n1 to output
        yc = yl + 1.4
        d.add(elm.Line().at(n1.center).to((n1.center[0], yc)))
        cx0 = (n1.center[0] + xo) / 2 - 0.6
        d.add(elm.Line().at((n1.center[0], yc)).to((cx0, yc)))
        d.add(elm.Capacitor().at((cx0, yc)).to((cx0 + 1.2, yc)).label(f'{c1[0]} {c1[1]}', fontsize=FS))
        d.add(elm.Line().at((cx0 + 1.2, yc)).to((xo, yc)))
        d.add(elm.Line().at((xo, yc)).to((xo, op.out[1])))
        no = d.add(elm.Dot().at((xo, op.out[1])))
        d.add(elm.Line().at(op.out).to(no.center))
        d.add(elm.Line().at(no.center).right().length(0.8))
        tag(d, d.here, outname, 'right')
        d.add(elm.Label().at((x + 1.0, y - 3.4)).label(q, fontsize=8, halign='left'))
        return no

    sallen_key(FX, FY, ('R8', 'R9'), '12k', '390k', ('C8', '470p'), ('C9', '47p'),
               'U2A', 'AMP', 'LP1', 'stage 1: Q = 0.54, f0 = 15.7 kHz')
    sallen_key(FX, FY - 8.0, ('R10', 'R11'), '33k', '200k', ('C10', '470p'), ('C11', '33p'),
               'U2B', 'LP1', 'FOUT', 'stage 2: Q = 1.32, f0 = 15.7 kHz')

    # ======================= OUTPUTS =======================
    OX, OY = 21, -12.5
    d.add(elm.Label().at((OX, OY + 1.8)).label('4) Outputs', fontsize=12, halign='left'))
    tag(d, (OX, OY), 'FOUT', 'left')
    d.add(elm.Line().at((OX, OY)).right().length(0.5))
    nf = d.add(elm.Dot())
    d.add(elm.Resistor().right().label('R7 100Ω', fontsize=FS))
    nj3 = d.add(elm.Dot())
    d.add(elm.Line().right().length(1.0).label('J3 OUT_DC', loc='right', fontsize=FS))
    d.add(elm.Capacitor().down().at(nj3.center).label('C6\n10n', loc='bottom', fontsize=FS))
    d.add(elm.Ground())
    d.add(elm.Line().at(nf.center).down().length(3.0))
    d.add(elm.Capacitor().right().label('C7 2.2µ', loc='bottom', fontsize=FS))
    d.add(elm.Resistor().right().label('R13 100Ω', loc='bottom', fontsize=FS))
    d.add(elm.Line().right().length(1.0).label('J4 OUT_AC', loc='right', fontsize=FS))

    d.add(elm.Label().at((0, -21.5)).label(
        'Piezo needle sensor - amplifier + filter, Rev D (Mygo2_robot)      gain 11 (JP1 closed) / 44 (open), '
        'band 16 Hz - 15 kHz, 3.3 V, ~2 mA', fontsize=10, halign='left'))

    for ext in ('svg', 'png', 'pdf'):
        d.save(os.path.join(OUT, f'amp_filter_schematic.{ext}'), dpi=150) if ext == 'png' else \
            d.save(os.path.join(OUT, f'amp_filter_schematic.{ext}'))
print('saved to', OUT)
