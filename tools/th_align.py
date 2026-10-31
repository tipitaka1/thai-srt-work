# -*- coding: utf-8 -*-
"""태국어 공식 녹취록 글자를 휘스퍼 조각 시각에 얹는 정렬기 (05_ 인수인계 5-2절 뼈대).

입력
  - 녹취록 문단 목록 [(문단번호, 태국어 글)]
  - 서브웍스 휘스퍼 조각 json (`*_나_STT_SSW.json`: segments[].words[] = 글자 1~2개씩 start·end·score)
출력
  - 녹취록 글자(비교용으로 고른 글자)마다 (시작, 끝, 맞음 여부, 휘스퍼 확률)
  - 문단마다 맞은 글자 비율

방법
  1. 글자 고르기: NFC, 태국 숫자 → 0~9, 빈칸·문장부호·ๆ·ฯ 빼기, 로마자는 소문자. 원래 글자 자리는 따로 들고 간다.
  2. 휘스퍼 조각 시각을 그 조각 글자 수대로 나눈다.
  3. 닻: 양쪽에 한 번씩만 나오는 12글자 조각 → 앞으로만 가는 가장 긴 사슬(LIS) → 30글자 넘게 떨어진 것만.
  4. 닻 사이 빈 곳은 difflib.SequenceMatcher(autojunk=False)로 글자 맞춤.
  5. 맞은 글자 = 휘스퍼 시각. 안 맞은 글자 = 앞뒤 맞은 글자 사이를 글자 수대로 나눈 '추정'.
"""
import bisect
import collections
import difflib
import unicodedata

THAI_DIGITS = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')


def _keep(c):
    return ('ก' <= c <= '๎' and c not in 'ๆฯ') or c.isdigit() or 'a' <= c <= 'z'


def canon(text):
    """화면에 쓸 글(NFC·태국 숫자 그대로)."""
    return unicodedata.normalize('NFC', text)


def norm_stream(text):
    """비교용 글자열과, 글자마다 canon(text) 안의 자리."""
    t = canon(text)
    out, pos = [], []
    for i, ch in enumerate(t):
        c = ch.translate(THAI_DIGITS).lower()
        if _keep(c):
            out.append(c)
            pos.append(i)
    return ''.join(out), pos


def whisper_stream(ssw):
    chars, t0, t1, pr = [], [], [], []
    for seg in ssw['segments']:
        for w in seg.get('words') or []:
            a, b = w.get('start'), w.get('end')
            if a is None or b is None:
                continue
            s = unicodedata.normalize('NFC', w.get('word') or '').translate(THAI_DIGITS).lower()
            cs = [c for c in s if _keep(c)]
            if not cs:
                continue
            n = len(cs)
            p = w.get('score', w.get('probability', 1.0))
            for k, c in enumerate(cs):
                chars.append(c)
                t0.append(a + (b - a) * k / n)
                t1.append(a + (b - a) * (k + 1) / n)
                pr.append(p)
    return ''.join(chars), t0, t1, pr


def _unique(s, n, lo, hi):
    cnt = collections.Counter(s[i:i + n] for i in range(lo, hi - n + 1))
    return {s[i:i + n]: i for i in range(lo, hi - n + 1) if cnt[s[i:i + n]] == 1}


def _lis(pairs):
    """pairs: (a, b) a 오름차순. b 도 오름차순인 가장 긴 사슬."""
    tails, tails_i, prev = [], [], [None] * len(pairs)
    for k, (_, b) in enumerate(pairs):
        j = bisect.bisect_left(tails, b)
        if j == len(tails):
            tails.append(b)
            tails_i.append(k)
        else:
            tails[j] = b
            tails_i[j] = k
        prev[k] = tails_i[j - 1] if j else None
    out, k = [], tails_i[-1] if tails_i else None
    while k is not None:
        out.append(pairs[k])
        k = prev[k]
    return out[::-1]


