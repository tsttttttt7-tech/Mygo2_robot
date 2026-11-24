#!/usr/bin/env python3
"""Frequency response of the piezo front end (gain stage + 4th-order Butterworth, 15 kHz).

Models: piezo as Cp in series, R1+R2 input network, MCP6002 as single-pole 1 MHz GBW.
    python filter_response.py [--gain 11] [--cp 10e-9]
"""
import argparse
import numpy as np

GBW = 1e6


def sallen_key(f, R1, R2, C1, C2):
    """Unity-gain Sallen-Key low-pass; C1 = feedback cap (to output), C2 = cap to GND."""
    s = 2j * np.pi * f
    k = (2 * np.pi * GBW / s) / (1 + 2 * np.pi * GBW / s)
    M = np.array([[1 / R1 + 1 / R2 + s * C1, -1 / R2 - s * C1 * k],
                  [-1 / R2, 1 / R2 + s * C2]])
    Va, Vp = np.linalg.solve(M, np.array([1 / R1, 0]))
    return k * Vp


def response(f, gain=11.0, cp=10e-9, r1=22e3, r2=4.7e6):
    s = 2j * np.pi * f
    hp = s * cp * r2 / (1 + s * cp * (r1 + r2))
    g = gain / (1 + gain * s / (2 * np.pi * GBW))
    return hp * g * sallen_key(f, 9.1e3, 9.1e3, 1.2e-9, 1e-9) * sallen_key(f, 3.9e3, 3.9e3, 6.8e-9, 1e-9)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--gain", type=float, default=11.0)
    p.add_argument("--cp", type=float, default=10e-9, help="piezo capacitance (F)")
    a = p.parse_args()
    for f in [10, 30, 100, 1e3, 5e3, 10e3, 12e3, 15e3, 20e3, 24e3, 40e3, 65e3, 80e3]:
        h = response(f, a.gain, a.cp)
        print(f"{f:8.0f} Hz  {20*np.log10(abs(h)/a.gain):7.2f} dB (rel. to gain {a.gain:g})")
