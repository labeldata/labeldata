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

# 각 모델별 필드 매핑 정의 (예시)
# 'unique_key'는 각 모델에서 update_or_create시 사용될 고유 키(API 응답의 키에 해당)
FIELD_MAPPING = {
    FoodItem: {
        'unique_key': 'prdlst_report_no',  # FoodItem에서 고유 키로 사용할 API 응답 키
        'lcns_no': 'lcns_no',
        'bssh_nm': 'bssh_nm',
        'prms_dt': 'prms_dt',
        'prdlst_nm': 'prdlst_nm',
        'prdlst_dcnm': 'prdlst_dcnm',
        'production': 'production',
        'hieng_lntrt_dvs_yn': 'hieng_lntrt_dvs_yn',
        'child_crtfc_yn': 'child_crtfc_yn',
        'pog_daycnt': 'pog_daycnt',
        'induty_cd_nm': 'induty_cd_nm',
        'qlity_mntnc_tmlmt_daycnt': 'qlity_mntnc_tmlmt_daycnt',
        'usages': 'usages',
        'prpos': 'prpos',
        'dispos': 'dispos',
        'frmlc_mtrqlt': 'frmlc_mtrqlt',
        'rawmtrl_nm': 'rawmtrl_nm',
        'last_updt_dtm': 'last_updt_dtm',
    },
    # 예시: BeverageItem 모델에 대해 필드 매핑 (실제 필드명에 맞게 수정)
    # BeverageItem: {
    #     'unique_key': 'report_no',
    #     'name': 'name',
    #     'volume': 'volume',
    #     'manufacturer': 'manufacturer',
    #     # 기타 필드 매핑...
    # },
}
def build_defaults(ModelClass, item):
    """
    주어진 ModelClass에 맞는 defaults 딕셔너리를 생성합니다.
    FIELD_MAPPING에 정의된 매핑 정보를 사용하여 API 응답(item)에서 값을 추출합니다.
    """
    mapping = FIELD_MAPPING.get(ModelClass, {})
    defaults = {}
    for model_field, api_key in mapping.items():
        # 'unique_key'는 update_or_create의 lookup용이므로 defaults에는 포함하지 않습니다.
        if model_field != 'unique_key':
            defaults[model_field] = item.get(api_key)
    defaults['update_datetime'] = now()
    return defaults