def align(T, W, n=12, gap_min=30, edge_ratio=3.0):
    """T 글자마다 W 의 짝 자리(없으면 -1)."""
    ut, uw = _unique(T, n, 0, len(T)), _unique(W, n, 0, len(W))
    pairs = sorted((i, uw[g]) for g, i in ut.items() if g in uw)
    chain = _lis(pairs)
    anchors, last = [], (-10 ** 9, -10 ** 9)
    for a, b in chain:
        if a - last[0] >= gap_min and b - last[1] >= gap_min:
            anchors.append((a, b))
            last = (a, b)
    m = [-1] * len(T)

    def fill(t_lo, t_hi, w_lo, w_hi):
        if t_hi <= t_lo or w_hi <= w_lo:
            return
        sm = difflib.SequenceMatcher(None, T[t_lo:t_hi], W[w_lo:w_hi], autojunk=False)
        for blk in sm.get_matching_blocks():
            for k in range(blk.size):
                m[t_lo + blk.a + k] = w_lo + blk.b + k

    if not anchors:
        return m, anchors
    # 앞 끝: 첫 닻 앞 녹취록 글자 수의 edge_ratio 배까지만 휘스퍼를 본다
    a0, b0 = anchors[0]
    fill(0, a0, max(0, b0 - int(a0 * edge_ratio) - 50), b0)
    for (a, b), (c, d) in zip(anchors, anchors[1:]):
        for k in range(n):
            m[a + k] = b + k
        fill(a + n, c, b + n, d)
    a, b = anchors[-1]
    for k in range(n):
        m[a + k] = b + k
    rest = len(T) - (a + n)
    fill(a + n, len(T), b + n, min(len(W), b + n + int(rest * edge_ratio) + 50))
    # 거꾸로 가는 짝 지우기(안전장치)
    lw = -1
    for i in range(len(T)):
        if m[i] >= 0:
            if m[i] <= lw:
                m[i] = -1
            else:
                lw = m[i]
    return m, anchors


def char_times(m, t0, t1, pr, n_T):
    """녹취록 글자마다 [시작, 끝, 맞음(1/0), 확률]. 안 맞은 글자는 앞뒤 사이를 고르게 나눈다."""
    out = [None] * n_T
    for i, j in enumerate(m):
        if j >= 0:
            out[i] = [t0[j], t1[j], 1, pr[j]]
    idx = [i for i in range(n_T) if out[i]]
    if not idx:
        return out
    for i in range(0, idx[0]):
        out[i] = [out[idx[0]][0], out[idx[0]][0], 0, 0.0]
    for i in range(idx[-1] + 1, n_T):
        out[i] = [out[idx[-1]][1], out[idx[-1]][1], 0, 0.0]
    for a, b in zip(idx, idx[1:]):
        if b - a > 1:
            s, e = out[a][1], out[b][0]
            if e < s:
                e = s
            k = b - a - 1
            for q in range(1, b - a):
                out[a + q] = [s + (e - s) * (q - 1) / k, s + (e - s) * q / k, 0, 0.0]
    return out


# ---- 2차: 소리 무리로 맞추기 (휘스퍼가 같은 소리를 다른 글자로 적은 곳) ----
_CLASSES = ['ก', 'ขฃคฅฆ', 'ง', 'จ', 'ฉชฌ', 'ซศษส', 'ญย', 'ฎด', 'ฏต', 'ฐฑฒถทธ', 'ณน', 'บ', 'ป', 'ผพภ', 'ฝฟ',
            'ม', 'รลฬฤฦ', 'ว', 'หฮ', 'อ', 'ะัา', 'ิี', 'ึื', 'ุู', 'เแ', 'โ', 'ใไ', 'ำ']
CLASS_MAP = {c: grp[0] for grp in _CLASSES for c in grp}
DROP = set('่้๊๋็์ํ๎')   # 성조·ไม้ไต่คู้·การันต์ 등


def refine(T, W, m, min_block=2, slack=3.0):
    """1차에서 안 맞은 녹취록 구간마다, 앞뒤 맞은 글자 사이의 휘스퍼 글과 소리 무리로 다시 맞춘다."""
    n = len(T)
    added = 0
    i = 0
    while i < n:
        if m[i] >= 0:
            i += 1
            continue
        j = i
        while j < n and m[j] < 0:
            j += 1
        if i > 0:
            wlo = m[i - 1] + 1
        else:
            wlo = max(0, (m[j] if j < n else len(W)) - int((j - i) * slack) - 50)
        if j < n:
            whi = m[j]
        else:
            whi = min(len(W), wlo + int((j - i) * slack) + 50)
        if whi > wlo:
            ti = [k for k in range(i, j) if T[k] not in DROP]
            wi = [k for k in range(wlo, whi) if W[k] not in DROP]
            ts = ''.join(CLASS_MAP.get(T[k], T[k]) for k in ti)
            ws = ''.join(CLASS_MAP.get(W[k], W[k]) for k in wi)
            if ts and ws:
                sm = difflib.SequenceMatcher(None, ts, ws, autojunk=False)
                small = len(ts) <= 4 and len(ws) <= 6
                for b in sm.get_matching_blocks():
                    if b.size >= (1 if small else min_block):
                        for q in range(b.size):
                            m[ti[b.a + q]] = wi[b.b + q]
                            added += 1
        i = j
    return added
