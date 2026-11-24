"""Rev D netlist: single source of truth for schematic + PCB generators."""

# ref, value, symbol, footprint, {pin: net}
PARTS = [
    ("J1", "PIEZO", "Conn_2", "Header_1x02", {"1": "PZ", "2": "GND"}),
    ("J2", "3V3 IN", "Conn_2", "Header_1x02", {"1": "V33", "2": "GND"}),
    ("J3", "OUT_DC (ESP32 ADC)", "Conn_2", "Header_1x02", {"1": "OUT_DC", "2": "GND"}),
    ("J4", "OUT_AC (PCM1808)", "Conn_2", "Header_1x02", {"1": "OUT_AC", "2": "GND"}),
    ("R1", "22k", "R_H", "R1206", {"1": "PZ", "2": "IN"}),
    ("R2", "4.7M", "R_V", "R1206", {"1": "IN", "2": "VREF"}),
    ("D1", "BAV99", "BAV199", "BAV99_SOT23", {"3": "IN", "1": "VREF", "2": "VREF"}),
    ("R4", "2.2k 1%", "R_V", "R1206", {"1": "FB", "2": "VREF"}),
    ("R3", "22k 1%", "R_H", "R1206", {"1": "FB", "2": "X"}),
    ("R14", "82k 1%", "R_H", "R1206", {"1": "X", "2": "AMP"}),
    ("JP1", "GAIN 11 = closed", "SJ_H", "SolderJumper_2", {"1": "X", "2": "AMP"}),
    ("C5", "47p C0G", "C_H", "C1206", {"1": "FB", "2": "AMP"}),
    ("R5", "10k", "R_V", "R1206", {"1": "AVDD", "2": "VDIV"}),
    ("R6", "10k", "R_V", "R1206", {"1": "VDIV", "2": "GND"}),
    ("C4", "10u", "C_V", "C1210", {"1": "VDIV", "2": "GND"}),
    ("R8", "9.1k 1%", "R_H", "R1206", {"1": "AMP", "2": "A1"}),
    ("R9", "9.1k 1%", "R_H", "R1206", {"1": "A1", "2": "P1"}),
    ("C8", "1.2n C0G", "C_H", "C1206", {"1": "A1", "2": "LP1"}),
    ("C9", "1n C0G", "C_V", "C1206", {"1": "P1", "2": "GND"}),
    ("R10", "3.9k 1%", "R_H", "R1206", {"1": "LP1", "2": "A2"}),
    ("R11", "3.9k 1%", "R_H", "R1206", {"1": "A2", "2": "P2"}),
    ("C10", "6.8n C0G", "C_H", "C1206", {"1": "A2", "2": "FOUT"}),
    ("C11", "1n C0G", "C_V", "C1206", {"1": "P2", "2": "GND"}),
    ("R7", "100R", "R_H", "R1206", {"1": "FOUT", "2": "OUT_DC"}),
    ("C6", "10n", "C_V", "C1206", {"1": "OUT_DC", "2": "GND"}),
    ("C7", "2.2u X7R", "C_H", "C1206", {"1": "FOUT", "2": "OACX"}),
    ("R13", "100R", "R_H", "R1206", {"1": "OACX", "2": "OUT_AC"}),
    ("R12", "10R", "R_H", "R1206", {"1": "V33", "2": "AVDD"}),
    ("C3", "47u", "C_V", "C1210", {"1": "AVDD", "2": "GND"}),
    ("C2", "100n", "C_V", "C1206", {"1": "AVDD", "2": "GND"}),
    ("C12", "100n", "C_V", "C1206", {"1": "AVDD", "2": "GND"}),
    ("U1", "MCP6002-I/P", "MCP6002_DIP", "DIP8",
     {"3": "IN", "2": "FB", "1": "AMP", "5": "VDIV", "6": "VREF", "7": "VREF", "8": "AVDD", "4": "GND"}),
    ("U2", "MCP6002-I/P", "MCP6002_DIP", "DIP8",
     {"3": "P1", "2": "LP1", "1": "LP1", "5": "P2", "6": "FOUT", "7": "FOUT", "8": "AVDD", "4": "GND"}),
]

UNIT_PINS = {"MCP6002_DIP": {1: ["3", "2", "1"], 2: ["5", "6", "7"], 3: ["8", "4"]},
             "BAV199": {1: ["3", "1"], 2: ["3", "2"]}}


def netmap():
    nets = {}
    for ref, _, _, _, pins in PARTS:
        for p, n in pins.items():
            nets.setdefault(n, set()).add((ref, p))
    return nets
