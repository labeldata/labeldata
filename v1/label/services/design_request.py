"""
표시 디자인 의뢰서.

표시사항을 다 만들고 나면 디자인 담당자에게 넘긴다. 지금 현장에서는 엑셀·
워드로 이런 문서를 손으로 짜서 보낸다 — 받은 것을 그대로 옮기면 이렇다.

    표시장소        표시사항        표시사항 내용            비고
    ──────────────────────────────────────────────────────────
    주표시면        제품명          알찬밤만쥬
    (제품명·내용량   내용량(총열량)  750 g(2,243 kcal)
     10p 이상,      특정성분        사양벌꿀 0.89 %, …
     특정성분 14p)
    ──────────────────────────────────────────────────────────
    정보표시면      식품유형        과자
    (10p 이상,      제조원          ㈜호남샤니 / 광주광역시 …   무광매트 날인
     자간 -5% 이상, 소비기한        별도표기일까지              확인 바랍니다
     장평 90% 이상) 원재료명        조림류/중국산(백앙금, …)
                                   [우유, 대두, 밀 함유]
                    …
                    * 알류(달걀), 메밀, … 혼입가능 있음
                    * 개봉된 제품은 밀봉 보관하시고 …

우리 미리보기가 내보내던 것은 **정보표시면 표 한 장**이었다. 의뢰서와 세 가지가
다르다.

  1. 표시장소(주표시면·정보표시면) 구분이 없다
  2. 규정 메모(10p 이상·자간·장평)가 없다 — 디자이너가 지켜야 하는 것이다
  3. 비고 열이 없다 — "무광매트 날인 확인" 같은 지시가 들어가는 자리다

세 가지를 채운다. 규정 숫자는 constants.LABEL_REGULATIONS 에서 오고, 사용자가
고친 것은 계정에 남는다 — 회사마다 사내 기준이 조금씩 다르기 때문이다.
"""
from v1.label.constants import LABEL_REGULATIONS

# 주표시면에 들어가는 항목. 나머지는 정보표시면이다.
#
# 앞면에 인쇄되는 것은 셋뿐이다 — 제품명, 내용량(과 그 열량), 그리고 제품명에
# 쓴 원재료의 함량(특정성분). 표시사항 표에도 제품명 줄이 있지만 그건 같은 말을
# 두 번 적은 것이라 의뢰서에서는 앞면 쪽에만 둔다.
#
# **목록은 display_panel 이 갖고 있다.** "어느 면에" 를 말하는 곳이 하나여야
# 한다 — 포장 형태별 표시면 정의도 거기 있다.
from v1.label.services.display_panel import MAIN_PANEL_FIELDS      # noqa: F401


def _font(kind, small_area):
    rule = LABEL_REGULATIONS['font_size'][kind]
    return rule['small_area_min'] if small_area else rule['min']


def default_notes(small_area=True, package_form=None):
    """
    표시장소마다 디자이너가 지켜야 하는 것.

    **소면적(정보표시면 100 cm² 미만) 완화값을 기본으로 쓴다.** 받은 의뢰서가
    그 기준이었고, 이 앱으로 만드는 라벨도 대개 그 크기다. 큰 포장이면 화면에서
    고치면 되고, 고친 값은 계정에 남는다.

    `package_form` 을 주면 **어느 면이 주표시면인지**를 맨 앞에 적는다. 그게
    빠져 있으면 디자이너는 "앞면" 을 짐작으로 정한다 — 상자 포장은 앞면·윗면·
    뒷면이 다 주표시면인데 뒷면에 표시사항을 몰아 놓는 식이다.

    Returns: {'main': [줄 …], 'info': [줄 …]}
    """
    from v1.label.services import display_panel

    spacing = LABEL_REGULATIONS['spacing']
    form = display_panel.PACKAGE_FORMS.get(package_form or '')
    return {
        'main': ([('표시 위치: %s' % form['main'])] if form else []) + [
            '제품명·내용량: %dp 이상' % _font('product_name', small_area),
            # 특정성분(제품명에 쓴 원재료의 함량)은 소면적이어도 줄지 않는다.
            # 받은 의뢰서도 14p 로 적혀 있었다.
            '특정성분: %dp 이상' % _font('origin', False),
        ],
        'info': ([('표시 위치: %s' % form['info'])] if form else []) + [
            '%dp 이상' % _font('general', small_area),
            '자간: %d%% 이상' % spacing['letter']['default'],
            '장평: %d%% 이상' % spacing['word']['min'],
        ],
    }


def notes_for(user, small_area=True, package_form=None, label=None):
    """
    이 사용자가 쓰는 규정 메모. 고쳐 둔 것이 없으면 기본값.

    `label` 을 주면 그 제품의 포장 형태를 쓴다 — 표시 위치는 사람이 정하는
    사내 기준이 아니라 **그 제품의 사실**이라 계정에 저장하지 않는다.
    """
    if label is not None and not package_form:
        package_form = (getattr(label, 'package_form', '') or '').strip() or None
    base = default_notes(small_area, package_form)
    try:
        prefs = (getattr(user, 'profile', None).list_prefs or {})
        saved = (prefs.get('design_request') or {}).get('notes')
    except Exception:
        saved = None
    if not isinstance(saved, dict):
        return base
    out = {}
    for panel in ('main', 'info'):
        lines = saved.get(panel)
        out[panel] = ([str(line)[:80] for line in lines[:8]]
                      if isinstance(lines, list) and lines else base[panel])
    return out


def save_notes(user, notes):
    """
    고친 규정 메모를 계정에 남긴다. **브라우저가 아니라 계정이다** — 사내
    기준은 그 사람이 일하는 방식이라 자리를 옮긴다고 달라지지 않는다.

    Returns: 남긴 값. 프로필이 없으면 None.
    """
    profile = getattr(user, 'profile', None)
    if profile is None:
        return None
    clean = {}
    for panel in ('main', 'info'):
        lines = (notes or {}).get(panel)
        if isinstance(lines, list):
            clean[panel] = [str(line)[:80] for line in lines[:8] if str(line).strip()]
    if not clean:
        return None
    prefs = dict(profile.list_prefs or {})
    prefs['design_request'] = dict(prefs.get('design_request') or {}, notes=clean)
    profile.list_prefs = prefs
    profile.save(update_fields=['list_prefs'])
    return clean
