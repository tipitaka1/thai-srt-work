"""공식 녹취록이 있는 법문 → 노래방 WebVTT (태국어 녹취록 + 한글 독음 ruby + 한국어 번역).

휘스퍼 글 대신 녹취록 글을 화면에 쓰고, 시각만 휘스퍼에서 가져온다.
  1. 정렬: 녹취록 글자를 휘스퍼 조각(서브웍스 `*_나_STT_SSW.json`, 글자 1~2개씩 시각)에 맞춘다 (tools/th_align.py).
     닻(양쪽에 한 번씩만 나오는 12글자) → 닻 사이 글자 맞춤 → 소리 무리(ข=ค, ท=ธ…)로 한 번 더.
     맞은 글자 = 휘스퍼 시각, 안 맞은 글자 = 앞뒤 맞은 글자 사이를 글자 수대로 나눈 추정.
  2. 줄: 문단마다 태국어 토막(녹취록 빈칸 단위) ↔ 한국어 문장 짝(pairs)대로 줄을 만든다. 2초가 안 되는 줄은 같은 문단 이웃과 합친다.
  3. 낱말: pythainlp(newmm)로 자르고, 낱말 시각 = 글자 시각. 앞뒤에 0.12초 넘게 붙은 무음은 음성 크기(10ms)로 잘라 낸다.
  4. 독음: --pron 사전(낱말 → 한글).

입력
  --paras   문단 목록 json [{p, th, ko, ph(태국어 토막), ks(한국어 문장)}]
  --pairs   문단별 줄 짝 json {"문단": [[한국어 첫, 끝, 태국어 첫, 끝], ...]} (1부터, 끝 포함)
  --pron    독음 사전 json {낱말: 한글}
  --pali    통째로 둘 빨리어 낱말과 독음 json (없어도 됨)
  --ssw     서브웍스 휘스퍼 조각 json
  --audio   원본 음성 (음성 크기용)
  --cut     앱 음성으로 잘라 낸 구간 (원본 초)
  --chapters "문단:제목" 를 | 로 이은 것
출력
  --out-vtt, --out-json
"""
import argparse
import json
import re
import subprocess
import sys

import numpy as np
from pythainlp.corpus.common import thai_words
from pythainlp.tokenize import word_tokenize
from pythainlp.util import dict_trie

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import th_align as A  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--paras', required=True)
ap.add_argument('--pairs', required=True)
ap.add_argument('--pron', required=True)
ap.add_argument('--pali', help='통째로 한 낱말로 둘 빨리어 등 {낱말: 한글} (독음 사전보다 앞섬)')
ap.add_argument('--bad-words', default='', help='pythainlp 사전에서 뺄 낱말(쉼표로 이음) — 엉뚱하게 잘리는 것 (예: มีนา → มี นา)')
ap.add_argument('--ssw', required=True)
ap.add_argument('--audio', required=True)
ap.add_argument('--cut', nargs=2, type=float, required=True)
ap.add_argument('--chapters', required=True)
ap.add_argument('--name', required=True, help='VTT 머리말에 적을 이름 (예: "LT1045 (1987-07-29) ...")')
ap.add_argument('--source', default='')
ap.add_argument('--engine', default='휘스퍼 large-v3 받아쓰기', help='VTT 머리말에 적을 시각 출처 (예: 일레븐랩스 scribe v2 받아쓰기)')
ap.add_argument('--min-cue', type=float, default=2.0)
ap.add_argument('--out-vtt', required=True)
ap.add_argument('--out-json', required=True)
ap.add_argument('--out-check', help='믿음(녹취록 글자 중 휘스퍼와 맞은 비율)이 낮은 줄 목록 csv — 귀로 확인할 곳')
a = ap.parse_args()
CUT0, CUT1 = a.cut

P = json.load(open(a.paras, encoding='utf-8'))
PAIRS = json.load(open(a.pairs, encoding='utf-8'))
PRON = json.load(open(a.pron, encoding='utf-8'))
PALI = json.load(open(a.pali, encoding='utf-8')) if a.pali else {}
PRON.update(PALI)
BAD_WORDS = {'วจะ', 'แล้'} | {w for w in a.bad_words.split(',') if w}   # pythainlp 사전에 든 엉뚱한 낱말 — 'แล้วจะ'를 'แล้|วจะ'로 자름
TRIE = dict_trie((set(thai_words()) - BAD_WORDS) | set(PALI))
CHAPTERS = [(int(x.split(':', 1)[0]), x.split(':', 1)[1]) for x in a.chapters.split('|')]

