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




logger = logging.getLogger(__name__)

# def call_api_endpoint(request, pk):
#     """API 데이터를 호출 및 저장"""
#     endpoint = get_object_or_404(ApiEndpoint, pk=pk)
#     start_position = 1
#     batch_size = 1000
#     total_saved = 0

#     logger.info(f"Starting API call for endpoint: {endpoint.name}")

#     try:
#         while True:
#             # API URL 구성
#             # api_url = f"{endpoint.url}/{endpoint.api_key.key}/{endpoint.service_name}/json/{start_position}/{start_position + batch_size - 1}"
#             # 2025년 1월 21일 이후 자료만
#             change_date = "20250121"
            
#             api_url = f"{endpoint.url}/{endpoint.api_key.key}/{endpoint.service_name}/json/{start_position}/{start_position + batch_size - 1}/CHNG_DT={change_date}"
#             logger.info(f"Calling API at URL: {api_url}")

#             response = requests.get(api_url, timeout=30)  # Timeout 설정
#             logger.info(f"API Response Status: {response.status_code}")

#             # API 응답 내용 기록
#             logger.debug(f"API Raw Response Text: {response.text[:500]}")

#             # 응답 상태 확인
#             if response.status_code != 200:
#                 logger.error(f"Unexpected status code: {response.status_code}")
#                 return JsonResponse({"error": f"Unexpected status code: {response.status_code}"}, status=500)

#             try:
#                 # JSON 데이터 파싱
#                 data = response.json()
#                 logger.debug(f"Parsed JSON Data: {str(data)[:500]}")
#             except ValueError:
#                 logger.error(f"Invalid JSON response: {response.text}")
#                 return JsonResponse({"error": "Invalid JSON response"}, status=500)

#             # 예상 서비스 이름 확인
#             if endpoint.service_name not in data:
#                 logger.error(f"Expected service name '{endpoint.service_name}' not found in response: {list(data.keys())}")
#                 return JsonResponse({"error": f"Invalid service name: {endpoint.service_name}"}, status=500)

#             items = data.get(endpoint.service_name, {}).get("row", [])
#             logger.info(f"Number of items fetched: {len(items)}")

#             # 데이터 저장 로직
#             for item in items:
#                 try:
#                     ReceivedAPIItem, created =  FoodItem.objects.update_or_create(

#                         # 품목제조번호 기준으로 있으면 업데이트, 없으면 인서트
#                         # last_updt_dtm (최종 업데이트 일자) 까지 같이 검색해서 테스트했으나
#                         # 같은 날 여러 번 수정한 케이스의 경우를 체크할 수 없어서 품목제조번호 기준으로 무조건 업데이트 하도록 변경
#                         prdlst_report_no=item.get("PRDLST_REPORT_NO"),
                        
#                         defaults={
#                             'lcns_no': item.get("LCNS_NO"),
#                             'bssh_nm': item.get("BSSH_NM"),
#                             'prms_dt': item.get("PRMS_DT"),
#                             'prdlst_nm': item.get("PRDLST_NM"),
#                             'prdlst_dcnm': item.get("PRDLST_DCNM"),
#                             'production': item.get("PRODUCTION"),
#                             'hieng_lntrt_dvs_yn': item.get("HIENG_LNTRT_DVS_NM"),
#                             'child_crtfc_yn': item.get("CHILD_CRTFC_YN"),
#                             'pog_daycnt': item.get("POG_DAYCNT"),
#                             'induty_cd_nm': item.get("INDUTY_CD_NM"),
#                             'qlity_mntnc_tmlmt_daycnt': item.get("QLITY_MNTNC_TMLMT_DAYCNT"),
#                             'usages': item.get("USAGE"),
#                             'prpos': item.get("PRPOS"),
#                             'dispos': item.get("DISPOS"),
#                             'frmlc_mtrqlt': item.get("FRMLC_MTRQLT"),
#                             'last_updt_dtm': item.get("LAST_UPDT_DTM"),
#                             'update_datetime': now()
#                         }
#                     )
#                     print(f"Created: {created} / 제품명 : {ReceivedAPIItem.prdlst_nm} 용도 : {ReceivedAPIItem.usages}")
#                 except Exception as e:
#                     logger.error(f"Failed to save item {item.get('PRDLST_NM')}: {e}")

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

