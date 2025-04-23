from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib import messages

def signup(request):
    """회원가입"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "회원가입 완료!")
            return redirect('main:home')  # 메인 화면으로 리디렉션
    else:
        form = UserCreationForm()
    return render(request, 'user_management/signup.html', {'form': form})

def login_view(request):
    """로그인"""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, "로그인 성공!")
            return redirect('main:home')  # 메인 화면으로 리디렉션
    else:
        form = AuthenticationForm()
    return render(request, 'user_management/login.html', {'form': form})

def logout_view(request):
    """로그아웃"""
    logout(request)
    messages.info(request, "로그아웃되었습니다.")
    return redirect('user_management:login')
