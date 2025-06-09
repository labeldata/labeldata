from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden, FileResponse
from django.db.models import Case, When, Value, IntegerField, Q
from django.contrib import messages
from .models import Board, Comment
from django import forms
import logging
from urllib.parse import quote
import mimetypes
import os

# 디버깅용 로거 설정
logger = logging.getLogger(__name__)

class BoardForm(forms.ModelForm):
    is_public = forms.ChoiceField(
        label='공개/비공개',
        choices=[(True, '공개'), (False, '비공개')],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial=True
    )
    is_notice = forms.BooleanField(
        label='공지사항',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Board
        fields = ['is_public', 'is_notice', 'title', 'content', 'attachment']
        labels = {
            'title': '제목',
            'content': '내용',
            'attachment': '첨부파일',
        }
        widgets = {
            'content': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # 관리자가 아닌 경우에도 is_notice 필드를 유지하도록 수정
        if not self.user or not self.user.is_staff:
            self.fields['is_notice'].widget.attrs['disabled'] = True  # 비활성화 처리

    def clean(self):
        cleaned_data = super().clean()
        is_notice = cleaned_data.get('is_notice')
        # 공지사항 등록/수정 시 관리자 검증
        if is_notice and (not self.user or not self.user.is_staff):
            raise forms.ValidationError('공지사항은 관리자만 작성할 수 있습니다.')
        return cleaned_data

class BoardListView(ListView):
    model = Board
    template_name = 'board/list.html'
    context_object_name = 'boards'
    paginate_by = 10

    def get_queryset(self):
        queryset = Board.objects.select_related('author').prefetch_related('comments').annotate(
            is_notice_order=Case(
                When(is_notice=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        ).order_by('-is_notice_order', '-created_at')
        if self.request.user.is_authenticated:
            if not self.request.user.is_staff:
                queryset = queryset.filter(
                    Q(is_public=True) | Q(author=self.request.user)
                )
        else:
            queryset = queryset.filter(is_public=True)
        return queryset

class BoardDetailView(DetailView):
    model = Board
    template_name = 'board/detail.html'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.is_public and request.user != self.object.author and not request.user.is_staff:
            return HttpResponseForbidden('비공개 게시글은 작성자 또는 관리자만 볼 수 있습니다.')
        self.object.views += 1
        self.object.save()
        context = self.get_context_data()
        return self.render_to_response(context)

class BoardCreateView(LoginRequiredMixin, CreateView):
    model = Board
    form_class = BoardForm
    template_name = 'board/form.html'
    success_url = reverse_lazy('board:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        # 현재 로그인한 사용자를 author로 설정
        form.instance.author = self.request.user
        # 관리자가 아닌 경우 공지사항 필드 강제 설정
        if not self.request.user.is_staff:
            form.instance.is_notice = False
        messages.success(self.request, '게시글이 등록되었습니다.')
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        return super().form_invalid(form)

class BoardUpdateView(LoginRequiredMixin, UpdateView):
    model = Board
    form_class = BoardForm
    template_name = 'board/form.html'
    success_url = reverse_lazy('board:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.author != request.user and not request.user.is_staff:
            return HttpResponseForbidden()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.author != request.user and not request.user.is_staff:
            return HttpResponseForbidden()
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, '게시글이 수정되었습니다.')
        return super().form_valid(form)

class BoardDeleteView(LoginRequiredMixin, DeleteView):
    model = Board
    template_name = 'board/confirm_delete.html'
    success_url = reverse_lazy('board:list')

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.author != request.user and not request.user.is_staff:
            return HttpResponseForbidden()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.author != request.user and not request.user.is_staff:
            return HttpResponseForbidden()
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, '게시글이 삭제되었습니다.')
        return super().form_valid(form)

@login_required
@require_POST
def add_comment(request, pk):
    board = get_object_or_404(Board, pk=pk)
    content = request.POST.get('content', '').strip()
    if not content:
        messages.error(request, '댓글 내용을 입력하세요.')
        return redirect('board:detail', pk=pk)
    Comment.objects.create(board=board, author=request.user, content=content)
    messages.success(request, '댓글이 등록되었습니다.')
    return redirect('board:detail', pk=pk)

@login_required
def edit_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if comment.author == request.user or request.user.is_staff:
        if request.method == 'POST':
            content = request.POST.get('content', '').strip()
            if not content:
                messages.error(request, '댓글 내용을 입력하세요.')
                return render(request, 'board/edit_comment.html', {'comment': comment})
            comment.content = content
            comment.save()
            messages.success(request, '댓글이 수정되었습니다.')
            return redirect('board:detail', pk=comment.board.pk)
        return render(request, 'board/edit_comment.html', {'comment': comment})
    return HttpResponseForbidden()

@login_required
@require_POST
def delete_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if comment.author == request.user or request.user.is_staff:
        board_pk = comment.board.pk
        comment.delete()
        messages.success(request, '댓글이 삭제되었습니다.')
        return redirect('board:detail', pk=board_pk)
    return HttpResponseForbidden()

def download_file(request, file_path):
    # 파일 이름 추출 및 안전한 이름으로 변환
    file_name = os.path.basename(file_path)
    safe_name = quote(file_name)  # 한글 및 특수 문자 인코딩

    # 파일의 Content-Type 추론
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = 'application/octet-stream'  # 기본값

    # 파일 응답 생성
    response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{safe_name}'
    return response