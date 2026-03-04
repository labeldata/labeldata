"""
매칭 엔진 (matcher.py)
AI 추출 키워드를 사용자 BOM/원료에서 RapidFuzz 퍼지 매칭 후
카테고리별 등급판정으로 관련도를 산출합니다.

[카테고리별 등급판정 기준]
  농산물  (I2640)      : 원료명 + 원산지 일치 → HIGH / 원료명만 → LOW
  국내가공 (I2620/I0490): 제조사+제품명 일치 → HIGH / 식품유형+(제조사 or 원산지) → MED / 원료명만 → LOW
  수입    (import/imp_insp): 원산지·식품유형·제조사 중 2개+ → HIGH / 1개 → MED / 원료명만 → LOW
  행정처분 (I0470/I0480/I0482): 업체명이 내 제품/원료의 제조사와 일치하면 알림(MED)

오탐지 제어:
  MIN_KEYWORD_LEN(≥2글자) + 단어 경계 검사
  원산지 확실 불일치 시 SAFE(매칭 제외)
"""
import logging
import re

from django.contrib.auth.models import User
from rapidfuzz import fuzz

from v1.regulatory.models import NewsIngredientMatch, NewsProductMatch, RegulatoryNews

logger = logging.getLogger(__name__)

# 매칭 임계값 (0~100). 이 값 이상이면 연관 원료로 판단.
MATCH_THRESHOLD: int = 72

# 키워드 최소 글자 수 (이보다 짧으면 완전 매칭일 때만 허용)
# 한국어 1글자 단일 키워드는 '소', '파', '낙', '구' 등 너무 다의적으로 오탐지 유발
MIN_KEYWORD_LEN: int = 2

# 단어 구분자: 이 문자로 단어를 분리하여 단어 경계 검사
_WORD_SPLIT_RE = re.compile(r'[\s&/,\(\)\.\[\]\{\}\-\u300c\u300d\u3010\u3011\xb7]+')


