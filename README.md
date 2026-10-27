# thai-srt-work · 태국법문 따라읽기

휘스퍼로 뽑은 태국어 법문 자막에 한글 독음과 한국어 번역을 달고, 말하는 단어마다 색이 차오르는 노래방식 자막(WebVTT)으로 듣는 저장소입니다.

## 폰에서 듣기

- 주소: <https://tipitaka1.github.io/thai-srt-work/>
- 처음 한 번 깃허브 페이지를 켜야 열립니다: **Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: `gh-pages` / `(root)` → Save** (1~2분 뒤 열림)
- 홈 화면에 추가하면 앱처럼 열립니다. 안드로이드 크롬은 메뉴 → 홈 화면에 추가, 아이폰 사파리는 공유 → 홈 화면에 추가.
- 지금 들어 있는 것: 루앙따 마하부와 법문 LT2401(2003.10.11) 중 9:20~9:53 샘플 ('종이 땡 울리면' 대목)

화면 보는 법: 태국어 단어 위 작은 글씨가 한글 독음, 아래 줄이 한국어 번역입니다. 단어를 누르면 그 자리부터 재생하고, 아래 버튼으로 속도·독음·번역·글자 크기를 바꿉니다. 번역 앞 ※는 참고 녹취와 대조해 휘스퍼가 잘못 들은 것이 확인된 줄, (?)는 뜻이 불확실한 줄입니다.

## PC에서 내 파일로 듣기

`index.html`을 내려받아 열고 「내 파일 열기」에서 음성(WAV·MP3)과 VTT를 함께 고릅니다. 파일은 PC 밖으로 나가지 않습니다. 전체 법문은 `subtitles/LT2401_2003-10-11_karaoke.vtt`를 원본 WAV·MP3와 함께 고르면 됩니다(1~180줄, 약 14분까지 독음·번역).

## 폴더

| 경로 | 내용 |
|---|---|
| `index.html`, `manifest.webmanifest`, `sw.js`, `icons/` | 웹앱 (폰·PC 공용) |
| `talks.json` | 앱에 뜨는 법문 목록 |
| `media/` | 샘플 음성(mp3)과 자막(vtt) |
| `subtitles/` | 전체 노래방 VTT, 독음·번역을 붙인 SRT |
| `work/LT2401/` | 휘스퍼 원본 SRT, 단어별 시각 JSON, 독음·번역(`pron_ko.txt`), 독음 토막에 맞춘 태국어 토막(`seg_th.txt`) |
| `tools/build_karaoke.py` | 위 자료로 VTT를 만드는 스크립트 |

## 법문 추가하기

1. `media/`에 mp3와 vtt를 넣습니다.
2. `talks.json`에 항목을 하나 더 적습니다 (`id`, `title`, `subtitle`, `speaker`, `audio`, `vtt`). 두 개 이상이면 앱 위쪽에 고르는 칸이 생깁니다.

## VTT 형식

```
102
00:00:03.460 --> 00:00:09.180
<ruby>จะ<rt>짜</rt></ruby> <00:00:03.640><ruby>ไม่<rt>마이</rt></ruby> …
<c.ko>다른 길은 없다고요. …</c>
```

- `<ruby>태국어<rt>독음</rt></ruby>`: 단어와 독음 한 쌍
- `<시:분:초.밀리초>`: 다음 단어가 시작하는 시각 (단어 바로 뒤에 붙은 시각은 그 단어가 끝나는 시각)
- `<c.ko>…</c>`: 한국어 번역 줄

표준 WebVTT라 다른 플레이어에서도 열립니다. 단어마다 차오르는 효과는 이 앱에서 보입니다.

단어 시각은 휘스퍼 단어 시각을 글자 위치로 나눠 잡은 뒤, 단어 앞뒤에 0.12초 넘게 붙은 무음을 음성 크기로 잘라 낸 값입니다.

## 다시 만들기

```
python3 tools/build_karaoke.py \
  --srt  work/LT2401/LT2401_2003-10-11.srt \
  --json work/LT2401/LT2401_2003-10-11_words.json \
  --mp3  <원본 mp3 경로> \
  --data work/LT2401 \
  --out  subtitles/LT2401_2003-10-11_karaoke.vtt \
  --site .
```

ffmpeg와 numpy가 필요합니다. 원본 25분 mp3는 저장소에 넣지 않았습니다.

## 회사 나스(DS1821+)로 옮길 때

패키지 센터에서 Web Station을 켜고, `web` 공유 폴더에 이 저장소 파일을 `thai-srt-work` 폴더째 복사합니다. 회사 와이파이에서는 `http://<나스 주소>/thai-srt-work/`로 열립니다. 회사 밖에서 열려면 DDNS, 역방향 프록시, HTTPS 인증서 설정이 더 필요합니다.
