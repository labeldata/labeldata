from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.utils.timezone import now
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Post, Comment, FoodType
from .forms import PostForm, CommentForm
from django.conf import settings
import requests
#commit test
from .utils import update_food_types_from_api, get_food_types  # utils.py에서 get_food_types 함수 가져오기

#API 갱신 view
def update_food_types(request):
    if update_food_types_from_api():
        messages.success(request, "식품유형 데이터가 성공적으로 갱신되었습니다.")
    else:
        messages.error(request, "식품유형 데이터를 가져오는 데 실패했습니다.")
    return redirect('admin:label_foodtype_changelist')  # 관리자 페이지로 이동

def get_food_types():
    try:
        # 데이터베이스에서 식품 유형 가져오기
        return [food_type.name for food_type in FoodType.objects.all()]
    except Exception as e:
        print(f"Error fetching food types: {e}")
        return []

#post view
@login_required
def post_list(request):
    search_query = request.GET.get('q', '')
    posts = Post.objects.all().order_by('-create_date')  # 최신 등록 순
    if search_query:
        posts = posts.filter(title__icontains=search_query)

    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'label/post_list.html', {'page_obj': page_obj})

@login_required
def post_create(request):
    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect('label:post_list')
    else:
        form = PostForm()

    # API에서 가져온 식품유형 데이터
    food_types = get_food_types()

    return render(request, 'label/post_form.html', {'form': form, 'food_types': food_types})

@login_required
def post_detail(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    comments = post.comments.all()
    comment_form = CommentForm()
    return render(request, 'label/post_detail.html', {
        'post': post, 'comments': comments, 'comment_form': comment_form
    })

@login_required
def post_edit(request, post_id):
    food_types = get_food_types()
    post = get_object_or_404(Post, pk=post_id)
    if request.user != post.author:
        return redirect('label:post_list')
    if request.method == 'POST':
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            post = form.save(commit=False)
            post.save()
            return redirect('label:post_detail', post_id=post.id)
    else:
        form = PostForm(instance=post)
    return render(request, 'label/post_form.html', {'form': form, 'food_types': food_types})

@login_required
def post_delete(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if request.user != post.author:
        return redirect('label:post_list')
    post.delete()
    return redirect('label:post_list')

@login_required
def post_like(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if request.user != post.author:
        post.likers.add(request.user)
    return redirect('label:post_detail', post_id=post_id)

#comment view
@login_required
def comment_create(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.create_date = now()
            comment.save()
    return redirect('label:post_detail', post_id=post.id)

@login_required
def comment_edit(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    if request.user != comment.author:
        return redirect('label:post_list')
    if request.method == 'POST':
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.modify_date = now()
            comment.save()
            return redirect('label:post_detail', post_id=comment.post.id)
    else:
        form = CommentForm(instance=comment)
    return render(request, 'label/comment_form.html', {'form': form})

@login_required
def comment_delete(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    if request.user != comment.author:
        return redirect('label:post_list')
    comment.delete()
    return redirect('label:post_detail', post_id=comment.post.id)

#user view
def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('label:post_list')
    else:
        form = UserCreationForm()
    return render(request, 'label/signup.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('label:post_list')
    else:
        form = AuthenticationForm()
    return render(request, 'label/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('label:login')

@login_required
def post_unlike(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if request.user != post.author:
        post.likers.remove(request.user)
    return redirect('label:post_detail', post_id=post_id)