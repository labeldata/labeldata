"""
수입식품 부적합·회수 수집 및 PythonAnywhere 업로드 스크립트
=============================================================
로컬 PC (한국 IP)에서 실행하여 해외 IP 차단 우회

대상:
  CFCFF01F01  수입 회수·판매중지
  CFCEE01F01  수입식품 부적합

실행:
  python import_scraper.py               # 전체 수집 + 서버 전송
  python import_scraper.py --max-pages 3 # 각 최대 3페이지 (테스트용)
  python import_scraper.py --dry-run     # 서버 전송 없이 로컬 저장만

필요 패키지:
  pip install requests beautifulsoup4

설정:
  스크립트 상단 PA_USERNAME, PA_API_TOKEN 을 채워 넣으세요.
"""
import argparse
import hashlib
import json
import logging
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ━━━ PythonAnywhere 설정 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PA_USERNAME  = 'labeldata'
PA_API_TOKEN = ''   # ← 여기에 PA API 토큰 입력 (계정 > API Token) — git에 올리지 말 것
PA_DEST_PATH = f'/home/{PA_USERNAME}/mysite/new_import_data.json'
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OUTPUT_FILE = Path(__file__).parent / 'scraped_import_data.json'

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
       'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

IMP_LIST_URL      = 'https://impfood.mfds.go.kr/CFCFF01F01/getCntntsList'
IMP_INSP_LIST_URL = 'https://impfood.mfds.go.kr/CFCEE01F01/getList'
IMP_DETAIL_URL    = 'https://impfood.mfds.go.kr/CFCFF01P01/getCntntsDetailPopup'
PAGE_SIZE = 20
TIMEOUT   = 20


# ─────────────────────────────────────────────────────────────
# 1. 수입 회수·판매중지 (CFCFF01F01)
# ─────────────────────────────────────────────────────────────

