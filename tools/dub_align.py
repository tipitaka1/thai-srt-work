"""한 번에 길게 읽힌 TTS 테이크를 문장별로 자른다.

문장 사이 쉼(무음)을 후보로 잡고, 문장마다 예상 길이(한글 음절 수 + 쉼표·마침표)에 맞도록
동적 계획법으로 경계를 고른다. 경계는 긴 쉼일수록, 문장 말하기 속도가 고를수록 점수가 좋다.
"""
import math
import re

import numpy as np


def frames_db(x, sr, hop_s=0.01):
    hop = int(sr * hop_s)
    n = len(x) // hop
    e = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9
    return np.convolve(20 * np.log10(e), np.ones(3) / 3, mode="same")


def units(s):
    """문장의 예상 길이 단위(한글 음절 1개 = 1): 숫자·라틴 글자 0.6, 문장 안 쉼표 류 2.5, 문장 안 마침표 4.5.
    (TTS가 줄 안의 마침표·쉼표에서도 꽤 쉬므로 그 쉼을 길이에 넣는다)"""
    u = len(re.findall(r"[가-힣]", s)) + 0.6 * len(re.findall(r"[0-9A-Za-z]", s))
    body = s.rstrip(" .!?…'\"’”")
    u += 2.5 * len(re.findall(r"[,·…]", body)) + 4.5 * len(re.findall(r"[.!?]", body))
    return max(u, 1.0)


def pauses(db, frac=0.4, min_len=0.12, win=5.0):
    """쉼 후보: 앞뒤 5초의 바닥(10%)과 말소리(95%) 사이 40% 아래로 0.12초 넘게 내려간 구간.
    긴 테이크에서 소리 크기나 바탕 잡음이 조금씩 달라져도 따라가도록 기준을 자리마다 다시 잡는다.
    (바닥은 말소리보다 60dB 아래로는 잡지 않는다: 쉼이 아예 0으로 나오는 테이크 대비)"""
    n = len(db)
    w, step = int(win * 100), 50
    centers = np.arange(0, n, step)
    lo, hi = [], []
    for c in centers:
        seg = db[max(0, c - w):min(n, c + w)]
        h = np.percentile(seg, 95)
        lo.append(max(np.percentile(seg, 10), h - 60))
        hi.append(h)
    lo = np.interp(np.arange(n), centers, lo)
    hi = np.interp(np.arange(n), centers, hi)
    sil = db < lo + frac * (hi - lo)
    out, i = [], 0
    while i < n:
        if sil[i]:
            j = i
            while j < n and sil[j]:
                j += 1
            out.append((i / 100, j / 100))
            i = j
        else:
            i += 1
    voiced = np.where(~sil)[0]
    start, end = voiced[0] / 100, (voiced[-1] + 1) / 100
    cands = [(a, b) for a, b in out if b - a >= min_len and a > start and b < end]
    return start, end, cands


def _dp(pts, u, rate, sigma, beta):
    n, m = len(u), len(pts) - 2
    INF = float("inf")
    cost = [[INF] * (m + 2) for _ in range(n + 1)]
    back = [[-1] * (m + 2) for _ in range(n + 1)]
    cost[0][0] = 0.0
    for k in range(1, n + 1):
        exp = u[k - 1] * rate
        js = range(1, m + 1) if k < n else (m + 1,)
        for j in js:
            seg_end = pts[j][0]
            best, arg = INF, -1
            for i in range(j - 1, -1, -1):
                d = seg_end - pts[i][1]
                if d > exp * 2.4:
                    break
                if cost[k - 1][i] == INF or d < exp * 0.42:
                    continue
                c = cost[k - 1][i] + (math.log(d / exp) / sigma) ** 2
                if c < best:
                    best, arg = c, i
            if arg >= 0 and k < n:
                plen = pts[j][1] - pts[j][0]
                best -= beta * math.log(plen / 0.12)
                if plen < 0.3:
                    best += 2.0
            cost[k][j], back[k][j] = best, arg
    if cost[n][m + 1] == INF:
        return None
    path, j = [], m + 1
    for k in range(n, 0, -1):
        path.append(j)
        j = back[k][j]
    path.append(0)
    return path[::-1]


def align(x, sr, sentences, sigma=0.22, beta=1.5):
    """문장별 (말 시작, 말 끝) 초 목록, 점검용 정보, 1단위당 초."""
    db = frames_db(x, sr)
    start, end, cands = pauses(db)
    n = len(sentences)
    u = [units(s) for s in sentences]
    pts = [(start, start)] + cands + [(end, end)]
    rate = ((end - start) - 0.8 * (n - 1)) / sum(u)
    path = None
    for _ in range(3):                      # 말 빠르기를 고쳐 가며 두세 번
        p = _dp(pts, u, rate, sigma, beta)
        if p is None:
            break
        path = p
        segs = [(pts[path[k]][1], pts[path[k + 1]][0]) for k in range(n)]
        rate = sum(e - s for s, e in segs) / sum(u)
    if path is None:
        raise ValueError("경계를 찾지 못했습니다")
    segs = [(pts[path[k]][1], pts[path[k + 1]][0]) for k in range(n)]
    info = [dict(text=sentences[k], dur=round(segs[k][1] - segs[k][0], 2),
                 dev=round(math.log((segs[k][1] - segs[k][0]) / (u[k] * rate)), 2),
                 pause_after=round(pts[path[k + 1]][1] - pts[path[k + 1]][0], 2) if k < n - 1 else None)
            for k in range(n)]
    return segs, info, rate
