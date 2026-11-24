# Piezo needle vibration sensor (for tissue classification)

A very small, very cheap contact sensor that clips onto the **proximal (outside) end of a needle**.
It picks up the vibration made at the needle tip as it passes through tissue layers.
The signal goes into a PC as ordinary 48 kHz audio, and Python handles event detection and tissue classification.

> Research and phantom/ex-vivo use only. Using this on patients requires sterilisation, electrical-safety
> isolation, ethics approval and medical-device approval.

---

## 1. What SURAG does (from patent EP 4 417 134 A1 and their papers)

| Item | SURAG (EP 4 417 134 A1, SURAG Medical GmbH, filed 15-02-2024) |
|---|---|
| Principle | The needle–tissue interaction makes a vibro-acoustic (VA) wave that travels **passively** up the needle. A sensor at the proximal end picks it up ([0048]). Nothing is placed in the patient. |
| Coupling | A coupling element (4a), ideally fitting **Luer-lock** or using a **clothes-peg style clamp** ([0043], [0045], Fig. 8). For biopsy needles, an adapter (3) made of two angled jaws (Fig. 5). |
| Sensor, option A ("direct", claim 2) | **Piezo or crystal microphone bonded directly to the coupling element** ([0058], Figs. 2 and 5). |
| Sensor, option B ("indirect", claim 3) | Membrane, then a tapered sound chamber, then a small air microphone (mechanical amplification, [0059]–[0072]). |
| Electronics | Analog pre-processing (4d), ADC (4e), controller (4f), wired or wireless link (4g) to a PC (5) ([0149]). |
| Processing | DC removal, then noise reduction (spectral gating), then enhancement (filters or DWT), then **event detection (Page-Hinkley / CUSUM)**, then features (time, spectral band energies, *instantaneous dominant frequency*, envelope), then SVM / kNN / Random Forest / CNN ([0110]–[0141]). |
| Classes for needles | Tissue type (fat / muscle / connective tissue) or layer (fascia, peritoneum) ([0141]). A Veress puncture event lasts about **50 ms** ([0103]). |

**This design uses option A**, a piezo disc bonded straight to the coupling. It needs the fewest parts, is the smallest,
has no air path that room noise can leak into, and is the cheapest.

### Patent note (not legal advice)
* EP 4 417 134 A1 is an **application**, not a granted patent. The EPO search report marks SURAG's own earlier
  patent DE 10 2017 114 077 (= WO 2019/002318, US 2020/229764, granted as **US 11,918,380 B2**) as an "X" document
  against claims 1–4. That means the broad device claims may not be new.
* Patents only apply in the countries where they are granted. The designated states are European countries plus
  some extension and validation states. **Iraq is not among them.** Academic research is also normally exempt.
* If you ever want to **sell** the device in Europe or the USA, have a patent attorney check it first.

---

## 2. The design: 4 parts + a clip

```
                3-D printed clip (PETG)            shielded 2-core cable (old earphone / mic lead)
          ┌───────────────────────────────┐        ┌──────────────────────────────────────────┐
needle ═══╪══▶ V-groove ▼                 │        │                                          │
shaft     │   ┌─────────────┐  hot-glue   │        │                                          ▼
          │   │ brass ▓▓▓▓▓ │  potting    │   G    │  D ─────────────── TIP (mic in, has bias) │  USB
          │   │ ceramic ░░░ ├──┬──────────┼──▶ JFET│                                    USB sound card ─▶ PC / laptop
          │   └─────────────┘  │          │        │  S ─────────────── SLEEVE (ground)        │  (16-bit, 48 kHz)
          │       piezo disc   Rg 10 MΩ   │        │                                          │
          │       (12–15 mm)   │          │        └──────────────────────────────────────────┘
          │       brass ───────┴──────────┼──────── GND (sleeve + cable shield)
          └───────────────────────────────┘
```

### Electrical schematic (it is the same circuit as inside an electret microphone)

```
  piezo (+) ceramic side ───────┬──────────── G
                                │             JFET (J201 / 2SK30A / BF245A / 2N3819)
                              Rg 10 MΩ        D ──────────────▶ 3.5 mm plug TIP  (mic input, provides ~2–3 V bias)
                                │             S ──┬───────────▶ 3.5 mm plug SLEEVE (GND)
  piezo (–) brass side ─────────┴─────────────────┘
                                             (Rs: see table; 0 Ω for J201 / 2SK30A)
```

