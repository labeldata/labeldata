import logging
import requests
import xml.etree.ElementTree as ET
import time
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.utils.timezone import now
from .models import ApiEndpoint
from v1.label.models import FoodItem, ImportedFood, AgriculturalProduct
from datetime import datetime, timedelta
from django.db import close_old_connections  # 추가
from django.http import HttpResponseNotFound, HttpResponseForbidden, HttpResponseServerError
from django.conf import settings
from django.http import Http404
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required  # 추가

# 로거 설정
logger = logging.getLogger(__name__)

# 회원가입
def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "회원가입 완료!")
            return redirect('label:post_list')
    else:
        form = UserCreationForm()
    return render(request, 'common/signup.html', {'form': form})

# 로그인
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, "로그인 성공!")
            return redirect('label:post_list')
    else:
        form = AuthenticationForm()
    return render(request, 'common/login.html', {'form': form})

# 로그아웃
def logout_view(request):
    logout(request)
    messages.info(request, "로그아웃되었습니다.")
    return redirect('common:login')


# 서비스별 매핑 정보를 하나의 딕셔너리로 관리
# 각 항목은 서비스 이름을 키로 사용하며, 해당 값은 사용할 모델과 필드 매핑 정보를 포함합니다.
# 필드 매핑은 튜플 형식으로 (모델 필드명, API 응답 키)를 지정합니다.
SERVICE_MAPPING = {
    'I1250': {
        'model': FoodItem,
        'fields': {
            'unique_key': ('prdlst_report_no', 'PRDLST_REPORT_NO'),
            'lcns_no': ('lcns_no', 'LCNS_NO'),
            'bssh_nm': ('bssh_nm', 'BSSH_NM'),
            'prms_dt': ('prms_dt', 'PRMS_DT'),
            'prdlst_nm': ('prdlst_nm', 'PRDLST_NM'),
            'prdlst_dcnm': ('prdlst_dcnm', 'PRDLST_DCNM'),
            'production': ('production', 'PRODUCTION'),
            'hieng_lntrt_dvs_yn': ('hieng_lntrt_dvs_yn', 'HIENG_LNTRT_DVS_NM'),
            'child_crtfc_yn': ('child_crtfc_yn', 'CHILD_CRTFC_YN'),
            'pog_daycnt': ('pog_daycnt', 'POG_DAYCNT'),
            'induty_cd_nm': ('induty_cd_nm', 'INDUTY_CD_NM'),
            'qlity_mntnc_tmlmt_daycnt': ('qlity_mntnc_tmlmt_daycnt', 'QLITY_MNTNC_TMLMT_DAYCNT'),
            'usages': ('usages', 'USAGE'),
            'prpos': ('prpos', 'PRPOS'),
            'dispos': ('dispos', 'DISPOS'),
            'frmlc_mtrqlt': ('frmlc_mtrqlt', 'FRMLC_MTRQLT'),
            'last_updt_dtm': ('last_updt_dtm', 'LAST_UPDT_DTM'),
        },
    },
    'C002': {
        'model': FoodItem,
        'fields': {
            'unique_key': ('prdlst_report_no', 'PRDLST_REPORT_NO'),
            'lcns_no': ('lcns_no', 'LCNS_NO'),
            'bssh_nm': ('bssh_nm', 'BSSH_NM'),
            'prms_dt': ('prms_dt', 'PRMS_DT'),
            'prdlst_nm': ('prdlst_nm', 'PRDLST_NM'),
            'rawmtrl_nm': ('rawmtrl_nm', 'RAWMTRL_NM'),
            'rawmtrl_ordno': ('rawmtrl_ordno', 'RAWMTRL_ORDNO'),  # 추가된 필드
            # 예시로 C002에서는 추가로 custom_field를 업데이트한다고 가정
            # 필요에 따라 다른 컬럼도 추가 가능
        },
    },
    'I1310': {
        'model': FoodItem,
        'fields': {
            'unique_key': ('prdlst_report_no', 'PRDLST_REPORT_NO'),
            'lcns_no': ('lcns_no', 'LCNS_NO'),
            'bssh_nm': ('bssh_nm', 'BSSH_NM'),
            'prms_dt': ('prms_dt', 'PRMS_DT'),
            'prdlst_nm': ('prdlst_nm', 'PRDLST_NM'),
            'prdlst_dcnm': ('prdlst_dcnm', 'PRDLST_DCNM'),
            'production': ('production', 'PRODUCTION'),
            'hieng_lntrt_dvs_yn': ('hieng_lntrt_dvs_yn', 'HIENG_LNTRT_DVS_NM'),
            'child_crtfc_yn': ('child_crtfc_yn', 'CHILD_CRTFC_YN'),
            'pog_daycnt': ('pog_daycnt', 'POG_DAYCNT'),
            'induty_cd_nm': ('induty_cd_nm', 'INDUTY_CD_NM'),
            'qlity_mntnc_tmlmt_daycnt': ('qlity_mntnc_tmlmt_daycnt', 'QLITY_MNTNC_TMLMT_DAYCNT'),
            'usages': ('usages', 'USAGE'),
            'prpos': ('prpos', 'PRPOS'),
            'dispos': ('dispos', 'DISPOS'),
            'frmlc_mtrqlt': ('frmlc_mtrqlt', 'FRMLC_MTRQLT'),
            'last_updt_dtm': ('last_updt_dtm', 'LAST_UPDT_DTM'),
        },
    },
    'C006': {
        'model': FoodItem,
        'fields': {
            'unique_key': ('prdlst_report_no', 'PRDLST_REPORT_NO'),
            'lcns_no': ('lcns_no', 'LCNS_NO'),
            'bssh_nm': ('bssh_nm', 'BSSH_NM'),
            'prms_dt': ('prms_dt', 'PRMS_DT'),
            'prdlst_nm': ('prdlst_nm', 'PRDLST_NM'),
            'rawmtrl_nm': ('rawmtrl_nm', 'RAWMTRL_NM'),
            'rawmtrl_ordno': ('rawmtrl_ordno', 'RAWMTRL_ORDNO'),  # 추가된 필드
            # 예시로 C002에서는 추가로 custom_field를 업데이트한다고 가정
            # 필요에 따라 다른 컬럼도 추가 가능
        },
    },
    'IMPORTED_FOOD': {
        'model': ImportedFood,  # 반드시 label.models.ImportedFood를 사용해야 함
        'fields': {
            'dcl_prduct_se_cd_nm': 'DCL_PRDUCT_SE_CD_NM',
            'bsn_ofc_name': 'BSN_OFC_NAME',
            'prduct_korean_nm': 'PRDUCT_KOREAN_NM',
            'prduct_nm': 'PRDUCT_NM',
            'expirde_dtm': 'EXPIRDE_DTM',
            'procs_dtm': 'PROCS_DTM',
            'ovsmnfst_nm': 'OVSMNFST_NM',
            'itm_nm': 'ITM_NM',
            'xport_ntncd_nm': 'XPORT_NTNCD_NM',
            'mnf_ntncn_nm': 'MNF_NTNCN_NM',
            'korlabel': 'KORLABEL',
            'irdnt_nm': 'IRDNT_NM',
            'expirde_bdgin_dtm': 'EXPIRDE_BDGIN_DTM',
            'expirde_end_dtm': 'EXPIRDE_END_DTM',
        }
    },
    'AGRICULTURAL_PRODUCT': {
        'model': AgriculturalProduct,
        'fields': {
            'unique_key': ('rprsnt_rawmtrl_nm', 'RPRSNT_RAWMTRL_NM'),
            'lclas_nm': ('lclas_nm', 'LCLAS_NM'),
            'mlsfc_nm': ('mlsfc_nm', 'MLSFC_NM'),
            'rprsnt_rawmtrl_nm': ('rprsnt_rawmtrl_nm', 'RPRSNT_RAWMTRL_NM'),
            'rawmtrl_ncknm': ('rawmtrl_ncknm', 'RAWMTRL_NCKNM'),
            'eng_nm': ('eng_nm', 'ENG_NM'),
            'scnm': ('scnm', 'SCNM'),
            'regn_cd_nm': ('regn_cd_nm', 'REGN_CD_NM'),
            'rawmtrl_stats_cd_nm': ('rawmtrl_stats_cd_nm', 'RAWMTRL_STATS_CD_NM'),
            'use_cnd_nm': ('use_cnd_nm', 'USE_CND_NM'),
        }
    },
    # 다른 서비스나 모델이 추가되면 아래와 같이 확장하면 됨.
    # 'SERVICE_NAME': {
    #     'model': SomeOtherModel,
    #     'fields': {
    #         'unique_key': ('field_name', 'API_KEY'),
    #         ...
    #     },
    # },
}

