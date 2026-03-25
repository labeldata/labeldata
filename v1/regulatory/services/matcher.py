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

# ── 오탐 학습 기반 고도화 상수 ────────────────────────────────────────────────
# Approach A: 동일 원료에 대한 유사 키워드 오탐 판단 임계값 (0~100)
_FP_KW_SIMILARITY: int = 85
# Approach A: 퍼지 확장을 적용할 최소 키워드 길이 (짧은 키워드 오버 필터 방지)
_FP_MIN_KW_LEN: int = 3
# Approach C: 위해도 1단계 하향 적용 최소 FP 횟수
_FP_PENALTY_LIGHT: int = 3
# Approach C: 위해도 2단계 하향 적용 최소 FP 횟수
_FP_PENALTY_HEAVY: int = 8
# 위해도 레벨 순서 (낮은 인덱스 = 낮은 위험)
_LEVEL_ORDER: list[str] = ['LOW', 'MED', 'HIGH']


class _FPPatternCache:
    """
    오탐 학습 패턴 캐시 (Approach A + C).

    Approach A — 퍼지 FP 스킵:
      • 정확 일치 (keyword, ingredient) → 매칭 제외
      • 동일 원료 + keyword 유사도 ≥ _FP_KW_SIMILARITY → 매칭 제외
        (keyword 길이 < _FP_MIN_KW_LEN 이면 퍼지 확장 미적용)

    Approach C — 키워드 레벨 위해도 패널티:
      • 해당 keyword가 FP 누적 횟수 N인 경우 위해도 레벨 자동 하향
        N < 3  → 변경 없음
        3 ≤ N < 8 → 1단계 (HIGH→MED, MED→LOW)
        N ≥ 8     → 2단계 (HIGH→LOW, 나머지 → LOW)
        LOW 이하로 내려가지 않음
    """

    def __init__(self, raw_patterns: list[tuple[str, str, int]]) -> None:
        # (kw_norm, ing_norm) → count
        self._exact: dict[tuple[str, str], int] = {}
        # ing_norm → [(kw_norm, count), ...]
        self._by_ing: dict[str, list[tuple[str, int]]] = {}
        # kw_norm → 해당 keyword의 전체 FP 누적 횟수
        self._kw_count: dict[str, int] = {}

        for kw, ing, count in raw_patterns:
            kw_n, ing_n = kw.strip(), ing.strip()
            if not kw_n or not ing_n:
                continue
            self._exact[(kw_n, ing_n)] = count

            if ing_n not in self._by_ing:
                self._by_ing[ing_n] = []
            self._by_ing[ing_n].append((kw_n, count))

            self._kw_count[kw_n] = self._kw_count.get(kw_n, 0) + count

    def is_fp(self, keyword: str, ingredient: str) -> bool:
        """
        Approach A: 정확 일치 또는 동일 원료에 대한 유사 키워드 오탐 여부 확인.
        True 이면 이 매칭을 완전히 제외한다.
        """
        kw_n, ing_n = keyword.strip(), ingredient.strip()

        # ① 정확 일치
        if (kw_n, ing_n) in self._exact:
            return True

        # ② 퍼지 키워드 확장 — 동일 원료, 표기 변형 키워드
        if len(kw_n) >= _FP_MIN_KW_LEN:
            for fp_kw, _ in self._by_ing.get(ing_n, []):
                if fuzz.ratio(kw_n, fp_kw) >= _FP_KW_SIMILARITY:
                    return True

        return False

    def keyword_fp_count(self, keyword: str) -> int:
        """
        Approach C: keyword의 전체 FP 누적 횟수 반환.
        이 값이 클수록 위해도 레벨 패널티가 커진다.
        """
        return self._kw_count.get(keyword.strip(), 0)

    def __bool__(self) -> bool:
        return bool(self._exact)