* The sound card's **mic-in "plug-in power"** (about 2–3 V through about 2.2 kΩ) powers the JFET. You need **no battery and no op-amp**.
* The JFET turns the piezo's very high impedance into a low impedance. Without it, the sound card's 2 kΩ input would cut
  off everything below about 10 kHz, and the cable would pick up noise.
* Rg = 10 MΩ and a 12 mm disc (C ≈ 5–8 nF) give a low cut-off of about **2–3 Hz**. The upper limit is set by the sound card (≈ 20 kHz).
  That covers the whole band SURAG uses (they record at 44.1 kHz).

| JFET you can find | Rs (source to GND) | Notes |
|---|---|---|
| J201, 2SK30A-O/Y, 2SK170 | **0 Ω** (S straight to GND) | Best choice: low Idss suits mic bias. |
| BF245A, 2N3819, MPF102 | **2.2 kΩ** (try 1–4.7 kΩ) | Idss is higher, so the resistor brings the drain to about half the bias voltage. |
| None available | — | Break open a ~250 IQD **electret mic capsule**, remove its diaphragm, and solder the piezo to the gate pad. The JFET inside is already wired correctly. |

### Bill of materials

| # | Part | Exact spec | Qty | Est. price (IQD)* |
|---|---|---|---|---|
| 1 | Piezo disc (bare buzzer element) | **12 mm or 15 mm** brass disc, with wires (20 mm works too; less sensitive at high frequencies but more signal) | 2 (1 spare) | 250–1,000 each |
| 2 | N-channel JFET | J201 / 2SK30A / BF245A / 2N3819 (see table) | 2 | 500–1,500 each |
| 3 | Resistor | 10 MΩ ¼ W (plus 2.2 kΩ if you use BF245/2N3819) | 2 | 50–250 |
| 4 | USB sound card | Any "USB 7.1 / 3D sound" dongle with a **mic input** (C-Media CM108/CM119 chip) | 1 | 3,000–7,000 |
| – | Cable | 3.5 mm **mono or stereo** plug with shielded lead (cut from old earphones or an aux cable) | 1 | 500–1,500 |
| – | Clip | 3-D printed (PETG/PLA), file `clip_dimensions` below; or a small wooden or plastic clothes-peg | 1 | 1,000–3,000 printing |
| – | Glue | Cyanoacrylate (super glue) for the disc, hot glue for potting | – | 500 |

\***Estimated** Baghdad street prices. I could not load the stores' websites from here to check current prices, so confirm by phone.
**Total ≈ 6,000–15,000 IQD (about $5–10).**

### Mechanical clip (smallest working version)

* Body: 20 × 18 × 8 mm clothes-peg style clip (as in patent Fig. 8, here holding a piezo instead of a membrane).
* **Jaw 1:** a 13–16 mm round pocket, 1 mm deep. The piezo **brass face points outward** and the ceramic side sits in the pocket on a 0.5 mm
  foam/rubber ring, so the disc can vibrate freely and is isolated from the clip.
* **Jaw 2:** a 90° **V-groove** that pushes the needle shaft (or the metal part of the hub) onto the **centre** of the brass face.
  A rubber band or the peg's spring gives the clamping force. Keep the force the same for every recording, because it changes the gain.
* Better option: put a **drop of super glue or a 2–3 mm steel bead** at the centre of the brass so the needle touches one hard point.
  Metal-to-metal contact transmits the high frequencies (puncture "clicks").
* Put the JFET and Rg **inside the clip**, within 2 cm of the disc, and fill with hot glue. Only the low-impedance cable leaves the clip.
* For your robot (Mygo2), mount the clip on the needle **between the needle holder and the hub**, and isolate the holder from the
  robot with a rubber pad so that motor vibration does not reach the piezo.

---

## 3. Where to buy in Baghdad

I could not open these shops' product pages from my environment, so **stock is not verified**. Call or message them with the Arabic list below.

