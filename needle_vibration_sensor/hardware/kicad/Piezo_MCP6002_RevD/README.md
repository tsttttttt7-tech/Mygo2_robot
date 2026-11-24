# Piezo MCP6002 - Rev D PCB project

Same style as Rev C (self-contained symbols/footprints, routed 2-layer board, DRC, BOM, previews), with the Rev D circuit.

## Open in KiCad
1. Extract the whole ZIP into one folder.
2. Open `Piezo_MCP6002_RevD.kicad_pro` in KiCad 7 or newer.
3. Open the schematic and the PCB from the project tree. If you edit copper, press **B** to refill the zones.

Keep `Piezo_PCB.pretty`, `Piezo_Local.kicad_sym`, `fp-lib-table` and `sym-lib-table` with the project.

## What is included
- Routed two-layer PCB, **48 × 32 mm** (Rev C: 70 × 45 mm), 1.6 mm.
- **All signal tracks on the top layer.** The bottom layer is an unbroken GND plane (best shielding for the high-impedance piezo input). GND pour on top as well.
- 33 components, 0.25 mm tracks, 0.6/0.3 mm vias (8 GND vias next to the SMD GND pads + about 90 stitching vias).
- `Schematic.pdf`, `PCB_top_preview`, `PCB_bottom_preview`, `PCB_routing_preview` (pours hidden), `PCB_assembly` (PNG + PDF).
- `Gerbers_Piezo_MCP6002_RevD.zip`: copper, mask, silk, paste, outline and Excellon drill. Ready to upload to JLCPCB / PCBWay.
- `BOM.csv`, `DRC.txt`, `Validation.txt`, `Connectivity.txt`.

## Changes from Rev C
| | Rev C | Rev D |
|---|---|---|
| Low-pass | 9.9 kHz, E96 values (14.7 k, 6.19 k) | **15 kHz**, E24 values (9.1 k, 3.9 k), sold in Baghdad |
| C1 (1 µF film input cap) | yes | **removed**: the piezo already blocks DC |
| Input clamp | BAV199 | **BAV99** (same SOT-23 pinout, in stock at Al-Hekmh) |
| Gain | fixed 11 | **11 with JP1 bridged / 48 with JP1 open** (R3 22 k + R14 82 k) |
| Stability | – | C5 47 pF across the feedback network |
| Outputs | J3 only | **J3 OUT_DC** (ESP32-S3 ADC, via R7/C6) + **J4 OUT_AC** (PCM1808, via C7/R13) |
| Supply filter | R12 22 Ω | R12 10 Ω |

## Connectors
| Connector | Pin 1 (square pad) | Pin 2 |
|---|---|---|
| J1 | Piezo ceramic (+) | Piezo brass / GND |
| J2 | Regulated 3.3 V from the ESP32 board | GND |
| J3 | OUT_DC, biased at 1.65 V, to ESP32-S3 GPIO1 | GND |
| J4 | OUT_AC to PCM1808 `L` | GND |

## Assembly notes
- **JP1:** bridge the two pads with solder for gain 11 (start here). Remove the bridge for gain 48.
- U1/U2 are DIP-8 (MCP6002-I/P from Al-Hekmh). Sockets are optional, but they add height (see the housing).
- Filter capacitors C8–C11 and C5 must be **C0G/NP0**. Clean the flux around R1/R2/D1/U1 pin 3 (high-impedance node).
- Three reference labels (C6, R10, R14) had no free silkscreen spot. They are on the assembly (F.Fab) layer: see `PCB_assembly.png`.
- Housing for this board: `../../stl/revD_48x32/` (58 × 42 mm body). Trim the through-hole leads to ≤ 1 mm under the board, because the cover lip leaves 1 mm.

## Validation
KiCad 7.0.11. DRC: **0 violations, 0 unconnected pads, 0 footprint errors**, with the Rev C project rules
(0.2 mm clearance, 0.5 mm copper-to-edge, 0.8 mm silk text). All 79 pad nets and 33 values/footprints match the schematic
netlist exported by KiCad itself (`Validation.txt`). No ERC (not available in kicad-cli 7), and no hardware test yet.

## Regenerate
Everything is produced by scripts in `../tools/` (`design.py` = the netlist):
`bash tools/build_all.sh` (add `--place` to re-run placement). Routing uses a custom 2-layer grid router, then KiCad fills the zones and runs DRC.
