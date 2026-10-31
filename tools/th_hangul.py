# -*- coding: utf-8 -*-
"""태국어 낱말 → 한글 독음.

1) 앞 법문(LT2401)에서 손본 독음 사전이 있으면 그것을 쓴다.
2) 없으면 tltk 의 발음(IPA, 음절마다 성조 숫자)을 한글 규칙으로 바꾼다.
   규칙은 LT2401 독음과 같은 꼴: ก→ㄲ, ข·ค→ㅋ, จ→ㅉ, ช·ฉ→ㅊ, ต→ㄸ, ท·ถ→ㅌ, ป→ㅃ, พ·ผ→ㅍ, ฟ→ㅍ,
   받침 -ด·-ต(t)→ㅅ, -บ(p)→ㅂ, -ก(k)→ㄱ, ɔ·ɤ→ㅓ, 겹모음 ia·ɯa·ua 는 '아'를 따로 적고 받침은 '아'에,
   -ย 받침 → '이', -ว 받침 → '우'(짧은 เ-า 는 '오'), 자음+ล 겹자음은 'ㄹㄹ'(쁠렁), 자음+ร 는 'ㄹ'(끄라).
성조와 장단은 적지 않는다.
"""
import os
import re
import sys
import warnings

warnings.filterwarnings('ignore')

CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
JUNG = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
JONG = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']


def block(c, v, j=''):
    return chr(0xAC00 + (CHO.index(c) * 21 + JUNG.index(v)) * 28 + JONG.index(j))


ONSET = {'k': 'ㄲ', 'kʰ': 'ㅋ', 'c': 'ㅉ', 'cʰ': 'ㅊ', 't': 'ㄸ', 'tʰ': 'ㅌ', 'p': 'ㅃ', 'pʰ': 'ㅍ',
         'b': 'ㅂ', 'd': 'ㄷ', 'ʔ': 'ㅇ', 'm': 'ㅁ', 'n': 'ㄴ', 'ŋ': 'ㅇ', 'f': 'ㅍ', 's': 'ㅅ', 'h': 'ㅎ',
         'l': 'ㄹ', 'r': 'ㄹ', 'w': 'ㅇ', 'j': 'ㅇ', '': 'ㅇ'}
VOWEL = {'a': 'ㅏ', 'i': 'ㅣ', 'ɯ': 'ㅡ', 'u': 'ㅜ', 'e': 'ㅔ', 'ɛ': 'ㅐ', 'o': 'ㅗ', 'ᴐ': 'ㅓ', 'ɔ': 'ㅓ', 'ɤ': 'ㅓ'}
W_GLIDE = {'ㅏ': 'ㅘ', 'ㅐ': 'ㅙ', 'ㅔ': 'ㅞ', 'ㅣ': 'ㅟ', 'ㅓ': 'ㅝ', 'ㅗ': 'ㅝ', 'ㅜ': 'ㅜ', 'ㅡ': 'ㅟ'}
J_GLIDE = {'ㅏ': 'ㅑ', 'ㅐ': 'ㅒ', 'ㅓ': 'ㅕ', 'ㅔ': 'ㅖ', 'ㅗ': 'ㅛ', 'ㅜ': 'ㅠ', 'ㅣ': 'ㅣ', 'ㅡ': 'ㅠ'}   # ยึด 윳
CODA = {'p': 'ㅂ', 't': 'ㅅ', 'k': 'ㄱ', 'm': 'ㅁ', 'n': 'ㄴ', 'ŋ': 'ㅇ', 'ʔ': '', '': ''}

_SYL = re.compile(r'^(kʰ|pʰ|tʰ|cʰ|[kptcbdʔmnŋfshlrwj]?)(l|r|w)?((?:iːa|ɯːa|uːa|ia|ɯa|ua|[aiɯueɛoᴐɔɤ])ː?)'
                  r'(kʰ|[ptkmnŋwjʔ])?([1-5])?$')