def _load_fp_patterns_for_user(user) -> '_FPPatternCache':
    """
    별도 테이블 없이 기존 매칭 레코드에서 오탐 패턴을 동적으로 유도한다.

    소스 1 — NewsProductMatch.false_positive_yn=True
      matched_keyword / matched_ingredient 가 오탐으로 확정된 (키워드, 원료명) 쌍.
      같은 조합이 반복 오탐될수록 count 증가 → Approach C 패널티 강화.

    소스 2 — NewsIngredientMatch.dismissed_yn=True
      보관함 원료에 대한 "해당 없음" 처리 이력.
      ingredient__prdlst_nm 을 원료명으로 사용.
    """
    from django.db.models import Count

    prod_fps = list(
        NewsProductMatch.objects
        .filter(product__user_id=user, false_positive_yn=True)
        .values('matched_keyword', 'matched_ingredient')
        .annotate(count=Count('id'))
        .values_list('matched_keyword', 'matched_ingredient', 'count')
    )

    ing_fps_qs = (
        NewsIngredientMatch.objects
        .filter(user=user, dismissed_yn=True)
        .values('matched_keyword', 'ingredient__prdlst_nm')
        .annotate(count=Count('id'))
        .values_list('matched_keyword', 'ingredient__prdlst_nm', 'count')
    )
    ing_fps = [(kw, ing, cnt) for kw, ing, cnt in ing_fps_qs if ing]

    return _FPPatternCache(prod_fps + ing_fps)


def _apply_fp_penalty(risk_dict: dict, fp_count: int) -> dict:
    """
    Approach C: FP 키워드 누적 횟수 기반 위해도 레벨 하향 조정.

    패널티 기준:
      fp_count < 3      → 변경 없음
      3 ≤ fp_count < 8  → 1단계 하향 (HIGH→MED, MED→LOW)
      fp_count ≥ 8      → 2단계 하향 (HIGH→LOW, MED→LOW)
    LOW 이하로 내려가지 않으며 SAFE는 변경 안 함.
    """
    level = risk_dict['level']
    if level in ('SAFE', 'LOW') or fp_count < _FP_PENALTY_LIGHT:
        return risk_dict

    steps     = 2 if fp_count >= _FP_PENALTY_HEAVY else 1
    level_idx = _LEVEL_ORDER.index(level)
    new_level = _LEVEL_ORDER[max(0, level_idx - steps)]

    if new_level == level:
        return risk_dict

    # 새 레벨의 최대 점수로 조정 (레벨 내 상한선 기준)
    new_score = {'MED': 15, 'LOW': 5}[new_level]
    return {
        'level':   new_level,
        'score':   new_score,
        'reasons': risk_dict['reasons'] + [
            f'오탐 이력({fp_count}회) 반영: {level}→{new_level} 하향',
        ],
    }


