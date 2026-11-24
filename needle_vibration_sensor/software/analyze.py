#!/usr/bin/env python3
"""Event detection + feature extraction + tissue classification for piezo needle recordings.

    pip install numpy scipy scikit-learn soundfile joblib matplotlib

    python analyze.py events  --wav insertion.wav [--plot]
    python analyze.py train   --data data/ --model model.joblib
    python analyze.py predict --model model.joblib --wav insertion.wav

Folder layout for training: data/<tissue_class>/*.wav (one insertion per file).
"""
import argparse
import glob
import os
import sys

import numpy as np
from scipy import signal
from scipy.stats import kurtosis, skew

PRE_S, POST_S = 0.010, 0.090          # event window: 10 ms before, 90 ms after onset
REFRACTORY_S = 0.060                  # min spacing between events
BANDS = [(50, 500), (500, 1500), (1500, 3000), (3000, 6000), (6000, 10000), (10000, 20000)]


# ---------------------------------------------------------------- I/O
def load_wav(path):
    import soundfile as sf
    x, fs = sf.read(path, dtype="float64", always_2d=True)
    return x[:, 0], fs


# ---------------------------------------------------------------- pre-processing
def preprocess(x, fs):
    """DC removal, 50 Hz-20 kHz band-pass, mains notch (50 Hz Iraq grid)."""
    x = x - np.mean(x)
    hi = min(20000, 0.45 * fs)
    sos = signal.butter(4, [50, hi], btype="band", fs=fs, output="sos")
    x = signal.sosfiltfilt(sos, x)
    for f0 in (50, 100, 150):
        b, a = signal.iirnotch(f0, 30, fs)
        x = signal.filtfilt(b, a, x)
    return x


def envelope(x, fs, smooth_ms=1.0):
    env = np.abs(signal.hilbert(x))
    n = max(1, int(smooth_ms * 1e-3 * fs))
    return np.convolve(env, np.ones(n) / n, mode="same")


# ---------------------------------------------------------------- event detection
def detect_events(x, fs, k=6.0, ph_delta=0.05, ph_lambda=3.0):
    """Onsets of abrupt energy increases (punctures / layer transitions).

    Page-Hinkley test on the log-envelope (decimated to 1 kHz), confirmed by an
    amplitude threshold of median + k*MAD.
    """
    env = envelope(x, fs)
    step = max(1, int(fs / 1000))
    le = np.log(env[::step] + 1e-9)
    med = np.median(le)
    mad = np.median(np.abs(le - med)) + 1e-9
    thr = med + k * 1.4826 * mad

    onsets, m_t, M_t, mean, n = [], 0.0, 0.0, le[0], 1
    last = -np.inf
    for i, v in enumerate(le):
        mean += (v - mean) / n
        n += 1
        m_t += v - mean - ph_delta
        M_t = min(M_t, m_t)
        if m_t - M_t > ph_lambda:                       # upward change detected
            j = i
            # walk back to where the rise started
            while j > 0 and le[j - 1] < le[j] and i - j < 20:
                j -= 1
            if le[i:i + 20].max(initial=-np.inf) > thr and (i - last) * step / fs > REFRACTORY_S:
                onsets.append(j * step)
                last = i
            m_t, M_t, mean, n = 0.0, 0.0, v, 1          # reset after each detection
    return np.array(onsets, dtype=int)


def windows(x, fs, onsets):
    pre, post = int(PRE_S * fs), int(POST_S * fs)
    for o in onsets:
        a, b = o - pre, o + post
        if a >= 0 and b <= len(x):
            yield o, x[a:b]


# ---------------------------------------------------------------- features
def features(seg, fs):
    eps = 1e-12
    env = envelope(seg, fs, 0.5)
    rms = np.sqrt(np.mean(seg ** 2)) + eps
    peak = np.max(np.abs(seg)) + eps
    ipk = int(np.argmax(env))
    rise = (env[ipk] - env[0]) / (ipk / fs + 1e-4)
    decay_n = np.argmax(env[ipk:] < env[ipk] / np.e) if np.any(env[ipk:] < env[ipk] / np.e) else len(env) - ipk
    env_peaks = len(signal.find_peaks(env, prominence=0.2 * env.max())[0])

    f, P = signal.welch(seg, fs, nperseg=min(1024, len(seg)))
    P = P + eps
    Pn = P / P.sum()
    centroid = np.sum(f * Pn)
    bandwidth = np.sqrt(np.sum(((f - centroid) ** 2) * Pn))
    rolloff = f[np.searchsorted(np.cumsum(Pn), 0.85)]
    flatness = np.exp(np.mean(np.log(P))) / np.mean(P)
    band_e = [np.log10(P[(f >= lo) & (f < hi)].sum() + eps) for lo, hi in BANDS]
    band_rel = [P[(f >= lo) & (f < hi)].sum() / P.sum() for lo, hi in BANDS]

    # instantaneous dominant frequency (frequency of max energy at each time step)
    ff, tt, S = signal.spectrogram(seg, fs, nperseg=256, noverlap=192)
    idf = ff[np.argmax(S, axis=0)]
    idf_slope = np.polyfit(np.arange(len(idf)), idf, 1)[0] if len(idf) > 1 else 0.0

    return np.array([
        np.log10(rms), np.log10(peak), peak / rms, kurtosis(seg), skew(seg),
        np.log10(abs(rise) + eps), decay_n / fs, env_peaks,
        centroid, bandwidth, rolloff, flatness,
        *band_e, *band_rel,
        np.mean(idf), np.std(idf), idf_slope,
        np.mean(np.abs(np.diff(np.sign(seg)))) / 2,   # zero-crossing rate
    ])


