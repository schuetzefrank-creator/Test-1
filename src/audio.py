"""Synthesised sound bed (no third-party audio): fire roar + crackles,
a warm low pad and soft whooshes on the shot changes. Writes out/ton.wav."""
import wave

import numpy as np

SR, DUR = 48000, 15.0
n = int(SR * DUR)
t = np.arange(n) / SR
rng = np.random.default_rng(7)


def onepole_lp(x, a):
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a * (x[i] - acc)
        y[i] = acc
    return y


# fire roar: low-passed noise with slow breathing
roar = onepole_lp(rng.normal(0, 1, n), 0.02)
roar = roar / np.abs(roar).max() * (0.55 + 0.25 * np.sin(2 * np.pi * 0.31 * t) * np.sin(2 * np.pi * 0.13 * t + 1))

# crackles: short decaying bursts of bright noise
crack = np.zeros(n)
for _ in range(110):
    s = rng.integers(0, n - 4000)
    ln = rng.integers(200, 2200)
    env = np.exp(-np.arange(ln) / (ln / 6))
    burst = np.diff(rng.normal(0, 1, ln + 1)) * env * rng.uniform(0.2, 1.0)
    crack[s:s + ln] += burst
crack *= 0.35

# warm pad (A1 + E2 + A2), swelling in and out
pad = sum(a * np.sin(2 * np.pi * f * t + p) for f, a, p in [(55, 0.5, 0), (82.4, 0.3, 1), (110, 0.2, 2), (164.8, 0.08, 0.5)])
pad *= np.clip(t / 3, 0, 1) * np.clip((DUR - t) / 1.5, 0, 1) * 0.35

# whooshes at transitions
whoosh = np.zeros(n)
for tc in (3.5, 6.7, 9.7, 12.3):
    s, ln = int((tc - 0.6) * SR), int(1.2 * SR)
    seg = rng.normal(0, 1, ln)
    seg = onepole_lp(seg, 0.06) - onepole_lp(seg, 0.005)
    env = np.sin(np.linspace(0, np.pi, ln)) ** 2
    whoosh[s:s + ln] += seg * env * 0.9

mix = 0.45 * roar + crack + pad + whoosh
mix *= np.clip(t / 1.5, 0, 1) * np.clip((DUR - t) / 0.8, 0, 1)
mix = np.tanh(mix * 1.2)
mix = mix / np.abs(mix).max() * 0.7
st = np.stack([mix, np.roll(mix, 240)], 1)  # tiny stereo width
with wave.open("out/ton.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes())
print("wrote out/ton.wav")
