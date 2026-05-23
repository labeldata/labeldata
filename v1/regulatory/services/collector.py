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
from django.db.models import Q
from django.utils import timezone
from v1.mobile.services.push_service import send_inspection_judgment_batch, send_inspection_batch_alerts

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

            # 페이지 내 모든 external_id 생성 후 기존 복수 여부를 일괄 조회
            candidate_ids: list[tuple[str, str]] = []  # [(rec_id, external_id), ...]
            for row in rows:
                id_key = svc['id_key']
                rec_id = str(row.get(id_key) or '').strip() if id_key else ''
                if not rec_id:
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
                candidate_ids.append((rec_id, f'{svc_id}-{rec_id}'))

            # 페이지 내 external_id 전체를 단일 쿼리로 조회
            all_ext_ids = [eid for _, eid in candidate_ids]
            existing_ids: set[str] = set(
                RegulatoryNews.objects
                .filter(source=RegulatoryNews.SOURCE_DOMESTIC, external_id__in=all_ext_ids)
                .values_list('external_id', flat=True)
            )

            for row, (rec_id, external_id) in zip(rows, candidate_ids):
                if external_id in existing_ids:
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
                    'collected_date':   _parse_date_field(row, ['CRET_DTM', 'LAST_UPDT_DTM']),
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

            # 페이지 내 external_id 생성 후 기존 여부 일괄 조회
            candidate_ids: list[tuple[str, str]] = []
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
                candidate_ids.append((rec_id, f'{svc_id}-{rec_id}'))

            all_ext_ids = [eid for _, eid in candidate_ids]
            existing_ids: set[str] = set(
                RegulatoryNews.objects
                .filter(source=RegulatoryNews.SOURCE_IMPORT, external_id__in=all_ext_ids)
                .values_list('external_id', flat=True)
            )

            for row, (rec_id, external_id) in zip(rows, candidate_ids):
                if external_id in existing_ids:
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
                    'collected_date':   _parse_date_field(row, ['CRET_DTM', 'LAST_UPDT_DTM']),
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
    'MNFDT':                    '제조일자',
    'REPORTR_TELNO':            '신고기관 전화번호',
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
    'DSPS_BGNDT':               '처분시작일',
    'DSPS_ENDDT':               '처분종료일',
    'DSPS_TYPECD_NM':           '처분유형',
    'DSPS_INSTTCD_NM':          '처분기관',
    'PRSDNT_NM':                '대표자명',
    'PUBLIC_DT':                '공표일',
    'DSPSCN':                   '처분내용',
    'PRCSCITYPOINT_INDUTYCD_NM': '업종명',
    # I0490 (회수)
    'PRDLST_CD':                '식품유형코드',
    'PRDLST_REPORT_NO':         '품목보고번호',
    'FRMLCUNIT':                '용량/중량',
    'BRCDNO':                   '바코드',
    'RTRVLDSUSE_SEQ':           '회수일련번호',
    'RTRVL_GRDCD_NM':           '회수등급',
    'IMG_FILE_PATH':            '이미지경로',
    'PRDLST_TYPE':              '식품유형구분',
    # 공통
    'TELNO':                    '전화번호',
    'LAST_UPDT_DTM':            '최종수정일시',
    'CRET_DTM':                 '등록일시',
    'SITE_ADDR':                '소재지',
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


# ── 수거검사(I0460) ────────────────────────────────────────────────────────────