def find_affected_products(news: RegulatoryNews, user: User) -> list[dict]:
    """
    뉴스의 ai_issues (또는 ai_keywords 폴백)를 해당 사용자의 BOM + 원료 보관함에서 퍼지 매칭.

    ai_issues가 있으면 관련도 카운트 기반 위해도 스코어링 적용.
    (제조사·원산지·제품명·식품유형 일치 개수로 HIGH/MED/LOW 판정)

    Returns:
        list of {
            'product':             MyLabel instance,
            'matched_bom':         ProductBOM instance | None,
            'matched_keyword':     str,
            'matched_ingredient':  str,
            'score':               float,      # 텍스트 유사도 점수
            'risk_score':          int,        # 관련도 종합 점수
            'risk_level':          str,        # HIGH / MED / LOW
            'risk_reasons':        list[str],  # 매칭 근거
        }
    """
    from v1.bom.models import ProductBOM
    from v1.label.models import MyIngredient

    vtype      = getattr(news, 'violation_type', '') or ''
    api_source = (news.api_source or '').strip()
    news_pname = (news.product_name or '').strip()
    is_admin   = api_source in ('I0470', 'I0480', 'I0482') or vtype == 'admin'

    # ── 행정처분 분기: 업체명↔내 제조사 매칭 ──────────────────────────────
    if is_admin:
        return _find_admin_matches(news, user, api_source)

    # 표시위반은 원료 매칭 불필요
    if vtype == 'labeling':
        return []

    # ai_issues 우선, 없으면 ai_keywords → 단순 issue dict 생성
    base_issues = news.ai_issues if news.ai_issues else [
        {'ingredient': kw, 'origin': None, 'manufacturer': None, 'food_type': None}
        for kw in (news.ai_keywords or [])
    ]
    if not base_issues:
        return []

    # 뉴스 제품명 + api_source 추가 (카테고리별 판정용)
    issues = [{**iss, '_news_product_name': news_pname, '_api_source': api_source}
              for iss in base_issues]

    # product_id → 최고 위해도 매칭 정보 (중복 제거)
    best: dict[int, dict] = {}

    def _update_best(product, bom, keyword, ingredient, score, risk_dict):
        pid = product.my_label_id
        # 위해도 점수(risk_score) 기준 최고값 유지
        cur_risk = best.get(pid, {}).get('risk_score', -1)
        if pid not in best or risk_dict['score'] > cur_risk:
            best[pid] = {
                'product':            product,
                'matched_bom':        bom,
                'matched_keyword':    keyword,
                'matched_ingredient': ingredient,
                'score':              score,
                'risk_score':         risk_dict['score'],
                'risk_level':         risk_dict['level'],
                'risk_reasons':       risk_dict['reasons'],
            }

    # ① BOM 원료명 매칭
    user_boms = (
        ProductBOM.objects
        .filter(parent_label__user_id=user, parent_label__delete_YN='N')
        .select_related('parent_label')
        .only('bom_id', 'ingredient_name', 'origin', 'manufacturer', 'food_type',
              'parent_label_id', 'parent_label__my_label_id',
              'parent_label__my_label_name', 'parent_label__user_id',
              'parent_label__delete_YN')
    )

    for bom in user_boms:
        if not bom.ingredient_name:
            continue
        for issue in issues:
            keyword = issue['ingredient']
            score = _fuzzy_score(keyword, bom.ingredient_name)
            if score >= MATCH_THRESHOLD:
                risk_dict = calculate_risk_score(bom, issue)
                if risk_dict['level'] == 'SAFE':
                    continue  # 원산지가 확실히 다르면 무시
                _update_best(bom.parent_label, bom, keyword, bom.ingredient_name, score, risk_dict)

    # ② 원료 보관함(MyIngredient) 매칭 → 해당 원료를 쓰는 완제품 추적
    user_ingredients = (
        MyIngredient.objects
        .filter(user_id=user, delete_YN='N')
        .prefetch_related('bom_usages__parent_label')
    )

    for ing in user_ingredients:
        ing_name = ing.prdlst_nm or ing.ingredient_display_name or ''
        if not ing_name:
            continue
        for issue in issues:
            keyword = issue['ingredient']
            score = _fuzzy_score(keyword, ing_name)
            if score >= MATCH_THRESHOLD:
                for bom in ing.bom_usages.all():
                    product = bom.parent_label
                    if not product or product.delete_YN == 'Y':
                        continue
                    risk_dict = calculate_risk_score(bom, issue)
                    if risk_dict['level'] == 'SAFE':
                        continue
                    _update_best(product, bom, keyword, ing_name, score, risk_dict)

    return list(best.values())


