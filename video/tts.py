"""Genera la voz en off por frases con Piper. Uso: python3 tts.py <modelo.onnx> <dir_salida> [length_scale]"""
import subprocess, sys, os, json, wave
from segments import SEGMENTS
model, out = sys.argv[1], sys.argv[2]
ls = sys.argv[3] if len(sys.argv) > 3 else "0.82"
os.makedirs(out, exist_ok=True)
durs = []
for i, (_, tts, _) in enumerate(SEGMENTS):
    raw, f = f"{out}/raw{i:02d}.wav", f"{out}/seg{i:02d}.wav"
    subprocess.run([sys.executable, "-m", "piper", "-m", model, "-f", raw, "--length-scale", ls],
                   input=tts.encode(), check=True, capture_output=True)
    # recorta silencios de inicio y fin, 44.1 kHz mono
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-af",
        "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse",
        "-ar", "44100", "-ac", "1", f], check=True)
    os.remove(raw)
    with wave.open(f) as w: durs.append(w.getnframes() / w.getframerate())
json.dump(durs, open(f"{out}/durs.json", "w"))
print([round(d, 2) for d in durs], "total", round(sum(durs), 2))