# ---- 1. 정렬 ----
ssw = json.load(open(a.ssw, encoding='utf-8-sig'))
W, t0, t1, pr = A.whisper_stream(ssw)
T, pidx, ppos = '', [], []
for k, o in enumerate(P):
    s, pos = A.norm_stream(o['th'])
    T += s
    pidx += [k] * len(s)
    ppos += pos
m, anchors = A.align(T, W)
exact = sum(1 for v in m if v >= 0)
added = A.refine(T, W, m)
ct = A.char_times(m, t0, t1, pr, len(T))
match_pct = sum(1 for v in m if v >= 0) / len(T) * 100
pos2t = {(pidx[i], ppos[i]): i for i in range(len(T))}
print(f'정렬: 녹취록 {len(T)}글자 · 휘스퍼 {len(W)}글자 · 닻 {len(anchors)} · 맞음 {exact}+{added} ({match_pct:.1f}%)')

# ---- 음성 크기 (10ms, dB) — 잘라 낸 구간만 ----
pcm = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(CUT0), '-to', str(CUT1), '-i', a.audio, '-ac', '1', '-ar', '16000',
                      '-f', 's16le', '-'], capture_output=True, check=True).stdout
x = np.frombuffer(pcm, dtype=np.int16)
nfr = len(x) // 160
ms = (x[:nfr * 160].astype(np.float32).reshape(nfr, 160) / 32768.0) ** 2
db = np.convolve(20 * np.log10(np.sqrt(ms.mean(1) + 1e-12) + 1e-9), np.ones(3) / 3, mode='same')
del ms


def fr(t):
    return int(round((t - CUT0) * 100))


def threshold(s, e):
    i0, i1 = max(0, fr(s)), min(nfr, max(fr(e), fr(s) + 1))
    if i1 <= i0:
        return None
    lo = np.percentile(db[max(0, i0 - 500):min(nfr, i1 + 500)], 10)
    hi = np.percentile(db[i0:i1], 95)
    return None if hi - lo < 10 else lo + 0.3 * (hi - lo)


def trim(s, e, thr):
    i0, i1 = max(0, fr(s)), min(nfr, fr(e))
    if thr is None or i1 - i0 < 8:
        return s, e
    v = db[i0:i1] > thr
    if not v.any():
        return s, e
    first, last = int(np.argmax(v)), len(v) - 1 - int(np.argmax(v[::-1]))
    if first >= 12:
        s = CUT0 + (i0 + first) / 100 - 0.02
    if len(v) - 1 - last >= 12:
        e = CUT0 + (i0 + last + 1) / 100 + 0.03
    return s, max(e, s + 0.08)


def speech_interp():
    """안 맞은 글자 묶음은 앞뒤 맞은 글자 사이의 '말소리 나는 시간'에만 글자 수대로 나눠 놓는다 (쉼에 글자가 놓이지 않게)."""
    n, i, moved = len(ct), 0, 0
    while i < n:
        if ct[i][2]:
            i += 1
            continue
        j = i
        while j < n and not ct[j][2]:
            j += 1
        if 0 < i and j < n and j - i >= 2:
            ta, tb = ct[i - 1][1], ct[j][0]
            f0, f1 = fr(ta), fr(tb)
            if tb - ta > 0.3 and 0 <= f0 < f1 <= nfr:
                seg = db[f0:f1]
                lo, hi = np.percentile(seg, 10), np.percentile(seg, 95)
                if hi - lo >= 10:
                    cum = np.cumsum(seg > lo + 0.3 * (hi - lo))
                    total = int(cum[-1])
                    if total >= 5:
                        k = j - i
                        for q in range(k):
                            fa = int(np.searchsorted(cum, total * q / k + 1e-9))
                            fb = int(np.searchsorted(cum, total * (q + 1) / k - 1e-9))
                            ct[i + q][0] = ta + fa / 100
                            ct[i + q][1] = ta + max(fb, fa + 1) / 100
                        moved += k
        i = j
    return moved


print('말소리 시간으로 다시 나눈 추정 글자:', speech_interp())