def _find_admin_matches(news: RegulatoryNews, user: User, api_source: str) -> list[dict]:
    """
    행정처분 전용 매칭: 뉴스 업체명이 내 BOM 원료의 제조사 또는
    제품 기본정보(제조원·유통전문판매원·소분원)와 일치하는지 확인.
    일치 시 MED 등급으로 알림. (원료 키워드 매칭 없이 업체명만 비교)
    """
    from v1.bom.models import ProductBOM
    from v1.label.models import MyLabel

    news_company = _normalize_corp(news.company_name or '')
    if not news_company:
        return []

    best: dict[int, dict] = {}

    # ── 1) BOM 원료 제조사 매칭 ────────────────────────────────────
    user_boms = (
        ProductBOM.objects
        .filter(parent_label__user_id=user, parent_label__delete_YN='N')
        .select_related('parent_label')
        .only('bom_id', 'manufacturer', 'ingredient_name',
              'parent_label_id', 'parent_label__my_label_id',
              'parent_label__my_label_name', 'parent_label__user_id',
              'parent_label__delete_YN')
    )

    for bom in user_boms:
        bom_mfr = _normalize_corp(bom.manufacturer or '')
        if not bom_mfr:
            continue
        if news_company in bom_mfr or bom_mfr in news_company:
            mfr_score = fuzz.ratio(news_company, bom_mfr)
            if mfr_score < 70:
                continue
            pid = bom.parent_label.my_label_id
            cur_score = best.get(pid, {}).get('risk_score', -1)
            risk_score = int(mfr_score)
            if pid not in best or risk_score > cur_score:
                best[pid] = {
                    'product':            bom.parent_label,
                    'matched_bom':        bom,
                    'matched_keyword':    news.company_name or '',
                    'matched_ingredient': bom.manufacturer or '',
                    'score':              float(mfr_score),
                    'risk_score':         risk_score,
                    'risk_level':         'MED',
                    'risk_reasons':       [f'처분업체 일치({(news.company_name or "")[:20]})',
                                           f'원료 제조사: {(bom.manufacturer or "")[:20]}',
                                           f'해당원료: {(bom.ingredient_name or "")[:20]}'],
                }

    # ── 2) 제품 기본정보 업체명 매칭 (제조원·유통전문판매원·소분원) ──
    LABEL_COMPANY_FIELDS = [
        ('bssh_nm',              '제조원'),
        ('distributor_address',  '유통전문판매원'),
        ('repacker_address',     '소분원'),
    ]

    user_labels = (
        MyLabel.objects
        .filter(user_id=user, delete_YN='N')
        .only('my_label_id', 'my_label_name', 'user_id', 'delete_YN',
              'bssh_nm', 'distributor_address', 'repacker_address')
    )

    for label in user_labels:
        pid = label.my_label_id
        for field_attr, field_label in LABEL_COMPANY_FIELDS:
            field_val = getattr(label, field_attr, None) or ''
            norm_val = _normalize_corp(field_val)
            if not norm_val:
                continue
            if news_company not in norm_val and norm_val not in news_company:
                continue
            score = fuzz.ratio(news_company, norm_val)
            if score < 70:
                continue
            cur_score = best.get(pid, {}).get('risk_score', -1)
            if pid not in best or int(score) > cur_score:
                best[pid] = {
                    'product':            label,
                    'matched_bom':        None,
                    'matched_keyword':    news.company_name or '',
                    'matched_ingredient': field_val[:200],
                    'score':              float(score),
                    'risk_score':         int(score),
                    'risk_level':         'MED',
                    'risk_reasons':       [f'처분업체 일치({(news.company_name or "")[:20]})',
                                           f'{field_label}: {field_val[:30]}'],
                }

    return list(best.values())


def save_matches(news: RegulatoryNews, matches: list[dict]) -> int:
    """
    매칭 결과를 NewsProductMatch 테이블에 저장.
    이미 존재하는 (news, product) 조합은 위해도 정보를 업데이트.

    Returns: 신규 저장 건수
    """
    saved = 0
    for m in matches:
        risk_level = m.get('risk_level', 'LOW')
        obj, created = NewsProductMatch.objects.get_or_create(
            news=news,
            product=m['product'],
            defaults={
                'matched_bom':        m.get('matched_bom'),
                'matched_keyword':    m['matched_keyword'],
                'matched_ingredient': m['matched_ingredient'],
                'match_score':        m['score'],
                'risk_score':         m.get('risk_score', 0),
                'risk_level':         risk_level,
                'risk_reasons':       m.get('risk_reasons', []),
            },
        )
        if created:
            saved += 1
        else:
            # 이미 존재하면 위해도 정보만 갱신
            update_needed = (
                obj.risk_score != m.get('risk_score', 0) or
                obj.risk_level != risk_level
            )
            if update_needed:
                obj.risk_score   = m.get('risk_score', 0)
                obj.risk_level   = risk_level
                obj.risk_reasons = m.get('risk_reasons', [])
                obj.save(update_fields=['risk_score', 'risk_level', 'risk_reasons'])

        logger.debug(
            f'[매칭] {news.external_id} ↔ {m["product"].my_label_name} '
            f'(키워드={m["matched_keyword"]}, 점수={m["score"]:.1f}, '
            f'위해도={risk_level}/{m.get("risk_score", 0)})'
        )
    return saved