def backfill_inspection_matches(user, days: int = 30) -> dict:
    """
    사용자가 인허가번호·회사명·품목보고번호를 신규 등록할 때 호출.
    최근 N일치 InspectionResult를 소급 매칭하고 InspectionMatch를 생성한다.

    - 판정결과가 있는 건(검사 완료): InspectionMatch만 생성, 푸시 없음
    - 판정결과가 없는 건(검사중):    InspectionMatch 생성 + 묶음 푸시 1건 발송

    Args:
        user: 소급 매칭 대상 User 인스턴스
        days: 소급 기간 (기본 30일)

    Returns:
        {'matched': int, 'pending_push': int}
    """
    from datetime import datetime, timedelta
    from v1.regulatory.models import InspectionResult, InspectionMatch
    from v1.user_management.models import UserProfile
    from v1.label.models import MyLabel

    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

    try:
        profile = user.profile
        license_no   = (profile.license_number or '').strip()
        company_name = (profile.company_name   or '').strip()
    except Exception:
        license_no   = ''
        company_name = ''

    labels = MyLabel.objects.filter(user_id=user, delete_YN='N').exclude(prdlst_report_no='')
    norm_company = _normalize_corp_name(company_name) if company_name else ''

    # 조건에 해당하는 InspectionResult 추출 (사용자 정보 기반만, AlertRule 키워드 제외)
    q = Q()
    if license_no and len(license_no) >= 10:
        # DB 1차 후보: 품목보고번호 = 인허가번호 완전일치 또는 시작 일치
        q |= Q(prdlst_report_no=license_no) | Q(prdlst_report_no__startswith=license_no)
    if norm_company and len(norm_company) >= 2:
        # DB 1차 후보: 업소명 포함 → Python에서 정규화 완전일치로 정밀 필터
        q |= Q(bssh_nm__contains=norm_company)
    for label in labels:
        if label.prdlst_report_no:
            q |= Q(prdlst_report_no=label.prdlst_report_no)

    if not q:
        return {'matched': 0, 'pending_push': 0}

    candidates = InspectionResult.objects.filter(q, tkawydtm__gte=cutoff)

    matched      = 0
    pending_push = []  # 검사중인 건 (판정결과 없음)

    for ins in candidates:
        # 매칭 사유 결정 (우선순위: 품목보고번호 > 인허가번호 > 회사명)
        label_obj    = None
        match_reason = None
        matched_value = ''

        for label in labels:
            if label.prdlst_report_no and label.prdlst_report_no == ins.prdlst_report_no:
                label_obj     = label
                match_reason  = InspectionMatch.REASON_LABEL
                matched_value = ins.prdlst_report_no
                break

        # 조건 2: 인허가번호 — 품목보고번호와 완전일치 또는 앞부분 일치
        if not match_reason and license_no and len(license_no) >= 10 and ins.prdlst_report_no:
            if ins.prdlst_report_no == license_no or ins.prdlst_report_no.startswith(license_no):
                match_reason  = InspectionMatch.REASON_LICENSE
                matched_value = license_no

        # 조건 3: 회사명 정규화 후 포함 일치 (법인명 제거 후 사용자 입력이 업체명에 포함되면 매칭)
        if not match_reason and norm_company and len(norm_company) >= 2 and ins.bssh_nm:
            if norm_company in _normalize_corp_name(ins.bssh_nm):
                match_reason  = InspectionMatch.REASON_COMPANY
                matched_value = company_name

        if not match_reason:
            continue

        # 이미 매칭된 건 스킵
        already = InspectionMatch.objects.filter(
            inspection=ins, user=user, alert_phase=InspectionMatch.PHASE_COLLECTION
        ).exists()
        if already:
            continue

        InspectionMatch.objects.create(
            inspection    = ins,
            user          = user,
            label         = label_obj,
            alert_phase   = InspectionMatch.PHASE_COLLECTION,
            match_reason  = match_reason,
            matched_value = matched_value,
            prev_judgment = '',
            notified_at   = None if ins.jdgmnt_cd_nm in ('', '검토중') else timezone.now(),  # 판정 완료건은 알림 skip
            read_yn       = False,
        )
        matched += 1

        if ins.jdgmnt_cd_nm in ('', '검토중'):  # 검사중·검토중인 건 모두 푸시 대상
            pending_push.append(ins)

    # 검사중·검토중 건 묶음 푸시 (건별이 아닌 1건 요약 발송)
    if pending_push:
        _send_backfill_push(user, pending_push)

    logger.info(f'[I0460 소급] user={user.pk} matched={matched} pending_push={len(pending_push)}')
    return {'matched': matched, 'pending_push': len(pending_push)}