def build_defaults(field_mapping, item):
    """
    주어진 field_mapping 정보를 사용하여 defaults 딕셔너리를 생성합니다.
    field_mapping: (모델 필드명, API 응답 키) 튜플들이 포함된 딕셔너리
    unique_key에 해당하는 필드는 defaults에서 제외합니다.
    """
    defaults = {}
    unique_field_name = None
    if 'unique_key' in field_mapping:
        unique_field_name = field_mapping['unique_key'][0]
    for model_field, mapping_tuple in field_mapping.items():
        if model_field == 'unique_key':
            continue
        model_field_name, api_key = mapping_tuple
        if unique_field_name and model_field_name == unique_field_name:
            continue  # lookup에 이미 사용된 필드는 defaults에서 제외
        defaults[model_field_name] = item.get(api_key, '')
    return defaults

def call_api_endpoint(request, pk):
    """API 데이터를 호출하여 저장 (서비스별 매핑 정보를 SERVICE_MAPPING으로 관리)"""
    endpoint = get_object_or_404(ApiEndpoint, pk=pk)
    # 플래그가 'Y'일 때만 start_position을 1로 초기화
    if endpoint.use_reset_start_position == 'Y':
        endpoint.last_start_position = 1
        endpoint.save()
    # 이어받기: last_start_position에서 시작
    start_position = endpoint.last_start_position
    batch_size = 1000
    total_saved = 0

    # 시작일자(YYYYMMDD) 사용 (자료형 안전하게 변환)
    try:
        start_date_int = int(endpoint.start_date)
    except (TypeError, ValueError):
        start_date_int = None

    if start_date_int == 0:
        change_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    elif start_date_int == 1:
        change_date = datetime.now().strftime("%Y%m%d")
    else:
        change_date = endpoint.start_date or datetime.now().strftime("%Y%m%d")
    logger.info(f"Starting API call for endpoint: {endpoint.name}, change_date: {change_date}")

        # service_name이 없거나 특정 서비스명일 때 별도 처리
    if not endpoint.service_name or endpoint.service_name == "IMPORTED_FOOD":
        # 수입식품 API 호출로 위임 (start_date 전달)
        return call_imported_food_api_endpoint(request, pk, start_date=change_date)
    elif endpoint.service_name == "AGRICULTURAL_PRODUCT":
        return call_agricultural_product_api_endpoint(request, pk)

    service_info = SERVICE_MAPPING.get(endpoint.service_name)
    if not service_info:
        logger.error(f"지원하지 않는 서비스 이름: {endpoint.service_name}")
        return JsonResponse({"error": f"지원하지 않는 서비스 이름: {endpoint.service_name}"}, status=500)

    ModelClass = service_info['model']
    field_mapping = service_info['fields']

    try:
        retry_count = 0
        max_retries = 3
        while True:
            # CHNG_DT에 시작일자 사용
            api_url = f"{endpoint.url}/{endpoint.api_key.key}/{endpoint.service_name}/json/{start_position}/{start_position + batch_size - 1}/CHNG_DT={change_date}"
            logger.info(f"Calling API at URL: {api_url}")

            for attempt in range(max_retries):
                try:
                    response = requests.get(api_url, timeout=60)
                    break
                except requests.exceptions.RequestException as e:
                    logger.warning(f"API 요청 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(3)
                    else:
                        logger.error(f"API 요청 최대 재시도 초과: {api_url}")
                        endpoint.last_start_position = start_position
                        endpoint.last_status = "failure"
                        endpoint.save()
                        return JsonResponse({"error": str(e)}, status=500)

            logger.info(f"API Response Status: {response.status_code}")
            logger.debug(f"API Raw Response Text: {response.text[:500]}")

            if response.status_code != 200:
                logger.error(f"Unexpected status code: {response.status_code}")
                return JsonResponse({"error": f"Unexpected status code: {response.status_code}"}, status=500)

            try:
                if not response.text.strip().startswith("{"):
                    if response.text.strip().startswith("<OpenAPI_ServiceResponse"):
                        logger.error("OpenAPI XML 에러 응답, 페이지 건너뜀")
                        continue  # XML 에러 응답은 무시하고 다음 페이지로
                    else:
                        logger.error("알 수 없는 비JSON 응답, 페이지 건너뜀")
                        continue

                data = response.json()
                logger.debug(f"Parsed JSON Data: {str(data)[:500]}")

                result = data.get(endpoint.service_name, {}).get("RESULT", {})
                code = result.get("CODE", "")
                message = result.get("MSG", "")

                logger.warning(f"API 응답 코드: {code} - {message} 호출 키: {endpoint.api_key.key}")

                # ERROR-500 재시도 로직
                if code == "ERROR-500":
                    retry_count += 1
                    logger.warning(f"API 서버 오류: {message} (code: {code}), 재시도 {retry_count}/{max_retries}")
                    if retry_count < max_retries:
                        time.sleep(3)
                        continue
                    else:
                        endpoint.last_start_position = start_position
                        endpoint.last_status = "failure"
                        endpoint.save()
                        return JsonResponse({"error": f"API 서버 오류: {message}", "code": code}, status=500)

                # 종료 조건 처리
                if code == "INFO-200":
                    logger.info("해당하는 데이터가 없습니다. 종료합니다.")
                    break

                if code == "INFO-300":
                    logger.warning("유효 호출 건수 초과. 이어받기를 위해 중단.")
                    endpoint.last_start_position = start_position
                    endpoint.last_status = "failure"
                    endpoint.save()
                    return JsonResponse({"error": "호출건수 초과로 중단됨", "code": code, "message": message}, status=429)

                if code in ("INFO-100", "INFO-400"):
                    endpoint.last_status = "failure"
                    endpoint.save()
                    return JsonResponse({"error": "인증/권한 오류", "code": code, "message": message}, status=403)

                if code.startswith("ERROR-") or code == "":
                    endpoint.last_start_position = start_position
                    endpoint.last_status = "failure"
                    endpoint.save()
                    return JsonResponse({"error": f"API 오류 발생", "code": code, "message": message}, status=500)

            except ValueError:
                logger.error(f"Invalid JSON response: {response.text}")
                return JsonResponse({"error": "Invalid JSON response"}, status=500)

            if endpoint.service_name not in data:
                logger.error(f"Expected service name '{endpoint.service_name}' not found in response: {list(data.keys())}")
                return JsonResponse({"error": f"Invalid service name: {endpoint.service_name}"}, status=500)

            items = data.get(endpoint.service_name, {}).get("row", [])
            logger.info(f"Number of items fetched: {len(items)} (change_date: {change_date})")
            for item in items:
                close_old_connections()  # DB 연결 유지
                try:
                    # 고유 키(lookup) 필드: 모델 필드명과 API 응답 키를 사용
                    unique_field_name, unique_api_key = field_mapping['unique_key']
                    unique_value = item.get(unique_api_key)

                    defaults = build_defaults(field_mapping, item)
                    
                    # 원재료명 정렬 로직 (C002, C006에서 rawmtrl_ordno가 있을 때)
                    if 'rawmtrl_ordno' in defaults and defaults.get('rawmtrl_ordno'):
                        rawmtrl_nm = defaults.get('rawmtrl_nm', '')
                        rawmtrl_ordno = defaults.get('rawmtrl_ordno', '')
                        
                        if rawmtrl_nm and rawmtrl_ordno:
                            try:
                                # 줄바꿈 문자를 공백으로 치환 (원재료명에 \n이 포함된 경우 처리)
                                rawmtrl_nm = rawmtrl_nm.replace('\n', '').replace('\r', '')
                                
                                # 괄호를 고려한 원재료명 분리 함수
                                def split_with_parentheses(text, separator):
                                    """괄호 밖의 separator만 구분자로 사용"""
                                    result = []
                                    current = []
                                    depth = 0
                                    i = 0
                                    
                                    while i < len(text):
                                        char = text[i]
                                        
                                        if char == '(':
                                            depth += 1
                                            current.append(char)
                                        elif char == ')':
                                            depth -= 1
                                            current.append(char)
                                        elif depth == 0 and text[i:i+len(separator)] == separator:
                                            # 괄호 밖에서 separator를 만났을 때
                                            result.append(''.join(current).strip())
                                            current = []
                                            i += len(separator) - 1  # separator 길이만큼 건너뛰기
                                        else:
                                            current.append(char)
                                        
                                        i += 1
                                    
                                    # 마지막 항목 추가
                                    if current:
                                        result.append(''.join(current).strip())
                                    
                                    return [x for x in result if x]  # 빈 문자열 제거
                                
                                # 원재료명: ", "로 분리 (괄호 고려), 원재료명 순서: ","로 분리
                                ingredients = split_with_parentheses(rawmtrl_nm, ', ')
                                orders = [x.strip() for x in rawmtrl_ordno.split(',') if x.strip()]
                                
                                # 순서가 숫자인지 확인하고 정렬
                                if len(ingredients) == len(orders):
                                    # (순서, 원재료명) 튜플 리스트 생성
                                    paired = list(zip(orders, ingredients))
                                    # 순서를 숫자로 변환하여 정렬
                                    paired_sorted = sorted(paired, key=lambda x: int(x[0]) if x[0].isdigit() else 999)
                                    # 정렬된 원재료명만 추출
                                    sorted_ingredients = [pair[1] for pair in paired_sorted]
                                    # ", "로 합쳐서 저장
                                    defaults['rawmtrl_nm_sorted'] = ', '.join(sorted_ingredients)
                                    logger.info(f"원재료명 정렬 완료: {unique_value}")
                                else:
                                    # 개수가 다르면 원본 그대로 저장
                                    defaults['rawmtrl_nm_sorted'] = rawmtrl_nm
                                    logger.warning(f"원재료명과 순서 개수 불일치: {unique_value} | 원재료({len(ingredients)}개): {rawmtrl_nm[:200]} | 순서({len(orders)}개): {rawmtrl_ordno}")
                            except Exception as e:
                                # 정렬 실패 시 원본 그대로 저장
                                defaults['rawmtrl_nm_sorted'] = rawmtrl_nm
                                logger.error(f"원재료명 정렬 실패 {unique_value}: {e}")
                        else:
                            defaults['rawmtrl_nm_sorted'] = rawmtrl_nm
                    
                    instance, created = ModelClass.objects.update_or_create(
                        **{unique_field_name: unique_value},
                        defaults=defaults
                    )
                except Exception as e:
                    logger.error(f"Failed to save item {item.get('PRDLST_NM')}: {e}")

            total_saved += len(items)

            if not items or len(items) < batch_size:
                logger.info("No more items to fetch. Exiting loop.")
                break

            start_position += batch_size
            endpoint.last_start_position = start_position
            endpoint.save()

        # 호출 상태 업데이트
        endpoint.last_called_at = now()
        endpoint.last_status = "success"
        endpoint.save()

        logger.info(f"Total saved items: {total_saved}, change_date: {change_date}")
        return JsonResponse({"success": True, "total_saved": total_saved})

    except requests.exceptions.RequestException as e:
        logger.error(f"API call failed: {e}")
        endpoint.last_start_position = start_position
        endpoint.last_status = "failure"
        endpoint.save()
        return JsonResponse({"error": str(e)}, status=500)


def call_imported_food_api_endpoint(request, pk, start_date=None):
    """
    수입식품(ImportedFood) API 데이터를 호출하여 저장
    """
    endpoint = get_object_or_404(ApiEndpoint, pk=pk)
    logger.info(f"Starting ImportedFood API call for endpoint: {endpoint.name}")

    ModelClass = ImportedFood
    field_mapping = {
        'dcl_prduct_se_cd_nm': 'DCL_PRDUCT_SE_CD_NM',
        'bsn_ofc_name': 'BSN_OFC_NAME',
        'prduct_korean_nm': 'PRDUCT_KOREAN_NM',
        'prduct_nm': 'PRDUCT_NM',
        'expirde_dtm': 'EXPIRDE_DTM',
        'procs_dtm': 'PROCS_DTM',
        'ovsmnfst_nm': 'OVSMNFST_NM',
        'itm_nm': 'ITM_NM',
        'xport_ntncd_nm': 'XPORT_NTNCD_NM',
        'mnf_ntncn_nm': 'MNF_NTNCN_NM',
        'korlabel': 'KORLABEL',
        'irdnt_nm': 'IRDNT_NM',
        'expirde_bdgin_dtm': 'EXPIRDE_BDGIN_DTM',
        'expirde_end_dtm': 'EXPIRDE_END_DTM',
    }

    service_key = endpoint.api_key.key
    base_url = endpoint.url
    num_of_rows = 100
    max_pages = 1000

    # procs_dtm_start도 동일하게 처리
    try:
        start_date_int = int(endpoint.start_date)
    except (TypeError, ValueError):
        start_date_int = None

    if start_date_int == 0:
        procs_dtm_start = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    elif start_date_int == 1:
        procs_dtm_start = datetime.now().strftime("%Y%m%d")
    else:
        procs_dtm_start = endpoint.start_date or datetime.now().strftime("%Y%m%d")

    end_date = '21251201'
    total_saved = 0
    session = requests.Session()
    debug_responses = []
    categories = ["가공식품", "식품첨가물", "축산물"]

    try:
        for category in categories:
            for page_no in range(1, max_pages + 1):
                url = (
                    f"{base_url}?serviceKey={service_key}"
                    f"&pageNo={page_no}&numOfRows={num_of_rows}&type=json"
                    f"&dclPrductSeCdNm={category}"
                    f"&procsDtmStart={procs_dtm_start}&procsDtmEnd={end_date}"
                )
                logger.info(f"ImportedFood API 요청: {url}")

                # 최대 3회 재시도
                for attempt in range(3):
                    try:
                        response = session.get(url, timeout=60)
                        break  # 성공 시 반복 탈출
                    except requests.exceptions.RequestException as e:
                        logger.warning(f"{url} 요청 실패 (시도 {attempt + 1}/3): {e}")
                        if attempt < 2:
                            time.sleep(5)
                        else:
                            raise Exception(f"최대 재시도 횟수 초과: {url}")

                debug_responses.append({
                    "category": category,
                    "page": page_no,
                    "status_code": response.status_code,
                    "text_head": response.text[:1000]
                })

                if response.status_code != 200:
                    logger.error(f"Unexpected status code: {response.status_code}")
                    break

                try:
                    if not response.text.strip().startswith("{"):
                        if response.text.strip().startswith("<OpenAPI_ServiceResponse"):
                            logger.error("OpenAPI XML 에러 응답, 페이지 건너뜀")
                            continue  # XML 에러 응답은 무시하고 다음 페이지로
                        else:
                            logger.error("알 수 없는 비JSON 응답, 페이지 건너뜀")
                            continue
                    data = response.json()
                except Exception as e:
                    logger.error(f"JSON 파싱 오류: {e}")
                    logger.error(f"응답 내용:\n{response.text[:500]}")
                    break

                body = data.get("body", {})
                items_container = body.get("items", [])
                if isinstance(items_container, dict):
                    items = items_container.get("item", [])
                elif isinstance(items_container, list):
                    items = items_container
                else:
                    items = []

                if isinstance(items, dict):
                    items = [items]
                if items and isinstance(items[0], dict) and "item" in items[0]:
                    items = [i["item"] for i in items if isinstance(i, dict) and "item" in i]

                if not items:
                    logger.info(f"No more items at page {page_no} for category {category}.")
                    break

                for obj in items:
                    close_old_connections()  # DB 연결 유지
                    lookup = {
                        'bsn_ofc_name': (obj.get('BSN_OFC_NAME') or '').strip(),
                        'prduct_korean_nm': (obj.get('PRDUCT_KOREAN_NM') or '').strip(),
                        'procs_dtm': (obj.get('PROCS_DTM') or '').strip(),
                        'ovsmnfst_nm': (obj.get('OVSMNFST_NM') or '').strip(),
                    }
                    defaults = {
                        model_field: obj.get(api_field, '')
                        for model_field, api_field in field_mapping.items()
                        if model_field not in lookup
                    }
                    qs = ModelClass.objects.filter(**lookup)
                    if qs.exists():
                        qs.update(**defaults)
                    else:
                        ModelClass.objects.create(**lookup, **defaults)
                        total_saved += 1

                logger.info(f"Page {page_no} 저장 완료 (category={category})")

        endpoint.last_called_at = now()
        endpoint.last_status = "success"
        endpoint.save()
        logger.info(f"Total ImportedFood saved: {total_saved}")
        return JsonResponse({
            "success": True,
            "total_saved": total_saved,
            "debug_responses": debug_responses[:3]
        })
    except Exception as e:
        logger.error(f"ImportedFood API call failed: {e}")
        endpoint.last_status = "failure"
        endpoint.save()
        return JsonResponse({"error": str(e)}, status=500)

def call_agricultural_product_api_endpoint(request, pk):
    """
    농수산물(AgriculturalProduct) API 데이터를 호출하여 저장
    """
    endpoint = get_object_or_404(ApiEndpoint, pk=pk)
    logger.info(f"Starting AgriculturalProduct API call for endpoint: {endpoint.name}")

    ModelClass = AgriculturalProduct
    field_mapping = SERVICE_MAPPING['AGRICULTURAL_PRODUCT']['fields']

    service_key = endpoint.api_key.key
    base_url = endpoint.url
    num_of_rows = 100
    max_pages = 100
    total_saved = 0
    session = requests.Session()
    debug_responses = []

    try:
        for page_no in range(1, max_pages + 1):
            params = {
                'serviceKey': service_key,
                'rprsnt_rawmtrl_nm': '',
                'pageNo': str(page_no),
                'numOfRows': str(num_of_rows),
                'type': 'json'
            }
            logger.info(f"AgriculturalProduct API 요청: {base_url} params={params}")
            response = session.get(base_url, params=params, timeout=60)
            debug_responses.append({
                "page": page_no,
                "status_code": response.status_code,
                "text_head": response.text[:1000]
            })
            if response.status_code != 200:
                logger.error(f"Unexpected status code: {response.status_code}")
                break

            try:
                if not response.text.strip().startswith("{"):
                    if response.text.strip().startswith("<OpenAPI_ServiceResponse"):
                        logger.error("OpenAPI XML 에러 응답, 페이지 건너뜀")
                        continue  # XML 에러 응답은 무시하고 다음 페이지로
                    else:
                        logger.error("알 수 없는 비JSON 응답, 페이지 건너뜀")
                        continue
                data = response.json()
            except Exception as e:
                logger.error(f"JSON 파싱 오류: {e}")
                break

            body = data.get("body", {})
            items = body.get("items", [])
            if isinstance(items, dict):
                items = items.get("item", [])
            elif isinstance(items, list):
                pass  # 이미 리스트
            else:
                items = []
            if isinstance(items, dict):
                items = [items]
            if not items:
                logger.info(f"No more items at page {page_no}.")
                break

            for obj in items:
                close_old_connections()  # DB 연결 유지
                unique_field_name, unique_api_key = field_mapping['unique_key']
                unique_value = (obj.get(unique_api_key, '') or '').strip()
                lookup = {unique_field_name: unique_value}
                defaults = build_defaults(field_mapping, obj)
                qs = ModelClass.objects.filter(**lookup)
                if qs.exists():
                    qs.update(**defaults)
                else:
                    ModelClass.objects.create(**lookup, **defaults)
                    total_saved += 1
            logger.info(f"Page {page_no} 저장 완료")
        endpoint.last_called_at = now()
        endpoint.last_status = "success"
        endpoint.save()
        logger.info(f"Total AgriculturalProduct saved: {total_saved}")
        return JsonResponse({
            "success": True,
            "total_saved": total_saved,
            "debug_responses": debug_responses[:3]
        })
    except Exception as e:
        logger.error(f"AgriculturalProduct API call failed: {e}")
        endpoint.last_status = "failure"
        endpoint.save()
        return JsonResponse({"error": str(e)}, status=500)

def custom_404(request, exception):
    """커스텀 404 에러 페이지 - 403도 통합 처리"""
    return render(request, '404.html', status=404)

def custom_403(request, exception):
    """403 에러를 404로 위장 (보안상 이유)"""
    # 보안을 위해 403도 404로 처리
    return render(request, '404.html', status=404)

def custom_500(request):
    """커스텀 500 에러 페이지"""
    return render(request, '500.html', status=500)

# 사용자 친화적인 403 처리가 필요한 경우를 위한 별도 뷰
def permission_denied_view(request):
    """명시적으로 403을 보여주고 싶은 경우 사용"""
    return render(request, '403.html', status=403)



@login_required
def show_404_page(request):
    """404 에러 페이지 직접 표시 (개발용)"""
    return render(request, '404.html', status=404)

@login_required
def show_403_page(request):
    """403 에러 페이지 직접 표시 (개발용)"""
    return render(request, '403.html', status=403)

@login_required
def show_500_page(request):
    """500 에러 페이지 직접 표시 (개발용)"""
    return render(request, '500.html', status=500)
