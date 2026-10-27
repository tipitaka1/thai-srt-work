"""한국어 더빙 mp3 만들기: TTS 테이크를 문장별로 잘라 태국어 문장 자리에 놓고, 태국어 원음을 작게 깔아 섞는다.

입력
  --side   build_karaoke.py가 만든 문장 시각 JSON (media/<이름>.json: start/end, cues[].rng/s/e/speech)
  --src    원본 법문 mp3 (side의 start~end 구간을 잘라 깐다)
  --req    TTS 요청 JSON들 (ranges[]와 lines[]가 문장 순서대로)
  --takes  테이크 폴더 (<요청 id>/<목소리>.flac)
  --voice  목소리 이름
출력
  --out    더빙 mp3 (원음 mp3와 길이·시각이 같다), --report 문장별 배치 기록(JSON)

배치: 한국어 문장은 태국어 문장이 말로 시작하는 때에 시작한다. 앞 문장이 길어 밀렸으면 바로 이어서 놓고,
다음 태국어 문장이 시작하고 0.7초 안에 끝나지 않으면 최대 1.2배까지 빠르게 한다(음높이 그대로).
섞기: 한국어 문장마다 말소리 크기를 -20dBFS로 맞추고, 한국어가 나오는 동안 태국어 원음은 약 -16dB, 쉬는 틈에는 약 -6dB.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dub_align import align  # noqa: E402

SR = 24000
ap = argparse.ArgumentParser()
ap.add_argument("--side", required=True)
ap.add_argument("--src", required=True)
ap.add_argument("--req", nargs="+", required=True)
ap.add_argument("--takes", required=True)
ap.add_argument("--voice", default="Schedar")
ap.add_argument("--out", required=True)
ap.add_argument("--report")
ap.add_argument("--bitrate", default="64k")
ap.add_argument("--max-speed", type=float, default=1.2)
ap.add_argument("--late-ok", type=float, default=0.7, help="다음 태국어 문장보다 이만큼(초)은 늦게 끝나도 빠르게 하지 않는다")
ap.add_argument("--gap", type=float, default=0.25, help="한국어 문장 사이 최소 쉼(초)")
a = ap.parse_args()

side = json.load(open(a.side, encoding="utf-8"))
cues = {c["rng"]: c for c in side["cues"]}
order = [c["rng"] for c in side["cues"]]
total = side["end"] - side["start"]


def decode(path, start=None, dur=None):
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", path]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, dtype=np.float32).copy()


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)


def speech_rms_db(x):
    """10ms 틀 가운데 소리가 큰 쪽 60%의 평균 크기 (말소리 크기)."""
    n = len(x) // 240
    fr = np.sqrt((x[: n * 240].reshape(n, 240) ** 2).mean(1)) + 1e-9
    top = np.sort(fr)[int(n * 0.4):]
    return 20 * np.log10(np.sqrt(np.mean(top ** 2)))


def stretch(x, f):
    if abs(f - 1) < 0.01:
        return x
    with tempfile.TemporaryDirectory() as d:
        i, o = os.path.join(d, "i.wav"), os.path.join(d, "o.wav")
        sf.write(i, x, SR, subtype="FLOAT")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", i, "-filter:a", f"atempo={f:.4f}", o], check=True)
        y, _ = sf.read(o, dtype="float32")
    return y


# ---- 1) 테이크를 문장별로 자르기 ----
clips, report = {}, []
for rq in a.req:
    r = json.load(open(rq, encoding="utf-8"))
    path = os.path.join(a.takes, r["id"], a.voice + ".flac")
    x, sr = sf.read(path, dtype="float32")
    if sr != SR:
        sys.exit(f"{path}: 표본률 {sr}")
    segs, info, rate = align(x, sr, r["lines"])
    gain = 10 ** ((-20.0 - speech_rms_db(x)) / 20)        # 테이크 전체 말소리를 -20dBFS로 맞추는 값
    bad = [k for k, i in enumerate(info) if abs(i["dev"]) > 0.35]
    print(f"{r['id']}: {len(x) / SR:.1f}초, 문장 {len(segs)}, 1자당 {rate:.3f}초, 어긋남 큰 문장 {len(bad)}개", bad[:10])
    pad, fade = int(0.04 * SR), int(0.012 * SR)
    for k, ((s, e), rng) in enumerate(zip(segs, r["ranges"])):
        i0, i1 = max(0, int(s * SR) - pad), min(len(x), int(e * SR) + pad)
        y = x[i0:i1].copy()
        g = 10 ** ((-20.0 - speech_rms_db(y)) / 20)        # 문장마다 다시 맞춘다 (긴 테이크에서 소리가 커지거나 작아져도 고르게)
        y *= min(max(g, gain / 2), gain * 2)               # 다만 테이크 기준에서 ±6dB 안에서만
        y[:fade] *= np.linspace(0, 1, fade)
        y[-fade:] *= np.linspace(1, 0, fade)
        clips[rng] = y
        report.append(dict(rng=rng, take=r["id"], at=round(s, 2), dur=round(e - s, 2), dev=info[k]["dev"]))

missing = [g for g in order if g not in clips]
if missing:
    sys.exit(f"테이크에 없는 문장: {missing[:5]} …")

# ---- 2) 태국어 문장 자리에 놓기 ----
voice = np.zeros(int(total * SR) + SR, dtype=np.float32)
active = np.zeros_like(voice)
prev_end, speeds = 0.0, []
rep = {d["rng"]: d for d in report}
for k, g in enumerate(order):
    c, y = cues[g], clips[g]
    start = max(c["speech"][0], prev_end + a.gap)
    nxt = cues[order[k + 1]]["speech"][0] + a.late_ok if k + 1 < len(order) else total - 0.3
    avail = nxt - a.gap - start
    d = len(y) / SR
    f = 1.0
    if d > avail:
        f = min(a.max_speed, d / max(avail, 0.3))
        if f < 1.04:
            f = 1.0
    if f > 1.0:
        y = stretch(y, f)
    i0 = int(start * SR)
    i1 = min(len(voice), i0 + len(y))
    voice[i0:i1] += y[: i1 - i0]
    active[i0:i1] = 1.0
    prev_end = start + len(y) / SR
    speeds.append(f)
    rep[g].update(place=round(start, 2), end=round(prev_end, 2), speed=round(f, 3),
                  late=round(start - c["speech"][0], 2))
late = [rep[g]["late"] for g in order]
print(f"빠르게 한 문장 {sum(f > 1 for f in speeds)}개 (최대 {max(speeds):.2f}배), "
      f"태국어보다 늦게 시작한 문장 {sum(v > 0.3 for v in late)}개 (최대 {max(late):.1f}초), 마지막 끝 {prev_end:.1f}초 / {total:.1f}초")

# ---- 3) 원음을 작게 깔기 ----
orig = decode(a.src, side["start"], total)
voice = voice[: len(orig)] if len(voice) >= len(orig) else np.pad(voice, (0, len(orig) - len(voice)))
active = active[: len(orig)] if len(active) >= len(orig) else np.pad(active, (0, len(orig) - len(active)))
orig *= 10 ** ((-20.0 - speech_rms_db(orig)) / 20)
hop = 240                                   # 10ms 단위 덮개: 빨리 내리고(0.15초) 천천히 올린다(0.9초)
n = len(orig) // hop + 1
act = np.array([active[i * hop:(i + 1) * hop].max() if i * hop < len(active) else 0 for i in range(n)])
pre = int(0.15 / 0.01)
act = np.maximum(act, np.concatenate([act[pre:], np.zeros(pre)]))   # 한국어가 나오기 조금 앞서 내린다
env = np.zeros(n)
up, down = 1 - np.exp(-1 / 15), 1 - np.exp(-1 / 90)
for i in range(n):
    p = env[i - 1] if i else 0.0
    env[i] = p + (act[i] - p) * (up if act[i] > p else down)
g_lo, g_hi = 10 ** (-16 / 20), 10 ** (-6 / 20)
gain = np.repeat(g_hi - (g_hi - g_lo) * env, hop)[: len(orig)]
mix = orig * gain + voice
peak = np.max(np.abs(mix))
if peak > 0.89:
    mix *= 0.89 / peak
print(f"섞음: 원음 {rms_db(orig * gain):.1f}dB, 한국어 {rms_db(voice):.1f}dB, 최고 {20 * np.log10(np.max(np.abs(mix))):.1f}dBFS")

with tempfile.TemporaryDirectory() as d:
    w = os.path.join(d, "mix.wav")
    sf.write(w, mix, SR, subtype="PCM_16")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", w, "-ac", "1", "-c:a", "libmp3lame", "-b:a", a.bitrate,
                    "-id3v2_version", "3", "-metadata", "title=한국어 더빙", a.out], check=True)
print("->", a.out, f"{os.path.getsize(a.out) / 1e6:.1f}MB")
if a.report:
    json.dump([rep[g] for g in order], open(a.report, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
