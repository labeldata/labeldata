"""
부적합 정보 수집기 (Collector)  V3

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[국내] 식품안전나라 OpenAPI (FOODSAFETY_API_KEY 사용)
  서비스 ID별 수집 대상:
    I2620 : 검사부적합 (국내 식품)
    I2640 : 검사부적합 (농산물)
    I0490 : 회수·판매중지
    I0470 : 행정처분
    I0480 : 행정처분 (제조가공업)
  API URL:
    https://openapi.foodsafetykorea.go.kr/api/{KEY}/{SVC}/json/{start}/{end}

[수입] 수입식품정보마루 (impfood.mfds.go.kr) 리스트 수집
  공식 API/RSS 없음 → 내부 AJAX 엔드포인트 사용
  X-Requested-With: XMLHttpRequest 헤더 필요 (미포함 시 HTML 반환)
  확인된 JSON 필드:
    cntntsSn   : ID
    cntntsSj   : 제품명
    iemCtntNm2 : 업체명
    iemCtntNm6 : 부적합 사유
    iemCtntNm1 : 식품유형
    iemCtntNm9 : 수입신고번호
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import hashlib
import logging
import time
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup
from django.conf import settings

from v1.regulatory.models import RegulatoryNews

logger = logging.getLogger(__name__)

# ── 공통 ──────────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 20  # seconds

_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)

# ── 국내 OpenAPI ───────────────────────────────────────────────────────────────
DOM_API_BASE  = 'https://openapi.foodsafetykorea.go.kr/api'
DOM_PAGE_SIZE = 100   # 건당 최대 100

# 서비스 ID → 필드 매핑 (실제 API 응답 필드명 기준)
DOM_SERVICES = [
    {
        'svc_id':    'I2620',
        'label':     '검사부적합(국내)',
        'prdt_keys': ['PRDTNM', 'PRDT_NM', 'PRDLST_CD_NM'],
        'bssh_keys': ['BSSHNM', 'BSSH_NM', 'INSTT_NM'],
        # 검사항목 + 검사결과 조합으로 위반내용 구성
        'viol_keys': ['TEST_ITMNM', 'TESTANALS_RSLT', 'STDR_STND'],
        'id_key':    '',            # 없음 → PRDTNM+DISTBTMLMT 조합 해시
    },
    {
        'svc_id':    'I2640',
        'label':     '검사부적합(농산물)',
        'prdt_keys': ['PRDTNM', 'PRDT_NM', 'PRDLST_CD_NM'],
        'bssh_keys': ['BSSHNM', 'BSSH_NM'],
        'viol_keys': ['TEST_ITMNM', 'TESTANALS_RSLT', 'STDR_STND'],
        'id_key':    '',
    },
    {
        'svc_id':    'I0490',
        'label':     '회수판매중지',
        'prdt_keys': ['PRDTNM', 'PRDT_NM'],
        'bssh_keys': ['BSSHNM', 'BSSH_NM', 'PRCSCITYPOINT_BSSHNM'],
        'viol_keys': ['RTRVLPRVNS', 'VIO_CONTNT', 'RECALL_REASON'],
        'id_key':    'LCNS_NO',
    },
    {
        'svc_id':    'I0470',
        'label':     '행정처분',
        # 행정처분은 업체 대상 → 제품명 대신 업체명+업종으로 대체
        'prdt_keys': ['PRDTNM', 'INDUTY_CD_NM', 'PRCSCITYPOINT_BSSHNM'],
        'bssh_keys': ['PRCSCITYPOINT_BSSHNM', 'BSSHNM'],
        'viol_keys': ['VILTCN', 'DSPS_GBN_NM', 'LAWORD_CD_NM'],
        'id_key':    'DSPSDTLS_SEQ',
    },
    {
        'svc_id':    'I0480',
        'label':     '행정처분(제조가공업)',
        'prdt_keys': ['PRDTNM', 'INDUTY_CD_NM', 'PRCSCITYPOINT_BSSHNM'],
        'bssh_keys': ['PRCSCITYPOINT_BSSHNM', 'BSSHNM'],
        'viol_keys': ['VILTCN', 'DSPS_GBN_NM', 'LAWORD_CD_NM'],
        'id_key':    'DSPSDTLS_SEQ',
    },
]

# I0482: 수입식품등의 수입판매업 행정처분 — 동일 OpenAPI 사용하지만 수입(import) 분류
IMP_ADMIN_SERVICES = [
    {
        'svc_id':    'I0482',
        'label':     '행정처분(수입영업자)',
        'prdt_keys': ['PRDTNM', 'INDUTY_CD_NM', 'PRCSCITYPOINT_BSSHNM'],
        'bssh_keys': ['PRCSCITYPOINT_BSSHNM', 'BSSHNM'],
        'viol_keys': ['VILTCN', 'DSPS_GBN_NM', 'LAWORD_CD_NM'],
        'id_key':    'DSPSDTLS_SEQ',
    },
]

# ── 수입 AJAX ─────────────────────────────────────────────────────────────────
IMP_LIST_URL      = 'https://impfood.mfds.go.kr/CFCFF01F01/getCntntsList'
IMP_INSP_LIST_URL = 'https://impfood.mfds.go.kr/CFCEE01F01/getList'
IMP_DETAIL_URL    = 'https://impfood.mfds.go.kr/CFCFF01P01/getCntntsDetailPopup'
IMP_PAGE_SIZE     = 20

_IMP_AJAX_HEADERS = {
    'User-Agent':       _UA,
    'Accept':           'application/json, text/javascript, */*; q=0.01',
    'Accept-Language':  'ko-KR,ko;q=0.9',
    'X-Requested-With': 'XMLHttpRequest',   # ← JSON 반환에 필수
    'Referer':          'https://impfood.mfds.go.kr/',
}
_IMP_INSP_AJAX_HEADERS = {
    'User-Agent':       _UA,
    'Accept':           'application/json, */*; q=0.01',
    'Accept-Language':  'ko-KR,ko;q=0.9',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer':          'https://impfood.mfds.go.kr/CFCEE01F01',
}
_IMP_HTML_HEADERS = {
    'User-Agent':      _UA,
    'Accept':          'text/html,application/xhtml+xml,*/*;q=0.9',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Referer':         'https://impfood.mfds.go.kr/',
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. 국내식품 부적합 — 식품안전나라 OpenAPI
# ─────────────────────────────────────────────────────────────────────────────

def collect_domestic_news(target_date: date | None = None, max_rows: int = 0) -> list[dict]:
    """
    국내 부적합 수집 — 5개 서비스 ID 순회
    max_rows: 0 = 전체, 1 이상 = 서비스당 최대 수집 건수 (테스트용)
    """
    api_key = getattr(settings, 'FOODSAFETY_API_KEY', '')
    if not api_key:
        logger.error('[국내 수집] FOODSAFETY_API_KEY 미설정 — settings.py 확인')
        return []

    all_results: list[dict] = []

    for svc in DOM_SERVICES:
        svc_id = svc['svc_id']
        label  = svc['label']
        logger.info(f'[국내 수집] {svc_id} ({label}) 시작')

        start = 1
        fetched = 0

        while True:
            end = start + DOM_PAGE_SIZE - 1
            url = f'{DOM_API_BASE}/{api_key}/{svc_id}/json/{start}/{end}'

            try:
                resp = requests.get(url, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.error(f'[국내 수집] {svc_id} start={start} 오류: {exc}')
                break

            # 응답 최상위 키 = 서비스 ID
            svc_data    = data.get(svc_id, {})
            result_code = svc_data.get('RESULT', {}).get('CODE', '')

            if result_code not in ('INFO-000', ''):
                msg = svc_data.get('RESULT', {}).get('MSG', result_code)
                logger.warning(f'[국내 수집] {svc_id} 응답 코드={result_code}: {msg}')
                break

            rows       = svc_data.get('row', [])
            total_cnt  = int(svc_data.get('total_count') or 0)

            if not rows:
                break

            for row in rows:
                # 고유 ID 생성: 서비스ID + 레코드 식별자
                id_key = svc['id_key']
                rec_id = str(row.get(id_key) or '').strip() if id_key else ''

                if not rec_id:
                    # 안정적 해시: PRDTNM + DISTBTMLMT + ADDR 조합
                    seed = ''.join([
                        str(row.get('PRDTNM') or row.get('PRDT_NM') or ''),
                        str(row.get('DISTBTMLMT') or row.get('DSPS_DCSNDT') or ''),
                        str(row.get('ADDR') or ''),
                        str(row.get('BSSHNM') or row.get('PRCSCITYPOINT_BSSHNM') or ''),
                    ])
                    if seed.strip():
                        rec_id = hashlib.md5(seed.encode()).hexdigest()[:12]
                    else:
                        rec_id = hashlib.md5(
                            ''.join(str(v) for v in row.values()).encode()
                        ).hexdigest()[:12]

                external_id = f'{svc_id}-{rec_id}'

                if RegulatoryNews.objects.filter(
                    source=RegulatoryNews.SOURCE_DOMESTIC,
                    external_id=external_id,
                ).exists():
                    fetched += 1
                    continue

                product_name = _pick(row, svc['prdt_keys'])
                company_name = _pick(row, svc['bssh_keys'])
                # 위반내용: 여러 필드를 의미 있게 조합
                violation    = _combine_viol(row, svc['viol_keys'], svc['svc_id'])

                if not product_name:
                    # I0470/I0480은 업체명을 제품명으로 대체
                    product_name = company_name or external_id

                all_results.append({
                    'source':           RegulatoryNews.SOURCE_DOMESTIC,
                    'api_source':       svc_id,
                    'external_id':      external_id,
                    'product_name':     product_name,
                    'company_name':     company_name,
                    'violation_reason': violation,
                    'raw_detail_text':  _row_to_text(row, label),
                    'event_date':       _parse_date_field(row, svc.get('date_keys', [])),
                })
                fetched += 1

            # 페이지 종료 조건
            limit = max_rows if max_rows else total_cnt
            if fetched >= limit or len(rows) < DOM_PAGE_SIZE:
                break

            start += DOM_PAGE_SIZE
            time.sleep(0.3)

        logger.info(f'[국내 수집] {svc_id} → 신규 처리 {fetched}건')

    logger.info(f'[국내 수집] 전체 신규 {len(all_results)}건')
    return all_results


# ─────────────────────────────────────────────────────────────────────────────
# 2. 수입판매업 행정처분 — 식품안전나라 OpenAPI I0482 (source=import)
# ─────────────────────────────────────────────────────────────────────────────

def collect_import_admin_news(max_rows: int = 0) -> list[dict]:
    """
    수입식품등의 수입판매업 행정처분(I0482) 수집.
    동일한 식품안전나라 OpenAPI를 사용하지만 source='import'로 저장하여
    수입 카테고리 체크박스와 일치시킨다.
    """
    api_key = getattr(settings, 'FOODSAFETY_API_KEY', '')
    if not api_key:
        logger.error('[수입행정처분 수집] FOODSAFETY_API_KEY 미설정')
        return []

    all_results: list[dict] = []

    for svc in IMP_ADMIN_SERVICES:
        svc_id = svc['svc_id']
        label  = svc['label']
        logger.info(f'[수입행정처분 수집] {svc_id} ({label}) 시작')

        start = 1
        fetched = 0

        while True:
            end = start + DOM_PAGE_SIZE - 1
            url = f'{DOM_API_BASE}/{api_key}/{svc_id}/json/{start}/{end}'

            try:
                resp = requests.get(url, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.error(f'[수입행정처분 수집] {svc_id} start={start} 오류: {exc}')
                break

            svc_data    = data.get(svc_id, {})
            result_code = svc_data.get('RESULT', {}).get('CODE', '')

            if result_code not in ('INFO-000', ''):
                msg = svc_data.get('RESULT', {}).get('MSG', result_code)
                logger.warning(f'[수입행정처분 수집] {svc_id} 응답 코드={result_code}: {msg}')
                break

            rows      = svc_data.get('row', [])
            total_cnt = int(svc_data.get('total_count') or 0)

            if not rows:
                break

            for row in rows:
                id_key = svc['id_key']
                rec_id = str(row.get(id_key) or '').strip() if id_key else ''

                if not rec_id:
                    seed = ''.join([
                        str(row.get('PRDTNM') or row.get('PRDT_NM') or ''),
                        str(row.get('DSPS_DCSNDT') or ''),
                        str(row.get('PRCSCITYPOINT_BSSHNM') or row.get('BSSHNM') or ''),
                    ])
                    rec_id = hashlib.md5(seed.encode() if seed.strip() else
                                         ''.join(str(v) for v in row.values()).encode()
                                         ).hexdigest()[:12]

                external_id = f'{svc_id}-{rec_id}'

                # source='import'로 중복 체크
                if RegulatoryNews.objects.filter(
                    source=RegulatoryNews.SOURCE_IMPORT,
                    external_id=external_id,
                ).exists():
                    fetched += 1
                    continue

                product_name = _pick(row, svc['prdt_keys'])
                company_name = _pick(row, svc['bssh_keys'])
                violation    = _combine_viol(row, svc['viol_keys'], svc_id)

                if not product_name:
                    product_name = company_name or external_id

                all_results.append({
                    'source':           RegulatoryNews.SOURCE_IMPORT,   # ← 수입으로 저장
                    'api_source':       svc_id,
                    'external_id':      external_id,
                    'product_name':     product_name,
                    'company_name':     company_name,
                    'violation_reason': violation,
                    'raw_detail_text':  _row_to_text(row, label),
                    'event_date':       _parse_date_field(row, svc.get('date_keys', [])),
                })
                fetched += 1

            limit = max_rows if max_rows else total_cnt
            if fetched >= limit or len(rows) < DOM_PAGE_SIZE:
                break

            start += DOM_PAGE_SIZE
            time.sleep(0.3)

        logger.info(f'[수입행정처분 수집] {svc_id} → 신규 처리 {fetched}건')

    logger.info(f'[수입행정처분 수집] 전체 신규 {len(all_results)}건')
    return all_results


# ─────────────────────────────────────────────────────────────────────────────
# 3. 수입식품 부적합 — 수입식품정보마루 리스트 (AJAX)
# ─────────────────────────────────────────────────────────────────────────────

def collect_import_news(target_date: date | None = None, max_pages: int = 0) -> list[dict]:
    """
    수입 부적합 수집 — impfood.mfds.go.kr 내부 AJAX
    X-Requested-With: XMLHttpRequest 헤더로 JSON 수신
    max_pages: 0 = 전체, 1 이상 = 최대 페이지 수 (테스트용)
    """
    results: list[dict] = []
    page = 1

    while True:
        if max_pages and page > max_pages:
            break

        params = {
            'page':            page,
            'limit':           IMP_PAGE_SIZE,
            'gbn':             'N',       # 부적합 구분
            'searchInpText':   '',
        }
        try:
            resp = requests.get(
                IMP_LIST_URL,
                params=params,
                headers=_IMP_AJAX_HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error(f'[수입 수집] page={page} 오류: {exc}')
            break

        rows = data.get('list') or []
        if not rows:
            logger.info(f'[수입 수집] page={page} 빈 응답 → 종료')
            break

        for row in rows:
            cntnts_sn = str(row.get('cntntsSn') or '').strip()
            if not cntnts_sn:
                continue

            external_id = f'IMP-{cntnts_sn}'
            if RegulatoryNews.objects.filter(
                source=RegulatoryNews.SOURCE_IMPORT,
                external_id=external_id,
            ).exists():
                continue

            # 확인된 실제 필드명 사용
            product_name = (row.get('cntntsSj') or '').strip()           # 제품명
            company_name = (row.get('iemCtntNm2') or '').strip()         # 업체명
            violation    = (row.get('iemCtntNm6') or '').strip()         # 부적합 사유
            food_type    = (row.get('iemCtntNm1') or '').strip()         # 식품유형
            import_no    = (row.get('iemCtntNm9') or '').strip()         # 수입신고번호

            # 상세 HTML 수집
            detail_text = _fetch_impfood_detail(cntnts_sn)

            # raw_detail_text: 상세 없으면 목록 필드 조합
            if not detail_text:
                parts = [
                    f'제품명: {product_name}',
                    f'업체명: {company_name}',
                    f'부적합사유: {violation}',
                    f'식품유형: {food_type}',
                    f'수입신고번호: {import_no}',
                ]
                detail_text = '\n'.join(p for p in parts if p.split(': ')[1])

            results.append({
                'source':           RegulatoryNews.SOURCE_IMPORT,
                'api_source':       'import',
                'external_id':      external_id,
                'product_name':     product_name or cntnts_sn,
                'company_name':     company_name,
                'violation_reason': violation,
                'raw_detail_text':  detail_text,
            })
            time.sleep(0.2)

        if len(rows) < IMP_PAGE_SIZE:
            break

        page += 1
        time.sleep(0.5)

    logger.info(f'[수입 수집] 신규 {len(results)}건')
    return results


# ─────────────────────────────────────────────────────────────────────────────
# 4. 수입식품부적합 수집 — impfood.mfds.go.kr/CFCEE01F01 (AJAX)
# ─────────────────────────────────────────────────────────────────────────────

def collect_import_insp_news(max_pages: int = 0) -> list[dict]:
    """
    수입식품부적합 수집 — impfood.mfds.go.kr/CFCEE01F01 내부 AJAX
    필드 맵:
      rcno            → external_id (IMP_INSP-{rcno})
      koreanPrductNm  → product_name
      mnfExpterNm     → company_name (제조/수출회사)
      violtCtnt       → violation_reason
      dclPrductSeNm   → 제품구분
      itmNm           → 품목명
      mnfNtnnm        → 제조국가
      impotDtm        → 부적합일자
    """
    results: list[dict] = []
    page = 1

    while True:
        if max_pages and page > max_pages:
            break

        try:
            resp = requests.get(
                IMP_INSP_LIST_URL,
                params={'page': page, 'limit': IMP_PAGE_SIZE},
                headers=_IMP_INSP_AJAX_HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error(f'[수입부적합 수집] page={page} 오류: {exc}')
            break

        rows = data.get('list') or []
        if not rows:
            logger.info(f'[수입부적합 수집] page={page} 빈 응답 → 종료')
            break

        for row in rows:
            rcno = str(row.get('rcno') or '').strip()
            if not rcno:
                continue

            external_id = f'IMP_INSP-{rcno}'

            if RegulatoryNews.objects.filter(
                source=RegulatoryNews.SOURCE_IMPORT,
                external_id=external_id,
            ).exists():
                continue

            product_name  = (row.get('koreanPrductNm') or '').strip()
            eng_product_name = (row.get('engPrductNm') or '').strip()
            if not product_name:
                product_name = eng_product_name
            company_name  = (row.get('mnfExpterNm') or '').strip()
            violation     = (row.get('violtCtnt') or '').strip()
            prod_se       = (row.get('dclPrductSeNm') or '').strip()
            itm_nm        = (row.get('itmNm') or '').strip()
            mfr_country   = (row.get('mnfNtnnm') or '').strip()
            proc_instt    = (row.get('procsInsttNm') or '').strip()
            insp_date     = (row.get('impotDtm') or '').strip()

            # impotDtm → event_date (수입검사 부적합일)
            event_date_val = _parse_date_field(row, ['impotDtm', 'violtDtm', 'rcvDtm'])

            detail_parts = []
            # 수입품목 원재료 힌트 — AI 파서가 ingredient로 추출하도록 명시
            if product_name and eng_product_name and product_name != eng_product_name:
                detail_parts.append(f'검사원료(수입품목): {product_name} / {eng_product_name}')
            elif product_name:
                detail_parts.append(f'검사원료(수입품목): {product_name}')
            if prod_se:      detail_parts.append(f'제품구분: {prod_se}')
            if itm_nm:       detail_parts.append(f'품목명(식품유형): {itm_nm}')
            if mfr_country:  detail_parts.append(f'원산지(제조국가): {mfr_country}')
            if company_name: detail_parts.append(f'제조/수출회사(제조사): {company_name}')
            if violation:    detail_parts.append(f'위반내역: {violation}')
            if proc_instt:   detail_parts.append(f'처리기관: {proc_instt}')
            if insp_date:    detail_parts.append(f'부적합일자: {insp_date}')

            results.append({
                'source':           RegulatoryNews.SOURCE_IMPORT,
                'api_source':       'imp_insp',
                'external_id':      external_id,
                'product_name':     product_name or rcno,
                'company_name':     company_name,
                'violation_reason': violation,
                'raw_detail_text':  '\n'.join(detail_parts),
                'event_date':       event_date_val,
            })

        if len(rows) < IMP_PAGE_SIZE:
            break

        page += 1
        time.sleep(0.3)

    logger.info(f'[수입품질부적합 수집] 신규 {len(results)}건')
    return results


def _fetch_impfood_detail(cntnts_sn: str) -> str:
    """수입식품정보마루 상세 팝업 HTML → 텍스트 파싱"""
    try:
        resp = requests.get(
            IMP_DETAIL_URL,
            params={'cntntsSn': cntnts_sn, 'callBackFn': 'fnPopupCallback'},
            headers=_IMP_HTML_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning(f'[수입 상세] cntntsSn={cntnts_sn} 오류: {exc}')
        return ''

    soup = BeautifulSoup(resp.text, 'html.parser')
    for tag in soup.find_all(['script', 'style', 'button', 'input']):
        tag.decompose()

    content = (
        soup.find('div', class_='cont_area')
        or soup.find('div', id='contents')
        or soup.find('div', class_='detail_view')
        or soup.find('table')
        or soup.body
    )
    if not content:
        return ''

    lines = []
    for row in content.find_all('tr'):
        cells = [td.get_text(separator=' ', strip=True) for td in row.find_all(['th', 'td'])]
        line = ' | '.join(c for c in cells if c)
        if line:
            lines.append(line)

    if not lines:
        lines = [content.get_text(separator='\n', strip=True)]

    return '\n'.join(lines)[:4000]


# ─────────────────────────────────────────────────────────────────────────────
# 내부 유틸리티
# ─────────────────────────────────────────────────────────────────────────────

def _pick(row: dict, keys: list[str]) -> str:
    """dict에서 후보 키 순서대로 첫 번째 비어있지 않은 값 반환"""
    for k in keys:
        val = row.get(k)
        if val and str(val).strip() and str(val).strip() not in ('-', 'null', 'None', 'N/A', '데이터없음'):
            return str(val).strip()
    return ''


def _parse_date_field(row: dict, keys: list[str]) -> 'date | None':
    """날짜 필드 후보 키에서 YYYY-MM-DD 또는 YYYYMMDD 형식 date 반환.
    파싱 실패 시 None 반환.
    미래 날짜(오늘 이후)는 수집일(오늘)로 대체한다."""
    today = datetime.today().date()
    for k in keys:
        val = str(row.get(k) or '').strip()
        if not val or val in ('-', 'null', 'None', 'N/A'):
            continue
        # YYYY-MM-DD 또는 YYYY.MM.DD
        for fmt in ('%Y-%m-%d', '%Y.%m.%d', '%Y%m%d'):
            try:
                parsed = datetime.strptime(val[:10] if fmt != '%Y%m%d' else val[:8], fmt).date()
                # 미래 날짜 방어: 오늘보다 미래면 오늘로 대체
                return parsed if parsed <= today else today
            except ValueError:
                continue
    return None


def _combine_viol(row: dict, keys: list[str], svc_id: str) -> str:
    """
    위반내용 여러 필드를 서비스 유형에 맞게 조합
    - I2620/I2640 (검사부적합): '검사항목: 다이아지논 / 검출량: 1.62mg/kg / 기준: 0.01mg/kg'
    - I0490 (회수): RTRVLPRVNS 단일
    - I0470/I0480 (행정처분): VILTCN 단일
    """
    if svc_id in ('I2620', 'I2640'):
        item  = row.get('TEST_ITMNM', '').strip()
        rslt  = row.get('TESTANALS_RSLT', '').strip()
        stdr  = row.get('STDR_STND', '').strip()
        parts = []
        if item: parts.append(f'검사항목: {item}')
        if rslt: parts.append(f'검출: {rslt}')
        if stdr: parts.append(f'기준: {stdr}')
        return ' / '.join(parts)
    return _pick(row, keys)


# 식품안전나라 OpenAPI 영문 필드명 → 한글 표시명 매핑
_FIELD_KO: dict[str, str] = {
    # 공통
    'PRDTNM':                   '제품명',
    'PRDT_NM':                  '제품명',
    'PRDLST_CD_NM':             '식품유형',
    'BSSHNM':                   '업소명',
    'BSSH_NM':                  '업소명',
    'INSTT_NM':                 '검사기관',
    'ADDR':                     '소재지',
    # I2620 / I2640 (검사부적합)
    'TEST_ITMNM':               '검사항목',
    'TESTANALS_RSLT':           '검출량',
    'STDR_STND':                '기준규격',
    'DISTBTMLMT':               '유통기한',
    # I0490 (회수)
    'RTRVLPRVNS':               '회수사유',
    'VIO_CONTNT':               '위반내용',
    'RECALL_REASON':            '회수이유',
    'LCNS_NO':                  '허가번호',
    'PRCSCITYPOINT_BSSHNM':     '처분업소명',
    # I0470 / I0480 / I0482 (행정처분)
    'INDUTY_CD_NM':             '업종명',
    'VILTCN':                   '위반내용',
    'DSPS_GBN_NM':              '처분구분',
    'LAWORD_CD_NM':             '법적근거',
    'DSPSDTLS_SEQ':             '처분번호',
    'DSPS_DCSNDT':              '처분확정일자',
    'DSPS_PRCD':                '처분기간',
    'DSPS_BGNG_DT':             '처분시작일',
    'DSPS_END_DT':              '처분종료일',
}


def _row_to_text(row: dict, label: str = '') -> str:
    """OpenAPI row dict → 읽기 좋은 텍스트 (AI 파싱 입력용)
    영문 API 필드명은 한글 표시명으로 변환합니다.
    """
    header = f'[{label}]\n' if label else ''
    lines = []
    for k, v in row.items():
        if v and str(v).strip() and str(v).strip() not in ('-', '데이터없음'):
            ko_key = _FIELD_KO.get(k, k)
            lines.append(f'{ko_key}: {v}')
    return header + '\n'.join(lines)