def _send_backfill_push(user, inspections: list) -> None:
    """소급 매칭된 검사중 건 묶음 푸시."""
    from v1.mobile.models import AppDevice
    from v1.mobile.services.push_service import _get_fcm_access_token
    import requests
    from django.conf import settings

    project_id = getattr(settings, 'FCM_PROJECT_ID', '')
    if not project_id:
        return

    device = AppDevice.objects.filter(user=user).order_by('-last_active_at').first()
    if not device or not device.fcm_token:
        return

    access_token = _get_fcm_access_token()
    if not access_token:
        return

    count = len(inspections)
    if count == 1:
        ins    = inspections[0]
        status = '검토중' if ins.jdgmnt_cd_nm == '검토중' else '검사 진행 중'
        title  = '🔍 수거검사 현황 안내'
        body   = f'{(ins.prdtnm or ins.bssh_nm)[:30]} — {status}'
    else:
        title = f'🔍 수거검사 현황 안내 ({count}건)'
        body  = f'내 제품·업소 관련 수거검사 {count}건이 진행 중입니다.'

    try:
        resp = requests.post(
            f'https://fcm.googleapis.com/v1/projects/{project_id}/messages:send',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            },
            json={
                'message': {
                    'token': device.fcm_token,
                    'notification': {'title': title, 'body': body},
                    'data': {
                        'type':       'inspection_backfill',
                        'count':      str(count),
                    },
                    'android': {
                        'priority': 'high',
                        'notification': {
                            'channel_id': 'food_safety_high',
                            'sound': 'default',
                        },
                    },
                    'apns': {
                        'payload': {'aps': {'sound': 'default'}},
                        'headers': {'apns-priority': '10'},
                    },
                },
            },
            timeout=5,
        )
        if resp.status_code != 200:
            logger.warning(f'[I0460 소급 푸시] 실패 {resp.status_code}: {resp.text[:200]}')
    except Exception as e:
        logger.warning(f'[I0460 소급 푸시] 오류: {e}')


def collect_inspection_data(
    last_updt_dtm: str | None = None,
    page_size: int = 1000,
    skip_trigger: bool = False,
) -> dict:
    """
    식약처 수거검사(I0460) 데이터를 수집해 InspectionResult에 저장하고,
    판정결과 변동을 감지해 InspectionMatch를 생성한다.

    Args:
        last_updt_dtm: 증분 수집 기준일 (YYYYMMDD). None이면 전체 수집.
        page_size: 1회 API 요청당 건수 (최대 1000).
        skip_trigger: True이면 매칭·알림 트리거를 생략하고 DB 저장만 수행.
                      대량 초기 적재 시 사용 후 --backfill-inspection으로 일괄 매칭.

    Returns:
        {'created': int, 'updated': int, 'skipped': int}
    """
    from v1.regulatory.models import InspectionResult

    api_key  = getattr(settings, 'FOODSAFETY_API_KEY', '')
    base_url = f'{DOM_API_BASE}/{api_key}/I0460/json'

    counts = {'created': 0, 'updated': 0, 'skipped': 0}
    judgment_changed_objs = []
    start  = 1

    while True:
        end = start + page_size - 1
        url = f'{base_url}/{start}/{end}'
        params = {}
        if last_updt_dtm:
            params['LAST_UPDT_DTM'] = last_updt_dtm

        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error(f'[I0460] API 호출 실패 start={start}: {exc}')
            break

        rows = (data.get('I0460') or {}).get('row') or []
        if not rows:
            break

        for row in rows:
            prno = (row.get('TKAWYPRNO') or '').strip()
            if not prno:
                counts['skipped'] += 1
                continue

            new_judgment = (row.get('JDGMNT_CD_NM') or '').strip()
            fields = {
                'plan_titl':            (row.get('PLAN_TITL')              or '').strip(),
                'bssh_nm':              (row.get('BSSH_NM')                or '').strip(),
                'prdtnm':               (row.get('PRDTNM')                 or '').strip(),
                'prdlst_report_no':     (row.get('PRDLST_REPORT_NO')       or '').strip(),
                'jdgmnt_cd_nm':         new_judgment,
                'induty_cd_nm':         (row.get('PRCSCITYPOINT_INDUTYCD_NM') or '').strip(),
                'site_addr':            (row.get('SITE_ADDR')              or '').strip(),
                'tkawydtm':             (row.get('TKAWYDTM')               or '').strip(),
                'tkawyspci_typecd_nm':  (row.get('TKAWYSPCI_TYPECD_NM')    or '').strip(),
                'exc_instt_nm':         (row.get('EXC_INSTT_NM')           or '').strip(),
                'last_updt_dtm':        (row.get('LAST_UPDT_DTM')          or '').strip(),
            }

            try:
                obj = InspectionResult.objects.get(tkawyprno=prno)
                # 판정결과·업소명 변동 감지
                prev_judgment = obj.jdgmnt_cd_nm
                prev_bssh_nm  = obj.bssh_nm
                # 최종 판정(적합/부적합)으로 확정된 경우에만 변동 알림 발송
                _FINAL_JUDGMENTS = {'적합', '부적합'}
                judgment_changed = (
                    prev_judgment != new_judgment
                    and new_judgment in _FINAL_JUDGMENTS
                )
                for attr, val in fields.items():
                    setattr(obj, attr, val)
                obj.save()
                counts['updated'] += 1
                if not skip_trigger and judgment_changed:
                    _trigger_inspection_match(obj, prev_judgment=prev_judgment, is_new=False)
                    judgment_changed_objs.append(obj)
                # 업소명이 바뀌면 REASON_COMPANY 매칭 재검증 (오래된 매칭 삭제)
                if not skip_trigger and prev_bssh_nm != obj.bssh_nm:
                    _revalidate_company_matches(obj)
            except InspectionResult.DoesNotExist:
                obj = InspectionResult.objects.create(tkawyprno=prno, **fields)
                counts['created'] += 1
                if not skip_trigger:
                    _trigger_inspection_match(obj, prev_judgment='', is_new=True)
                    # PHASE_COLLECTION은 루프 종료 후 send_inspection_batch_alerts()로 일괄 발송

        if len(rows) < page_size:
            break
        start += page_size
        time.sleep(0.5)

    # PHASE_JUDGMENT 알림: 판정변동 건 전체를 사용자별 1건 FCM으로 즉시 발송
    if not skip_trigger and judgment_changed_objs:
        send_inspection_judgment_batch(judgment_changed_objs)

    # PHASE_COLLECTION 알림: notified_at 기록 (FCM은 send_pending_alerts 커맨드에서)
    if not skip_trigger:
        send_inspection_batch_alerts()

    logger.info(f'[I0460] 수집 완료: {counts}')
    return counts


