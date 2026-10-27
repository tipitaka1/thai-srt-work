import html
import json
import sys

core_path, repo = sys.argv[1], sys.argv[2]
BASE = "https://tipitaka1.github.io/thai-srt-work/"
core = open(core_path, encoding="utf-8").read()
head, body = core.split("<!--HEAD-END-->")
t = json.load(open(f"{repo}/talks.json", encoding="utf-8"))[0]
share_title = " · ".join(x for x in (t["title"], t["speaker"], t["dateShort"]) if x)
def describe(t):
    what = "태국어 원문, 한글 독음, 한국어 번역"   # 더빙 여부로 바꾸지 않는다 (카톡 미리보기가 바뀌지 않게)
    whole = f"{t['length']} 법문 전체를 " if t.get("length") else ""
    return f"{t['speaker']}({t['age']}) · {t['date']} · {t['audience']} — {whole}{what}과 함께 듣기"


desc = describe(t)
e = lambda s: html.escape(s, quote=True)
head = head.replace("<title>숲속 수행승 법문 듣기</title>", f"<title>{e(share_title)}</title>")
og = f"""<meta name="description" content="{e(desc)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="숲속 수행승 법문 듣기">
<meta property="og:title" content="{e(share_title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{BASE}">
<meta property="og:image" content="{BASE}{t['card']}">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="1200">
<meta property="og:image:alt" content="{e(share_title)}">
<meta name="twitter:card" content="summary_large_image">"""
page = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0f1412" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#f3f4ef" media="(prefers-color-scheme: light)">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="숲속 법문 듣기">
{og}
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icons/icon-192.png">
<link rel="apple-touch-icon" href="icons/icon-192.png">
<style>:root{{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}[hidden]{{display:none!important}}</style>
{head.strip()}
</head>
<body>
{body.strip()}
</body>
</html>
"""
open(f"{repo}/index.html", "w", encoding="utf-8", newline="\n").write(page)
print("index.html ok |", share_title)

# 법문마다 카톡 미리보기 전용 주소: 정적 og 태그 + 앱으로 바로 넘김
import os
pages = []
for t in json.load(open(f"{repo}/talks.json", encoding="utf-8")):
    if t.get("share"):
        pages.append((t["share"], t))
        pages += [(old, t) for old in t.get("oldShare", [])]   # 예전 공유 주소도 같은 미리보기로 이 법문에 넘긴다
for page_path, t in pages:
    st = " · ".join(x for x in (t["title"], t["speaker"], t["dateShort"]) if x)
    ds = describe(t)
    url, app = BASE + t["share"], f"../?t={t['id']}"
    sp = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(st)}</title>
<meta name="description" content="{e(ds)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="숲속 수행승 법문 듣기">
<meta property="og:title" content="{e(st)}">
<meta property="og:description" content="{e(ds)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}{t['card']}">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="1200">
<meta property="og:image:alt" content="{e(st)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{url}">
<meta http-equiv="refresh" content="0; url={app}">
<style>body{{margin:0;padding:24px;background:#0f1412;color:#f2eee4;font:16px/1.6 sans-serif}}a{{color:#eba443}}</style>
</head>
<body>
<p><a href="{app}">{e(t['title'])} 열기</a></p>
<script>location.replace({json.dumps(app)});</script>
</body>
</html>
"""
    os.makedirs(os.path.dirname(f"{repo}/{page_path}"), exist_ok=True)
    open(f"{repo}/{page_path}", "w", encoding="utf-8", newline="\n").write(sp)
    print("share page ok |", page_path)