def find_matching_ingredients_unlinked(news: RegulatoryNews, user: User) -> list[dict]:
    """
    어떤 제품 BOM에도 연결되지 않은 원료 보관함(MyIngredient) 항목 중
    뉴스 ai_issues/ai_keywords와 퍼지 매칭되는 원료 정보 목록 반환.

    Returns:
        list of {
            'ingredient':       MyIngredient instance,
            'matched_keyword':  str,
            'score':            float,
            'risk_level':       str (HIGH/MED/LOW),
            'risk_score':       int,
        }
    """
    from v1.label.models import MyIngredient

    api_source = (news.api_source or '').strip()
    vtype = getattr(news, 'violation_type', '') or ''
    is_admin = api_source in ('I0470', 'I0480', 'I0482') or vtype == 'admin'

    # 행정처분 / 표시위반 → 원료 키워드 매칭 불필요
    if is_admin or vtype == 'labeling':
        return []

    base_issues = news.ai_issues if news.ai_issues else [
        {'ingredient': kw, 'origin': None, 'manufacturer': None, 'food_type': None}
        for kw in (news.ai_keywords or [])
    ]
    if not base_issues:
        return []

    # BOM에 연결된 적 없는 원료 보관함 항목만
    unlinked_ings = list(
        MyIngredient.objects
        .filter(user_id=user, delete_YN='N', bom_usages__isnull=True)
        .only('my_ingredient_id', 'prdlst_nm', 'ingredient_display_name',
              'bssh_nm', 'prdlst_dcnm')
    )

    results: list[dict] = []
    seen_ids: set[int] = set()

    for ing in unlinked_ings:
        ing_name = ing.prdlst_nm or ing.ingredient_display_name or ''
        if not ing_name:
            continue
        best_score = 0.0
        best_keyword = ''
        best_risk_level = 'LOW'
        best_risk_score = 0

        for issue in base_issues:
            keyword = issue.get('ingredient', '')
            if not _is_valid_keyword(keyword):
                continue
            score = _fuzzy_score(keyword, ing_name)
            if score < MATCH_THRESHOLD:
                continue

            # 원료 보관함 항목은 BOM 세부정보(origin/manufacturer/food_type)가 없으므로
            # 뉴스의 issue 속성과 원료 자체의 속성만으로 간이 등급 산정
            risk_score = int(score)
            risk_level = 'LOW'
            origin_match = (
                issue.get('origin') and ing.prdlst_dcnm and
                (issue['origin'].strip() in ing.prdlst_dcnm or
                 ing.prdlst_dcnm in issue['origin'])
            )
            mfr_match = (
                issue.get('manufacturer') and ing.bssh_nm and
                fuzz.partial_ratio(
                    _normalize_corp(issue['manufacturer']),
                    _normalize_corp(ing.bssh_nm)
                ) >= 80
            )
            if origin_match and mfr_match:
                risk_level = 'HIGH'
                risk_score = min(100, int(score) + 20)
            elif origin_match or mfr_match:
                risk_level = 'MED'
                risk_score = min(100, int(score) + 10)

            if score > best_score:
                best_score = score
                best_keyword = keyword
                best_risk_level = risk_level
                best_risk_score = risk_score

        if best_score >= MATCH_THRESHOLD and ing.my_ingredient_id not in seen_ids:
            seen_ids.add(ing.my_ingredient_id)
            results.append({
                'ingredient':      ing,
                'matched_keyword': best_keyword,
                'score':           best_score,
                'risk_level':      best_risk_level,
                'risk_score':      best_risk_score,
            })

    return results