FEATURE_NAMES = (["log_rms", "log_peak", "crest", "kurtosis", "skew", "log_rise", "decay_s", "env_peaks",
                  "centroid", "bandwidth", "rolloff85", "flatness"]
                 + [f"logE_{lo}_{hi}" for lo, hi in BANDS] + [f"relE_{lo}_{hi}" for lo, hi in BANDS]
                 + ["idf_mean", "idf_std", "idf_slope", "zcr"])


def file_features(path):
    x, fs = load_wav(path)
    x = preprocess(x, fs)
    on = detect_events(x, fs)
    feats = [features(seg, fs) for _, seg in windows(x, fs, on)]
    if not feats:   # fallback: the 3 most energetic 100 ms windows
        n = int((PRE_S + POST_S) * fs)
        segs = [x[i:i + n] for i in range(0, len(x) - n, n // 2)]
        segs.sort(key=lambda s: -np.sum(s ** 2))
        feats = [features(s, fs) for s in segs[:3]]
    return np.array(feats), on, x, fs


# ---------------------------------------------------------------- commands
def cmd_events(a):
    F, on, x, fs = file_features(a.wav)
    print(f"{len(on)} events")
    for o in on:
        print(f"  t = {o / fs:8.3f} s")
    if a.plot:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 1, sharex=True, figsize=(11, 6))
        t = np.arange(len(x)) / fs
        ax[0].plot(t, x, lw=0.5)
        for o in on:
            ax[0].axvline(o / fs, color="r", alpha=0.6)
        ax[0].set_ylabel("piezo (filtered)")
        ax[1].specgram(x, Fs=fs, NFFT=512, noverlap=384, cmap="magma")
        ax[1].set_ylabel("Hz"); ax[1].set_xlabel("s")
        plt.tight_layout(); plt.show()


def cmd_train(a):
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import GroupKFold, cross_val_predict
    from sklearn.metrics import classification_report, confusion_matrix

    X, y, g = [], [], []
    classes = sorted(d for d in os.listdir(a.data) if os.path.isdir(os.path.join(a.data, d)))
    for c in classes:
        for i, w in enumerate(sorted(glob.glob(os.path.join(a.data, c, "*.wav")))):
            F, *_ = file_features(w)
            X.append(F); y += [c] * len(F); g += [w] * len(F)
            print(f"{c:12s} {os.path.basename(w):25s} {len(F)} events")
    X = np.vstack(X); y = np.array(y); g = np.array(g)
    clf = RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=0)
    n_split = min(5, len(set(g)))
    if n_split >= 2 and len(classes) >= 2:
        pred = cross_val_predict(clf, X, y, groups=g, cv=GroupKFold(n_split))
        print("\nCross-validation (grouped by recording, no leakage):")
        print(classification_report(y, pred, zero_division=0))
        print("confusion matrix (rows=true):", classes)
        print(confusion_matrix(y, pred, labels=classes))
    clf.fit(X, y)
    top = np.argsort(clf.feature_importances_)[::-1][:8]
    print("top features:", ", ".join(FEATURE_NAMES[i] for i in top))
    joblib.dump(clf, a.model)
    print("saved", a.model)


def cmd_predict(a):
    import joblib
    clf = joblib.load(a.model)
    F, on, x, fs = file_features(a.wav)
    proba = clf.predict_proba(F)
    for k, p in enumerate(proba):
        t = on[k] / fs if k < len(on) else float("nan")
        print(f"event {k:2d} t={t:7.3f}s -> {clf.classes_[np.argmax(p)]:12s} ({p.max():.2f})")
    mean = proba.mean(axis=0)
    print(f"\nrecording -> {clf.classes_[np.argmax(mean)]} ({mean.max():.2f})")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("events"); e.add_argument("--wav", required=True); e.add_argument("--plot", action="store_true")
    t = sub.add_parser("train"); t.add_argument("--data", required=True); t.add_argument("--model", default="model.joblib")
    r = sub.add_parser("predict"); r.add_argument("--model", required=True); r.add_argument("--wav", required=True)
    a = p.parse_args()
    {"events": cmd_events, "train": cmd_train, "predict": cmd_predict}[a.cmd](a)


if __name__ == "__main__":
    main()
