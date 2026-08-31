"""
주의사항·기타표시사항에 **자주 쓰는 문구** 목록. 한 곳에서만 관리한다.

이 목록은 원래 화면(`_tab_basic_info.html`)의 빠른 입력 버튼에만 박혀 있었다.
그런데 같은 문구가 판독에서도 필요하다 — 주의사항과 기타표시사항은 대부분
여기 있는 문구로 만들어져 있어서, 모델이 "이 문장이 무엇인지" 를 알면 두 가지를
얻는다.

  1. 글자를 확정한다   흐리게 찍혀도 "아, 이건 그 문장이다" 로 끝까지 읽는다
  2. 칸을 가른다       1399 는 주의사항, HACCP 인증은 기타표시사항이다

목록을 두 벌로 두면 어느 날 한쪽만 고쳐진다. 화면 버튼도 프롬프트도 여기서
가져간다.

**목록에 있다는 이유로 채우면 안 된다.** 판독에서 이 목록은 *읽은 글자를
확정하는 데만* 쓴다. 사진에 없는 문구를 가져와 적으면 그것이 곧 지어낸 값이고,
이 결과는 법적 표시물에 그대로 들어간다.
"""
import logging
import re

logger = logging.getLogger(__name__)

# 문구 하나: chip(버튼에 쓰는 짧은 이름) · text(실제로 들어가는 문장) ·
# title(버튼 툴팁) · icon · tone(부트스트랩 outline 색)
#
# 순서가 곧 화면 버튼 순서다.
PHRASES = {
    'cautions': [
        ('1399', '부정·불량식품 신고는 국번없이 1399',
         '부정불량식품 신고 (법정 의무)', 'fas fa-phone-alt', 'danger'),
        ('페닐알라닌', '이 제품에는 페닐알라닌이 함유되어 있습니다. (페닐케톤뇨증 환자 주의)',
         '아스파탐 법정 필수 표시', 'fas fa-exclamation-circle', 'danger'),
        ('개봉후보관', '개봉 후에는 변질될 우려가 있으니 반드시 밀봉하여 냉장 보관하시고, 가급적 빨리 섭취하시기 바랍니다.',
         '개봉 후 보관 및 취급', 'fas fa-box-open', 'secondary'),
        ('직사광선', '직사광선을 피하고 서늘한 곳에 보관하시기 바랍니다.',
         '보관 조건', 'fas fa-sun', 'secondary'),
        ('재냉동금지', '냉동 제품은 해동 후 재냉동하지 마시기 바랍니다.',
         '재냉동 금지', 'fas fa-snowflake', 'secondary'),
        ('용기파손', '용기가 파손되거나 부풀어 있는 경우 섭취하지 마시기 바랍니다.',
         '용기 파손 주의', 'fas fa-box', 'secondary'),
        ('어린이', '어린이가 먹을 경우 보호자의 지도가 필요합니다.',
         '어린이 주의', 'fas fa-child', 'secondary'),
        ('질식', '질식의 위험이 있으니 주의하시기 바랍니다.',
         '질식 주의', 'fas fa-lungs', 'secondary'),
        ('화상', '뜨거우니 화상에 주의하시기 바랍니다.',
         '화상 주의', 'fas fa-fire', 'secondary'),
        ('튐주의', '제품 개봉 시 내용물이 튈 수 있으니 주의하시기 바랍니다.',
         '개봉 주의', 'fas fa-exclamation', 'secondary'),
        ('의약품복용자', '특정 질환이 있거나 의약품 복용 중이신 분은 섭취 전 의사 및 전문가와 상담하시기 바랍니다. 본 제품은 질병의 예방 및 치료를 위한 의약품이 아닙니다.',
         '건강기능식품 일반 주의', 'fas fa-user-md', 'info'),
        ('임산부/어린이', '임산부 및 수유부, 어린이(또는 특정 연령층)는 섭취에 주의해야 합니다.',
         '특정 대상 주의', 'fas fa-baby', 'info'),
        ('이상사례', '본 제품 섭취 시 이상 사례 발생 또는 불편함을 느끼는 경우, 섭취를 중단하고 소비자 상담실 또는 1577-2488(이상사례 신고 핫라인)로 신고하여 주십시오.',
         '이상사례 신고', 'fas fa-phone-volume', 'info'),
    ],
    'additional_info': [
        ('상담센터', '제품에 대한 문의 사항 및 상담은 종합상담센터 1577-1255 (유료)로 연락 주시기 바랍니다.',
         '소비자 상담실', 'fas fa-headset', 'primary'),
        ('품질보증', '본 제품은 공정거래위원회 고시 소비자분쟁해결기준에 의거, 교환 또는 보상받을 수 있습니다.',
         '품질보증', 'fas fa-certificate', 'primary'),
        ('HACCP', 'HACCP 인증 제품', 'HACCP 인증', 'fas fa-check-circle', 'success'),
        ('ISO22000', 'ISO 22000 인증', 'ISO 22000', 'fas fa-award', 'success'),
        ('유기농', '유기농 인증 제품', '유기농 인증', 'fas fa-leaf', 'success'),
        ('KS', 'KS 인증 제품', 'KS 인증', 'fas fa-stamp', 'success'),
        ('전통식품', '전통식품 품질인증', '전통식품', 'fas fa-landmark', 'success'),
        ('GMP', '우수식품인증(GMP)', 'GMP', 'fas fa-star', 'success'),
        ('저탄소', '저탄소 인증 제품', '저탄소 인증', 'fas fa-seedling', 'success'),
        ('무글루텐', '무 글루텐 (Gluten Free)', '글루텐 프리', 'fas fa-ban', 'info'),
        ('비건', '비건 인증 (Vegan)', '비건 인증', 'fas fa-leaf', 'info'),
        ('할랄', '할랄(Halal) 인증 제품', '할랄 인증', 'fas fa-moon', 'info'),
        ('무첨가', '무(無) MSG, 무(無) 합성보존료, 무(無) 합성착색료', '무첨가', 'fas fa-ban', 'secondary'),
        ('Non-GMO', 'Non-GMO 제품', 'Non-GMO', 'fas fa-dna', 'secondary'),
        ('저나트륨', '저나트륨 제품', '저나트륨', 'fas fa-heart', 'secondary'),
    ],
}