def save_ingredient_matches(news: RegulatoryNews, user: User,
                            matches: list[dict]) -> int:
    """
    find_matching_ingredients_unlinked() 결과를 NewsIngredientMatch 테이블에 저장.
    기존 레코드는 위해도만 갱신 (dismissed_yn 유지).
    Returns: 신규 저장 건수
    """
    saved = 0
    for m in matches:
        obj, created = NewsIngredientMatch.objects.get_or_create(
            news=news,
            user=user,
            ingredient=m['ingredient'],
            defaults={
                'matched_keyword': m['matched_keyword'],
                'match_score':     m['score'],
                'risk_level':      m['risk_level'],
                'risk_score':      m['risk_score'],
            },
        )
        if created:
            saved += 1
        else:
            if obj.risk_score != m['risk_score'] or obj.risk_level != m['risk_level']:
                obj.risk_score = m['risk_score']
                obj.risk_level = m['risk_level']
                obj.save(update_fields=['risk_score', 'risk_level', 'updated_at'])
    return saved


def run_matching_for_all_users(news: RegulatoryNews) -> int:
    """
    모든 활성 사용자에 대해 매칭 실행 (제품 매칭 + 원료 보관함 단독 매칭).
    Returns: 전체 신규 매칭 건수
    """
    total = 0
    for user in User.objects.filter(is_active=True):
        # ① 제품 BOM 매칭
        product_matches = find_affected_products(news, user)
        if product_matches:
            total += save_matches(news, product_matches)
        # ② 원료 보관함 단독 매칭
        ing_matches = find_matching_ingredients_unlinked(news, user)
        if ing_matches:
            total += save_ingredient_matches(news, user, ing_matches)
    return total


# ── 퍼지 점수 계산 ────────────────────────────────────────────────────────────

def _is_valid_keyword(keyword: str) -> bool:
    """
    매칭에 사용할 수 있는 키워드인지 확인
    - 공백/특수문자를 제거하여 순수 글자 수 판정
    - 1글자 한국어 단일 키워드는 차단 (예: '파', '소', '낙', '구')
    """
    kw   = keyword.strip()
    pure = re.sub(r'[\s\W]', '', kw)
    return len(pure) >= MIN_KEYWORD_LEN


def _tokenize(text: str) -> list[str]:
    """단어 분리: 구분자 기준으로 토큰화 (빈 토큰 제외)"""
    return [t for t in _WORD_SPLIT_RE.split(text.strip()) if t]


def _has_keyword_as_whole_token(keyword: str, target: str) -> bool:
    """
    키워드가 target의 의미있는 단어 단위로 존재하는지 확인.

    통과 기준 (우선순위 순):
      ① 동일 길이 근사 매칭 (표기 차이 허용)
         - 같은 글자 수 단어에서 1글자 차이 → ratio ≥ 65
         - 예: "마늘쫑(3자)" ≈ "마늘종(3자)" → ratio=67% → True
      ② 다른 길이 완전 매칭
         - 예: "쪽파" ≈ "쪽파" 토큰 → ratio ≥ 80 → True
      ③ 어근 포함 (접두/접미) — 키워드 길이가 토큰의 40% 이상
         - "쪽파"(2)가 "흙쪽파"(3) 접미 → 67% ≥ 40% → True
         - "홍고추"(3)가 "홍고추분말"(5) 접두 → 60% ≥ 40% → True

    차단 기준:
      - "파"(1글자): MIN_KEYWORD_LEN에서 이미 차단
      - "파"(1글자)가 "파스타"에 포함: 길이 비율 1/3=33% < 40% → False
    """
    kw   = keyword.strip().lower()
    toks = [t.lower() for t in _tokenize(target)]

    for tok in toks:
        if not tok:
            continue

        kw_len  = len(kw)
        tok_len = len(tok)

        # ① 동일 길이: 1글자 차이(표기 변이)를 허용하기 위해 임계값 65
        if kw_len == tok_len:
            if fuzz.ratio(kw, tok) >= 65:
                return True

        # ② 다른 길이: 완전 유사 매칭 (임계값 80)
        elif fuzz.ratio(kw, tok) >= 80:
            return True

        # ③ 어근 포함 검사 (접두/접미)
        if tok_len > 0:
            ratio_len = kw_len / tok_len
            if ratio_len >= 0.4:
                # 접두어 (예: "홍고추" in "홍고추분말")
                if tok.startswith(kw):
                    return True
                # 접미어 (예: "쪽파" in "흙쪽파")
                if tok.endswith(kw):
                    return True

    return False