def tokens(text):
    """빈칸으로 먼저 나눈 뒤 조각마다 newmm (사전의 'ทั้งๆ ที่'처럼 빈칸 낀 말이 한 낱말이 되지 않게)."""
    for piece in re.split(r'( +)', text):
        if not piece:
            continue
        if not piece.strip():
            yield piece
        else:
            yield from word_tokenize(piece, engine='newmm', keep_whitespace=True, custom_dict=TRIE)


def words_of(k, text, base):
    out, pos = [], base
    for w in tokens(text):
        if not w.strip():
            pos += len(w)
            continue
        idx = [pos2t[(k, q)] for q in range(pos, pos + len(w)) if (k, q) in pos2t]
        pos += len(w)
        if w == 'ๆ' and out:
            out[-1]['th'] += w
            out[-1]['rep'] = True
            continue
        if not idx:
            if out:
                out[-1]['th'] += w
            continue
        out.append({'th': w, 's': min(ct[i][0] for i in idx), 'e': max(ct[i][1] for i in idx),
                    'ok': sum(ct[i][2] for i in idx), 'n': len(idx)})
    return out


def pron(w):
    th = w['th'].replace(' ', '').strip('.…?!,"\'()[]')   # 낱말에 붙은 문장부호는 떼고 찾는다 (พ้นทุกข์... · ๑.)
    h = PRON.get(th.rstrip('ๆ'), '')
    return h + h if (th.endswith('ๆ') and h) else h   # ๆ 는 앞말을 한 번 더 (LT2401: จริงๆ 찡찡)


# ---- 2. 줄 ----
cues = []
for k, o in enumerate(P):
    th, ph = o['th'], o['ph']
    starts, q = [], 0
    for piece in ph:
        q = th.index(piece, q)
        starts.append(q)
        q += len(piece)
    for (k0, k1, a0, a1) in PAIRS[str(o['p'])]:
        s_, e_ = starts[a0 - 1], starts[a1 - 1] + len(ph[a1 - 1])
        ko = ' '.join(o['ks'][k0 - 1:k1])
        ko = re.sub(r'\*\[(옮긴이:[^\]]*)\]\*', r'[\1]', ko)
        cues.append({'p': o['p'], 'k': [k0, k1], 't': [a0, a1], 'words': words_of(k, th[s_:e_], s_), 'tr': ko})

# ---- 3. 낱말 시각 다듬기 ----
for c in cues:
    ws = c['words']
    thr = threshold(ws[0]['s'], ws[-1]['e'])
    last = None
    for w in ws:
        s2, e2 = trim(w['s'], w['e'], thr)
        if last is not None:
            s2 = max(s2, last)
        w['s'], w['e'] = s2, max(e2, s2 + 0.05)
        last = w['s']
    c['s'], c['e'] = ws[0]['s'], ws[-1]['e']


def conf(ws):
    return round(sum(w['ok'] for w in ws) / max(1, sum(w['n'] for w in ws)), 3)


merged, i = 0, 0
while i < len(cues):
    c = cues[i]
    if c['e'] - c['s'] < a.min_cue:
        j = i + 1 if i + 1 < len(cues) and cues[i + 1]['p'] == c['p'] else (i - 1 if i > 0 and cues[i - 1]['p'] == c['p'] else None)
        if j is not None:
            x0, x1 = (c, cues[j]) if j > i else (cues[j], c)
            nc = {'p': x0['p'], 'k': [x0['k'][0], x1['k'][1]], 't': [x0['t'][0], x1['t'][1]], 'words': x0['words'] + x1['words'],
                  'tr': x0['tr'] + ' ' + x1['tr'], 's': x0['s'], 'e': x1['e']}
            lo = min(i, j)
            cues[lo:lo + 2] = [nc]
            merged += 1
            i = max(0, lo - 1)
            continue
    i += 1
for c in cues:
    c['conf'] = conf(c['words'])
for x0, x1 in zip(cues, cues[1:]):
    if x1['s'] < x0['s'] + 0.05:
        x1['s'] = x0['s'] + 0.05
        x1['words'][0]['s'] = max(x1['words'][0]['s'], x1['s'])

# ---- 잘라 낸 음성 기준으로 ----
for c in cues:
    for w in c['words']:
        w['s'] -= CUT0
        w['e'] -= CUT0
    c['s'] -= CUT0
    c['e'] -= CUT0
for x0, x1 in zip(cues, cues[1:]):
    x0['end'] = min(x0['e'] + 0.4, x1['s'])
