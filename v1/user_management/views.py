from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from .models import UserProfile, CompanyDocument
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
            privacy_agree = request.POST.get('privacy_agree')
            
            # 개인정보 처리방침 동의 확인
            if not privacy_agree:
                messages.error(request, "개인정보 처리방침에 동의해주세요.")
                return render(request, 'user_management/signup.html')
            
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
    """이메일 인증 처리 (1시간 유효)"""
    uid = request.GET.get('uid')
    token = request.GET.get('token')
    
    context = {}

    try:
        user = User.objects.get(id=uid)
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Case 1: 이미 인증된 경우
        if profile.is_email_verified:
            context['result_type'] = 'info'
            context['message_text'] = '이미 인증된 계정입니다.'
        # Case 2: 토큰이 일치하는 경우
        elif profile.email_verification_token == token and token:
            # 시간 검증: 발송 시간으로부터 1시간 이내인지 확인
            if profile.email_verification_sent_at:
                time_diff = timezone.now() - profile.email_verification_sent_at
                # 1시간 = 3600초
                if time_diff.total_seconds() > 3600:
                    # 인증 링크 만료
                    context['result_type'] = 'error'
                    context['message_text'] = '인증 링크가 만료되었습니다. (유효시간: 1시간)'
                    context['show_resend'] = True
                    context['user_email'] = user.email
                else:
                    # 인증 성공
                    user.is_active = True
                    user.save()
                    profile.is_email_verified = True
                    profile.email_verification_token = ''
                    profile.save()
                    context['result_type'] = 'success'
                    context['message_text'] = '이메일 인증이 완료되었습니다. 로그인하세요.'
            else:
                # 발송 시간 정보가 없는 경우 (예외 상황)
                context['result_type'] = 'error'
                context['message_text'] = '인증 정보를 확인할 수 없습니다.'
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
    """로그인 (이메일 인증된 계정만 허용, Guest 로그인 지원)"""
    if request.method == 'POST':
        # Guest 로그인 처리
        if request.POST.get('guest_login') == '1':
            email = 'guest@labeasylabel.com'
            password = 'rptmxmfhrmdls1!'
        else:
            email = request.POST.get('username', '').strip()
            password = request.POST.get('password')
        
        # 먼저 사용자 존재 여부 및 비밀번호 확인
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            # 인증 상태 확인
            if hasattr(user, 'profile') and not user.profile.is_email_verified:
                # 인증되지 않은 계정
                request.session['unverified_email'] = email
                messages.warning(request, "이메일 인증이 완료되지 않았습니다. 인증메일을 확인하거나 재발송 버튼을 클릭하세요.")
            else:
                login(request, user)
                return redirect('main:home')
        else:
            # 사용자가 없거나 비밀번호가 틀린 경우
            # 비활성 사용자도 체크 (is_active=False인 경우)
            try:
                inactive_user = User.objects.get(username=email, is_active=False)
                if inactive_user.check_password(password):
                    # 비밀번호는 맞지만 인증이 안된 경우
                    request.session['unverified_email'] = email
                    messages.warning(request, "이메일 인증이 완료되지 않았습니다. 인증메일을 확인하거나 재발송 버튼을 클릭하세요.")
                else:
                    messages.error(request, "아이디 또는 비밀번호가 올바르지 않습니다.")
            except User.DoesNotExist:
                messages.error(request, "아이디 또는 비밀번호가 올바르지 않습니다.")
    
    # 세션에 저장된 이메일 가져오기
    unverified_email = request.session.get('unverified_email', '')
    form = AuthenticationForm()
    return render(request, 'user_management/login.html', {'form': form, 'unverified_email': unverified_email})

