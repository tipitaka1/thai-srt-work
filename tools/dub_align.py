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
    """문장의 예상 길이 단위: 한글 음절 1, 숫자·라틴 글자 0.6, 쉼표 류 1.5, 문장 안 마침표 2."""
    u = len(re.findall(r"[가-힣]", s)) + 0.6 * len(re.findall(r"[0-9A-Za-z]", s))
    body = s.rstrip(" .!?…'\"’”")
    u += 1.5 * len(re.findall(r"[,·…]", body)) + 2.0 * len(re.findall(r"[.!?]", body))
    return max(u, 1.0)


def pauses(db, min_len=0.15):
    floor, peak = np.percentile(db, 5), np.percentile(db, 95)
    thr = floor + 0.25 * (peak - floor)
    sil = db < thr
    out, i, n = [], 0, len(db)
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


def align(x, sr, sentences, sigma=0.18, beta=1.0):
    """문장별 (말 시작, 말 끝) 초 목록과 점검용 정보."""
    db = frames_db(x, sr)
    start, end, cands = pauses(db)
    n, m = len(sentences), len(cands)
    u = [units(s) for s in sentences]
    speech = (end - start) - 0.45 * (n - 1)          # 문장 사이 쉼을 대략 뺀 말 시간
    rate = speech / sum(u)
    # 경계 후보: 0 = 시작, 1..m = 쉼 후보, m+1 = 끝
    pts = [(start, start)] + cands + [(end, end)]
    INF = float("inf")
    cost = [[INF] * (m + 2) for _ in range(n + 1)]
    back = [[-1] * (m + 2) for _ in range(n + 1)]
    cost[0][0] = 0.0
    for k in range(1, n + 1):
        exp = u[k - 1] * rate
        lo_j = 1 if k < n else m + 1
        hi_j = m if k < n else m + 1
        for j in range(lo_j, hi_j + 1):
            seg_end = pts[j][0]
            best, arg = INF, -1
            for i in range(0, j):
                if cost[k - 1][i] == INF:
                    continue
                seg_start = pts[i][1]
                d = seg_end - seg_start
                if d <= 0.2:
                    continue
                r = math.log(d / exp)
                if abs(r) > 1.2:
                    continue
                c = cost[k - 1][i] + (r / sigma) ** 2
                if k < n:
                    plen = pts[j][1] - pts[j][0]
                    c -= beta * math.log(plen / 0.2)
                if c < best:
                    best, arg = c, i
            cost[k][j], back[k][j] = best, arg
    if cost[n][m + 1] == INF:
        raise ValueError("경계를 찾지 못했습니다")
    path, j = [], m + 1
    for k in range(n, 0, -1):
        path.append(j)
        j = back[k][j]
    path.append(0)
    path = path[::-1]
    segs = []
    for k in range(n):
        s, e = pts[path[k]][1], pts[path[k + 1]][0]
        segs.append((s, e))
    info = [dict(text=sentences[k], dur=round(segs[k][1] - segs[k][0], 2),
                 dev=round(math.log((segs[k][1] - segs[k][0]) / (u[k] * rate)), 2),
                 pause_after=round(pts[path[k + 1]][1] - pts[path[k + 1]][0], 2) if k < n - 1 else None)
            for k in range(n)]
    return segs, info, rate
