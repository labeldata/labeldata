import logging
import requests
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.utils.timezone import now
from .models import ApiEndpoint
from v1.label.models import FoodItem, ImportedFood


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
            # 예시로 C002에서는 추가로 custom_field를 업데이트한다고 가정
            # 필요에 따라 다른 컬럼도 추가 가능
        },
    },
    'IMPORTED_FOOD': {
        'model': ImportedFood,  # 반드시 label.models.ImportedFood를 사용해야 함
        'fields': {
            'dcl_prduct_se_cd_nm': 'DCL_PRDUCT_SE_CD_NM',
            'bsn_ofc_name': 'BSN_OFC_NM',
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
    """
    defaults = {}
    for model_field, mapping_tuple in field_mapping.items():
        # 'unique_key'는 lookup용이므로 defaults에는 포함하지 않습니다.
        if model_field == 'unique_key':
            continue
        model_field_name, api_key = mapping_tuple
        # API 응답에 해당 키가 없으면 빈 문자열을 기본값으로 사용합니다.
        defaults[model_field_name] = item.get(api_key, '')
    defaults['update_datetime'] = now()
    return defaults

def call_api_endpoint(request, pk):
    """API 데이터를 호출하여 저장 (서비스별 매핑 정보를 SERVICE_MAPPING으로 관리)"""
    endpoint = get_object_or_404(ApiEndpoint, pk=pk)
    start_position = 1
    batch_size = 1000
    total_saved = 0

    logger.info(f"Starting API call for endpoint: {endpoint.name}")

    # service_name이 없으면(예: 수입식품) 별도 처리
    if not endpoint.service_name:
        # 수입식품 API 호출로 위임
        return call_imported_food_api_endpoint(request, pk)

    service_info = SERVICE_MAPPING.get(endpoint.service_name)
    if not service_info:
        logger.error(f"지원하지 않는 서비스 이름: {endpoint.service_name}")
        return JsonResponse({"error": f"지원하지 않는 서비스 이름: {endpoint.service_name}"}, status=500)

    ModelClass = service_info['model']
    field_mapping = service_info['fields']

    try:
        while True:
            # 예: 2025년 2월 1일 이후 자료만 가져옴
            change_date = "20250211"
            api_url = f"{endpoint.url}/{endpoint.api_key.key}/{endpoint.service_name}/json/{start_position}/{start_position + batch_size - 1}/CHNG_DT={change_date}"
            logger.info(f"Calling API at URL: {api_url}")

            response = requests.get(api_url, timeout=300)
            logger.info(f"API Response Status: {response.status_code}")
            logger.debug(f"API Raw Response Text: {response.text[:500]}")

            if response.status_code != 200:
                logger.error(f"Unexpected status code: {response.status_code}")
                return JsonResponse({"error": f"Unexpected status code: {response.status_code}"}, status=500)

            try:
                data = response.json()
                logger.debug(f"Parsed JSON Data: {str(data)[:500]}")
            except ValueError:
                logger.error(f"Invalid JSON response: {response.text}")
                return JsonResponse({"error": "Invalid JSON response"}, status=500)

            if endpoint.service_name not in data:
                logger.error(f"Expected service name '{endpoint.service_name}' not found in response: {list(data.keys())}")
                return JsonResponse({"error": f"Invalid service name: {endpoint.service_name}"}, status=500)

            items = data.get(endpoint.service_name, {}).get("row", [])
            logger.info(f"Number of items fetched: {len(items)}")

            for item in items:
                try:
                    # 고유 키(lookup) 필드: 모델 필드명과 API 응답 키를 사용
                    unique_field_name, unique_api_key = field_mapping['unique_key']
                    unique_value = item.get(unique_api_key)

                    defaults = build_defaults(field_mapping, item)
                    instance, created = ModelClass.objects.update_or_create(
                        **{unique_field_name: unique_value},
                        defaults=defaults
                    )
                    print(f"Created: {created} / 제품명 : {instance.prdlst_nm if hasattr(instance, 'prdlst_nm') else 'N/A'}")
                except Exception as e:
                    logger.error(f"Failed to save item {item.get('PRDLST_NM')}: {e}")

            total_saved += len(items)

            if not items or len(items) < batch_size:
                logger.info("No more items to fetch. Exiting loop.")
                break

            start_position += batch_size

        # 호출 상태 업데이트
        endpoint.last_called_at = now()
        endpoint.last_status = "success"
        endpoint.save()

        logger.info(f"Total saved items: {total_saved}")
        return JsonResponse({"success": True, "total_saved": total_saved})

    except requests.exceptions.RequestException as e:
        logger.error(f"API call failed: {e}")
        endpoint.last_status = "failure"
        endpoint.save()
        return JsonResponse({"error": str(e)}, status=500)

def call_imported_food_api_endpoint(request, pk):
    """
    수입식품(ImportedFood) API 데이터를 호출하여 저장
    """
    endpoint = get_object_or_404(ApiEndpoint, pk=pk)
    logger.info(f"Starting ImportedFood API call for endpoint: {endpoint.name}")

    from label.models import ImportedFood

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
        'expirde_bdgin_dtm': 'EXPIRDE_BEGIN_DTM',
        'expirde_end_dtm': 'EXPIRDE_END_DTM',
    }

    service_key = endpoint.api_key.key
    base_url = endpoint.url
    num_of_rows = 100
    max_pages = 100
    start_date = '20250101'
    end_date = '20251201'
    total_saved = 0
    headers = None

    session = requests.Session()
    debug_responses = []

    categories = ["가공식품", "식품첨가물"]

    try:
        for category in categories:
            for page_no in range(1, max_pages + 1):
                url = (
                    f"{base_url}?serviceKey={service_key}"
                    f"&pageNo={page_no}&numOfRows={num_of_rows}&type=json"
                    f"&dclPrductSeCdNm={category}"
                    f"&procsDtmStart={start_date}&procsDtmEnd={end_date}"
                )
                print(url)
                logger.info(f"ImportedFood API 요청: {url}")
                response = session.get(url, timeout=60)
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
                    data = response.json()
                except Exception as e:
                    logger.error(f"JSON 파싱 오류: {e}")
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
                    # 중복 체크 기준 필드 (strip, None 처리, 모두 str로 변환)
                    lookup = dict(
                        bsn_ofc_name=(obj.get('BSN_OFC_NM') or '').strip(),
                        prduct_korean_nm=(obj.get('PRDUCT_KOREAN_NM') or '').strip(),
                        procs_dtm=(obj.get('PROCS_DTM') or '').strip(),
                        ovsmnfst_nm=(obj.get('OVSMNFST_NM') or '').strip(),
                    )
                    # defaults에서 lookup에 포함된 필드는 제거 (중복 방지)
                    defaults = {
                        model_field: obj.get(api_field, '')
                        for model_field, api_field in field_mapping.items()
                        if model_field not in lookup
                    }
                    # DB에도 동일하게 strip해서 비교
                    qs = ModelClass.objects.filter(
                        bsn_ofc_name=lookup['bsn_ofc_name'],
                        prduct_korean_nm=lookup['prduct_korean_nm'],
                        procs_dtm=lookup['procs_dtm'],
                        ovsmnfst_nm=lookup['ovsmnfst_nm'],
                    )
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