cues[-1]['end'] = min(cues[-1]['e'] + 0.6, CUT1 - CUT0)
for c in cues:
    c['start'] = max(0.0, c['s'] - 0.12)
for x0, x1 in zip(cues, cues[1:]):
    if x1['start'] < x0['end']:
        x1['start'] = x0['end']


def fmt(t):
    msx = int(round(t * 1000))
    h, msx = divmod(msx, 3600000)
    mi, msx = divmod(msx, 60000)
    s, msx = divmod(msx, 1000)
    return f'{h:02d}:{mi:02d}:{s:02d}.{msx:03d}'


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def payload(c):
    s0, e0 = c['start'], c['end']
    last = [s0]

    def tag(t):
        t = max(t, last[0] + 0.001)
        if t >= e0 - 0.001:
            return ''
        last[0] = t
        return f'<{fmt(t)}>'
    out, ws = [], c['words']
    for i, w in enumerate(ws):
        pre = tag(w['s']) if (i > 0 or w['s'] > s0 + 0.05) else ''
        nxt = ws[i + 1]['s'] if i + 1 < len(ws) else e0
        post = tag(w['e']) if nxt - w['e'] >= 0.15 else ''
        out.append(f"{pre}<ruby>{esc(w['th'])}<rt>{esc(pron(w))}</rt></ruby>{post}")
    return ' '.join(out) + f"\n<c.ko>{esc(c['tr'])}</c>"


chap = []
for pnum, title in CHAPTERS:
    c = next(c for c in cues if c['p'] == pnum)
    chap.append({'t': round(c['start'], 2), 'title': title})

head = f"""WEBVTT
Kind: captions
Language: th

NOTE
{a.name}
태국어는 공식 녹취록 글이고, 시각은 {a.engine}에 녹취록 글자를 맞춰 얹은 값입니다(글자 {match_pct:.0f}% 일치, 안 맞은 글자는 앞뒤 사이를 나눈 추정).
태국어 단어마다 <ruby>태국어<rt>한글 독음</rt></ruby>, 둘째 줄 <c.ko>는 한국어 번역입니다. 단어 앞뒤에 0.12초 넘게 붙은 무음은 음성 크기로 잘라 냈습니다.
잘라 낸 구간: 원본 {fmt(CUT0)} ~ {fmt(CUT1)} (시각은 잘라 낸 음성 기준 0초부터).

"""
with open(a.out_vtt, 'w', encoding='utf-8', newline='\n') as f:
    f.write(head)
    for n, c in enumerate(cues, 1):
        f.write(f"{n}\n{fmt(c['start'])} --> {fmt(c['end'])}\n{payload(c)}\n\n")
meta = {'source': a.source, 'start': CUT0, 'end': CUT1, 'match_pct': round(match_pct, 1), 'chapters': chap,
        'cues': [{'n': n, 'para': c['p'], 'ko': c['k'], 'th': c['t'], 's': round(c['start'], 2), 'e': round(c['end'], 2),
                  'speech': [round(c['s'], 2), round(c['e'], 2)], 'conf': c['conf'], 'tr': c['tr']}
                 for n, c in enumerate(cues, 1)]}
with open(a.out_json, 'w', encoding='utf-8', newline='\n') as f:
    json.dump(meta, f, ensure_ascii=False, indent=1)
    f.write('\n')
if a.out_check:
    import csv
    with open(a.out_check, 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['줄', '시각', '문단', '믿음', '태국어 앞부분', '번역'])
        for n, c in enumerate(cues, 1):
            if c['conf'] < 0.5:
                th = ''.join(w['th'] for w in c['words'])
                mm, ss = divmod(int(c['start']), 60)
                wr.writerow([n, f'{mm}:{ss:02d}', c['p'], c['conf'], th[:40], c['tr']])
nw = sum(len(c['words']) for c in cues)
nop = sum(1 for c in cues for w in c['words'] if not pron(w))
durs = [c['end'] - c['start'] for c in cues]
print(f'줄 {len(cues)} (짧은 줄 {merged}번 합침) · 낱말 {nw} · 독음 없는 낱말 {nop}')
print(f'줄 길이 초: 가장 짧은 {min(durs):.1f} · 가운데 {float(np.median(durs)):.1f} · 가장 긴 {max(durs):.1f}')
print('믿음 0.5 미만 줄:', sum(1 for c in cues if c['conf'] < 0.5), '· 차례:', json.dumps(chap, ensure_ascii=False))
