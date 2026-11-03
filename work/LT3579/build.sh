#!/bin/sh
# LT3579 다시 만들기 (저장소 뿌리에서). 원본 wma 와 일레븐랩스 조각 json(본 법문 구간만 남긴 사본)은 저장소에 없다.
# 조각 json 은 00_번역완료_음원.zip 의 서브웍스_일레븐랩스/*.json 에서 segments 를 4:28.3~43:13.0 구간만 남긴 것.
set -e
WMA="$1"; SSW="${2:-work/LT3579/LT3579_eleven_cut.json}"
python3 -I tools/talk_to_pairs.py --md work/LT3579/transcript_ID3579.md --talk work/LT3579/talk_ko.txt --first-line 11 --last-line 88 --out-dir work/LT3579
python3 -I tools/build_transcript.py --paras work/LT3579/paras.json --pairs work/LT3579/pairs.json \
  --pron work/LT3579/pron_ko.json --pali work/LT3579/pali.json \
  --ssw "$SSW" --audio "$WMA" --cut 268.3 2593.0 \
  --chapters "$(cat work/LT3579/chapters.txt)" \
  --name "LT3579 (2005-09-05) Luang Ta Maha Bua - อดอาหารนี้ดีทุกขั้นสำหรับเรา (단식은 어느 단계에서든 나에게 좋았다)" \
  --source "LT3579_20050905_47m_a5-09-48.wma" --engine "일레븐랩스 scribe v2 받아쓰기(낱말 시각)" \
  --bad-words "มีนา,ระมา,เสียที่,ได้เสีย,มานะ,ว่าความ,ว่าง่าย,เป็นน้ำ,ที่แล้ว,จะจ้า,ไหนจะ,เจ้าที่,หันมา,ฉันนั้น" \
  --out-vtt media/LT3579_talk.vtt --out-json media/LT3579_talk.json --out-check work/LT3579/low_conf.csv
ffmpeg -v error -y -ss 268.3 -to 2593.0 -i "$WMA" -ac 1 -ar 48000 -af "afade=t=in:d=0.3,afade=t=out:st=2324.1:d=0.6" -c:a libopus -b:a 24k -f webm media/LT3579_talk.webm