# ── 업체명 정규화: 법인 접미/접두사 제거 ──────────────────────────────────────
import re as _re
_CORP_SFXS_RE = _re.compile(
    r'\s*(주식회사|유한회사|합자회사|합명회사|협동조합|\(주\)|\(유\)|㈜|co\.?,?\s*ltd\.?|inc\.?)\s*',
    _re.IGNORECASE,
)


def _normalize_corp_name(name: str) -> str:
    """업체명에서 법인 유형 접미/접두사를 제거하고 공백을 정리합니다."""
    name = _CORP_SFXS_RE.sub('', name).strip()
    return name


def _revalidate_company_matches(inspection) -> None:
    """
    InspectionResult.bssh_nm이 변경됐을 때 REASON_COMPANY 기반 InspectionMatch를 재검증.
    현재 bssh_nm에 더 이상 사용자 회사명이 포함되지 않으면 해당 매칭을 삭제한다.
    """
    import logging as _logging
    from v1.regulatory.models import InspectionMatch

    _logger = _logging.getLogger(__name__)
    norm_bssh = _normalize_corp_name(inspection.bssh_nm) if inspection.bssh_nm else ''

    stale = []
    for match in InspectionMatch.objects.filter(
        inspection=inspection,
        match_reason=InspectionMatch.REASON_COMPANY,
    ).select_related('user'):
        try:
            company_name = (match.user.profile.company_name or '').strip()
        except Exception:
            company_name = ''

        norm_company = _normalize_corp_name(company_name) if company_name else ''
        if not norm_company or not norm_bssh or norm_company not in norm_bssh:
            stale.append(match.pk)
            _logger.info(
                '[I0460] bssh_nm 변경으로 매칭 삭제: tkawyprno=%s user_id=%s '
                'bssh_nm=%r company=%r',
                inspection.tkawyprno, match.user_id, inspection.bssh_nm, company_name,
            )

    if stale:
        InspectionMatch.objects.filter(pk__in=stale).delete()