def call_api_endpoint(request, pk):
    # API 데이터를 호출 및 저장 또는 원재료명 업데이트
    endpoint = get_object_or_404(ApiEndpoint, pk=pk)
    start_position = 1
    batch_size = 1000
    total_saved = 0
    total_updated = 0  # 업데이트된 항목 수

    logger.info(f"Starting API call for endpoint: {endpoint.name}")

    try:
        while True:
            # API URL 구성
            change_date = "20250201"
            api_url = f"{endpoint.url}/{endpoint.api_key.key}/{endpoint.service_name}/json/{start_position}/{start_position + batch_size - 1}/CHNG_DT={change_date}"
            logger.info(f"Calling API at URL: {api_url}")

            response = requests.get(api_url, timeout=30)
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
                    # 기존 데이터가 있는지 확인
                    existing_item = FoodItem.objects.filter(prdlst_report_no=item.get("PRDLST_REPORT_NO")).first()

                    if existing_item:
                        # 기존 데이터가 있을 경우, 원재료명만 업데이트
                        existing_item.rawmtrl_nm = item.get("RAWMTRL_NM")
                        existing_item.save(update_fields=["rawmtrl_nm", "update_datetime"])
                        logger.info(f"Updated rawmtrl_nm for {existing_item.prdlst_report_no}")
                        total_updated += 1
                    else:
                        # 기존 데이터가 없을 경우 새 데이터 삽입
                        FoodItem.objects.create(
                            prdlst_report_no=item.get("PRDLST_REPORT_NO"),
                            lcns_no=item.get("LCNS_NO"),
                            bssh_nm=item.get("BSSH_NM"),
                            prms_dt=item.get("PRMS_DT"),
                            prdlst_nm=item.get("PRDLST_NM"),
                            prdlst_dcnm=item.get("PRDLST_DCNM"),
                            production=item.get("PRODUCTION"),
                            hieng_lntrt_dvs_yn=item.get("HIENG_LNTRT_DVS_NM"),
                            child_crtfc_yn=item.get("CHILD_CRTFC_YN"),
                            pog_daycnt=item.get("POG_DAYCNT"),
                            induty_cd_nm=item.get("INDUTY_CD_NM"),
                            qlity_mntnc_tmlmt_daycnt=item.get("QLITY_MNTNC_TMLMT_DAYCNT"),
                            usages=item.get("USAGE"),
                            prpos=item.get("PRPOS"),
                            dispos=item.get("DISPOS"),
                            frmlc_mtrqlt=item.get("FRMLC_MTRQLT"),
                            rawmtrl_nm=item.get("RAWMTRL_NM"),
                            last_updt_dtm=item.get("LAST_UPDT_DTM"),
                            update_datetime=now()
                        )
                        logger.info(f"Created new item with prdlst_report_no: {item.get('PRDLST_REPORT_NO')}")
                        total_saved += 1
                except Exception as e:
                    logger.error(f"Failed to process item {item.get('PRDLST_REPORT_NO')}: {e}")

            if not items or len(items) < batch_size:
                logger.info("No more items to fetch. Exiting loop.")
                break

            start_position += batch_size

        # 호출 상태 업데이트
        endpoint.last_called_at = now()
        endpoint.last_status = "success"
        endpoint.save()

        logger.info(f"Total saved items: {total_saved}")
        logger.info(f"Total updated items: {total_updated}")
        return JsonResponse({"success": True, "total_saved": total_saved, "total_updated": total_updated})

    except requests.exceptions.RequestException as e:
        logger.error(f"API call failed: {e}")
        endpoint.last_status = "failure"
        endpoint.save()
        return JsonResponse({"error": str(e)}, status=500)