def syl_parts(s):
    m = _SYL.match(s)
    if not m:
        return None
    on, cl, vw, cd, _ = m.groups()
    return on or '', cl or '', vw, cd or ''


def syl_hangul(parts, ao='우', prev_open=None):
    """음절 하나 → 한글 덩어리 목록. ao: 짧은 เ-า 이면 '오'."""
    on, cl, vw, cd = parts
    out = []
    lead = ONSET.get(on, 'ㅇ')
    if on == 'ŋ':
        out.append('응')
        lead = 'ㅇ'
    if cl in ('l', 'r') and on:
        out.append(block(lead, 'ㅡ', 'ㄹ' if cl == 'l' else ''))
        lead = 'ㄹ'
        glide = ''
    elif cl == 'w':
        glide = 'w'
    else:
        glide = 'w' if on == 'w' else 'j' if on == 'j' else ''
    base = vw.replace('ː', '')
    if len(base) == 2:                     # ia ɯa ua
        v1, v2 = VOWEL[base[0]], 'ㅏ'
    else:
        v1, v2 = VOWEL[base], None
    if base == 'ɤ' and cd in ('m', 'ŋ'):   # LT2401: เริ่ม 름 · เพิ่ง 픙 (เกิน 껀 · เดิน 던 은 ㅓ)
        v1 = 'ㅡ'
    if glide == 'w':
        v1 = W_GLIDE.get(v1, v1)
    elif glide == 'j':
        v1 = J_GLIDE.get(v1, v1)
    tail = ''
    jong = CODA.get(cd, '') if cd not in ('w', 'j') else ''
    if cd == 'j':
        tail = '이'
    elif cd == 'w':
        tail = ao if base == 'a' else '우'
    if v2:
        out.append(block(lead, v1))
        out.append(block('ㅇ', v2, jong))
    else:
        out.append(block(lead, v1, jong))
    if tail:
        out.append(tail)
    return out


def _add_jong(ch, j):
    code = ord(ch) - 0xAC00
    if not (0 <= code < 11172) or code % 28:
        return ch
    return chr(ord(ch) + JONG.index(j))


def _drop_jong(ch):
    code = ord(ch) - 0xAC00
    if not (0 <= code < 11172):
        return ch
    return chr(ord(ch) - code % 28)


SAME_PLACE = {'t': ('t',), 'p': ('p',), 'k': ('k',)}   # เจตนา 쩨따나 (พุทธ 풋타 는 그대로)


_tltk = None


def _stub_gensim():
    """tltk 는 단어 벡터(여기서는 안 씀) 때문에 gensim 을 부르기만 한다. 없으면 빈 대역을 넣는다."""
    try:
        import gensim  # noqa: F401
        return
    except ImportError:
        pass
    import types
    g, gm, gd = (types.ModuleType(n) for n in ('gensim', 'gensim.models', 'gensim.models.doc2vec'))
    gm.Word2Vec = gm.KeyedVectors = type('Stub', (), {})
    gd.Doc2Vec = gd.TaggedDocument = type('Stub', (), {})
    g.models, gm.doc2vec = gm, gd
    sys.modules.update({'gensim': g, 'gensim.models': gm, 'gensim.models.doc2vec': gd})


_NORM_IPA = [('O', 'ᴐ'), ('x', 'ɛ'), ('@', 'ɤ'), ('N', 'ŋ'), ('?', 'ʔ'), ('U', 'ɯ'),
             ('|', ' '), ('~', '.'), ('^', '.'), ("'", '.'), ('4', '5'), ('3', '4'), ('2', '3'), ('1', '2'), ('0', '1')]


def _g2p(word):
    """tltk.nlp.th2ipa 와 같은 바꿈을 하되, 조각이 여럿인 결과도 받는다."""
    global _tltk
    if _tltk is None:
        _stub_gensim()
        import tltk
        _tltk = tltk
    raw = _tltk.nlp.g2p(word)
    out = []
    for seg in raw.split('<s/>'):
        parts = seg.split('<tr/>')
        if len(parts) < 2 or not parts[1].strip():
            continue
        tran = parts[1]
        tran = re.sub(r"([aeiouUxO@])\1", r"\1ː", tran)
        tran = re.sub(r"([ptkc])h", r"\1ʰ", tran)
        for k, v in _NORM_IPA:
            tran = tran.replace(k, v)
        out.append(tran.strip())
    return out


