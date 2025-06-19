from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.models import User
from .models import UserProfile
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

def signup(request):
    """회원가입 (이메일 인증 방식)"""
    if request.method == 'POST':
        try:
            email = request.POST.get('username', '').strip().lower()
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            
            # 이메일 형식 체크
            if not email or '@' not in email:
                messages.error(request, "아이디는 이메일 형식이어야 합니다.")
                return render(request, 'user_management/signup.html')
            
            if password1 != password2:
                messages.error(request, "비밀번호가 일치하지 않습니다.")
                return render(request, 'user_management/signup.html')
            
            # 대소문자 구분 없이 중복 체크
            if User.objects.filter(username__iexact=email).exists():
                messages.error(request, "이미 가입된 이메일입니다.")
                return render(request, 'user_management/signup.html')
            
            # 사용자 생성
            user = User.objects.create_user(username=email, email=email, password=password1, is_active=False)
            
            # 인증 토큰 생성 및 저장
            token = get_random_string(32)
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.is_email_verified = False
            profile.email_verification_token = token
            profile.email_verification_sent_at = timezone.now()
            profile.save()
            
            # 인증 메일 발송
            verify_url = request.build_absolute_uri(f"/user-management/verify-email/?uid={user.id}&token={token}")
            send_mail(
                '이메일 인증 요청',
                f'아래 링크를 클릭하여 이메일 인증을 완료하세요:\n{verify_url}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
            )
            messages.info(request, "이메일 인증 링크가 발송되었습니다. 이메일을 확인하세요.")
            return render(request, 'user_management/signup_done.html')
            
        except Exception as e:
            messages.error(request, "회원가입 중 오류가 발생했습니다. 다시 시도해주세요.")
            return render(request, 'user_management/signup.html')
    else:
        form = UserCreationForm()
    return render(request, 'user_management/signup.html', {'form': form})

def verify_email(request):
    """이메일 인증 처리"""
    uid = request.GET.get('uid')
    token = request.GET.get('token')
    
    context = {}

    try:
        user = User.objects.get(id=uid)
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Case 1: 성공적인 첫 인증
        if profile.email_verification_token == token and token:
            user.is_active = True
            user.save()
            profile.is_email_verified = True
            profile.email_verification_token = ''
            profile.save()
            context['result_type'] = 'success'
            context['message_text'] = '이메일 인증이 완료되었습니다. 로그인하세요.'
        # Case 2: 이미 인증된 경우 (예: 링크 재클릭)
        elif profile.is_email_verified:
            context['result_type'] = 'info'
            context['message_text'] = '이미 인증된 계정입니다.'
        # Case 3: 잘못된 링크
        else:
            context['result_type'] = 'error'
            context['message_text'] = '잘못된 인증 링크입니다.'

    except User.DoesNotExist:
        context['result_type'] = 'error'
        context['message_text'] = '인증 정보를 확인할 수 없습니다.'
    except Exception:
        context['result_type'] = 'error'
        context['message_text'] = '인증 과정에서 오류가 발생했습니다.'
    
    return render(request, 'user_management/verify_result.html', context)

def login_view(request):
    """로그인 (이메일 인증된 계정만 허용)"""
    if request.method == 'POST':
        email = request.POST.get('username', '').strip()
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            if hasattr(user, 'profile') and not user.profile.is_email_verified:
                messages.error(request, "이메일 인증이 완료되어야 로그인할 수 있습니다.")
            else:
                login(request, user)
                messages.success(request, "로그인 성공!")
                return redirect('main:home')
        else:
            messages.error(request, "아이디 또는 비밀번호가 올바르지 않습니다.")
    form = AuthenticationForm()
    return render(request, 'user_management/login.html', {'form': form})

def logout_view(request):
    """로그아웃"""
    if request.method == 'POST':
        logout(request)
        messages.info(request, "로그아웃되었습니다.")
    return redirect('user_management:login')

def password_reset_request(request):
    """비밀번호 재설정 요청 (이메일로 링크 발송)"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        try:
            user = User.objects.get(username=email)
            token = get_random_string(32)
            profile = user.profile
            profile.password_reset_token = token
            profile.password_reset_sent_at = timezone.now()
            profile.save()
            reset_url = request.build_absolute_uri(f"/user-management/password-reset-confirm/?uid={user.id}&token={token}")
            send_mail(
                '비밀번호 재설정',
                f'아래 링크를 클릭하여 비밀번호를 재설정하세요:\n{reset_url}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
            )
            messages.info(request, "비밀번호 재설정 링크가 이메일로 발송되었습니다.")
        except User.DoesNotExist:
            messages.error(request, "가입된 이메일이 없습니다.")
    return render(request, 'user_management/password_reset_request.html')

def password_reset_confirm(request):
    """비밀번호 재설정 확인"""
    uid = request.GET.get('uid')
    token = request.GET.get('token')
    try:
        user = User.objects.get(id=uid)
        profile = user.profile
        if profile.password_reset_token != token:
            messages.error(request, "잘못된 비밀번호 재설정 링크입니다.")
            return render(request, 'user_management/password_reset_confirm.html')
        if request.method == 'POST':
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            if password1 != password2:
                messages.error(request, "비밀번호가 일치하지 않습니다.")
            else:
                user.set_password(password1)
                user.save()
                profile.password_reset_token = ''
                profile.save()
                messages.success(request, "비밀번호가 성공적으로 변경되었습니다. 로그인하세요.")
                return redirect('user_management:login')
    except Exception:
        messages.error(request, "비밀번호 재설정 정보를 확인할 수 없습니다.")
    return render(request, 'user_management/password_reset_confirm.html')

def signup_done_view(request):
    """회원가입 완료 페이지 (테스트용)"""
    messages.info(request, "이메일 인증 링크가 발송되었습니다. 이메일을 확인하세요.")
    return render(request, 'user_management/signup_done.html')
