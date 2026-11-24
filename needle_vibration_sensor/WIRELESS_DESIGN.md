# Wireless piezo needle sensor: amplifier/filter, ADC, microcontroller, Wi-Fi

```
 needle ─▶ piezo disc ─▶ [AMP + FILTER PCB]  ─────────▶  ADC  ─────▶  ESP32-S3  ─── Wi-Fi (UDP) ───▶ laptop
           (20/27 mm)    MCP6002 ×2, gain 11/48         A: ESP32-S3 built-in            "NEEDLE-SENSOR"      receiver.py ─▶ WAV
                         4th-order 15 kHz low-pass         12-bit, 80 kSPS                                    analyze.py ─▶ tissue class
                         3.3 V, about 35 × 25 mm        B: PCM1808 module
                                                           24-bit, 48 kSPS
```

## Short answer

| Block | Choice | Why | Available in Baghdad? |
|---|---|---|---|
| Sensor | Piezo disc 20 mm (or 27 mm), brass side on the needle | Direct contact, as in patent EP 4 417 134 claim 2 | **Yes**: Al-Hekmh lists 27 mm / 20 mm discs (BUZZ27/BUZZ20) |
| Amplifier + filter | **2 × MCP6002** (your Rev C topology, retuned) | Rail-to-rail at 3.3 V, picoamp input current (good for piezo), 1 MHz | **Yes**: [MCP6002-I/P at Al-Hekmh](https://alhekmh.com/mcp6002-i-p-ic-opamp-dual-rail-to-rail-1-8v-5-5v-1mhz-10t-dip-8/) |
| Input clamp | BAV99 (SOT-23) | Available version of the BAV199 | **Yes**: [BAV99 at Al-Hekmh](https://alhekmh.com/bav99-a7-diode-dual-series-fast-100v-215ma-4ns-sot-23/) |
| ADC (buy, no PCB) | **A: built into the ESP32-S3** (12-bit, 80 kSPS) | The only fast ADC I could find in Iraqi shops | **Yes**: comes with the ESP32 board |
| | **B: PCM1808 module** (24-bit, 99 dB SNR, 48 kSPS) | Best quality, about $3–5, has its own anti-alias filter | **No**: not listed by any Iraqi shop I found. Order online. |
| | ~~ADS1115 module~~ | Only 860 samples/s. Needle vibration needs at least 30,000/s. | Yes (UrukTech, Qariya), but **unsuitable** |
| Microcontroller + wireless | **ESP32-S3 N16R8** board | Dual core, Wi-Fi, fast ADC DMA, I²S master with MCLK on any pin | **Yes**: [Iraqi Bazaar, IQD 20,000](https://iraqibazaar.com/en/product/esp32-s3-n16r8-cam-16mb-flash-8mb-psram-without-camera/) |
| Link | Wi-Fi **SoftAP + UDP**, 160–290 kB/s | No router needed, about 10 m range, packet-loss counter | – |
| Power | 1 × 18650 or LiPo with charger + 5 V boost (an "18650 battery shield"), or a small USB power bank | ESP32 Wi-Fi peaks at about 350 mA | Common in Baghdad shops (not checked online) |

**Recommended path:** build the amplifier PCB and the ESP32-S3 with **ADC A** now, from parts available in Baghdad.
Order a PCM1808 module online at the same time. When it arrives, connect it to the same PCB output and set
`#define ADC_MODE 1` in the firmware. Nothing else changes.

Bluetooth is **not** used. BLE manages about 50–100 kB/s in practice, which is too little for continuous 24-bit audio.

---

## 1. Amplifier + filter PCB (you make this one)

Single 3.3 V supply. Same topology as your Rev C, with these changes:

| Change vs Rev C | Reason |
|---|---|
| Low-pass corner **9.9 kHz → 15 kHz** | Puncture events excite high frequencies (patent [0138]). Keep more of them. |
| All filter values from the **E24 series** (9.1 k, 3.9 k) | Shops in Baghdad stock E24 values, not 14.7 k / 6.19 k 1 % parts. |
| **BAV199 → BAV99** | BAV99 is in stock at Al-Hekmh. At about 0 V bias its leakage is negligible. |
| **C1 removed** | The piezo is itself a capacitor, so it already blocks DC. One less, and the largest, part. |
| **Gain jumper ×11 / ×48** | ×48 for the 12-bit ESP32 ADC (otherwise ADC noise dominates). ×11 for the PCM1808. |
| Two outputs: **DC output** (to the ESP32 ADC) and **AC output** (to the PCM1808) | So one PCB serves both ADCs. |

### Netlist (U1, U2 = MCP6002, SOIC-8 or DIP-8; pin 8 = AVDD, pin 4 = GND)

| Ref | Value | Connects | Function |
|---|---|---|---|
| J1 | 2-pin | 1 = piezo ceramic (+), 2 = piezo brass, **GND** | Piezo input. Keep the wires under 3 cm. |
| R1 | 22 kΩ | J1.1 → IN | Limits current during big impacts (MCP6002 input limit ±2 mA up to about 44 V) |
| R2 | 4.7 MΩ | IN → VREF | Input bias. Low cut-off ≈ 3.4 Hz with a 10 nF piezo. |
| D1 | BAV99 | pin 3 → IN; pins 1 and 2 → VREF | Anti-parallel clamp to VREF |
| U1A | MCP6002 | + (3) = IN, − (2) = FB, out (1) = AMP | Non-inverting gain stage |
| R4 | 2.2 kΩ 1 % | FB → VREF | Gain resistor |
| R3 | 22 kΩ 1 % | FB → X | Feedback |
| R14 + JP1 | 82 kΩ 1 %, solder jumper across it | X → AMP | JP1 closed: gain **11**. JP1 open: gain **48**. |
| C5 | 47 pF C0G | across R3 + R14 (FB → AMP) | Stability and RF roll-off |
| R5, R6 | 10 kΩ, 10 kΩ | AVDD → VDIV → GND | Half-supply divider |
| C4 | 10 µF | VDIV → GND | Filters VREF (placed **before** the buffer) |
| U1B | MCP6002 | + (5) = VDIV, − (6) = out (7) = **VREF** | VREF buffer, 1.65 V |
| R8, R9 | 9.1 kΩ, 9.1 kΩ | AMP → A1 → P1 | Sallen-Key 1 (Q = 0.55, f₀ = 16.0 kHz) |
| C8 | 1.2 nF film/C0G | A1 → LP1 (U2A output) | Feedback capacitor |
| C9 | 1 nF film/C0G | P1 → GND | |
| U2A | MCP6002 | + (3) = P1, − (2) = out (1) = LP1 | Unity-gain buffer |
| R10, R11 | 3.9 kΩ, 3.9 kΩ | LP1 → A2 → P2 | Sallen-Key 2 (Q = 1.30, f₀ = 15.7 kHz) |
| C10 | 6.8 nF film/C0G | A2 → FOUT (U2B output) | Feedback capacitor |
| C11 | 1 nF film/C0G | P2 → GND | |
| U2B | MCP6002 | + (5) = P2, − (6) = out (7) = FOUT | Unity-gain buffer |
| R7, C6 | 100 Ω, 10 nF | FOUT → **J3.1 (OUT_DC)**; C6 to GND | Charge reservoir for the ESP32 ADC's sampling capacitor |
| C7, R13 | 2.2 µF film or X7R, 100 Ω | FOUT → C7 → R13 → **J4.1 (OUT_AC)** | AC output for the PCM1808 |
| R12 | 10 Ω | J2.1 (3V3 from ESP32 board) → AVDD | Supply filter, together with C3 |
| C3 | 47 µF | AVDD → GND | |
| C2, C12 | 100 nF | U1/U2 pin 8 → GND, right at the pins | Decoupling |
| J2, J3, J4 | 2-pin each | 3V3/GND, OUT_DC/GND, OUT_AC/GND | |

That is **31 parts**. With SOIC-8 and 0805 parts the board fits in about **30 × 20 mm**; with DIP-8 (the version confirmed in stock) about 40 × 25 mm.
Use 1206 if you hand-solder. Film (polyester "2A102J" type) capacitors are fine for the filter. Do not use X7R or Y5V there: they are microphonic and drift.

### Calculated response (`software/filter_response.py`, MCP6002 1 MHz GBW model, 10 nF piezo)

| f | gain ×11 | gain ×48 |
|---|---|---|
| 30 Hz | −0.10 dB | – |
| 1 kHz | −0.04 dB | – |
| 10 kHz | +0.12 dB | – |
| 12 kHz | −0.23 dB | −1.40 dB |
| 15 kHz | −2.2 dB | −3.9 dB |
| 24 kHz | −15 dB | |
| 65 kHz (folds back into the band at 80 kSPS) | **−51 dB** | |

* Headroom: the output swings ±1.55 V, so the input clips at about **±140 mV (×11)** or **±32 mV (×48)**. Start at ×11, look at real
  punctures, then open JP1 if the signals are small.
* These are model results only, not measured. Check them on the bench (step 4 in your Rev C notes still applies).

### Layout rules
Put the PCB **on the clip, right behind the piezo**. Ground pour on the bottom layer. Guard ring around IN/R2/D1, and clean the flux there.
Keep the ESP32 and its antenna at least 5 cm away, connected by a 3-wire shielded cable (3V3, GND, OUT).

---

## 2. ADC

### A: ESP32-S3 built-in (available now)
* Connect J3 (OUT_DC) to **GPIO1** (ADC1 channel 0). Never use ADC2 pins, because ADC2 does not work while Wi-Fi is on.
* Continuous DMA at **80 kSPS**, 12 dB attenuation (0–3.1 V). The 4-pole filter acts as the anti-alias filter.
* Expect about 9–10 effective bits. Use **gain ×48** so that ADC noise is not the limit. Wi-Fi bursts add some noise: the firmware lowers
  TX power, and you should keep the antenna away from the analog board.

### B: PCM1808 module (best quality, order online)
* Module pins: `5V`, `3.3V`, `GND`, `SCK`, `BCK`, `LRC`, `OUT`, `FMT`, `MD0`, `MD1`, `L`, `R`.
* Tie **FMT = MD0 = MD1 = GND** (slave mode, I²S 24-bit). The ESP32 supplies all clocks.
* Wiring: SCK → GPIO38 (12.288 MHz MCLK), BCK → GPIO39, LRC → GPIO40, OUT → GPIO41, L → J4 (OUT_AC), 5V → 5 V, GND → GND.
* Full scale is about 3 Vpp at 5 V, which matches our ±1.55 V output. Use gain ×11. **R** is a free second channel: add a second piezo on the
  needle holder as a **reference for robot/motor noise**, then subtract it on the laptop (adaptive noise cancelling).
* The PCM1808 needs **5 V** for its analog section, so run this version from a 5 V boost / power bank.

---

## 3. Microcontroller: ESP32-S3

* Board: **ESP32-S3-N16R8** (DevKitC-1 style or the "CAM" board without camera, [Iraqi Bazaar IQD 20,000](https://iraqibazaar.com/en/product/esp32-s3-n16r8-cam-16mb-flash-8mb-psram-without-camera/)).
  The pins used (1, 38–42) are free on both boards.
* Firmware: `firmware/needle_sensor/needle_sensor.ino` (Arduino IDE, board package **esp32 by Espressif 3.x**, board "ESP32S3 Dev Module").
  Set `ADC_MODE` to 0 (built-in ADC) or 1 (PCM1808).
* **GPIO42 = sync input** from your robot (HIGH while inserting). It is recorded in every packet, so each recording carries the insertion timing.
* **I have not compiled this firmware** (the toolchain download is blocked in my environment). It follows the ESP-IDF 5 `adc_continuous` and
  `i2s_std` APIs. Compile it and fix any small errors when you first build it.

## 4. Wireless link

* The ESP32 creates its own network **NEEDLE-SENSOR** (password `needle1234`, channel 6). No router or internet needed.
* The laptop joins it and runs `python software/receiver.py --seconds 20 --out data/fat/ins_001.wav`.
  The receiver sends a "hello" every second, and the ESP streams **UDP** packets back to that laptop only:
  8 ms per packet at 80 kSPS (1.3 kB), or 5 ms at 48 kSPS stereo 24-bit (1.45 kB).
* Every packet has a sequence number. The receiver fills any lost packet with zeros and prints the loss rate
  (tested here with a simulated sensor, including a dropped packet).
* The resulting WAV opens directly in `analyze.py` (channel 0 = needle piezo, last channel = robot trigger).

## 5. Power

| Option | Parts | Notes |
|---|---|---|
| Simplest | Small USB power bank into the ESP32's USB-C | Clean enough with R12/C3. Needed for the PCM1808. |
| Smallest | 1 × 18650 (or 500 mAh LiPo) + TP4056 charger + 5 V boost, or an "18650 battery shield" board | Feed 5 V to the ESP32's 5V pin. **Do not** connect a bare 3.7 V cell to the 5V pin, because the AMS1117 regulator on the board drops out. |

The analog board takes its 3.3 V from the ESP32 board's 3V3 pin through R12/C3. About 2 mA.

---

## 6. Shopping list (Baghdad)

| Part | Qty | Where | Status |
|---|---|---|---|
| MCP6002-I/P (or SOIC) | 2 (+1 spare) | [Al-Hekmh, Tahrir Sq.](https://alhekmh.com/mcp6002-i-p-ic-opamp-dual-rail-to-rail-1-8v-5-5v-1mhz-10t-dip-8/) | Listed online |
| BAV99 SOT-23 | 1 | [Al-Hekmh](https://alhekmh.com/bav99-a7-diode-dual-series-fast-100v-215ma-4ns-sot-23/) | Listed online |
| Piezo disc 20 mm / 27 mm | 2 | [Al-Hekmh acoustics](https://alhekmh.com/acoustics/) (BUZZ27/BUZZ20) | Listed online |
| ESP32-S3 N16R8 board | 1 | [Iraqi Bazaar](https://iraqibazaar.com/en/product/esp32-s3-n16r8-cam-16mb-flash-8mb-psram-without-camera/), IQD 20,000 | Listed online |
| Resistors (22 k, 2.2 k, 82 k, 10 k ×2, 4.7 M, 9.1 k ×2, 3.9 k ×2, 100 Ω ×2, 10 Ω) | – | Any component shop, Tahrir Sq. market | Standard E24 values |
| Film caps 1 nF ×2, 1.2 nF, 6.8 nF; 47 pF; 10 nF; 100 nF ×2; 2.2 µF; 10 µF; 47 µF | – | Any component shop | Standard |
| 18650 battery shield **or** TP4056 + MT3608, or a power bank | 1 | Maker shops (UrukTech, Ardunic) | Common; not checked online |
| PCM1808 module (option B) | 1 | Order online (AliExpress, eBay, Amazon) | **Not found in Iraqi shops** |
| Fallback MCU: classic ESP32 DevKit | – | [UrukTech](https://www.uruktech.com/product/esp32-development-board/) | Works, but the ADC is noisier, and MCLK only on GPIO0/1/3 (change pins) |

Stock and prices change. Confirm by phone before you go. Qariya (Scientific Village) also lists ADS1115 and ESP32-S3 boards,
but some of its prices are shown in SAR, so I could not confirm it is an Iraqi shop.