def ipa_hangul(ipa, word=''):
    """'kʰwaːm1.pʰiːan1' → '쾀피안'. 못 바꾸는 음절이 있으면 None."""
    if not ipa.strip() or ipa.strip().endswith('.') or '..' in ipa:
        return None
    syls = []
    for chunk in ipa.split():
        for x in chunk.split('.'):
            if not x:
                return None
            pr = syl_parts(x)
            if pr is None:
                return None
            syls.append(pr)
    # 짧은 เ-า(เจ้า·เรา·เขา) 는 '오', -าว(ราว·ยาว) 는 '우' (LT2401 독음과 같게)
    n_short = len(re.findall('เ[\u0e01-\u0e2e]{1,2}[\u0e48-\u0e4b]?า(?!ว)', word))
    n_long = len(re.findall('[\u0e32]ว', word))
    out_syl = []
    k_aw = 0
    for pr in syls:
        ao = '우'
        if pr[2].replace('ː', '') == 'a' and pr[3] == 'w':
            if n_short and not n_long:
                ao = '오'
            elif n_short and n_long:
                ao = '오' if k_aw < n_short else '우'
            k_aw += 1
        out_syl.append(syl_hangul(pr, ao))
    # 잇기: ล 앞 열린 음절은 받침 ㄹ(เวลา 웰라 · ทะเล 탈레), 같은 자리 받침+첫소리는 받침을 뺌(เจตนา 쩨따나)
    for i in range(1, len(syls)):
        on, cl, _, _ = syls[i]
        prev = syls[i - 1]
        if on == 'l' and not cl and prev[3] in ('', 'ʔ') and not out_syl[i - 1][-1] in ('이', '우', '오'):
            out_syl[i - 1][-1] = _add_jong(out_syl[i - 1][-1], 'ㄹ')
        if prev[3] in SAME_PLACE and on in SAME_PLACE[prev[3]]:
            out_syl[i - 1][-1] = _drop_jong(out_syl[i - 1][-1])
    return ''.join(''.join(x) for x in out_syl)


DIG = {'0': '쑨', '1': '능', '2': '성', '3': '삼', '4': '시', '5': '하', '6': '혹', '7': '쩻', '8': '뺏', '9': '까오'}


def number_hangul(num):
    """태국어로 읽은 수 (0~9999)."""
    n = int(num)
    if n == 0:
        return '쑨'
    out = ''
    for val, name in ((1000, '판'), (100, '러이')):
        q, n = divmod(n, val)
        if q:
            out += DIG[str(q)] + name
    q, r = divmod(n, 10)
    if q:
        out += ('' if q == 1 else '이' if q == 2 else DIG[str(q)]) + '십'
    if r:
        out += '엣' if (r == 1 and (q or len(out) > 0)) else DIG[str(r)]
    return out


OVERRIDE = {'กิเลส': '끼렛'}   # 법문의 열쇠말은 익은 꼴로


def hangul(word, dic=None):
    """(독음, 출처) 출처 = 'fix' | 'dict' | 'num' | 'rule' | '' (못 만듦)."""
    if word in OVERRIDE:
        return OVERRIDE[word], 'fix'
    if dic and word in dic:
        return dic[word], 'dict'
    w = word.translate(str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789'))
    if re.fullmatch(r'\d{1,4}', w):
        return number_hangul(w), 'num'
    if not re.search('[\u0e01-\u0e2e]', word):
        return '', ''
    try:
        segs = _g2p(word)
    except Exception:
        return '', ''
    if not segs:
        return '', ''
    h = ipa_hangul(' '.join(segs), word)
    return (h, 'rule') if h else ('', '')
