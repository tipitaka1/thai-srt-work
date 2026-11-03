# -*- coding: utf-8 -*-
"""공식 녹취록(정답) 대비 일레븐랩스·휘스퍼 받아쓰기의 오류율.

- 글자 오류율 CER = 편집거리(정답, 받아쓰기) / 정답 글자 수  (빈칸·문장부호 뺀 태국어 글자열 기준)
- 낱말 오류율 WER = 같은 식, pythainlp newmm 으로 자른 낱말열 기준
- 받아쓰기는 법문 앞뒤의 잡담까지 들어 있으므로, 정답과 정렬(th_align)해서 맞닿은 구간만 잘라 비교한다.
"""
import json
import re
import sys
import unicodedata
import collections

sys.path.insert(0, '/home/user/thai-srt-work/tools')
import th_align as A  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402
from pythainlp.tokenize import word_tokenize  # noqa: E402

REF_MD, ELEVEN, WHISPER, OUT = sys.argv[1:5]

# ---- 정답: ¶ 문단 (머리말·꼬리말 제외) ----
lines = open(REF_MD, encoding='utf-8').read().split('\n')
paras = []
for ln in lines[10:88]:          # 11행 ~ 88행 (0-based 10..87)
    s = ln.strip()
    if not s:
        continue
    s = re.sub(r'^>>\s*', '', s)
    s = re.sub(r'^(ผู้กำกับ|หลวงตา)\s+', '', s)
    paras.append(s)
assert paras[0].startswith('วันนี้คนไม่มากนัก') and paras[-1].endswith('เอาละจะให้พร'), (paras[0][:30], paras[-1][-30:])

T, pidx = '', []
for k, p in enumerate(paras):
    s, _ = A.norm_stream(p)
    T += s
    pidx += [k] * len(s)


def load_hyp(path):
    d = json.load(open(path, encoding='utf-8-sig'))
    segs = []
    for sg in d['segments']:
        txt = re.sub(r'\[[^\]]*\]', '', sg['text'])      # [เสียงหัวเราะ] 같은 표시 제거
        segs.append((sg['start'], sg['end'], txt))
    W, w_t0, w_t1, _ = A.whisper_stream(d)
    # 조각 글자 → 시각 (문자열 자리 → 시각)
    return segs, W, w_t0, w_t1


def tokens(s):
    return [w for w in word_tokenize(s, engine='newmm', keep_whitespace=False) if w.strip()]


def ops_count(ref, hyp):
    c = collections.Counter(op.tag for op in Levenshtein.editops(ref, hyp))
    return c['replace'], c['delete'], c['insert']


def mmss(t):
    return f'{int(t // 60)}:{int(t % 60):02d}'


report = {}
for name, path in (('일레븐랩스', ELEVEN), ('휘스퍼', WHISPER)):
    segs, W, t0, t1 = load_hyp(path)
    m, anchors = A.align(T, W)
    A.refine(T, W, m)
    matched = [v for v in m if v >= 0]
    exact = len(matched)
    lo, hi = min(matched), max(matched) + 1
    H = W[lo:hi]
    dist = Levenshtein.distance(T, H)
    sub, dele, ins = ops_count(T, H)
    # 낱말 단위 (정답 문단 글 그대로 / 받아쓰기는 맞닿은 구간의 조각 글)
    span_t0, span_t1 = t0[lo], t1[hi - 1]
    hyp_text = ''.join(txt for s, e, txt in segs if e > span_t0 and s < span_t1)
    ref_text = ' '.join(paras)
    rt, ht = tokens(unicodedata.normalize('NFC', ref_text)), tokens(unicodedata.normalize('NFC', hyp_text))
    wdist = Levenshtein.distance(rt, ht)
    # 문단별 CER
    per = []
    for k, p in enumerate(paras):
        idx = [i for i in range(len(T)) if pidx[i] == k]
        mm = [m[i] for i in idx if m[i] >= 0]
        ref_p = T[idx[0]:idx[-1] + 1]
        if len(mm) < 5:
            per.append((k + 1, len(ref_p), None, 0.0))
            continue
        hyp_p = W[min(mm):max(mm) + 1]
        per.append((k + 1, len(ref_p), Levenshtein.distance(ref_p, hyp_p) / len(ref_p), len(mm) / len(ref_p)))
    # 받아쓰기 쪽 반복(환각) 덩어리: 같은 2~6글자가 6번 넘게 연달아
    hall = [(mmss(t0[mo.start()]), mo.group(0)[:30]) for mo in re.finditer(r'(.{2,6}?)\1{5,}', W)]
    report[name] = dict(
        ref_chars=len(T), hyp_chars_span=len(H), hyp_chars_all=len(W),
        span=(mmss(span_t0), mmss(span_t1)), cer=dist / len(T), sub=sub, dele=dele, ins=ins,
        exact_pct=exact / len(T) * 100, anchors=len(anchors),
        ref_words=len(rt), hyp_words=len(ht), wer=wdist / len(rt), per=per, hall=hall)

json.dump(report, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
for name, r in report.items():
    print(f"\n== {name} ==")
    print(f"정답 {r['ref_chars']:,}글자 · 받아쓰기 전체 {r['hyp_chars_all']:,}글자 · 법문 구간 {r['span'][0]}~{r['span'][1]} {r['hyp_chars_span']:,}글자")
    print(f"글자 오류율 CER {r['cer']*100:.1f}%  (바꿈 {r['sub']:,} · 빠짐 {r['dele']:,} · 끼어듦 {r['ins']:,})")
    print(f"낱말 오류율 WER {r['wer']*100:.1f}%  (정답 {r['ref_words']:,}낱말 · 받아쓰기 {r['hyp_words']:,}낱말)")
    print(f"정답 글자 중 받아쓰기와 자리까지 맞은 글자 {r['exact_pct']:.1f}% · 닻 {r['anchors']}")
    print("반복 환각 덩어리:", r['hall'][:8] if r['hall'] else '없음')
    worst = sorted([x for x in r['per'] if x[2] is not None], key=lambda x: -x[2])[:5]
    print("문단별 CER 나쁜 순 5:", [(f'¶{p}', f'{c*100:.0f}%') for p, n, c, e in worst])
