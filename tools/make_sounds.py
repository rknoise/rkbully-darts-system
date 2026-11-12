"""A hangeffektek (assets/sounds/*.wav) legyártása: kis, szintetizált hangok, külső fájl és csomag nélkül.

Használat:  python tools/make_sounds.py
Ha más hangokat szeretnél, egyszerűen írd felül a WAV fájlokat az assets/sounds mappában (16 bites, mono vagy sztereó).
"""
import math
import random
import struct
import wave
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "sounds"
RATE = 44100
NOTE = {"C4": 261.63, "E4": 329.63, "G4": 392.0, "A4": 440.0, "C5": 523.25, "E5": 659.25, "G5": 783.99, "C6": 1046.5,
        "D5": 587.33, "B4": 493.88}


def silence(seconds):
    return [0.0] * int(RATE * seconds)


def tone(freq, seconds, volume=0.5, decay=6.0, shape="sine", glide=None, attack=0.004):
    """Egy hang lecsengő hangerővel; `glide`: a végfrekvencia (hangmagasság-csúszás)."""
    n = int(RATE * seconds)
    out, phase = [], 0.0
    for i in range(n):
        t = i / RATE
        f = freq if glide is None else freq + (glide - freq) * (i / n)
        phase += 2 * math.pi * f / RATE
        if shape == "saw":
            v = 2 * ((phase / (2 * math.pi)) % 1.0) - 1
        elif shape == "square":
            v = 1.0 if math.sin(phase) >= 0 else -1.0
        else:
            v = math.sin(phase) + 0.25 * math.sin(2 * phase) + 0.1 * math.sin(3 * phase)
        env = min(1.0, t / attack) * math.exp(-decay * t / seconds)
        out.append(v * env * volume)
    return out


def noise(seconds, volume=0.4, decay=30.0, seed=1):
    rnd = random.Random(seed)
    n = int(RATE * seconds)
    return [(rnd.random() * 2 - 1) * volume * math.exp(-decay * i / n) for i in range(n)]


def mix(*tracks):
    n = max(len(t) for t in tracks)
    return [sum(t[i] for t in tracks if i < len(t)) for i in range(n)]


def delayed(track, seconds):
    return silence(seconds) + track


def concat(*tracks):
    return [x for t in tracks for x in t]


def write(name, samples, peak=0.85):
    top = max(max(abs(x) for x in samples), 1e-9)
    scale = min(1.0, peak / top)                         # csak lehalkít, ha túlcsordulna
    data = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, x * scale)) * 32767)) for x in samples)
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data)


def build():
    # egy nyíl a táblában: tompa puffanás + rövid kattanás
    write("dart.wav", mix(tone(190, 0.11, 0.7, decay=7, glide=85), noise(0.03, 0.5)))
    # dupla: tiszta, rövid "ding"
    write("double.wav", mix(tone(NOTE["A4"] * 2, 0.35, 0.45, decay=5), delayed(tone(NOTE["E5"] * 2, 0.3, 0.3, decay=5), 0.04),
                            noise(0.02, 0.3)))
    # tripla: gyors, felfelé futó háromhangos csilingelés
    write("triple.wav", concat(tone(NOTE["E5"], 0.07, 0.4, decay=3), tone(NOTE["G5"], 0.07, 0.4, decay=3),
                               mix(tone(NOTE["C6"], 0.5, 0.45, decay=4), tone(NOTE["E5"] * 4, 0.45, 0.2, decay=5))))
    # bull: mély gong + szikrázó felhang
    write("bull.wav", mix(tone(110, 1.0, 0.7, decay=3.5, glide=95), tone(220, 0.9, 0.35, decay=4),
                          delayed(tone(NOTE["C6"] * 2, 0.5, 0.25, decay=5), 0.05), noise(0.04, 0.4)))
    # kör vége, következő játékos: halk, két hangos jelzés
    write("next.wav", concat(tone(NOTE["E5"], 0.09, 0.28, decay=5), tone(NOTE["A4"], 0.14, 0.24, decay=5)))
    # 100+ kör: ketyegő, kétszólamú csengő
    write("ton.wav", mix(tone(NOTE["E5"], 0.45, 0.4, decay=4), delayed(tone(NOTE["A4"] * 2, 0.5, 0.4, decay=4), 0.11)))
    # 180: felfelé futó futam és hosszan kitartott dúr akkord
    run = concat(*(tone(NOTE[n], 0.11, 0.4, decay=3) for n in ("C5", "E5", "G5")))
    chord = mix(tone(NOTE["C5"], 1.1, 0.3, decay=3), tone(NOTE["E5"], 1.1, 0.3, decay=3),
                tone(NOTE["G5"], 1.1, 0.3, decay=3), tone(NOTE["C6"], 1.1, 0.3, decay=3))
    write("oneeighty.wav", concat(run, chord))
    # bust: lefelé csúszó, mély berregés
    write("bust.wav", concat(tone(260, 0.22, 0.45, decay=2, shape="saw", glide=170),
                             tone(170, 0.32, 0.45, decay=3, shape="saw", glide=95)))
    # győzelem: fanfár
    notes = ("C5", "E5", "G5", "C6", "G5", "C6")
    seq = concat(*(tone(NOTE[n], 0.13, 0.4, decay=2.5) for n in notes[:-1]))
    final = mix(*(tone(NOTE[n], 1.3, 0.28, decay=3) for n in ("C5", "E5", "G5", "C6")))
    write("win.wav", concat(seq, final))


if __name__ == "__main__":
    build()
    for f in sorted(OUT.glob("*.wav")):
        with wave.open(str(f)) as w:
            print(f"{f.name:14s} {w.getnframes() / w.getframerate():.2f} s  {f.stat().st_size // 1024} KB")