def _fuzzy_score(keyword: str, target: str) -> float:
    """
    RapidFuzz 복합 점수 (오탐지 방지 필터 3단계)

    1단계: 키워드 유효성 — 너무 짧은 키워드 차단 (MIN_KEYWORD_LEN)
    2단계: 단어 경계 검사 — 키워드가 target의 한 토큰 전체와 매칭되어야 통과
    3단계: 통과 시 partial_ratio + token_set_ratio 복합 점수 반환
    """
    if not keyword or not target:
        return 0.0

    # 1단계: 최소 글자 수 검사
    if not _is_valid_keyword(keyword):
        logger.debug(f'[매칭 필터] 키워드 너무 짧음: "{keyword}" → 건너뜀')
        return 0.0

    # 2단계: 단어 경계 검사 ('파' → '파스타' 오탐지 차단)
    if not _has_keyword_as_whole_token(keyword, target):
        logger.debug(f'[매칭 필터] 단어경계 실패: "{keyword}" ∉ tokenized("{target}")')
        return 0.0

    # 3단계: 퍼지 점수 산정
    kw      = keyword.strip().lower()
    tg      = target.strip().lower()
    partial = fuzz.partial_ratio(kw, tg)
    token   = fuzz.token_set_ratio(kw, tg)
    return max(partial, token)


# ── 카테고리별 위해도 판정 ─────────────────────────────────────────────────────

def _get_category(api_source: str) -> str:
    """api_source → 카테고리 ('agri' | 'import' | 'domestic')"""
    if api_source == 'I2640':
        return 'agri'
    if api_source in ('import', 'imp_insp'):
        return 'import'
    return 'domestic'  # I2620, I0490, I0470, I0480, I0482 등


