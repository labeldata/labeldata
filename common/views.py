import logging
import requests
import time
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.utils.timezone import now
from .models import ApiEndpoint
from label.models import FoodItem


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

# # 각 모델별 필드 매핑 정의 (예시)
# # 'unique_key'는 각 모델에서 update_or_create시 사용될 고유 키(API 응답의 키에 해당)
# FIELD_MAPPING = {
#     FoodItem: {
#         'unique_key': ('prdlst_report_no', 'PRDLST_REPORT_NO'),  # lookup 시에는 'prdlst_report_no' 사용, 값은 'PRDLST_REPORT_NO' 키에서 추출
#         'lcns_no': ('lcns_no', 'LCNS_NO'),
#         'bssh_nm': ('bssh_nm', 'BSSH_NM'),
#         'prms_dt': ('prms_dt', 'PRMS_DT'),
#         'prdlst_nm': ('prdlst_nm', 'PRDLST_NM'),
#         'prdlst_dcnm': ('prdlst_dcnm', 'PRDLST_DCNM'),
#         'production': ('production', 'PRODUCTION'),
#         'hieng_lntrt_dvs_yn': ('hieng_lntrt_dvs_yn', 'HIENG_LNTRT_DVS_NM'),
#         'child_crtfc_yn': ('child_crtfc_yn', 'CHILD_CRTFC_YN'),
#         'pog_daycnt': ('pog_daycnt', 'POG_DAYCNT'),
#         'induty_cd_nm': ('induty_cd_nm', 'INDUTY_CD_NM'),
#         'qlity_mntnc_tmlmt_daycnt': ('qlity_mntnc_tmlmt_daycnt', 'QLITY_MNTNC_TMLMT_DAYCNT'),
#         'usages': ('usages', 'USAGE'),
#         'prpos': ('prpos', 'PRPOS'),
#         'dispos': ('dispos', 'DISPOS'),
#         'frmlc_mtrqlt': ('frmlc_mtrqlt', 'FRMLC_MTRQLT'),
#         'rawmtrl_nm': ('rawmtrl_nm', 'RAWMTRL_NM'),
#         'last_updt_dtm': ('last_updt_dtm', 'LAST_UPDT_DTM'),
#     },
#     # 예시: BeverageItem 모델에 대해 필드 매핑 (실제 필드명에 맞게 수정)
#     # BeverageItem: {
#     #     'unique_key': 'report_no',
#     #     'name': 'name',
#     #     'volume': 'volume',
#     #     'manufacturer': 'manufacturer',
#     #     # 기타 필드 매핑...
#     # },
# }
# def build_defaults(ModelClass, item):
#     """
#     주어진 ModelClass에 맞는 defaults 딕셔너리를 생성합니다.
#     FIELD_MAPPING에 정의된 매핑 정보를 사용하여 API 응답(item)에서 값을 추출합니다.
#     """
#     mapping = FIELD_MAPPING.get(ModelClass, {})
#     defaults = {}
#     for model_field, mapping_tuple in mapping.items():
#         # 'unique_key'는 lookup용이므로 defaults에는 포함하지 않습니다.
#         if model_field == 'unique_key':
#             continue
#         model_field_name, api_key = mapping_tuple
#         defaults[model_field_name] = item.get(api_key)
#     defaults['update_datetime'] = now()
#     return defaults


# def call_api_endpoint(request, pk):
#     """API 데이터를 호출 및 저장"""
#     endpoint = get_object_or_404(ApiEndpoint, pk=pk)
#     start_position = 1
#     batch_size = 1000
#     total_saved = 0

#     logger.info(f"Starting API call for endpoint: {endpoint.name}")

#     # 서비스 이름에 따른 모델 매핑 (필요에 따라 추가 모델을 매핑하세요)
#     MODEL_MAPPING = {
#         'I1250': FoodItem,
#         'C002' : FoodItem,
#         # 예시: 'beverage_service': BeverageItem,
#     }