def find_affected_products(
    news: RegulatoryNews,
    user: User,
    prefetched_boms: list | None = None,
    prefetched_ingredients: list | None = None,
    fp_patterns: '_FPPatternCache | None' = None,
    prefetched_labels: list | None = None,
    prefetched_contacts: list | None = None,
) -> list[dict]:
    """
    뉴스의 ai_issues (또는 ai_keywords 폴백)를 해당 사용자의 BOM + 원료 보관함에서 퍼지 매칭.

    prefetched_boms / prefetched_ingredients: build_user_match_cache() 로 미리 로드한
        데이터를 전달하면 DB 재조회 없이 메모리에서 바로 사용한다.

    Returns:
        list of {
            'product':             MyLabel instance,
            'matched_bom':         ProductBOM instance | None,
            'matched_keyword':     str,
            'matched_ingredient':  str,
            'score':               float,
            'risk_score':          int,
            'risk_level':          str,
            'risk_reasons':        list[str],
        }
    """
    from v1.bom.models import ProductBOM
    from v1.label.models import MyIngredient

    vtype      = getattr(news, 'violation_type', '') or ''
    api_source = (news.api_source or '').strip()
    news_pname = (news.product_name or '').strip()
    is_admin   = api_source in ('I0470', 'I0480', 'I0482') or vtype == 'admin'

    # 오탐 패턴 캐시 — Approach A (퍼지 스킵) + C (위해도 패널티) 에 사용
    if fp_patterns is None:
        fp_patterns = _load_fp_patterns_for_user(user)

    # ── 행정처분 분기: 업체명↔내 제조사 매칭 ──────────────────────────────
    if is_admin:
        return _find_admin_matches(
            news, user, api_source,
            prefetched_boms=prefetched_boms,
            prefetched_contacts=prefetched_contacts,
        )

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

    # ① BOM 원료명 매칭 (캐시 우선)
    user_boms = prefetched_boms if prefetched_boms is not None else list(
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
                # Approach A: 정확 일치 또는 유사 키워드 오탐 패턴 → 완전 제외
                if fp_patterns.is_fp(keyword, bom.ingredient_name):
                    logger.debug(
                        f'[오탐 A] {keyword!r} ↔ {bom.ingredient_name!r} — 학습 패턴 제외'
                    )
                    continue
                risk_dict = calculate_risk_score(bom, issue)
                if risk_dict['level'] == 'SAFE':
                    continue
                # Approach C: 동일 keyword 누적 FP 횟수 기반 위해도 하향 조정
                kw_fp = fp_patterns.keyword_fp_count(keyword)
                if kw_fp >= _FP_PENALTY_LIGHT:
                    risk_dict = _apply_fp_penalty(risk_dict, kw_fp)
                    logger.debug(
                        f'[오탐 C] {keyword!r} FP {kw_fp}회 → {risk_dict["level"]} 하향'
                    )
                _update_best(bom.parent_label, bom, keyword, bom.ingredient_name, score, risk_dict)

    # ② 원료 보관함(MyIngredient) 매칭 (캐시 우선)
    user_ingredients = prefetched_ingredients if prefetched_ingredients is not None else list(
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
                # Approach A: 정확 일치 또는 유사 키워드 오탐 패턴 → 완전 제외
                if fp_patterns.is_fp(keyword, ing_name):
                    logger.debug(
                        f'[오탐 A] {keyword!r} ↔ {ing_name!r} — 학습 패턴 제외'
                    )
                    continue
                # Approach C: 동일 keyword 누적 FP 횟수 기반 위해도 하향
                kw_fp = fp_patterns.keyword_fp_count(keyword)
                for bom in ing.bom_usages.all():
                    product = bom.parent_label
                    if not product or product.delete_YN == 'Y':
                        continue
                    risk_dict = calculate_risk_score(bom, issue)
                    if risk_dict['level'] == 'SAFE':
                        continue
                    if kw_fp >= _FP_PENALTY_LIGHT:
                        risk_dict = _apply_fp_penalty(risk_dict, kw_fp)
                    _update_best(product, bom, keyword, ing_name, score, risk_dict)

    # ③ 제품 레벨 매칭 (제품명·식품유형·제조사·연락처 업체명)
    product_level = _find_product_level_matches(
        news, user, issues,
        prefetched_labels=prefetched_labels,
        prefetched_contacts=prefetched_contacts,
        prefetched_boms=prefetched_boms,
    )
    for m in product_level:
        _update_best(
            m['product'], m['matched_bom'],
            m['matched_keyword'], m['matched_ingredient'],
            m['score'], {'level': m['risk_level'], 'score': m['risk_score'], 'reasons': m['risk_reasons']},
        )

    return list(best.values())


def _find_product_level_matches(
    news: RegulatoryNews,
    user: User,
    issues: list[dict],
    prefetched_labels: list | None = None,
    prefetched_contacts: list | None = None,
    prefetched_boms: list | None = None,
) -> list[dict]:
    """
    제품 레벨 매칭: 원료 키워드 매칭 없이 제품·제조사·연락처 정보를 직접 비교.
      - 제품명  : news.product_name ↔ MyLabel.my_label_name
      - 식품유형: issues[].food_type ↔ MyLabel.food_type
      - 제조사  : issues[].manufacturer ↔ MyLabel 제조원/유통전문판매원/소분원/수입원
                  정확일치 → MED, 부분일치 → LOW
      - 연락처  : news.company_name / issues[].manufacturer ↔ UserContact.company
                  → 연락처 회사와 일치하는 BOM 제조사를 가진 제품에 알림
    """
    from v1.bom.models import ProductBOM
    from v1.label.models import MyLabel
    from v1.products.models import UserContact

    # ── 데이터 로드 (캐시 우선) ──────────────────────────────────────────────
    user_labels = prefetched_labels if prefetched_labels is not None else list(
        MyLabel.objects
        .filter(user_id=user, delete_YN='N')
        .only('my_label_id', 'my_label_name', 'prdlst_nm', 'food_type', 'prdlst_dcnm',
              'bssh_nm', 'distributor_address', 'repacker_address', 'importer_address',
              'user_id', 'delete_YN')
    )
    user_contacts = prefetched_contacts if prefetched_contacts is not None else list(
        UserContact.objects.filter(owner=user).only('company')
    )
    user_boms = prefetched_boms if prefetched_boms is not None else list(
        ProductBOM.objects
        .filter(parent_label__user_id=user, parent_label__delete_YN='N')
        .select_related('parent_label')
        .only('bom_id', 'ingredient_name', 'manufacturer',
              'parent_label_id', 'parent_label__my_label_id',
              'parent_label__my_label_name', 'parent_label__user_id',
              'parent_label__delete_YN')
    )

    LABEL_COMPANY_FIELDS = [
        ('bssh_nm',             '제조원'),
        ('distributor_address', '유통전문판매원'),
        ('repacker_address',    '소분원'),
        ('importer_address',    '수입원'),
    ]
    LEVEL_SCORE = {'HIGH': 30, 'MED': 15, 'LOW': 7}
    best: dict[int, dict] = {}

    def _update(label, bom, keyword, ingredient, score, level, reasons):
        pid = label.my_label_id
        rs  = LEVEL_SCORE.get(level, 5)
        if pid not in best or rs > best[pid]['risk_score']:
            best[pid] = {
                'product': label, 'matched_bom': bom,
                'matched_keyword': keyword, 'matched_ingredient': ingredient,
                'score': score, 'risk_score': rs,
                'risk_level': level, 'risk_reasons': reasons,
            }

    news_pname  = (news.product_name or '').strip()
    news_company = _normalize_corp(news.company_name or '')

    for label in user_labels:
        # ── 1) 제품명 비교 ───────────────────────────────────────────────────
        if news_pname:
            label_pname = (label.my_label_name or label.prdlst_nm or '').strip()
            if label_pname:
                ps = fuzz.partial_ratio(label_pname.lower(), news_pname.lower())
                if ps >= 80:
                    level = 'MED' if ps >= 92 else 'LOW'
                    _update(label, None, news_pname, label_pname, float(ps), level,
                            [f'제품명 유사({ps}%)', f'부적합 제품: {news_pname[:30]}'])

        # ── 2) 식품유형 비교 ─────────────────────────────────────────────────
        label_ftype = (label.food_type or label.prdlst_dcnm or '').strip()
        if label_ftype:
            for issue in issues:
                issue_ftype = (issue.get('food_type') or '').strip()
                if issue_ftype and (issue_ftype in label_ftype or label_ftype in issue_ftype):
                    _update(label, None, issue_ftype, label_ftype, 80.0, 'LOW',
                            [f'식품유형 일치({issue_ftype})', f'내 제품 유형: {label_ftype[:20]}'])

        # ── 3) 제조사(MyLabel 필드) ↔ issues[].manufacturer ─────────────────
        for issue in issues:
            issue_mfr = _normalize_corp(issue.get('manufacturer') or '')
            if not issue_mfr:
                continue
            for field_attr, field_label in LABEL_COMPANY_FIELDS:
                norm_val = _normalize_corp(getattr(label, field_attr, None) or '')
                if not norm_val:
                    continue
                raw_val = (getattr(label, field_attr, None) or '')
                if norm_val == issue_mfr:
                    _update(label, None, issue.get('manufacturer', ''), raw_val[:200],
                            100.0, 'MED',
                            [f'제조사 정확일치({issue.get("manufacturer", "")[:20]})',
                             f'{field_label}: {raw_val[:30]}'])
                elif issue_mfr in norm_val or norm_val in issue_mfr:
                    sc = fuzz.ratio(issue_mfr, norm_val)
                    if sc >= 70:
                        _update(label, None, issue.get('manufacturer', ''), raw_val[:200],
                                float(sc), 'LOW',
                                [f'제조사 부분일치({issue.get("manufacturer", "")[:20]})',
                                 f'{field_label}: {raw_val[:30]}'])

    # ── 4) 연락처 업체명 비교 → BOM 제조사 경유 제품 연결 ────────────────────
    # news.company_name 및 issues[].manufacturer 를 연락처 업체명과 비교
    compare_corps: set[str] = set()
    if news_company:
        compare_corps.add(news_company)
    for issue in issues:
        c = _normalize_corp(issue.get('manufacturer') or '')
        if c:
            compare_corps.add(c)

    if compare_corps and user_contacts:
        for contact in user_contacts:
            contact_corp = _normalize_corp(contact.company or '')
            if not contact_corp:
                continue
            for cmp in compare_corps:
                is_exact   = (contact_corp == cmp)
                is_partial = not is_exact and (contact_corp in cmp or cmp in contact_corp)
                if not (is_exact or is_partial):
                    continue
                sc = fuzz.ratio(contact_corp, cmp)
                if sc < 70:
                    continue
                level = 'MED' if is_exact else 'LOW'
                for bom in user_boms:
                    bom_corp = _normalize_corp(bom.manufacturer or '')
                    if not bom_corp:
                        continue
                    if bom_corp == contact_corp or contact_corp in bom_corp or bom_corp in contact_corp:
                        if fuzz.ratio(bom_corp, contact_corp) < 70:
                            continue
                        _update(
                            bom.parent_label, bom,
                            contact.company or '', bom.manufacturer or '',
                            float(sc), level,
                            [f'연락처 업체 {"정확" if is_exact else "부분"}일치'
                             f'({(contact.company or "")[:20]})',
                             f'원료 제조사: {(bom.manufacturer or "")[:20]}',
                             f'해당원료: {(bom.ingredient_name or "")[:20]}'],
                        )

    return list(best.values())


def _find_admin_matches(
    news: RegulatoryNews,
    user: User,
    api_source: str,
    prefetched_boms: list | None = None,
    prefetched_contacts: list | None = None,
) -> list[dict]:
    """
    행정처분 전용 매칭: 뉴스 업체명이 내 BOM 원료의 제조사 또는
    제품 기본정보(제조원·유통전문판매원·소분원) 또는 연락처 업체명과 일치하는지 확인.
    일치 시 MED 등급으로 알림. (원료 키워드 매칭 없이 업체명만 비교)
    """
    from v1.bom.models import ProductBOM
    from v1.label.models import MyLabel
    from v1.products.models import UserContact

    news_company = _normalize_corp(news.company_name or '')
    if not news_company:
        return []

    best: dict[int, dict] = {}

    # ── 1) BOM 원료 제조사 매칭 ────────────────────────────────────
    user_boms = prefetched_boms if prefetched_boms is not None else list(
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

    # ── 3) 연락처 업체명 매칭 → BOM 제조사 경유 제품 연결 ──────────────────
    user_contacts = prefetched_contacts if prefetched_contacts is not None else list(
        UserContact.objects.filter(owner=user).only('company')
    )
    for contact in user_contacts:
        contact_corp = _normalize_corp(contact.company or '')
        if not contact_corp:
            continue
        if news_company not in contact_corp and contact_corp not in news_company:
            continue
        sc = fuzz.ratio(news_company, contact_corp)
        if sc < 70:
            continue
        is_exact = (news_company == contact_corp)
        level    = 'MED' if is_exact else 'LOW'
        for bom in user_boms:
            bom_corp = _normalize_corp(bom.manufacturer or '')
            if not bom_corp:
                continue
            if bom_corp != contact_corp and contact_corp not in bom_corp and bom_corp not in contact_corp:
                continue
            if fuzz.ratio(bom_corp, contact_corp) < 70:
                continue
            pid = bom.parent_label.my_label_id
            cur_score = best.get(pid, {}).get('risk_score', -1)
            if pid not in best or int(sc) > cur_score:
                best[pid] = {
                    'product':            bom.parent_label,
                    'matched_bom':        bom,
                    'matched_keyword':    news.company_name or '',
                    'matched_ingredient': bom.manufacturer or '',
                    'score':              float(sc),
                    'risk_score':         int(sc),
                    'risk_level':         level,
                    'risk_reasons':       [
                        f'처분업체-연락처 {"정확" if is_exact else "부분"}일치'
                        f'({(news.company_name or "")[:20]})',
                        f'연락처: {(contact.company or "")[:20]}',
                        f'원료 제조사: {(bom.manufacturer or "")[:20]}',
                        f'해당원료: {(bom.ingredient_name or "")[:20]}',
                    ],
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
            # 오탐 처리된 레코드는 건드리지 않음 (사용자가 의도적으로 제외한 항목)
            if obj.false_positive_yn:
                continue
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


def find_matching_ingredients_unlinked(
    news: RegulatoryNews,
    user: User,
    prefetched_ingredients: list | None = None,
    fp_patterns: '_FPPatternCache | None' = None,
) -> list[dict]:
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

    # 오탐 패턴 캐시 로드 (A + C)
    if fp_patterns is None:
        fp_patterns = _load_fp_patterns_for_user(user)

    base_issues = news.ai_issues if news.ai_issues else [
        {'ingredient': kw, 'origin': None, 'manufacturer': None, 'food_type': None}
        for kw in (news.ai_keywords or [])
    ]
    if not base_issues:
        return []

    # BOM에 연결된 적 없는 원료 보관함 항목만 (캐시 우선)
    if prefetched_ingredients is not None:
        unlinked_ings = [
            ing for ing in prefetched_ingredients
            if not ing.bom_usages.all().exists()  # type: ignore[attr-defined]
        ]
    else:
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

            # Approach A: 정확 일치 또는 유사 키워드 오탐 패턴 → 완전 제외
            if fp_patterns.is_fp(keyword, ing_name):
                logger.debug(
                    f'[오탐 A] {keyword!r} ↔ {ing_name!r} (unlinked) — 학습 패턴 제외'
                )
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

            # Approach C: FP 누적 횟수 기반 위해도 레벨 하향 조정
            kw_fp = fp_patterns.keyword_fp_count(keyword)
            if kw_fp >= _FP_PENALTY_LIGHT and risk_level not in ('SAFE', 'LOW'):
                penalized = _apply_fp_penalty(
                    {'level': risk_level, 'score': risk_score, 'reasons': []}, kw_fp
                )
                risk_level = penalized['level']
                risk_score = min(risk_score, penalized['score'] + int(score))

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
            # 해당없음(dismissed) 처리된 레코드는 건드리지 않음
            if obj.dismissed_yn:
                continue
            if obj.risk_score != m['risk_score'] or obj.risk_level != m['risk_level']:
                obj.risk_score = m['risk_score']
                obj.risk_level = m['risk_level']
                obj.save(update_fields=['risk_score', 'risk_level', 'updated_at'])
    return saved


def build_user_match_cache() -> dict:
    """
    모든 활성 사용자의 BOM·원료 보관함·제품·연락처 데이터를 한 번에 조회하여 캐시 반환.
    매칭 배치 실행 전 1회 호출하면 뉴스 건수 × 사용자 수만큼 반복되던
    DB 쿼리를 사용자 수만큼으로 줄일 수 있다.

    반환 형식:
        {
            user_id: {
                'user':        User instance,
                'boms':        list[ProductBOM],
                'ingredients': list[MyIngredient],
                'labels':      list[MyLabel],
                'contacts':    list[UserContact],
                'fp_patterns': _FPPatternCache,
            },
            ...
        }
    """
    from v1.bom.models import ProductBOM
    from v1.label.models import MyIngredient, MyLabel
    from v1.products.models import UserContact

    cache = {}
    for user in User.objects.filter(is_active=True):
        boms = list(
            ProductBOM.objects
            .filter(parent_label__user_id=user, parent_label__delete_YN='N')
            .select_related('parent_label')
            .only('bom_id', 'ingredient_name', 'origin', 'manufacturer', 'food_type',
                  'parent_label_id', 'parent_label__my_label_id',
                  'parent_label__my_label_name', 'parent_label__user_id',
                  'parent_label__delete_YN')
        )
        ingredients = list(
            MyIngredient.objects
            .filter(user_id=user, delete_YN='N')
            .prefetch_related('bom_usages__parent_label')
        )
        labels = list(
            MyLabel.objects
            .filter(user_id=user, delete_YN='N')
            .only('my_label_id', 'my_label_name', 'prdlst_nm', 'food_type', 'prdlst_dcnm',
                  'bssh_nm', 'distributor_address', 'repacker_address', 'importer_address',
                  'user_id', 'delete_YN')
        )
        contacts = list(
            UserContact.objects.filter(owner=user).only('company')
        )
        fp_patterns = _load_fp_patterns_for_user(user)
        cache[user.pk] = {
            'user':        user,
            'boms':        boms,
            'ingredients': ingredients,
            'labels':      labels,
            'contacts':    contacts,
            'fp_patterns': fp_patterns,
        }
    return cache


def run_matching_for_all_users(news: RegulatoryNews, user_cache: dict | None = None) -> int:
    """
    모든 활성 사용자에 대해 매칭 실행 (제품 매칭 + 원료 보관함 단독 매칭).

    user_cache: build_user_match_cache() 결과. 배치 처리 시 전달하면
                뉴스 1건마다 DB를 재조회하지 않아 CPU/쿼리 수를 크게 줄인다.
                None 이면 기존 방식(건별 DB 조회)으로 동작.

    Returns: 전체 신규 매칭 건수
    """
    total = 0

    if user_cache is not None:
        # 캐시 사용: DB 재조회 없이 메모리에서 바로 매칭
        for entry in user_cache.values():
            user = entry['user']
            fp_patterns = entry.get('fp_patterns')
            product_matches = find_affected_products(
                news, user,
                prefetched_boms=entry['boms'],
                prefetched_ingredients=entry['ingredients'],
                fp_patterns=fp_patterns,
                prefetched_labels=entry.get('labels'),
                prefetched_contacts=entry.get('contacts'),
            )
            if product_matches:
                total += save_matches(news, product_matches)
            ing_matches = find_matching_ingredients_unlinked(
                news, user,
                prefetched_ingredients=entry['ingredients'],
                fp_patterns=fp_patterns,
            )
            if ing_matches:
                total += save_ingredient_matches(news, user, ing_matches)
    else:
        # 캐시 없음: 기존 방식(signals 등 단건 호출 시)
        for user in User.objects.filter(is_active=True):
            product_matches = find_affected_products(news, user)
            if product_matches:
                total += save_matches(news, product_matches)
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
    # mfr_exact_match : 정규화 후 완전 일치 → 관심(MED)
    # mfr_partial_match: 한쪽이 다른쪽을 포함(부분 일치) → 일반(LOW)
    news_mfr = (news_issue.get('manufacturer') or '').strip()
    bom_mfr  = (getattr(bom, 'manufacturer', '') or '').strip()
    mfr_exact_match   = False
    mfr_partial_match = False
    if news_mfr and bom_mfr:
        n_corp = _normalize_corp(news_mfr)
        b_corp = _normalize_corp(bom_mfr)
        if n_corp and b_corp:
            if n_corp == b_corp:
                mfr_exact_match = True
                reasons.append(f"제조업체 정확일치({news_mfr[:15]})")
            elif n_corp in b_corp or b_corp in n_corp:
                mfr_partial_match = True
                reasons.append(f"제조업체 부분일치({news_mfr[:15]})")
    # 하위 호환: 기존 mfr_match 참조 코드를 위해 정확일치일 때만 True
    mfr_match = mfr_exact_match

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
    if origin_conflict and not mfr_exact_match and not mfr_partial_match and not pname_match and not ftype_match:
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
        # 수입: 원산지·식품유형·제조사(정확) 중 2개+ → HIGH / 1개 → MED
        # 제조사 부분일치 단독 → LOW
        match_cnt = sum([origin_match, ftype_match, mfr_exact_match])
        if match_cnt >= 2:
            level = 'HIGH'; score = match_cnt * 10
        elif match_cnt == 1:
            level = 'MED';  score = 10
        elif mfr_partial_match:
            level = 'LOW';  score = 7
        else:
            level = 'LOW';  score = 5

    else:
        # 국내가공 (I2620, I0490 등)
        # 제조사(정확) + 제품명 일치 → HIGH (특급)
        if mfr_exact_match and pname_match:
            level = 'HIGH'; score = 30
        # 식품유형 + (제조사 정확 or 원산지) → MED
        elif ftype_match and (mfr_exact_match or origin_match):
            level = 'MED';  score = 15
        # 제조사 정확 단독 or 원산지 단독 → MED (관심)
        elif mfr_exact_match or origin_match:
            level = 'MED';  score = 10
        # 제조사 부분일치 단독 → LOW (일반)
        elif mfr_partial_match:
            level = 'LOW';  score = 7
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