def call_api_endpoint(request, pk):
    """API 데이터를 호출 및 저장"""
    endpoint = get_object_or_404(ApiEndpoint, pk=pk)
    start_position = 1
    batch_size = 1000
    total_saved = 0

    logger.info(f"Starting API call for endpoint: {endpoint.name}")

    # 서비스 이름에 따른 모델 매핑 (필요에 따라 추가 모델을 매핑하세요)
    MODEL_MAPPING = {
        'I1250': FoodItem,
        # 예시: 'beverage_service': BeverageItem,
    }

    if endpoint.service_name not in MODEL_MAPPING:
        logger.error(f"지원하지 않는 서비스 이름: {endpoint.service_name}")
        return JsonResponse({"error": f"지원하지 않는 서비스 이름: {endpoint.service_name}"}, status=500)

    ModelClass = MODEL_MAPPING[endpoint.service_name]
    # 해당 모델의 필드 매핑 정보가 존재하는지 확인
    if ModelClass not in FIELD_MAPPING:
        logger.error(f"{ModelClass.__name__}에 대한 필드 매핑 정보가 없습니다.")
        return JsonResponse({"error": f"{ModelClass.__name__}에 대한 필드 매핑 정보가 없습니다."}, status=500)



    try:
        while True:
            # 예: 2025년 1월 21일 이후 자료만 가져옴
            change_date = "20250121"
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
                    # 각 모델의 고유 키(lookup) 필드를 FIELD_MAPPING에서 가져옴
                    unique_key_field = FIELD_MAPPING[ModelClass]['unique_key']
                    unique_value = item.get(FIELD_MAPPING[ModelClass]['unique_key'])
                    
                    defaults = build_defaults(ModelClass, item)
                    instance, created = ModelClass.objects.update_or_create(
                        **{unique_key_field: unique_value},
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

# def call_api_endpoint(request, pk):
#     # API 데이터를 호출 및 저장 또는 원재료명 업데이트
#     endpoint = get_object_or_404(ApiEndpoint, pk=pk)
#     start_position = 1
#     batch_size = 1000
#     total_saved = 0
#     total_updated = 0  # 업데이트된 항목 수

#     logger.info(f"Starting API call for endpoint: {endpoint.name}")

#     try:
#         while True:
#             # API URL 구성
#             change_date = "20250201"
#             api_url = f"{endpoint.url}/{endpoint.api_key.key}/{endpoint.service_name}/json/{start_position}/{start_position + batch_size - 1}/CHNG_DT={change_date}"
#             logger.info(f"Calling API at URL: {api_url}")

#             response = requests.get(api_url, timeout=30)
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
#                     # 기존 데이터가 있는지 확인
#                     existing_item = FoodItem.objects.filter(prdlst_report_no=item.get("PRDLST_REPORT_NO")).first()

#                     if existing_item:
#                         # 기존 데이터가 있을 경우, 원재료명만 업데이트
#                         existing_item.rawmtrl_nm = item.get("RAWMTRL_NM")
#                         existing_item.save(update_fields=["rawmtrl_nm", "update_datetime"])
#                         logger.info(f"Updated rawmtrl_nm for {existing_item.prdlst_report_no}")
#                         total_updated += 1
#                     else:
#                         # 기존 데이터가 없을 경우 새 데이터 삽입
#                         FoodItem.objects.create(
#                             prdlst_report_no=item.get("PRDLST_REPORT_NO"),
#                             lcns_no=item.get("LCNS_NO"),
#                             bssh_nm=item.get("BSSH_NM"),
#                             prms_dt=item.get("PRMS_DT"),
#                             prdlst_nm=item.get("PRDLST_NM"),
#                             prdlst_dcnm=item.get("PRDLST_DCNM"),
#                             production=item.get("PRODUCTION"),
#                             hieng_lntrt_dvs_yn=item.get("HIENG_LNTRT_DVS_NM"),
#                             child_crtfc_yn=item.get("CHILD_CRTFC_YN"),
#                             pog_daycnt=item.get("POG_DAYCNT"),
#                             induty_cd_nm=item.get("INDUTY_CD_NM"),
#                             qlity_mntnc_tmlmt_daycnt=item.get("QLITY_MNTNC_TMLMT_DAYCNT"),
#                             usages=item.get("USAGE"),
#                             prpos=item.get("PRPOS"),
#                             dispos=item.get("DISPOS"),
#                             frmlc_mtrqlt=item.get("FRMLC_MTRQLT"),
#                             rawmtrl_nm=item.get("RAWMTRL_NM"),
#                             last_updt_dtm=item.get("LAST_UPDT_DTM"),
#                             update_datetime=now()
#                         )
#                         logger.info(f"Created new item with prdlst_report_no: {item.get('PRDLST_REPORT_NO')}")
#                         total_saved += 1
#                 except Exception as e:
#                     logger.error(f"Failed to process item {item.get('PRDLST_REPORT_NO')}: {e}")

#             if not items or len(items) < batch_size:
#                 logger.info("No more items to fetch. Exiting loop.")
#                 break

#             start_position += batch_size

#         # 호출 상태 업데이트
#         endpoint.last_called_at = now()
#         endpoint.last_status = "success"
#         endpoint.save()

#         logger.info(f"Total saved items: {total_saved}")
#         logger.info(f"Total updated items: {total_updated}")
#         return JsonResponse({"success": True, "total_saved": total_saved, "total_updated": total_updated})

#     except requests.exceptions.RequestException as e:
#         logger.error(f"API call failed: {e}")
#         endpoint.last_status = "failure"
#         endpoint.save()
#         return JsonResponse({"error": str(e)}, status=500)