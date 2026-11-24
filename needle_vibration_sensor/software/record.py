#!/usr/bin/env python3
"""Record the piezo needle sensor from a USB sound card.

    pip install sounddevice soundfile numpy
    python record.py --list
    python record.py --device 3 --seconds 10 --out data/fat/ins_001.wav
"""
import argparse
import sys
import time

import numpy as np

try:
    import sounddevice as sd
    import soundfile as sf
except ImportError:
    sys.exit("Install first:  pip install sounddevice soundfile numpy")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--list", action="store_true", help="list audio devices and exit")
    p.add_argument("--device", type=int, help="input device index (from --list)")
    p.add_argument("--rate", type=int, default=48000, help="sample rate (48000 or 44100)")
    p.add_argument("--seconds", type=float, default=10.0)
    p.add_argument("--out", default="recording.wav")
    args = p.parse_args()

    if args.list:
        print(sd.query_devices())
        return

    frames = int(args.seconds * args.rate)
    print(f"Recording {args.seconds:.1f} s @ {args.rate} Hz from device {args.device} ... insert the needle now.")
    chunks = []

    def cb(indata, n, t, status):
        if status:
            print(status, file=sys.stderr)
        chunks.append(indata[:, 0].copy())
        peak = float(np.max(np.abs(indata[:, 0])))
        bar = "#" * int(min(peak, 1.0) * 50)
        print(f"\r|{bar:<50}| {peak:5.3f}", end="", flush=True)

    with sd.InputStream(device=args.device, channels=1, samplerate=args.rate,
                        dtype="float32", blocksize=1024, callback=cb):
        time.sleep(args.seconds)
    print()

    x = np.concatenate(chunks)[:frames]
    sf.write(args.out, x, args.rate, subtype="PCM_16")

    x = x - np.mean(x)
    peak = np.max(np.abs(x))
    floor = np.percentile(np.abs(x), 20) + 1e-12
    print(f"saved {args.out}: peak={peak:.3f} FS, noise floor≈{floor:.5f} FS, "
          f"peak/floor={20*np.log10(peak/floor):.1f} dB")
    if peak > 0.98:
        print("WARNING: clipping. Lower the mic level in the OS mixer.")
    if peak < 0.01:
        print("WARNING: very weak signal. Check the JFET wiring/bias or raise the mic level.")


if __name__ == "__main__":
    main()