def collect_import_recall(max_pages: int = 0) -> list:
    results, page = [], 1
    while True:
        if max_pages and page > max_pages:
            break
        try:
            resp = requests.get(
                IMP_LIST_URL,
                params={'page': page, 'limit': PAGE_SIZE, 'gbn': 'N', 'searchInpText': ''},
                headers={'User-Agent': _UA, 'Accept': 'application/json, */*; q=0.01',
                         'X-Requested-With': 'XMLHttpRequest', 'Referer': 'https://impfood.mfds.go.kr/'},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            rows = resp.json().get('list') or []
        except Exception as e:
            logger.error(f'[회수] page={page} 오류: {e}')
            break

        if not rows:
            break
        logger.info(f'[회수] page={page} → {len(rows)}건')

        for row in rows:
            sn = str(row.get('cntntsSn') or '').strip()
            if not sn:
                continue
            product  = (row.get('cntntsSj')    or '').strip()
            company  = (row.get('iemCtntNm2')  or '').strip()
            reason   = (row.get('iemCtntNm6')  or '').strip()
            food_type = (row.get('iemCtntNm1') or '').strip()
            import_no = (row.get('iemCtntNm9') or '').strip()

            detail = _fetch_detail(sn)
            if not detail:
                parts = [f'제품명: {product}', f'업체명: {company}',
                         f'부적합사유: {reason}', f'식품유형: {food_type}',
                         f'수입신고번호: {import_no}']
                detail = '\n'.join(p for p in parts if p.split(': ', 1)[1])

            results.append({
                'source': 'import', 'api_source': 'import',
                'external_id': f'IMP-{sn}',
                'product_name': product or sn,
                'company_name': company,
                'violation_reason': reason,
                'raw_detail_text': detail,
                'event_date': None,
            })
            time.sleep(0.2)

        if len(rows) < PAGE_SIZE:
            break
        page += 1
        time.sleep(0.5)

    logger.info(f'[회수] 완료: {len(results)}건')
    return results


# ─────────────────────────────────────────────────────────────
# 2. 수입식품 부적합 (CFCEE01F01)
# ─────────────────────────────────────────────────────────────

def collect_import_insp(max_pages: int = 0) -> list:
    results, page = [], 1
    while True:
        if max_pages and page > max_pages:
            break
        try:
            resp = requests.get(
                IMP_INSP_LIST_URL,
                params={'page': page, 'limit': PAGE_SIZE},
                headers={'User-Agent': _UA, 'Accept': 'application/json, */*; q=0.01',
                         'X-Requested-With': 'XMLHttpRequest',
                         'Referer': 'https://impfood.mfds.go.kr/CFCEE01F01'},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            rows = resp.json().get('list') or []
        except Exception as e:
            logger.error(f'[부적합] page={page} 오류: {e}')
            break

        if not rows:
            break
        logger.info(f'[부적합] page={page} → {len(rows)}건')

        for row in rows:
            rcno = str(row.get('rcno') or '').strip()
            if not rcno:
                continue
            product     = (row.get('koreanPrductNm') or '').strip()
            product_eng = (row.get('engPrductNm')    or '').strip()
            if not product:
                product = product_eng
            company     = (row.get('mnfExpterNm')    or '').strip()
            violation   = (row.get('violtCtnt')      or '').strip()
            prod_se     = (row.get('dclPrductSeNm')  or '').strip()
            itm_nm      = (row.get('itmNm')          or '').strip()
            country     = (row.get('mnfNtnnm')       or '').strip()
            proc_instt  = (row.get('procsInsttNm')   or '').strip()
            insp_date   = (row.get('impotDtm')       or '').strip()

            event_date = _parse_date(row, ['impotDtm', 'violtDtm', 'rcvDtm'])

            parts = []
            if product and product_eng and product != product_eng:
                parts.append(f'검사원료(수입품목): {product} / {product_eng}')
            elif product:
                parts.append(f'검사원료(수입품목): {product}')
            if prod_se:    parts.append(f'제품구분: {prod_se}')
            if itm_nm:     parts.append(f'품목명(식품유형): {itm_nm}')
            if country:    parts.append(f'원산지(제조국가): {country}')
            if company:    parts.append(f'제조/수출회사(제조사): {company}')
            if violation:  parts.append(f'위반내역: {violation}')
            if proc_instt: parts.append(f'처리기관: {proc_instt}')
            if insp_date:  parts.append(f'부적합일자: {insp_date}')

            results.append({
                'source': 'import', 'api_source': 'imp_insp',
                'external_id': f'IMP_INSP-{rcno}',
                'product_name': product or rcno,
                'company_name': company,
                'violation_reason': violation,
                'raw_detail_text': '\n'.join(parts),
                'event_date': event_date,
            })

        if len(rows) < PAGE_SIZE:
            break
        page += 1
        time.sleep(0.3)

    logger.info(f'[부적합] 완료: {len(results)}건')
    return results


# ─────────────────────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────────────────────

def _fetch_detail(sn: str) -> str:
    try:
        resp = requests.get(
            IMP_DETAIL_URL,
            params={'cntntsSn': sn, 'callBackFn': 'fnPopupCallback'},
            headers={'User-Agent': _UA, 'Accept': 'text/html,*/*;q=0.9',
                     'Referer': 'https://impfood.mfds.go.kr/'},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
    except Exception:
        return ''
    soup = BeautifulSoup(resp.text, 'html.parser')
    for tag in soup.find_all(['script', 'style', 'button', 'input']):
        tag.decompose()
    content = (soup.find('div', class_='cont_area') or soup.find('div', id='contents')
               or soup.find('table') or soup.body)
    if not content:
        return ''
    lines = []
    for row in content.find_all('tr'):
        cells = [td.get_text(separator=' ', strip=True) for td in row.find_all(['th', 'td'])]
        line = ' | '.join(c for c in cells if c)
        if line:
            lines.append(line)
    return '\n'.join(lines)[:4000] if lines else content.get_text(separator='\n', strip=True)[:4000]


def _parse_date(row: dict, keys: list) -> str | None:
    for k in keys:
        val = str(row.get(k) or '').strip()
        if not val or val in ('-', 'null', 'None'):
            continue
        for fmt in ('%Y-%m-%d', '%Y.%m.%d', '%Y%m%d'):
            try:
                return datetime.strptime(val[:10] if fmt != '%Y%m%d' else val[:8], fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
    return None


def _upload(local_file: Path) -> bool:
    if not PA_API_TOKEN:
        logger.error('PA_API_TOKEN 이 비어 있습니다. 스크립트 상단에 토큰을 입력하세요.')
        return False
    url = f'https://www.pythonanywhere.com/api/v0/user/{PA_USERNAME}/files/path{PA_DEST_PATH}'
    try:
        with open(local_file, 'rb') as f:
            resp = requests.post(url, headers={'Authorization': f'Token {PA_API_TOKEN}'},
                                 files={'content': f}, timeout=60)
        if resp.status_code in (200, 201):
            logger.info(f'[업로드] 성공 (HTTP {resp.status_code})')
            return True
        logger.error(f'[업로드] 실패 {resp.status_code}: {resp.text[:200]}')
    except Exception as e:
        logger.error(f'[업로드] 예외: {e}')
    return False


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='수입식품 부적합·회수 수집 후 PA 서버로 전송')
    parser.add_argument('--max-pages', type=int, default=0,
                        help='스크래퍼당 최대 페이지 수 (0=전체)')
    parser.add_argument('--dry-run', action='store_true',
                        help='로컬 저장만, 서버 전송 없음')
    args = parser.parse_args()

    items = []
    items.extend(collect_import_recall(max_pages=args.max_pages))
    items.extend(collect_import_insp(max_pages=args.max_pages))

    if not items:
        logger.warning('수집된 데이터 없음')
        return

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    logger.info(f'[저장] {OUTPUT_FILE} → {len(items)}건')

    if args.dry_run:
        logger.info('[dry-run] 서버 전송 생략')
        return

    if _upload(OUTPUT_FILE):
        print('\n✅ 업로드 완료 — PA 스케줄러가 다음 실행 시 자동으로 DB에 반영합니다.')
    else:
        print('\n❌ 업로드 실패 — 로그를 확인하세요.')


if __name__ == '__main__':
    main()
