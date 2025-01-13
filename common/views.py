import logging
import requests
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from .models import ApiEndpoint

logger = logging.getLogger(__name__)  # 로깅 객체 설정

def signup(request):
    """회원가입"""
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


def login_view(request):
    """로그인"""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, "로그인 성공!")
            return redirect('label:post_list')
    else:
        form = AuthenticationForm()
    return render(request, 'common/login.html', {'form': form})


def logout_view(request):
    """로그아웃"""
    logout(request)
    messages.info(request, "로그아웃되었습니다.")
    return redirect('common:login')


def call_api_endpoint(request, pk):
    """API 데이터를 호출 및 저장"""
    endpoint = get_object_or_404(ApiEndpoint, pk=pk)
    start_position = 1
    batch_size = 3
    total_saved = 0

    try:
        while True:
            # API URL 구성: {BASE_URL}/{API_KEY}/{SERVICE_NAME}/json/{START}/{END}
            api_url = f"{endpoint.url}/{endpoint.api_key.key}/{endpoint.service_name}/json/{start_position}/{start_position + batch_size - 1}"
            logger.debug(f"Calling API: {api_url}")

            response = requests.get(api_url)
            response.raise_for_status()

            data = response.json()
            items = data.get(endpoint.service_name, {}).get("row", [])
            total_saved += len(items)

            for item in items:
                logger.debug(f"Saving item: {item.get('PRDLST_NM')}")

            if len(items) < batch_size:
                break
            start_position += batch_size

        logger.info(f"총 저장된 데이터: {total_saved}")
        return JsonResponse({"success": True, "total_saved": total_saved})
    except requests.RequestException as e:
        logger.error(f"API 호출 실패: {e}")
        return JsonResponse({"error": str(e)}, status=500)
    except ValueError as e:
        logger.error(f"JSON 변환 실패: {e}")
        return JsonResponse({"error": "Invalid JSON response"}, status=500)