FIELD_LABELS = {'cautions': '주의사항', 'additional_info': '기타표시사항'}

# 읽은 문장을 상용 문구로 확정할 점수.
#
# 낮추면 안 된다. 여기서 하는 일은 "비슷하니 이 문장이었을 것" 이라며 글자를
# 바꿔치우는 것이라, 실제로 다른 문장을 상용 문구로 덮으면 라벨에 없는 말이
# 인쇄된다. 88 은 60자짜리 문장에서 예닐곱 자가 다른 정도다.
SNAP_MIN_SCORE = 88

_WS = re.compile(r'\s+')
_DIGITS = re.compile(r'\d+')
# 문장 단위로 다시 시도할 때 쓰는 경계. 한국어 표시문구는 "…습니다." 로 끝난다.
_SENTENCE = re.compile(r'(?<=\.)\s+')


def phrases_for(field):
    """화면 버튼이 쓰는 형태. dict 로 돌려 템플릿에서 점 표기로 꺼내 쓴다."""
    return [
        {'chip': chip, 'text': text, 'title': title, 'icon': icon, 'tone': tone}
        for chip, text, title, icon, tone in PHRASES.get(field, ())
    ]


def texts_for(field):
    return [row[1] for row in PHRASES.get(field, ())]


def _squeeze(text):
    return _WS.sub('', str(text or ''))


def _ratio(a, b):
    try:
        from rapidfuzz import fuzz
    except ImportError:      # 상용 문구 대조만 못 할 뿐, 판독은 계속돼야 한다
        return 100 if a == b else 0
    return int(fuzz.ratio(a, b))


def best_match(field, sentence):
    """
    문장 하나를 상용 문구에 맞춰 본다. 못 맞추면 (None, 점수).

    **숫자는 반드시 그대로여야 한다.** 상담 번호는 회사마다 다르다 —
    "1577-1234" 를 목록의 "1577-1255" 로 맞추면 남의 회사 번호를 인쇄한다.
    글자만 보면 두 문장은 98점이라 그냥 통과한다.
    """
    text = _squeeze(sentence)
    if not text:
        return None, 0

    best, best_score = None, 0
    for candidate in texts_for(field):
        score = _ratio(text, _squeeze(candidate))
        if score > best_score:
            best, best_score = candidate, score

    if best is None or best_score < SNAP_MIN_SCORE:
        return None, best_score
    if _DIGITS.findall(sentence) != _DIGITS.findall(best):
        return None, best_score
    return best, best_score


def snap_text(field, value):
    """
    주의사항·기타표시사항 한 칸을 상용 문구에 맞춘다.

    줄 단위로 먼저 보고, 안 맞으면 그 줄을 문장으로 갈라 다시 본다. 한 줄에
    여러 문장을 이어 적은 라벨이 흔한데, 줄 전체로만 견주면 한 문장이 달라도
    점수가 무너져 아무것도 못 맞춘다.

    Returns: (새 값, [{'from','to','score'} …])
    """
    original = str(value or '')
    if not original.strip() or field not in PHRASES:
        return original, []

    changes = []

    def fix(sentence):
        stripped = sentence.strip()
        if not stripped:
            return sentence
        matched, score = best_match(field, stripped)
        if not matched or matched == stripped:
            return sentence
        changes.append({'from': stripped, 'to': matched, 'score': score})
        return matched

    out_lines = []
    for line in original.splitlines():
        fixed = fix(line)
        if fixed != line:
            out_lines.append(fixed)
            continue
        parts = _SENTENCE.split(line)
        if len(parts) > 1:
            fixed_parts = [fix(part) for part in parts]
            out_lines.append(' '.join(p.strip() for p in fixed_parts if p.strip()))
        else:
            out_lines.append(line)

    if not changes:
        return original, []
    return '\n'.join(out_lines), changes


def prompt_block():
    """
    판독 프롬프트에 실을 목록.

    문장을 통째로 싣는다. 짧은 이름만 실으면 모델이 "그 문장" 을 알 수 없어
    글자를 확정하는 데 쓸 수 없다.
    """
    lines = [
        '주의사항(cautions)·기타표시사항(additional_info) 에 흔히 쓰이는 문구다.',
        '사진에서 읽은 문장이 아래 것과 거의 같으면 **아래 문장 그대로** 옮기고,',
        '어느 칸에 넣을지도 아래 구분을 따르시오 (1399 는 주의사항, 인증 표시는 기타표시사항).',
        '**사진에 없는 문구를 이 목록에서 가져와 채우지 마시오.** 이 목록은 읽은 글자를',
        '확정하는 데만 쓴다 — 목록에 있다는 이유로 적으면 그것이 곧 지어낸 값이다.',
        '전화번호와 숫자는 사진에 적힌 것을 그대로 두시오. 상담 번호는 회사마다 다르다.',
    ]
    for field in ('cautions', 'additional_info'):
        lines.append('')
        lines.append('  [%s]' % FIELD_LABELS[field])
        for text in texts_for(field):
            lines.append('    · %s' % text)
    return '\n'.join(lines)