def resend_verification_email(request):
    """인증 메일 재발송"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        try:
            user = User.objects.get(username=email, is_active=False)
            profile = user.profile
            
            # 새로운 토큰 생성
            token = get_random_string(32)
            profile.email_verification_token = token
            profile.email_verification_sent_at = timezone.now()
            profile.save()
            
            # 인증 메일 발송
            verify_url = request.build_absolute_uri(f"/user-management/verify-email/?uid={user.id}&token={token}")
            send_mail(
                '이메일 인증 요청 (재발송)',
                f'아래 링크를 클릭하여 이메일 인증을 완료하세요:\n{verify_url}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
            )
            messages.success(request, "인증 메일이 재발송되었습니다. 이메일을 확인하세요.")
        except User.DoesNotExist:
            messages.error(request, "해당 이메일로 가입된 계정을 찾을 수 없습니다.")
        except Exception as e:
            messages.error(request, "메일 발송 중 오류가 발생했습니다.")
    
    return redirect('user_management:login')

def logout_view(request):
    """로그아웃 — 로그아웃 전 UI 모드에 따라 적절한 홈으로 이동"""
    if request.method == 'POST':
        # logout() 전에 세션에서 UI 모드 저장 (logout 호출 시 세션 초기화됨)
        ui_mode = request.session.get('ui_mode', 'v2')
        logout(request)
        messages.info(request, "로그아웃되었습니다.")
        if ui_mode == 'v1':
            return redirect('main:home_v1')
        return redirect('main:home_dashboard')
    return redirect('main:home_dashboard')

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

@login_required
def change_password(request):
    """비밀번호 변경"""
    # Guest 사용자는 비밀번호 변경 불가
    if request.user.email == 'guest@labeasylabel.com':
        messages.error(request, 'Guest 계정은 비밀번호를 변경할 수 없습니다.')
        return redirect('main:home')
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # 비밀번호 변경 후에도 로그인 상태 유지
            messages.success(request, '비밀번호가 성공적으로 변경되었습니다.')
            return redirect('user_management:change_password')
        else:
            messages.error(request, '비밀번호 변경에 실패했습니다. 입력 내용을 확인해주세요.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'user_management/change_password.html', {'form': form})

@login_required
def user_profile(request):
    """내 정보 수정 — 회사 정보 + 고정 서류 관리"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    documents = CompanyDocument.objects.filter(user=request.user)
    is_guest = request.user.email == 'guest@labeasylabel.com'

    if request.method == 'POST':
        if is_guest:
            messages.error(request, 'Guest 계정은 정보를 수정할 수 없습니다.')
            return redirect('user_management:user_profile')

        action = request.POST.get('action', 'save_info')

        if action == 'save_info':
            # 회사 기본 정보 저장
            profile.company_name = request.POST.get('company_name', '').strip()
            profile.license_number = request.POST.get('license_number', '').strip()
            profile.manufacturer_name = request.POST.get('manufacturer_name', '').strip()
            profile.manufacturer_address = request.POST.get('manufacturer_address', '').strip()
            profile.save()
            messages.success(request, '기업 정보가 저장되었습니다.')

        elif action == 'upload_document':
            doc_type = request.POST.get('doc_type', '')
            doc_name = request.POST.get('doc_name', '').strip()
            note = request.POST.get('note', '').strip()
            doc_file = request.FILES.get('doc_file')
            if doc_file and doc_type:
                CompanyDocument.objects.create(
                    user=request.user,
                    doc_type=doc_type,
                    doc_name=doc_name,
                    note=note,
                    doc_file=doc_file,
                )
                messages.success(request, '서류가 등록되었습니다.')
            else:
                messages.error(request, '서류 종류와 파일을 모두 선택해주세요.')

        elif action == 'change_password':
            if is_guest:
                messages.error(request, 'Guest 계정은 비밀번호를 변경할 수 없습니다.')
            else:
                form = PasswordChangeForm(request.user, request.POST)
                if form.is_valid():
                    user = form.save()
                    update_session_auth_hash(request, user)
                    messages.success(request, '비밀번호가 변경되었습니다.')
                else:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, error)

        return redirect('user_management:user_profile')

    pw_form = PasswordChangeForm(request.user)
    doc_type_choices = CompanyDocument.DOC_TYPE_CHOICES
    # 서류 종류별로 그룹화
    docs_by_type = {}
    for doc in documents:
        docs_by_type.setdefault(doc.doc_type, []).append(doc)

    return render(request, 'user_management/user_profile.html', {
        'profile': profile,
        'documents': documents,
        'docs_by_type': docs_by_type,
        'doc_type_choices': doc_type_choices,
        'pw_form': pw_form,
        'is_guest': is_guest,
    })


@login_required
def delete_company_document(request, pk):
    """고정 서류 삭제"""
    if request.method == 'POST':
        try:
            doc = CompanyDocument.objects.get(pk=pk, user=request.user)
            doc.doc_file.delete(save=False)
            doc.delete()
            messages.success(request, '서류가 삭제되었습니다.')
        except CompanyDocument.DoesNotExist:
            messages.error(request, '서류를 찾을 수 없습니다.')
    return redirect('user_management:user_profile')


def privacy_policy(request):
    """개인정보 처리방침 페이지"""
    return render(request, 'user_management/privacy_policy.html')
