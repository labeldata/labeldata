import logging
import requests
import xml.etree.ElementTree as ET
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.utils.timezone import now
from label.models import Post
from .models import ApiEndpoint

logger = logging.getLogger(__name__)

# ---- API 호출 관련 기능 ----

def fetch_and_save_data(api_url, start_pos, end_pos):
    """API 데이터를 호출하고 저장하는 함수"""
    url = f"{api_url}/{start_pos}/{end_pos}"
    logger.info(f"Fetching data from: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error("API 호출 시간 초과")
        return {"error": "timeout"}
    except requests.exceptions.RequestException as e:
        logger.error(f"API 호출 실패: {e}")
        return {"error": str(e)}

    if "application/xml" in response.headers.get("Content-Type", ""):
        try:
            root = ET.fromstring(response.text)
            items = root.findall(".//row")
            saved_count = 0

            for item in items:
                product_name = item.find("PRDLST_NM").text if item.find("PRDLST_NM") else "Unknown"
                manufacturer = item.find("BSSH_NM").text if item.find("BSSH_NM") else "Unknown"
                unique_key = item.find("PRDLST_CD").text if item.find("PRDLST_CD") else None

                if unique_key:
                    _, created = Post.objects.get_or_create(
                        unique_key=unique_key,
                        defaults={
                            "title": product_name,
                            "api_data": {"manufacturer": manufacturer},
                            "is_api_data": True,
                            "create_date": now(),
                        },
                    )
                    if created:
                        saved_count += 1
            return {"success": True, "saved_count": saved_count}
        except ET.ParseError as e:
            logger.error(f"XML 파싱 실패: {e}")
            return {"error": "parse_error"}
    else:
        logger.error(f"Unexpected Content-Type: {response.headers.get('Content-Type')}")
        return {"error": "invalid_content_type"}

def call_api_endpoint(request, endpoint_id):
    """API 데이터를 호출하고 누적 저장"""
    endpoint = get_object_or_404(ApiEndpoint, pk=endpoint_id)
    api_url = endpoint.url
    batch_size = 1000
    start_position = 1
    total_saved = 0

    while True:
        end_position = start_position + batch_size - 1
        result = fetch_and_save_data(api_url, start_position, end_position)

        if "error" in result:
            return JsonResponse({"error": result["error"], "total_saved": total_saved})

        total_saved += result["saved_count"]

        if result["saved_count"] == 0:
            break

        start_position = end_position + 1

    logger.info(f"총 저장된 데이터: {total_saved}건")
    return JsonResponse({"success": True, "total_saved": total_saved})


# ---- 회원가입/로그인/로그아웃 관련 기능 ----

def signup(request):
    """회원가입 처리"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "회원가입이 완료되었습니다!")
            return redirect('label:post_list')  # 게시판으로 리다이렉트
        else:
            messages.error(request, "회원가입 중 문제가 발생했습니다.")
    else:
        form = UserCreationForm()
    return render(request, 'common/signup.html', {'form': form})


def login_view(request):
    """로그인 처리"""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "로그인 성공!")
            return redirect('label:post_list')
        else:
            messages.error(request, "로그인 정보가 잘못되었습니다.")
    else:
        form = AuthenticationForm()
    return render(request, 'common/login.html', {'form': form})


def logout_view(request):
    """로그아웃 처리"""
    logout(request)
    messages.info(request, "로그아웃되었습니다.")
    return redirect('common:login')