"""휘스퍼 태국어 자막 -> 노래방 WebVTT (태국어 단어 + 한글 독음 ruby + 한국어 번역).

입력
  --srt   휘스퍼 태국어 SRT (줄 번호·시각 기준)
  --json  같은 자막의 단어별 시각 JSON (segments[].words[].word/start/end)
  --mp3   법문 음성 (무음 구간을 찾아 단어 시작·끝을 다듬는 데 씀)
  --data  pron_ko.txt (N|독음|번역), seg_th.txt (N|독음 토막 수에 맞춘 태국어 토막, 공백 구분)
출력
  --out   전체 VTT,  --site 웹앱 폴더(media/ 아래 샘플 mp3·vtt),  --clip 샘플 구간(초)

단어 시각: 휘스퍼 단어 시각을 글자 위치로 나눠 토막마다 잡고,
토막 앞뒤에 0.12초 넘게 붙은 무음은 음성 크기(10ms)로 잘라 냅니다.
"""
import argparse
import os
import subprocess
import sys
import json

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--srt", required=True)
ap.add_argument("--json", required=True)
ap.add_argument("--mp3", required=True)
ap.add_argument("--data", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--site", required=True)
ap.add_argument("--clip", nargs=2, type=float, default=[560.0, 592.9])
ap.add_argument("--clip-name", default="LT2401_sample_0920")
ap.add_argument("--reseg", help="문장 단위로 다시 나눈 파일 (줄.토막-줄.토막|번역, '## 제목' 줄은 목차). 주면 --clip 대신 이 범위로 자른다")
ap.add_argument("--bitrate", default="64k", help="잘라 낸 mp3 비트레이트 (모노)")
a = ap.parse_args()


def ts(x):
    h, m, s = x.strip().replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def fmt(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


NOTE_WORDS = ("휘스퍼", "불명", "추정", "깨짐", "누락")


def clean_tr(s):
    """화면용 번역: ※, (?), 휘스퍼 검토 메모 괄호를 뺀다 (원본 pron_ko.txt는 그대로 둔다)."""
    s = s.replace("※", "").replace("(?)", "")
    out, i, cut_end = [], 0, False
    while i < len(s):
        if s[i] == "(":
            depth, j = 0, i
            while j < len(s):
                depth += {"(": 1, ")": -1}.get(s[j], 0)
                if depth == 0:
                    break
                j += 1
            if any(k in s[i + 1:j] for k in NOTE_WORDS):
                cut_end = not s[j + 1:].strip()
                i = j + 1
                continue
        out.append(s[i])
        i += 1
    s = " ".join("".join(out).split())
    if cut_end and s[-1:] in ("요", "다"):
        s += "."
    return s


def read_map(path, nf):
    m = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.strip():
                p = line.split("|", nf - 1)
                m[int(p[0])] = p[1:]
    return m


with open(a.srt, encoding="utf-8-sig") as f:
    raw = f.read().replace("\r\n", "\n")
cues = []
for b in raw.strip("\n").split("\n\n"):
    ls = b.split("\n")
    s0, e0 = ls[1].split("-->")
    cues.append(dict(n=int(ls[0]), s=ts(s0), e=ts(e0), th="".join(x.strip() for x in ls[2:])))

with open(a.json, encoding="utf-8-sig") as f:
    segs = json.load(f)["segments"]
assert len(segs) == len(cues), "SRT와 JSON의 줄 수가 다릅니다"

pt = read_map(os.path.join(a.data, "pron_ko.txt"), 3)
sg = read_map(os.path.join(a.data, "seg_th.txt"), 2)
bad = []
for c, sj in zip(cues, segs):
    n = c["n"]
    c["wj"] = [(w["word"], w["start"], w["end"]) for w in sj["words"]]
    if "".join(w for w, _, _ in c["wj"]) != c["th"]:
        c["wj"] = None
    if n in sg:
        pieces = sg[n][0].split(" ")
        toks = pt[n][0].split()
        if "".join(pieces) != c["th"] or len(pieces) != len(toks):
            bad.append(n)
        c["words"] = list(zip(pieces, toks))
        c["tr"] = pt[n][1].strip()
if bad:
    sys.exit(f"태국어 토막이 원문·독음과 맞지 않는 줄: {bad}")

# ---- 음성 크기 (10ms, dB) ----
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", a.mp3, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
nfr = len(x) // 160
db = np.convolve(20 * np.log10(np.sqrt((x[: nfr * 160].reshape(nfr, 160) ** 2).mean(1) + 1e-12) + 1e-9),
                 np.ones(3) / 3, mode="same")


def threshold(s, e):
    i0, i1 = int(s * 100), max(int(e * 100), int(s * 100) + 1)
    lo = np.percentile(db[max(0, i0 - 500):min(nfr, i1 + 500)], 10)
    hi = np.percentile(db[i0:i1], 95)
    return None if hi - lo < 10 else lo + 0.3 * (hi - lo)


def trim(s, e, thr):
    i0, i1 = int(s * 100), int(e * 100)
    if thr is None or i1 - i0 < 8:
        return s, e
    v = db[i0:i1] > thr
    if not v.any():
        return s, e
    first, last = int(np.argmax(v)), len(v) - 1 - int(np.argmax(v[::-1]))
    if first >= 12:
        s = (i0 + first) / 100 - 0.02
    if len(v) - 1 - last >= 12:
        e = (i0 + last + 1) / 100 + 0.03
    return s, max(e, s + 0.08)


trimmed = 0
for c in cues:
    if "words" not in c:
        continue
    if not c["wj"]:
        sys.exit(f"{c['n']}번 줄: JSON 단어가 자막 글과 맞지 않습니다")
    spans, pos = [], 0
    for w, ws, we in c["wj"]:
        spans.append((pos, pos + len(w), ws, we))
        pos += len(w)

    def t_start(xc):
        for p0, p1, ws, we in spans:
            if p0 <= xc < p1:
                return ws + (we - ws) * (xc - p0) / (p1 - p0)
        return spans[-1][3]

    def t_end(xc):
        for p0, p1, ws, we in spans:
            if p0 < xc <= p1:
                return ws + (we - ws) * (xc - p0) / (p1 - p0)
        return spans[0][2]

    thr = threshold(c["s"], c["e"])
    st, en, pos = [], [], 0
    for th, _ in c["words"]:
        s1, e1 = t_start(pos), t_end(pos + len(th))
        pos += len(th)
        s2, e2 = trim(s1, e1, thr)
        trimmed += (s2, e2) != (s1, e1)
        s2 = min(max(s2, c["s"], en[-1] if en else c["s"]), c["e"] - 0.02)
        st.append(s2)
        en.append(min(max(e2, s2 + 0.05), c["e"]))
    c["st"], c["en"] = st, en
print("cues:", len(cues), "| karaoke:", sum("words" in c for c in cues), "| trimmed pieces:", trimmed)


def payload(c, off=0.0, lim=None):
    s0 = max(0.0, c["s"] - off)
    e0 = (c["e"] - off) if lim is None else min(lim, c["e"] - off)
    if "words" not in c:
        return s0, e0, esc(c["th"].replace("�", ""))
    st = [t - off for t in c["st"]]
    en = [t - off for t in c["en"]]
    last = [s0]

    def tag(t):
        t = max(t, last[0] + 0.001)
        if t >= e0 - 0.001:
            return ""
        last[0] = t
        return f"<{fmt(t)}>"

    out = []
    for i, (th, ko) in enumerate(c["words"]):
        if "�" in th:                      # 휘스퍼가 깨뜨린 글자 토막은 화면에서 뺀다
            continue
        pre = tag(st[i]) if (i > 0 or st[0] > s0 + 0.05) else ""
        nxt = st[i + 1] if i + 1 < len(st) else e0
        post = tag(en[i]) if nxt - en[i] >= 0.15 else ""
        out.append(f"{pre}<ruby>{esc(th)}<rt>{esc(ko)}</rt></ruby>{post}")
    return s0, e0, " ".join(out) + f"\n<c.ko>{esc(clean_tr(c['tr']))}</c>"


HEAD = """WEBVTT
Kind: captions
Language: th

NOTE
LT2401 (2003-10-11) Luang Ta Maha Bua - Whisper large-v3 Thai
태국어 단어마다 <ruby>태국어<rt>한글 독음</rt></ruby>, 둘째 줄 <c.ko>는 한국어 번역입니다.
단어 앞 시각 태그가 노래방 시각입니다. 휘스퍼 단어 시각을 글자 위치로 나누고 앞뒤 무음을 잘라 낸 추정치예요.
"""


def write_vtt(path, items, extra):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(HEAD + extra + "\n")
        for n, s, e, p in items:
            f.write(f"{n}\n{fmt(s)} --> {fmt(e)}\n{p}\n\n")


write_vtt(a.out, [(c["n"], *payload(c)) for c in cues],
          "독음·번역이 있는 줄만 노래방으로 나오고, 나머지는 태국어 원문만 있습니다.\n")
def resegment(path):
    """휘스퍼 줄을 넘나들며 태국어 토막 단위로 문장을 다시 묶는다 (번역이 1~2줄이 되게).
    '## 제목' 줄은 다음 문장에서 시작하는 목차 항목이다."""
    segs, chapters = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            if line.startswith("## "):
                chapters.append((len(segs), line[3:].strip()))
                continue
            rng, tr = line.split("|", 1)
            (l0, i0), (l1, i1) = [tuple(map(int, p.split("."))) for p in rng.split("-")]
            words, st, en = [], [], []
            for n in range(l0, l1 + 1):
                c = cues[n - 1]
                lo, hi = (i0 if n == l0 else 0), (i1 if n == l1 else len(c["words"]) - 1)
                words += c["words"][lo:hi + 1]
                st += c["st"][lo:hi + 1]
                en += c["en"][lo:hi + 1]
            segs.append(dict(n=len(segs) + 1, rng=rng, words=words, st=st, en=en, tr=tr.strip()))
    for i, s in enumerate(segs):
        s["s"] = max(s["st"][0] - 0.12, segs[i - 1]["en"][-1] if i else 0.0)
    for i, s in enumerate(segs):
        s["e"] = min(s["en"][-1] + 0.5, segs[i + 1]["s"]) if i + 1 < len(segs) else s["en"][-1] + 0.6
    return segs, chapters


media = os.path.join(a.site, "media")
os.makedirs(media, exist_ok=True)
if a.reseg:
    segs, chapters = resegment(a.reseg)
    c0, c1 = min(a.clip[0], segs[0]["s"] - 0.2), segs[-1]["e"] + 0.3
    clip = [(s["n"], *payload(s, c0, c1 - c0)) for s in segs]
    side = dict(source=os.path.basename(a.mp3), start=round(c0, 3), end=round(c1, 3),
                chapters=[dict(t=round(max(0.0, segs[i]["s"] - c0), 2), title=t) for i, t in chapters],
                cues=[dict(n=s["n"], rng=s["rng"], s=round(s["s"] - c0, 3), e=round(s["e"] - c0, 3),
                           speech=[round(s["st"][0] - c0, 3), round(s["en"][-1] - c0, 3)], tr=clean_tr(s["tr"]))
                      for s in segs])
    with open(os.path.join(media, a.clip_name + ".json"), "w", encoding="utf-8") as f:
        json.dump(side, f, ensure_ascii=False, indent=1)
    for i, t in chapters:
        x = segs[i]["s"] - c0
        print(f"목차 {int(x // 60)}:{int(x % 60):02d}  {t}")
else:
    c0, c1 = a.clip
    clip = [(c["n"], *payload(c, c0, c1 - c0)) for c in cues if c["s"] < c1 - 0.3 and c["e"] > c0 + 0.3]
write_vtt(os.path.join(media, a.clip_name + ".vtt"), clip,
          f"잘라 낸 구간: 원본 {fmt(c0)} ~ {fmt(c1)} (시각은 잘라 낸 음성 기준 0초부터).\n")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(c0), "-i", a.mp3, "-t", f"{c1 - c0:.3f}", "-ac", "1",
                "-c:a", "libmp3lame", "-b:a", a.bitrate, os.path.join(media, a.clip_name + ".mp3")], check=True)
print("clip cues:", [n for n, *_ in clip])
for n in (1, 102):
    c = cues[n - 1]
    print(n, [(th, round(s, 2), round(e, 2)) for (th, _), s, e in zip(c["words"], c["st"], c["en"])][:8])
