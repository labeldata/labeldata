from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.utils.timezone import now
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Post, Comment, FoodItem
from .forms import PostForm, CommentForm
from .utils import update_food_types_from_api, get_food_types
from django.contrib.auth import login


# --- 관리자용 ---
def update_food_types(request):
    """식품유형 데이터 갱신"""
    if update_food_types_from_api():
        messages.success(request, "식품유형 데이터가 성공적으로 갱신되었습니다.")
    else:
        messages.error(request, "식품유형 데이터를 가져오는 데 실패했습니다.")
    return redirect('admin:label_foodtype_changelist')


# --- 게시글 ---
@login_required
def post_list(request):
    """게시글 목록"""
    search_query = request.GET.get('q', '')
    order = request.GET.get('order', '-create_date')  # 기본값: 최신순

    # 정렬 적용
    posts = Post.objects.all().order_by(order)
    if search_query:
        posts = posts.filter(title__icontains=search_query)

    paginator = Paginator(posts, 10)  # 페이지당 10개
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'label/post_list.html', {'page_obj': page_obj, 'order': order})


@login_required
def post_create(request):
    """게시글 작성"""
    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect('label:post_list')
    else:
        form = PostForm()

    return render(request, 'label/post_form.html', {'form': form})


@login_required
def post_detail(request, post_id):
    """게시글 상세보기"""
    post = get_object_or_404(Post, pk=post_id)
    comments = post.comments.all()
    comment_form = CommentForm()
    return render(request, 'label/post_detail.html', {
        'post': post, 'comments': comments, 'comment_form': comment_form
    })


@login_required
def post_edit(request, post_id):
    """게시글 수정"""
    post = get_object_or_404(Post, pk=post_id)
    if request.user != post.author:
        messages.error(request, "수정 권한이 없습니다.")
        return redirect('label:post_list')

    if request.method == 'POST':
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            post = form.save()
            return redirect('label:post_detail', post_id=post.id)
    else:
        form = PostForm(instance=post)

    return render(request, 'label/post_form.html', {'form': form})


@login_required
def post_delete(request, post_id):
    """게시글 삭제"""
    post = get_object_or_404(Post, pk=post_id)
    if request.user != post.author:
        messages.error(request, "삭제 권한이 없습니다.")
        return redirect('label:post_list')

    post.delete()
    messages.success(request, "게시글이 삭제되었습니다.")
    return redirect('label:post_list')


@login_required
def post_like(request, post_id):
    """게시글 좋아요"""
    post = get_object_or_404(Post, pk=post_id)
    if request.user != post.author:
        if request.user in post.likers.all():
            post.likers.remove(request.user)
        else:
            post.likers.add(request.user)
    return redirect('label:post_detail', post_id=post_id)

@login_required
def post_unlike(request, post_id):
    """
    게시글 좋아요 취소
    """
    post = get_object_or_404(Post, pk=post_id)
    if request.user != post.author:  # 본인이 작성한 게시글은 제외
        post.likers.remove(request.user)  # 좋아요 관계에서 제거
    return redirect('label:post_detail', post_id=post_id)

# --- 댓글 ---
@login_required
def comment_create(request, post_id):
    """댓글 작성"""
    post = get_object_or_404(Post, pk=post_id)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
    return redirect('label:post_detail', post_id=post.id)


@login_required
def comment_edit(request, comment_id):
    """댓글 수정"""
    comment = get_object_or_404(Comment, pk=comment_id)
    if request.user != comment.author:
        messages.error(request, "수정 권한이 없습니다.")
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
    """댓글 삭제"""
    comment = get_object_or_404(Comment, pk=comment_id)
    if request.user != comment.author:
        messages.error(request, "삭제 권한이 없습니다.")
        return redirect('label:post_list')

    comment.delete()
    messages.success(request, "댓글이 삭제되었습니다.")
    return redirect('label:post_detail', post_id=comment.post.id)

def food_item_list(request):
    items = FoodItem.objects.all().order_by("-report_date")
    return render(request, "label/food_item_list.html", {"items": items})