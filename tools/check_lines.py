"""N|태국어 토막|독음|번역 파일을 SRT와 대조: 토막을 이으면 원문과 같은지, 토막 수와 독음 수가 같은지."""
import sys
srt, data = sys.argv[1], sys.argv[2]
t = open(srt, encoding='utf-8').read().strip().split('\n\n')
th = {}
for b in t:
    l = b.split('\n')
    th[int(l[0])] = ''.join(x.strip() for x in l[2:])
bad = 0
for line in open(data, encoding='utf-8'):
    line = line.rstrip('\n')
    if not line.strip():
        continue
    n, seg, pr, tr = line.split('|')
    n = int(n)
    pieces = seg.split(' ')
    toks = pr.split()
    j = ''.join(pieces)
    if j != th[n]:
        bad += 1
        # 처음 어긋나는 자리
        k = next((i for i, (a, b) in enumerate(zip(j, th[n])) if a != b), min(len(j), len(th[n])))
        print(f"{n}: 원문 불일치 @{k}: 토막={j[k-3:k+6]!r} 원문={th[n][k-3:k+6]!r}  ({[hex(ord(c)) for c in th[n][k:k+3]]})")
    if len(pieces) != len(toks):
        bad += 1
        print(f"{n}: 토막 {len(pieces)}개 / 독음 {len(toks)}개")
        for a, b in zip(pieces, toks):
            pass
    if '' in pieces:
        bad += 1
        print(f"{n}: 빈 토막")
print('문제 줄 수:', bad)
