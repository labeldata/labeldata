from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Post, Comment, FoodItem, Label
from .forms import PostForm, CommentForm, LabelForm
from django.core.paginator import Paginator

@login_required
def post_create(request):
    """게시글 생성"""
    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, "게시글이 생성되었습니다.")
            return redirect('label:post_list')
    else:
        form = PostForm()
    return render(request, 'label/post_form.html', {'form': form})


@login_required
def post_edit(request, pk):
    """게시글 수정"""
    post = get_object_or_404(Post, pk=pk)
    if request.user != post.author:
        messages.error(request, "수정 권한이 없습니다.")
        return redirect('label:post_list')

    if request.method == 'POST':
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, "게시글이 수정되었습니다.")
            return redirect('label:post_detail', pk=post.pk)
    else:
        form = PostForm(instance=post)
    return render(request, 'label/post_form.html', {'form': form})


@login_required
def post_delete(request, pk):
    """게시글 삭제"""
    post = get_object_or_404(Post, pk=pk)
    if request.user != post.author:
        messages.error(request, "삭제 권한이 없습니다.")
        return redirect('label:post_list')

    if request.method == 'POST':
        post.delete()
        messages.success(request, "게시글이 삭제되었습니다.")
        return redirect('label:post_list')

    return render(request, 'label/post_confirm_delete.html', {'post': post})


def post_list(request):
    """게시글 목록"""
    search_query = request.GET.get('q', '')
    posts = Post.objects.filter(title__icontains=search_query) if search_query else Post.objects.all()
    posts = posts.order_by('-create_date')
    paginator = Paginator(posts, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'label/post_list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
    })


def post_detail(request, pk):
    """게시글 상세보기"""
    post = get_object_or_404(Post, pk=pk)
    return render(request, 'label/post_detail.html', {'post': post})


@login_required
def comment_create(request, pk):
    """댓글 생성"""
    post = get_object_or_404(Post, pk=pk)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
            messages.success(request, "댓글이 작성되었습니다.")
            return redirect('label:post_detail', pk=pk)
    else:
        form = CommentForm()
    return render(request, 'label/comment_form.html', {'form': form})


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
            form.save()
            messages.success(request, "댓글이 수정되었습니다.")
            return redirect('label:post_detail', pk=comment.post.pk)
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

    if request.method == 'POST':
        comment.delete()
        messages.success(request, "댓글이 삭제되었습니다.")
        return redirect('label:post_detail', pk=comment.post.pk)

    return render(request, 'label/comment_confirm_delete.html', {'comment': comment})

def food_item_list(request):
    """제품 목록"""
    items = FoodItem.objects.all().order_by('-report_date')
    paginator = Paginator(items, 10)  # 페이지네이션
    page_obj = paginator.get_page(request.GET.get('page'))
    
    return render(request, 'label/food_item_list.html', {'page_obj': page_obj})

@login_required
def label_create_or_edit(request, pk=None):
    """라벨 생성 및 수정"""
    food_item = None
    if not pk:
        food_item_id = request.GET.get('food_item_id')
        if not food_item_id:
            return render(request, 'label/error.html', {'message': 'Food item ID가 필요합니다.'})
        food_item = get_object_or_404(FoodItem, id=food_item_id)

    label = get_object_or_404(Label, pk=pk) if pk else None

    if request.method == "POST":
        form = LabelForm(request.POST, instance=label)
        if form.is_valid():
            label = form.save(commit=False)
            if not pk:
                label.food_item = food_item
            label.save()
            return redirect('label:food_item_list')
    else:
        form = LabelForm(instance=label)

    return render(request, 'label/label_form.html', {'form': form, 'food_item': food_item})