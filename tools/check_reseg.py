"""문장 나누기 파일(talk_ko.txt) 점검: 첫 문장부터 끝까지 토막이 빈틈없이 이어지는지, 번역 길이가 33~58자인지, 검토 표시가 남았는지.

python3 tools/check_reseg.py work/<ID>/seg_th.txt work/<ID>/talk_ko.txt [첫줄.토막]
"""
import sys

seg_path, talk_path = sys.argv[1], sys.argv[2]
first = tuple(map(int, sys.argv[3].split("."))) if len(sys.argv) > 3 else None
sg = {}
for l in open(seg_path, encoding="utf-8"):
    p = l.rstrip("\n").split("|")
    sg[int(p[0])] = p[1].split(" ")
prev, n, bad, lens, chap = None, 0, [], [], 0
for l in open(talk_path, encoding="utf-8"):
    l = l.rstrip("\n")
    if not l.strip():
        continue
    if l.startswith("## "):
        chap += 1
        continue
    rng, tr = l.split("|", 1)
    n += 1
    (a, b), (c, d) = [tuple(map(int, p.split("."))) for p in rng.split("-")]
    if prev is None:
        exp = first or (a, b)
    else:
        exp = (prev[0], prev[1] + 1) if prev[1] + 1 < len(sg[prev[0]]) else (prev[0] + 1, 0)
    if (a, b) != exp:
        bad.append(f"{rng}: 시작이 {exp[0]}.{exp[1]} 이어야 함 (빈틈이나 겹침)")
    if d >= len(sg[c]):
        bad.append(f"{rng}: 끝 토막 번호가 범위 밖 (줄 {c}은 토막 {len(sg[c])}개, 0부터)")
    lens.append(len(tr))
    if not 33 <= len(tr) <= 58:
        bad.append(f"{rng}: 번역 {len(tr)}자 (33~58자)")
    if any(x in tr for x in ("※", "(?)")):
        bad.append(f"{rng}: 검토 표시가 남음")
    prev = (c, d)
print(f"문장 {n}개, 차례 {chap}개, 끝 {prev[0]}.{prev[1]}, 번역 {min(lens)}~{max(lens)}자 (평균 {sum(lens) / len(lens):.1f})")
print("\n".join(bad) if bad else "문제 없음")
sys.exit(1 if bad else 0)
