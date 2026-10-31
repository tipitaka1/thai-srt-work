"""TTS 테이크가 뒤로 갈수록 커지거나(peak) 쉼 사이 잡음이 올라오는지(floor) 30초 단위로 본다.
긴 테이크는 3~4분 넘어서 소리가 커지고 잡음이 끼는 일이 있었다: peak가 처음보다 5dB 넘게 오르거나 floor가 -45dB 위로 오면 그 덩어리를 짧게 나눠 다시 읽힌다.

python3 tools/take_quality.py <take.flac> [...]
"""
import sys

import numpy as np
import soundfile as sf

for path in sys.argv[1:]:
    x, sr = sf.read(path, dtype="float32")
    hop = sr // 100
    n = len(x) // hop
    db = 20 * np.log10(np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    rows, W = [], 3000
    for i in range(0, n - W // 2, W):
        w = db[i:i + W]
        rows.append((i // 100, np.percentile(w, 10), np.percentile(w, 95)))
    p0 = rows[0][2]
    warn = [f"{t}s" for t, fl, pk in rows if pk - p0 > 5 or (-100 < fl > -45)]
    print(f"{path}: {len(x) / sr:.0f}초 | " + " | ".join(f"{t}s 바닥{fl:.0f} 말{pk:.0f}" for t, fl, pk in rows))
    print("  ->", "주의: " + ", ".join(warn) if warn else "고름")