#     if endpoint.service_name not in MODEL_MAPPING:
#         logger.error(f"지원하지 않는 서비스 이름: {endpoint.service_name}")
#         return JsonResponse({"error": f"지원하지 않는 서비스 이름: {endpoint.service_name}"}, status=500)

#     ModelClass = MODEL_MAPPING[endpoint.service_name]
#     # 해당 모델의 필드 매핑 정보가 존재하는지 확인
#     if ModelClass not in FIELD_MAPPING:
#         logger.error(f"{ModelClass.__name__}에 대한 필드 매핑 정보가 없습니다.")
#         return JsonResponse({"error": f"{ModelClass.__name__}에 대한 필드 매핑 정보가 없습니다."}, status=500)

#     try:
#         while True:
#             # 예: 2025년 2월 1일 이후 자료만 가져옴
#             change_date = "20250201"
#             api_url = f"{endpoint.url}/{endpoint.api_key.key}/{endpoint.service_name}/json/{start_position}/{start_position + batch_size - 1}/CHNG_DT={change_date}"
#             logger.info(f"Calling API at URL: {api_url}")

#             response = requests.get(api_url, timeout=300)
#             logger.info(f"API Response Status: {response.status_code}")
#             logger.debug(f"API Raw Response Text: {response.text[:500]}")

#             if response.status_code != 200:
#                 logger.error(f"Unexpected status code: {response.status_code}")
#                 return JsonResponse({"error": f"Unexpected status code: {response.status_code}"}, status=500)

#             try:
#                 data = response.json()
#                 logger.debug(f"Parsed JSON Data: {str(data)[:500]}")
#             except ValueError:
#                 logger.error(f"Invalid JSON response: {response.text}")
#                 return JsonResponse({"error": "Invalid JSON response"}, status=500)

#             if endpoint.service_name not in data:
#                 logger.error(f"Expected service name '{endpoint.service_name}' not found in response: {list(data.keys())}")
#                 return JsonResponse({"error": f"Invalid service name: {endpoint.service_name}"}, status=500)

#             items = data.get(endpoint.service_name, {}).get("row", [])
#             logger.info(f"Number of items fetched: {len(items)}")

#             for item in items:
#                 try:
#                     # 각 모델의 고유 키(lookup) 필드를 FIELD_MAPPING에서 가져옴
#                     unique_field_name, unique_api_key = FIELD_MAPPING[ModelClass]['unique_key']
#                     unique_value = item.get(unique_api_key)

#                     defaults = build_defaults(ModelClass, item)
#                     instance, created = ModelClass.objects.update_or_create(
#                         **{unique_field_name: unique_value},
#                         defaults=defaults
#                     )
#                     print(f"Created: {created} / 제품명 : {instance.prdlst_nm if hasattr(instance, 'prdlst_nm') else 'N/A'}")
#                 except Exception as e:
#                     logger.error(f"Failed to save item {item.get('prdlst_nm')}: {e}")

#             total_saved += len(items)

#             if not items or len(items) < batch_size:
#                 logger.info("No more items to fetch. Exiting loop.")
#                 break

#             start_position += batch_size

#         # 호출 상태 업데이트
#         endpoint.last_called_at = now()
#         endpoint.last_status = "success"
#         endpoint.save()

#         logger.info(f"Total saved items: {total_saved}")
#         return JsonResponse({"success": True, "total_saved": total_saved})

#     except requests.exceptions.RequestException as e:
#         logger.error(f"API call failed: {e}")
#         endpoint.last_status = "failure"
#         endpoint.save()
#         return JsonResponse({"error": str(e)}, status=500)

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

    service_info = SERVICE_MAPPING.get(endpoint.service_name)
    if not service_info:
        logger.error(f"지원하지 않는 서비스 이름: {endpoint.service_name}")
        return JsonResponse({"error": f"지원하지 않는 서비스 이름: {endpoint.service_name}"}, status=500)

    ModelClass = service_info['model']
    field_mapping = service_info['fields']

    try:
        while True:
            # 예: 2025년 2월 1일 이후 자료만 가져옴
            change_date = "20250201"
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
    