| Shop | Where | Good for |
|---|---|---|
| **Al-Hekmh Electronics** (alhekmh.com) | Electronics market, **Tahrir Square, Baghdad** | Sensors, modules, transistors, resistors |
| **Ardunic Shop** (ardunic.com) | **Jadriya, Baghdad**, tel. +964 771 818 0804, daily about 9:00–20:00, delivers | Arduino/maker parts, piezo, sound modules |
| **UrukTech** (uruktech.com) | Baghdad, online with delivery to all of Iraq | Maker parts, kits |
| **Dijlah Electronics** (دجلة للالكترونيات) | Baghdad, Facebook page with orders through its website | Arduino and accessories |
| Iraqi Bazaar (iraqibazaar.com) | Online, prices in IQD | USB sound card, cables |
| Sangar Tech (sangartech.com) | Sulaymaniyah, ships to Baghdad | Backup source for JFETs and piezo |

USB sound cards and earphone cables are sold in any computer-accessory shop in Baghdad (for example in the computer markets on
**Al-Sinaa Street**). Piezo buzzer discs, JFETs and resistors are standard stock in the component shops around the Tahrir Square electronics market.

### Shopping list in Arabic (copy and send)

```
السلام عليكم، أحتاج القطع التالية:
1) قرص بيزو (Piezo disc / buzzer element) قطر 12 ملم أو 15 ملم مع أسلاك — عدد 2
2) ترانزستور JFET نوع J201 أو 2SK30A أو BF245A أو 2N3819 — عدد 2
3) مقاومة 10 ميگا أوم (10MΩ) ربع واط — عدد 2، ومقاومة 2.2 كيلو أوم — عدد 2
4) كارت صوت USB (USB Sound Card) فيه مدخل مايك — عدد 1
5) كيبل صوت 3.5 ملم مع شيلد (Shielded) — عدد 1
هل متوفرة وكم السعر؟ شكراً
```

---

## 4. Build and test (about 1 hour)

1. Solder Rg (10 MΩ) between the piezo's two wires, as close to the disc as possible.
2. JFET: **gate** to the ceramic (+) wire, **source** to the brass (–) wire and the cable shield, **drain** to the plug **tip**.
   On a stereo plug, join tip and ring. (Pinouts differ: J201 is D-S-G, 2N3819 is D-G-S, BF245A is G-S-D. Check the datasheet.)
3. Plug into the USB sound card's **pink mic jack**. In the OS sound settings, set mic level to about 50 % and **turn off AGC,
   noise suppression and "enhancements"**, which would distort the signal.
4. Run `python software/record.py --list` to find the device, then
   `python software/record.py --device <id> --seconds 10 --out test.wav`.
   Tap the needle tip lightly. You should see sharp clicks, and the script prints peak level and noise floor.
5. If nothing comes through: measure the drain voltage with the plug inserted. It should be 0.5–2 V. About 0 V means no bias (try
   another card or check the wiring). Close to the full bias voltage means the JFET is off (check the gate wire, or try Rs = 0).

---

## 5. Data and classification pipeline (`software/`)

| Script | What it does |
|---|---|
| `record.py` | Records the piezo from the USB sound card (48 kHz, 16-bit) to WAV, live level meter, optional label. |
| `analyze.py` | Pre-processing (DC removal, 50 Hz–20 kHz band-pass, noise-floor gating), then **event detection (Page-Hinkley/CUSUM on the envelope)**, then per-event features (RMS, peak, kurtosis, crest factor, rise slope, spectral centroid, roll-off, 6 log band energies, **instantaneous dominant frequency** mean/std/slope, envelope peaks), then **Random Forest** with cross-validation. |

Workflow for tissue classification:

```
data/
  fat/      ins_001.wav ins_002.wav ...
  muscle/   ...
  liver/    ...
  fascia/   ...
python software/analyze.py train  --data data --model model.joblib
python software/analyze.py predict --model model.joblib --wav new_insertion.wav
python software/analyze.py events  --wav new_insertion.wav --plot     # see detected punctures
```

Tips that matter more than the hardware:
* Fix the **insertion speed** (the robot helps here: use 1–5 mm/s and keep it constant), the needle type, and the clip force.
* Record **≥ 30 insertions per tissue class** and split train/test **by sample/specimen**, not by event, to avoid leakage.
* Log the robot's needle depth at the same time as the audio. Depth plus VA features works much better than VA alone.
* Record 5 s of the robot moving **without tissue** first to see motor noise, and filter or isolate it.