def calculate_risk_score(bom, news_issue: dict) -> dict:
    """
    카테고리별 등급판정 (관련도 기준).

    [농산물 I2640]
      HIGH : 원료명 + 원산지 일치
      MED  : 원료명 + 식품유형 일치
      LOW  : 원료명만 일치
      SAFE : 원산지 확실 불일치

    [국내가공 I2620/I0490]
      HIGH : 제조사 + 제품명 일치  (동일 제조사·동일 제품 → 특급 위험)
      MED  : 식품유형 + (제조사 or 원산지) 일치
      LOW  : 원료명만 일치
      SAFE : 원산지 확실 불일치

    [수입 import/imp_insp]
      HIGH : 원산지·식품유형·제조사 중 2개+ 일치
      MED  : 원산지·식품유형·제조사 중 1개 일치
      LOW  : 원료명만 일치
      SAFE : 원산지 확실 불일치
    """
    api_source = (news_issue.get('_api_source') or '').strip()
    category   = _get_category(api_source)
    reasons    = [f"원료명 일치({news_issue['ingredient']})"]
    origin_conflict = False

    # ── 공통: 원산지 비교 ────────────────────────────────────────────────────
    news_origin = (news_issue.get('origin') or '').strip()
    bom_origin  = (getattr(bom, 'origin', '') or '').strip()
    origin_match = False
    if news_origin and bom_origin:
        n_norm = _normalize_text(news_origin)
        b_norm = _normalize_text(bom_origin)
        if n_norm in b_norm or b_norm in n_norm:
            origin_match = True
            reasons.append(f"원산지 일치({news_origin})")
        elif _origins_conflict(news_origin, bom_origin):
            origin_conflict = True
            reasons.append(f"원산지 불일치({news_origin} ≠ {bom_origin})")

    # ── 공통: 제조사 비교 ────────────────────────────────────────────────────
    news_mfr = (news_issue.get('manufacturer') or '').strip()
    bom_mfr  = (getattr(bom, 'manufacturer', '') or '').strip()
    mfr_match = False
    if news_mfr and bom_mfr:
        n_corp = _normalize_corp(news_mfr)
        b_corp = _normalize_corp(bom_mfr)
        if n_corp and b_corp and (n_corp in b_corp or b_corp in n_corp):
            mfr_match = True
            reasons.append(f"제조업체 일치({news_mfr[:15]})")

    # ── 공통: 제품명 유사도 ──────────────────────────────────────────────────
    news_pname = (news_issue.get('_news_product_name') or '').strip()
    my_pname   = (getattr(bom.parent_label, 'my_label_name', '') or '').strip()
    pname_match = False
    if news_pname and my_pname:
        ps = fuzz.partial_ratio(my_pname.lower(), news_pname.lower())
        if ps >= 75:
            pname_match = True
            reasons.append(f"제품명 유사({ps}%)")

    # ── 공통: 식품유형 비교 ──────────────────────────────────────────────────
    news_ft = (news_issue.get('food_type') or '').strip()
    bom_ft  = (getattr(bom, 'food_type', '') or '').strip()
    ftype_match = False
    if news_ft and bom_ft and (news_ft in bom_ft or bom_ft in news_ft):
        ftype_match = True
        reasons.append(f"식품유형 일치({news_ft})")

    # ── 공통: 원산지 확실 불일치 시 SAFE (모든 카테고리 공통) ─────────────────
    if origin_conflict and not mfr_match and not pname_match and not ftype_match:
        return {'level': 'SAFE', 'score': 0, 'reasons': reasons}

    # ────────────────────────────────────────────────────────────────────────
    # 카테고리별 판정
    # ────────────────────────────────────────────────────────────────────────
    if category == 'agri':
        # 농산물: 원산지 일치 → HIGH / 식품유형 일치 → MED / 없으면 LOW
        if origin_match:
            level = 'HIGH'; score = 20
        elif ftype_match:
            level = 'MED';  score = 10
        else:
            level = 'LOW';  score = 5

    elif category == 'import':
        # 수입: 원산지·식품유형·제조사 중 2개+ → HIGH / 1개 → MED
        match_cnt = sum([origin_match, ftype_match, mfr_match])
        if match_cnt >= 2:
            level = 'HIGH'; score = match_cnt * 10
        elif match_cnt == 1:
            level = 'MED';  score = 10
        else:
            level = 'LOW';  score = 5

    else:
        # 국내가공 (I2620, I0490 등)
        # 제조사 + 제품명 일치 → HIGH (특급)
        if mfr_match and pname_match:
            level = 'HIGH'; score = 30
        # 식품유형 + (제조사 or 원산지) → MED
        elif ftype_match and (mfr_match or origin_match):
            level = 'MED';  score = 15
        # 제조사 단독 or 원산지 단독 → MED
        elif mfr_match or origin_match:
            level = 'MED';  score = 10
        else:
            level = 'LOW';  score = 5

    return {'level': level, 'score': score, 'reasons': reasons}


def _normalize_text(text: str) -> str:
    """공백·특수문자 제거 후 소문자 정규화"""
    return re.sub(r'[\s\-·,]', '', text).lower()


def _normalize_corp(name: str) -> str:
    """법인 유형명 제거 후 정규화 (주식회사 희망상사 → 희망상사)"""
    remove = ['주식회사', '(주)', '㈜', '유한회사', '유한책임회사', 'co.,ltd', 'corp']
    n = name.lower()
    for r in remove:
        n = n.replace(r.lower(), '')
    return re.sub(r'[\s\-·,\(\)]', '', n).strip()


def _origins_conflict(origin_a: str, origin_b: str) -> bool:
    """
    두 원산지가 확실히 다른지 판단.
    '국내산','국산','한국산' 등 매핑 + 국가명 비교.
    """
    domestic = {'국내', '국산', '국내산', '한국', '한국산', '국내생산'}

    def _key(o: str) -> str:
        n = _normalize_text(o)
        if any(d in n for d in domestic):
            return 'korea'
        return n

    key_a = _key(origin_a)
    key_b = _key(origin_b)
    # 둘 다 도출된 경우에만 비교
    if key_a and key_b and key_a != key_b:
        return True
    return False