def _trigger_inspection_match(inspection, prev_judgment: str, is_new: bool) -> None:
    """
    InspectionResult 1건에 대해 매칭 대상 사용자를 찾아 InspectionMatch를 생성한다.

    매칭 조건 (OR, 사용자 등록 정보 기반만 적용 — AlertRule 키워드 제외):
      1. 내제품(MyLabel.prdlst_report_no) == inspection.prdlst_report_no
      2. 내정보(UserProfile.license_number): 품목보고번호와 완전일치 또는 앞부분 일치 (len≥10)
      3. 내정보(UserProfile.company_name) 정규화 완전일치 == inspection.bssh_nm 정규화

    알림 생성 기준 (수거일 tkawydtm 기준):
      - 신규 수거 (PHASE_COLLECTION): 최근 7일 이내 수거 건만
      - 판정결과 변동 (PHASE_JUDGMENT): 최근 30일 이내 수거 건만
    """
    from datetime import datetime, timedelta
    from django.utils import timezone
    from v1.regulatory.models import InspectionMatch
    from v1.label.models import MyLabel
    from v1.user_management.models import UserProfile

    # ── 날짜 필터: 오래된 데이터 알림 차단 ────────────────────────────────────
    alert_phase = InspectionMatch.PHASE_COLLECTION if is_new else InspectionMatch.PHASE_JUDGMENT

    # PHASE_JUDGMENT: 최종 판정(적합/부적합)이 아니면 알림 생성 안 함
    if alert_phase == InspectionMatch.PHASE_JUDGMENT:
        _FINAL_JUDGMENTS = {'적합', '부적합'}
        if inspection.jdgmnt_cd_nm not in _FINAL_JUDGMENTS:
            logger.debug(
                '[I0460] 판정변동 알림 스킵 (미확정 판정: %s): %s',
                inspection.jdgmnt_cd_nm, inspection.tkawyprno,
            )
            return

    max_days = 7 if is_new else 30
    tkawydtm = (inspection.tkawydtm or '').strip()
    if tkawydtm and len(tkawydtm) >= 8:
        try:
            collect_date = datetime.strptime(tkawydtm[:8], '%Y%m%d').date()
            cutoff = (timezone.now() - timedelta(days=max_days)).date()
            if collect_date < cutoff:
                logger.debug(
                    f'[I0460] 알림 스킵 (수거일 {collect_date} < {cutoff}): {inspection.tkawyprno}'
                )
                return
        except ValueError:
            pass  # 날짜 파싱 실패 시 필터 적용 안 함

    report_no  = inspection.prdlst_report_no
    bssh_nm    = inspection.bssh_nm

    # 매칭된 (user, label, reason, matched_value) 목록 수집 (user 중복 허용 안 함)
    matched: dict[int, dict] = {}  # user_id → match info

    # ── 조건 1: 내제품 품목보고번호 일치 ──────────────────────────────────────
    if report_no:
        labels = (
            MyLabel.objects
            .filter(prdlst_report_no=report_no, delete_YN='N')
            .select_related('user_id')
        )
        for label in labels:
            uid = label.user_id_id
            if uid not in matched:
                matched[uid] = {
                    'label':         label,
                    'match_reason':  InspectionMatch.REASON_LABEL,
                    'matched_value': report_no,
                }

    # ── 조건 2 & 3: 내정보 인허가번호 / 회사명 ────────────────────────────────
    profiles = UserProfile.objects.exclude(
        license_number='', company_name=''
    ).values('user_id', 'license_number', 'company_name')

    norm_bssh = _normalize_corp_name(bssh_nm) if bssh_nm else ''

    for profile in profiles:
        uid = profile['user_id']
        if uid in matched:
            continue

        license_no   = (profile['license_number'] or '').strip()
        company_name = (profile['company_name']   or '').strip()

        # 조건 2: 인허가번호 — 완전일치 또는 앞부분 일치 (len≥10)
        if license_no and report_no and len(license_no) >= 10 and (
            report_no == license_no or report_no.startswith(license_no)
        ):
            matched[uid] = {
                'label':         None,
                'match_reason':  InspectionMatch.REASON_LICENSE,
                'matched_value': license_no,
            }
        # 조건 3: 회사명 정규화 후 포함 일치 (법인명 제거 후 사용자 입력이 업체명에 포함되면 매칭)
        elif company_name and norm_bssh and len(company_name) >= 2 and _normalize_corp_name(company_name) in norm_bssh:
            matched[uid] = {
                'label':         None,
                'match_reason':  InspectionMatch.REASON_COMPANY,
                'matched_value': company_name,
            }

    if not matched:
        return

    from django.contrib.auth.models import User
    now = timezone.now()

    for uid, info in matched.items():
        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            continue

        # 같은 단계의 매칭이 이미 존재하면 스킵
        exists = InspectionMatch.objects.filter(
            inspection=inspection, user=user, alert_phase=alert_phase
        ).exists()
        if exists:
            continue

        InspectionMatch.objects.create(
            inspection    = inspection,
            user          = user,
            label         = info['label'],
            alert_phase   = alert_phase,
            match_reason  = info['match_reason'],
            matched_value = info['matched_value'],
            prev_judgment = prev_judgment if not is_new else '',
            notified_at   = None,
            read_yn       = False,
        )

    logger.info(
        f'[I0460] InspectionMatch 생성: inspection={inspection.tkawyprno} '
        f'phase={alert_phase} matched_users={list(matched.keys())}'
    )
