"""법문 하나를 HTML 파일 하나로 묶는다 (음성·자막·초상을 안에 넣음). 인터넷 없이, 서버 없이 더블클릭으로 열린다.

  python3 tools/make_offline.py <저장소> <법문 id> <출력 html>

- 앱 화면(index.html)을 그대로 쓰되, talks.json 과 자막(vtt)은 fetch 를 가로채 안에 넣은 글을 돌려주고,
  음성은 base64 로 넣었다가 열 때 Blob 주소로 바꿔 au.src 에 준다 (파일 주소로 열어도 탐색이 된다).
- 공유 단추는 깃허브 앱의 공유 주소(s/<id>.html)를 가리키게 둔다.
- 더빙(dub)은 넣지 않는다. 글꼴은 인터넷이 되면 구글 글꼴, 아니면 폰·PC 글꼴.
"""
import base64
import html
import json
import mimetypes
import re
import sys

repo, want, out = sys.argv[1], sys.argv[2], sys.argv[3]
BASE = "https://tipitaka1.github.io/thai-srt-work/"
talks = json.load(open(f"{repo}/talks.json", encoding="utf-8"))
t = next(x for x in talks if x["id"] == want)
page = open(f"{repo}/index.html", encoding="utf-8").read()


def data_uri(path):
    mt = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return f"data:{mt};base64," + base64.b64encode(open(f"{repo}/{path}", "rb").read()).decode()


talk = dict(t)
talk.pop("dub", None)
talk.pop("oldShare", None)
for k in ("portrait", "portraitFull"):
    if talk.get(k):
        talk[k] = data_uri(talk[k])
talk["share"] = BASE + t["share"] if t.get("share") else BASE + "?t=" + t["id"]
talk["card"] = BASE + t["card"] if t.get("card") else ""
audio_b64 = base64.b64encode(open(f"{repo}/{t['audio']}", "rb").read()).decode()
audio_mt = mimetypes.guess_type(t["audio"])[0] or "audio/webm"
vtt = open(f"{repo}/{t['vtt']}", encoding="utf-8").read()

inject = f"""<script>
/* 오프라인 묶음: talks.json·자막은 fetch 를 가로채 안에 든 글을 주고, 음성은 Blob 주소로 준다 */
(function () {{
  var TALK = {json.dumps(talk, ensure_ascii=False)};
  var VTT = {json.dumps(vtt, ensure_ascii=False)};
  var AUDIO_B64 = "{audio_b64}";
  function blobUrl(b64, type) {{
    var bin = atob(b64), u = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    return URL.createObjectURL(new Blob([u], {{ type: type }}));
  }}
  var vttPath = TALK.vtt;
  TALK.audio = blobUrl(AUDIO_B64, {json.dumps(audio_mt)});
  AUDIO_B64 = null;
  var inline = {{}};
  inline['talks.json'] = JSON.stringify([TALK]);
  inline[vttPath] = VTT;
  var f0 = window.fetch.bind(window);
  window.fetch = function (u, o) {{
    var k = typeof u === 'string' ? u : (u && u.url) || '';
    if (Object.prototype.hasOwnProperty.call(inline, k))
      return Promise.resolve(new Response(inline[k], {{ status: 200, headers: {{ 'Content-Type': 'text/plain; charset=utf-8' }} }}));
    return f0(u, o);
  }};
}})();
</script>"""

share_title = " · ".join(x for x in (t["title"], t["speaker"], t["dateShort"]) if x)
page = re.sub(r"<title>.*?</title>", f"<title>{html.escape(share_title)}</title>", page, count=1, flags=re.S)
page = re.sub(r'<link rel="manifest"[^>]*>\n?', "", page)
page = page.replace("<head>\n", "<head>\n" + inject + "\n", 1)
open(out, "w", encoding="utf-8", newline="\n").write(page)
print(f"{out}: {len(page.encode('utf-8')) / 1048576:.1f} MB · {share_title}")
