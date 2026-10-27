"""카톡 공유용 정사각 카드(1200x1200).
카톡이 위아래를 잘라 가로로 보여 줄 때도 보이도록, 글귀·제목·설법자·초상을 가운데 띠(y 300~900)에 모은다."""
import base64
import json
import sys

from playwright.sync_api import sync_playwright

repo, out = sys.argv[1], sys.argv[2]
t = json.load(open(f"{repo}/talks.json", encoding="utf-8"))[0]
F = "/tmp/claude-0/fonttest/node_modules/@fontsource/noto-sans-thai/files/"
thai = "".join(
    f"@font-face{{font-family:'NST';font-weight:{w};src:url(data:font/woff2;base64,"
    f"{base64.b64encode(open(F + f'noto-sans-thai-thai-{w}-normal.woff2', 'rb').read()).decode()}) format('woff2')}}"
    for w in (400, 600))
wheel = "".join(
    f'<line x1="{50 + 9 * c}" y1="{50 + 9 * s}" x2="{50 + 34 * c}" y2="{50 + 34 * s}"/>'
    for c, s in [(1, 0), (.7071, .7071), (0, 1), (-.7071, .7071), (-1, 0), (-.7071, -.7071), (0, -1), (.7071, -.7071)])
title = t.get("cardTitle", t["title"]).replace("\n", "<br>")
pf = base64.b64encode(open(f"{repo}/" + t["portraitFull"], "rb").read()).decode()
html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{thai}
*{{box-sizing:border-box}}
body{{margin:0;width:1200px;height:1200px;background:#0f1412;color:#f2eee4;font-family:'Noto Sans CJK KR',sans-serif}}
.card{{position:relative;width:1200px;height:1200px;padding:0 100px;display:flex;align-items:center;gap:56px;
  background:radial-gradient(90% 55% at 78% 50%,#1c2823 0%,#0f1412 65%)}}
.txt{{flex:1;min-width:0}}
.eyebrow{{display:flex;align-items:center;gap:16px;margin:0 0 30px;font-size:34px;font-weight:600;color:#eba443;letter-spacing:.03em}}
.eyebrow svg{{width:46px;height:46px;flex:none}}
.ttl{{margin:0;font-size:62px;line-height:1.26;font-weight:700;letter-spacing:-.025em;word-break:keep-all}}
.thai{{margin:22px 0 0;font-family:'NST';font-size:30px;line-height:1.45;color:#a9a597}}
.rule{{width:100px;height:5px;border-radius:3px;background:#eba443;margin:30px 0 24px}}
.who{{margin:0;font-size:40px;font-weight:600;color:#f2eee4}}
.when{{margin:10px 0 0;font-size:31px;line-height:1.45;color:#cfcabe}}
.pf{{width:330px;height:372px;object-fit:cover;border-radius:6px;box-shadow:0 18px 50px rgba(0,0,0,.45);flex:none}}
.foot{{position:absolute;left:100px;right:100px;bottom:84px;display:flex;justify-content:space-between;font-size:27px;color:#7c8781}}
</style></head><body><div class="card">
<div class="txt">
<p class="eyebrow"><svg viewBox="0 0 100 100" fill="none" stroke="#eba443" stroke-width="6" stroke-linecap="round">
<circle cx="50" cy="50" r="34"/><circle cx="50" cy="50" r="7" fill="#eba443" stroke="none"/>{wheel}</svg>숲속 수행승 법문</p>
<h1 class="ttl">{title}</h1>
<p class="thai">{t.get("thaiTitle", "")}</p>
<div class="rule"></div>
<p class="who">{t["speaker"]} · 당시 {t["age"]}</p>
<p class="when">{t["date"]}{" · " + t["length"] if t.get("length") else ""}<br>{t["audience"]}</p>
</div>
<img class="pf" src="data:image/jpeg;base64,{pf}" alt="">
<div class="foot"><span>숲속 수행승 법문 듣기</span><span>태국어 원문 · 한글 독음 · 한국어 번역</span></div>
</div></body></html>"""
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 1200})
    pg.set_content(html)
    pg.wait_for_timeout(400)
    box = pg.evaluate("()=>{const r=document.querySelector('.txt').getBoundingClientRect();"
                      "const q=document.querySelector('.pf').getBoundingClientRect();return [r.top,r.bottom,q.top,q.bottom]}")
    pg.screenshot(path=out)
    b.close()
print("글 블록 y:", [round(v) for v in box[:2]], "| 초상 y:", [round(v) for v in box[2:]], "(가로 2:1로 잘려도 보이는 띠: 300~900)")
