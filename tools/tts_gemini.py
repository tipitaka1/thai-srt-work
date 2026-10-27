"""제미나이 TTS로 한국어 더빙 원음(테이크)을 만든다. 깃허브 Actions에서 돈다 (키는 저장소 비밀값 GEMINI_API_KEY).

tts/requests/*.json 하나가 요청 하나:
  {"id": "...", "voices": ["Charon", ...], "models": [선호 순서, 생략 가능],
   "style": "연출 메모", "lines": ["문장", ...]}
문장을 한 줄씩 이어 한 번에 읽힌다 (조각마다 톤이 달라지지 않게, 한 테이크 최대 약 655초).
결과: <out>/<id>/<voice>.flac, <out>/<id>/<voice>.json (모델, 길이, 토큰, 끝난 이유). 이미 있으면 건너뛴다.
"""
import base64
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request

import numpy as np
import soundfile as sf

API = "https://generativelanguage.googleapis.com/v1beta"
KEY = os.environ.get("GEMINI_API_KEY", "")
PREF = ["gemini-2.5-pro-tts", "gemini-2.5-pro-preview-tts", "gemini-3.1-flash-tts-preview",
        "gemini-2.5-flash-tts", "gemini-2.5-flash-preview-tts"]


def call(method, path, body=None, timeout=1500):
    req = urllib.request.Request(API + path, method=method,
                                 headers={"x-goog-api-key": KEY, "Content-Type": "application/json"},
                                 data=None if body is None else json.dumps(body).encode("utf-8"))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def tts_models():
    names, tok = [], ""
    while True:
        d = call("GET", "/models?pageSize=200" + (f"&pageToken={tok}" if tok else ""))
        names += [m["name"].split("/")[-1] for m in d.get("models", []) if "tts" in m["name"]]
        tok = d.get("nextPageToken")
        if not tok:
            return names


def synth(model, voice, text):
    body = {"contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    for attempt in range(6):
        try:
            d = call("POST", f"/models/{model}:generateContent", body)
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:400]}")
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(30 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            print("  연결 문제:", e)
            time.sleep(20)
            continue
        cand = (d.get("candidates") or [{}])[0]
        parts = [p["inlineData"] for p in cand.get("content", {}).get("parts", []) if "inlineData" in p]
        if not parts:
            print("  음성 없는 응답:", json.dumps(d, ensure_ascii=False)[:400])
            time.sleep(15)
            continue
        pcm = b"".join(base64.b64decode(p["data"]) for p in parts)
        return pcm, parts[0].get("mimeType", ""), d.get("usageMetadata", {}), cand.get("finishReason")
    raise RuntimeError("TTS 실패")


def main(req_dir, out_dir):
    if not KEY:
        sys.exit("GEMINI_API_KEY 비밀값이 없습니다")
    avail = tts_models()
    print("TTS 모델:", avail)
    for path in sorted(glob.glob(os.path.join(req_dir, "*.json"))):
        r = json.load(open(path, encoding="utf-8"))
        models = [m for m in r.get("models", PREF) if m in avail] or avail
        model = models[0]
        text = r["style"].strip() + "\n\n#### 대본\n" + "\n".join(r["lines"])
        os.makedirs(os.path.join(out_dir, r["id"]), exist_ok=True)
        for voice in r["voices"]:
            base = os.path.join(out_dir, r["id"], voice)
            if os.path.exists(base + ".flac"):
                print(r["id"], voice, "이미 있음")
                continue
            t0 = time.time()
            print(r["id"], voice, model, f"{sum(len(x) for x in r['lines'])}자 …", flush=True)
            pcm, mime, usage, finish = synth(model, voice, text)
            rate = int(next((p.split("=")[1] for p in mime.split(";") if p.strip().startswith("rate=")), 24000))
            x = np.frombuffer(pcm[: len(pcm) // 2 * 2], dtype="<i2")
            sf.write(base + ".flac", x, rate, subtype="PCM_16", format="FLAC")
            meta = dict(id=r["id"], voice=voice, model=model, mime=mime, rate=rate, seconds=round(len(x) / rate, 2),
                        finish=finish, usage=usage, lines=len(r["lines"]), took=round(time.time() - t0, 1))
            json.dump(meta, open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print("  ->", meta["seconds"], "초,", finish, flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
