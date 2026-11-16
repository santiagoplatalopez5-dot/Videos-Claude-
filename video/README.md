# Video: «¿El choque de puños de Goku Dios y Beerus ya no es canon?»

- `goku-vs-beerus-canon.mp4`: video final (1080x1920, 30 fps, 57 s).
- `segments.py`: frases de la voz en off y de los subtítulos.
- `tts.py`: genera la voz con [Piper](https://github.com/OHF-Voice/piper1-gpl) (voz `es_MX-ald-medium`).
- `make_video.py`: dibuja las escenas, sintetiza efectos y música, y monta el video con ffmpeg.

## Regenerar

```bash
pip install piper-tts numpy pillow
python3 -m piper.download_voices es_MX-ald-medium
python3 tts.py es_MX-ald-medium.onnx build/tts 0.76
python3 make_video.py build goku-vs-beerus-canon.mp4
```

Para usar otra voz (por ejemplo, ElevenLabs), sustituye los archivos `build/tts/segNN.wav`
(44,1 kHz, mono) y actualiza las duraciones en `build/tts/durs.json`.
