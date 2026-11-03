"""녹취록 법문의 번역 파일(talk_ko.txt) → build_transcript.py 입력(paras.json, pairs.json, 차례 문자열).

talk_ko.txt 형식
  # 제목            → 바로 아래 문단에서 시작하는 차례
  ## ¶N             → 녹취록 문단 번호 (머리말 ¶1–3 다음 본문이 ¶4)
  a-b|한국어 문장    → 그 문단의 태국어 토막 a~b(빈칸 단위, 1부터, 끝 포함)에 붙는 한 줄

확인하는 것
  - 문단마다 토막 범위가 1부터 끝까지 빈틈도 겹침도 없이 이어지는지
  - 번역 글자 수(33~58자 권장) 밖인 줄

사용
  python3 tools/talk_to_pairs.py --md work/LT3579/transcript_ID3579.md --talk work/LT3579/talk_ko.txt \
      --first-line 11 --last-line 88 --out-dir work/LT3579 [--show]
"""
import argparse
import json
import re
import unicodedata

ap = argparse.ArgumentParser()
ap.add_argument('--md', required=True, help='녹취록 md (luangta.com 사본)')
ap.add_argument('--talk', required=True)
ap.add_argument('--first-line', type=int, required=True, help='본문 첫 줄(1부터) — 머리말 다음')
ap.add_argument('--last-line', type=int, required=True, help='본문 끝 줄(포함)')
ap.add_argument('--first-para', type=int, default=4, help='본문 첫 문단의 ¶ 번호')
ap.add_argument('--out-dir', required=True)
ap.add_argument('--min', type=int, default=33)
ap.add_argument('--max', type=int, default=58)
ap.add_argument('--show', action='store_true', help='줄마다 태국어·번역을 나란히 찍는다')
a = ap.parse_args()

lines = open(a.md, encoding='utf-8').read().split('\n')
paras = []
for ln in lines[a.first_line - 1:a.last_line]:
    s = ln.strip()
    if not s:
        continue
    s = re.sub(r'^>>\s*', '', s)
    s = re.sub(r'^(ผู้กำกับ|หลวงตา)\s+', '', s)
    paras.append(unicodedata.normalize('NFC', s))
P = {a.first_para + k: p for k, p in enumerate(paras)}

talk = {}
chapters = []
pending_title, cur = None, None
for raw in open(a.talk, encoding='utf-8'):
    s = raw.rstrip('\n')
    if not s.strip() or s.startswith('#  '):      # 빈 줄, 머리 주석의 이어지는 줄
        continue
    m = re.match(r'^## ¶(\d+)', s)
    if m:
        cur = int(m.group(1))
        talk[cur] = []
        if pending_title:
            chapters.append((cur, pending_title))
            pending_title = None
        continue
    m = re.match(r'^# (.+)$', s)
    if m:                                          # `## ¶` 바로 앞의 마지막 `# ` 줄만 차례 제목이 된다 (머리 주석은 덮어써짐)
        pending_title = m.group(1).strip()
        continue
    m = re.match(r'^(\d+)-(\d+)\|(.*)$', s)
    if not m:
        raise SystemExit(f'형식 오류: {s[:60]}')
    talk[cur].append((int(m.group(1)), int(m.group(2)), m.group(3).strip()))

bad = 0
out_paras, pairs = [], {}
nlines = 0
for p, th in P.items():
    ph = th.split()
    rows = talk.get(p)
    if not rows:
        print(f'¶{p}: 번역 없음')
        bad += 1
        continue
    exp = 1
    ks = []
    pr = []
    for i, (a0, a1, ko) in enumerate(rows, 1):
        if a0 != exp or a1 < a0:
            print(f'¶{p} {a0}-{a1}: 토막 번호가 {exp}부터 이어지지 않음')
            bad += 1
        exp = a1 + 1
        if not ko:
            print(f'¶{p} {a0}-{a1}: 번역이 비었음')
            bad += 1
        n = len(ko)
        if n < a.min or n > a.max:
            print(f'¶{p} {a0}-{a1}: {n}자 — {ko}')
        ks.append(ko)
        pr.append([i, i, a0, a1])
        nlines += 1
        if a.show:
            print(f"¶{p} {a0}-{a1} | {' '.join(ph[a0 - 1:a1])}\n        → {ko}")
    if exp != len(ph) + 1:
        print(f'¶{p}: 토막 {len(ph)}개인데 {exp - 1}까지만 덮음')
        bad += 1
    out_paras.append({'p': p, 'th': th, 'ko': ' '.join(ks), 'ph': ph, 'ks': ks})
    pairs[str(p)] = pr
extra = set(talk) - set(P)
if extra:
    print('녹취록에 없는 문단:', sorted(extra))
    bad += 1

json.dump(out_paras, open(f'{a.out_dir}/paras.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(pairs, open(f'{a.out_dir}/pairs.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
ch = '|'.join(f'{p}:{t}' for p, t in chapters)
open(f'{a.out_dir}/chapters.txt', 'w', encoding='utf-8').write(ch + '\n')
lens = [len(k) for o in out_paras for k in o['ks']]
print(f'문단 {len(out_paras)} · 줄 {nlines} · 글자 수 가운데 {sorted(lens)[len(lens) // 2]} · 범위 밖 {sum(1 for n in lens if n < a.min or n > a.max)} · 차례 {len(chapters)}')
print('차례:', ch)
print('문제', bad)
