#!/usr/bin/env python3
"""Receive the wireless needle sensor stream (UDP) and save it as a WAV file.

1. Connect the laptop's Wi-Fi to "NEEDLE-SENSOR" (password needle1234).
2. python receiver.py --seconds 20 --out data/fat/ins_001.wav

Output WAV: float32, channel 0 = needle piezo (and channel 1 = 2nd piezo in PCM1808 mode),
last channel = robot trigger (0/1). Lost packets are filled with zeros and reported.
"""
import argparse
import socket
import struct
import time

import numpy as np

HDR = struct.Struct("<4sIIBBBB")


def decode(payload, fmt, nch):
    if fmt == 1:                                   # uint16 12-bit codes -> float around 0
        x = np.frombuffer(payload, "<u2").astype(np.float32)
        return ((x - 2048.0) / 2048.0).reshape(-1, 1)
    if fmt == 2:                                   # packed int24, interleaved
        b = np.frombuffer(payload, np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        v = np.where(v & 0x800000, v - (1 << 24), v)
        return (v / float(1 << 23)).astype(np.float32).reshape(-1, nch)
    raise ValueError(f"unknown format {fmt}")


def receive(sock, seconds, esp_ip="192.168.4.1", port=5005, verbose=True):
    chunks, last_seq, lost, fs, t_end, t_hello = [], None, 0, None, time.time() + seconds, 0
    sock.settimeout(0.5)
    while time.time() < t_end:
        if time.time() - t_hello > 1.0:            # keep-alive so the ESP keeps streaming to us
            sock.sendto(b"hello", (esp_ip, port)); t_hello = time.time()
        try:
            data, _ = sock.recvfrom(2048)
        except socket.timeout:
            if verbose:
                print("waiting for sensor ...")
            continue
        magic, seq, fs_pkt, fmt, nch, trig, _ = HDR.unpack_from(data)
        if magic != b"NDL1":
            continue
        x = decode(data[HDR.size:], fmt, nch)
        if last_seq is not None and seq != last_seq + 1 and seq > last_seq:
            gap = seq - last_seq - 1
            lost += gap
            chunks += [np.zeros((len(x), x.shape[1] + 1), np.float32)] * gap
        last_seq, fs = seq, fs_pkt
        chunks.append(np.hstack([x, np.full((len(x), 1), trig, np.float32)]))
    if not chunks:
        raise SystemExit("no data received - is the laptop connected to NEEDLE-SENSOR?")
    return np.vstack(chunks), fs, lost, len(chunks)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seconds", type=float, default=10)
    p.add_argument("--out", default="wireless.wav")
    p.add_argument("--esp", default="192.168.4.1")
    p.add_argument("--port", type=int, default=5005)
    a = p.parse_args()

    import soundfile as sf
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", a.port))
    x, fs, lost, n = receive(s, a.seconds, a.esp, a.port)
    sf.write(a.out, x, fs, subtype="FLOAT")
    print(f"saved {a.out}: {len(x)/fs:.1f} s @ {fs} Hz, {x.shape[1]-1} signal ch + trigger, "
          f"lost packets {lost}/{n + lost} ({100*lost/max(1, n+lost):.2f} %)")


if __name__ == "__main__":
    main()
