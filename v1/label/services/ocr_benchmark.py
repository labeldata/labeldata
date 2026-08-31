"""
판독 결과를 정답과 대조해 점수를 낸다.

화면에서 사람이 열 번 눌러 재는 것은 느리고, 무엇보다 사람마다 다르게 고친다.
정답을 한 번 적어 두면 몇 번이든 같은 잣대로 잴 수 있다.

**같은 사진도 매번 다르게 읽힌다.** 한 번 돌린 결과로 "이 방식이 낫다" 를
정하면 안 된다. 여러 번 돌려 평균과 편차를 함께 본다.

채점은 완전일치가 아니라 유사도로 한다. 원재료명 300자를 한 글자도 안 틀리게
읽는 일은 없고, "쉬레드치즈" 를 "쉐르드치즈" 로 읽은 것과 통째로 지어낸 것은
전혀 다른 실패다. 그 둘을 같이 0점 처리하면 개선이 보이지 않는다.
"""
import json
import logging
import re
import statistics
import unicodedata
from pathlib import Path

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# 유사도 등급. 100 이 완전일치.
#
# 짧은 값은 두 글자만 틀려도 크게 깎인다. "쉬레드치즈, 양배추, 양상추" 를
# "쉐르드치즈, ..." 로 읽으면 83점이다 - 한 글자씩 어긋났을 뿐 알아볼 수 있는데,
# 기준이 높으면 통째로 지어낸 것(20점 안팎)과 같은 칸에 들어간다. 그 둘을
# 가르는 것이 이 등급의 목적이므로 여유를 둔다.
GRADE_EXACT = 98      # 사실상 같다 (띄어쓰기·기호 차이)
GRADE_CLOSE = 75      # 알아볼 수 있게 읽었다 (경미한 오독)

_WS = re.compile(r'\s+')


def normalize(text):
    """비교 전에 표기 흔들림을 줄인다. 뜻이 바뀌는 것은 건드리지 않는다."""
    s = _WS.sub(' ', str(text or '')).strip()
    # 전각/반각 괄호, 대시 정도만 맞춘다
    for a, b in (('（', '('), ('）', ')'), ('［', '['), ('］', ']'),
                 ('，', ','), ('～', '~'), ('－', '-')):
        s = s.replace(a, b)
    return s


def squeeze(text):
    """
    비교할 때만 쓰는 형태. 공백을 없애고 **호환 문자를 펼친다.**

    "냉장(0~10 ℃)에서 보관" 과 "냉장(0~10℃)에서 보관" 은 같은 값이다. 공백을
    남겨 두면 띄어쓰기 하나에 2점씩 깎여, 제대로 읽은 것이 "다름" 으로 잡힌다.

    ℃(한 글자)와 °C(두 글자)도 같은 값이다. 라벨은 둘을 섞어 쓰고 모델도 섞어
    낸다. NFKC 로 펼치면 ℃ -> °C, ㎖ -> ml, ㎏ -> kg 로 한쪽에 모인다 —
    실제로 "냉동(-18 °C 이하)" 를 "냉동(-18 ℃ 이하)" 로 옳게 읽고도 89.7점으로
    깎였다. 뜻이 같은 표기 차이에 점수를 깎으면 진짜 오독이 묻힌다.

    표시할 때는 normalize() 한 읽기 좋은 형태를 쓴다 — 사람에게는 사진에 적힌
    글자 그대로를 보여 줘야 한다.
    """
    return _WS.sub('', unicodedata.normalize('NFKC', normalize(text)))


def score_one(expected, actual):
    """
    한 항목의 점수(0~100)와 등급.

    정답이 비어 있으면 채점하지 않는다(None) - 그 라벨에 없는 항목이다.
    """
    exp = squeeze(expected)
    if not exp:
        return None, 'skip'
    act = squeeze(actual)
    if not act:
        return 0.0, 'miss'          # 정답이 있는데 못 읽었다
    ratio = fuzz.ratio(exp, act)
    if ratio >= GRADE_EXACT:
        return ratio, 'exact'
    if ratio >= GRADE_CLOSE:
        return ratio, 'close'
    return ratio, 'wrong'


def flatten(ocr_data):
    """{키: {'value':…}} 를 {키: 값} 으로."""
    out = {}
    for key, item in (ocr_data or {}).items():
        if isinstance(item, dict):
            out[key] = item.get('value') or ''
        else:
            out[key] = item or ''
    return out


def compare(expected, ocr_data):
    """
    정답과 판독 결과를 항목별로 채점한다.

    Returns: {'fields': {키: {score, grade, expected, actual}}, 'mean': …}
    """
    actual = flatten(ocr_data)
    fields = {}
    scores = []
    for key, exp in (expected or {}).items():
        score, grade = score_one(exp, actual.get(key))
        if grade == 'skip':
            continue
        fields[key] = {
            'score': round(score, 1),
            'grade': grade,
            'expected': normalize(exp),
            'actual': normalize(actual.get(key)),
        }
        scores.append(score)
    return {
        'fields': fields,
        'mean': round(statistics.mean(scores), 1) if scores else 0.0,
        'counted': len(scores),
    }


def crop_image(path, box):
    """
    정답 파일에 적힌 영역만 잘라 낸다. box 는 [x, y, w, h] (원본 픽셀).

    화면의 자르기 기능과 같은 일을 코드로 한다 - 방식 비교를 사람 손 없이
    돌리기 위해서다.
    """
    import io as _io

    from PIL import Image

    img = Image.open(path)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    x, y, w, h = [int(v) for v in box]
    img = img.crop((x, y, x + w, y + h))
    buf = _io.BytesIO()
    img.save(buf, format='JPEG', quality=95)
    buf.seek(0)
    return buf


def load_cases(directory):
    """
    사진과 정답 파일의 짝을 모은다.

        labels/
          더블치즈샐러드.jpg
          더블치즈샐러드.json      <- 정답

    정답 파일에는 항목별 정답을 적는다. 없는 항목은 빼거나 빈 값으로 둔다.
    "crop": [x, y, w, h] 를 넣으면 그 영역만 잘라 읽는 방식도 함께 잰다.
    """
    root = Path(directory)
    if not root.is_dir():
        raise FileNotFoundError(f'폴더가 없다: {root}')

    cases = []
    for answer in sorted(root.glob('*.json')):
        image = None
        for ext in ('.jpg', '.jpeg', '.png', '.webp', '.JPG', '.PNG'):
            candidate = answer.with_suffix(ext)
            if candidate.is_file():
                image = candidate
                break
        if image is None:
            logger.warning('정답은 있는데 사진이 없다: %s', answer.name)
            continue
        try:
            data = json.loads(answer.read_text(encoding='utf-8'))
        except Exception as exc:
            logger.error('정답 파일을 읽지 못했다 (%s): %s', answer.name, exc)
            continue
        crop = data.pop('crop', None)
        cases.append({'name': answer.stem, 'image': image,
                      'expected': data, 'crop': crop})
    return cases


def summarize(runs):
    """
    여러 번 돌린 결과를 항목별로 모은다.

    평균만 보면 안 된다 - 같은 사진에서 90점과 20점이 번갈아 나오는 항목과
    늘 55점인 항목은 전혀 다른 문제다. 편차를 함께 낸다.
    """
    per_field = {}
    for run in runs:
        for key, row in run['fields'].items():
            per_field.setdefault(key, []).append(row['score'])

    out = []
    for key, scores in per_field.items():
        out.append({
            'field': key,
            'runs': len(scores),
            'mean': round(statistics.mean(scores), 1),
            'worst': round(min(scores), 1),
            'best': round(max(scores), 1),
            'spread': round(max(scores) - min(scores), 1),
        })
    return sorted(out, key=lambda r: r['mean'])
