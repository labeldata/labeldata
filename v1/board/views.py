from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden, FileResponse
from django.db.models import Case, When, Value, IntegerField, Q
from django.contrib import messages
from django.conf import settings
from .models import Board, Comment
from django import forms
from urllib.parse import quote
import mimetypes
import os

class BoardForm(forms.ModelForm):
    is_hidden = forms.BooleanField(
        label='비밀글',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    is_notice = forms.BooleanField(
        label='공지사항',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    image = forms.ImageField(
        label='이미지 첨부',
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )
    delete_attachment = forms.BooleanField(
        label='첨부파일 삭제', required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    delete_image = forms.BooleanField(
        label='이미지 삭제', required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Board
        fields = ['is_hidden', 'is_notice', 'title', 'content', 'attachment', 'image']  # 폼 필드에는 삭제필드 미포함
        labels = {
            'title': '제목',
            'content': '내용',
            'attachment': '첨부파일',
            'image': '이미지 첨부',
        }
        widgets = {
            'content': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # 관리자가 아닌 경우 is_notice, attachment, image 필드 제거
        if not self.user or not self.user.is_staff:
            self.fields.pop('is_notice', None)
            self.fields.pop('attachment', None)
            self.fields.pop('image', None)  # 이미지 필드도 관리자만
        # 삭제 체크박스는 수정폼에서만 노출
        if not self.instance.pk or not self.user or not self.user.is_staff:
            self.fields.pop('delete_attachment', None)
            self.fields.pop('delete_image', None)

    def clean(self):
        cleaned_data = super().clean()
        is_notice = cleaned_data.get('is_notice')
        # 공지사항 등록/수정 시 관리자 검증
        if is_notice and (not self.user or not self.user.is_staff):
            raise forms.ValidationError('공지사항은 관리자만 작성할 수 있습니다.')
        # 이미지 첨부도 관리자만 허용
        if not self.user or not self.user.is_staff:
            if 'image' in self.cleaned_data and self.cleaned_data['image']:
                raise forms.ValidationError('이미지 첨부는 관리자만 사용할 수 있습니다.')
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
                    Q(is_hidden=False) | Q(author=self.request.user)
                )
        else:
            queryset = queryset.filter(is_hidden=False)
        return queryset

class BoardDetailView(DetailView):
    model = Board
    template_name = 'board/detail.html'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.is_hidden and request.user != self.object.author and not request.user.is_staff:
            return HttpResponseForbidden('비밀글은 작성자 또는 관리자만 볼 수 있습니다.')
        
        # 작성자 본인이 아닌 경우에만 조회수 증가
        if request.user != self.object.author:
            # update_fields를 사용하여 조회수만 업데이트
            Board.objects.filter(pk=self.object.pk).update(views=self.object.views + 1)
            self.object.views += 1  # 메모리상의 객체도 업데이트
        
        context = self.get_context_data()
        return self.render_to_response(context)

class BoardCreateView(LoginRequiredMixin, CreateView):
    model = Board
    form_class = BoardForm
    template_name = 'board/form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        # 현재 로그인한 사용자를 author로 설정
        form.instance.author = self.request.user
        
        # 관리자가 아닌 경우 공지사항, 첨부파일, 이미지 업로드 방지
        if not self.request.user.is_staff:
            form.instance.is_notice = False
            form.instance.attachment = None
            form.instance.image = None
        
        # 공지사항 권한 검증
        if form.instance.is_notice and not self.request.user.is_staff:
            messages.error(self.request, '공지사항은 관리자만 작성할 수 있습니다.')
            return self.form_invalid(form)
        
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('board:detail', kwargs={'pk': self.object.pk})

class BoardUpdateView(LoginRequiredMixin, UpdateView):
    model = Board
    form_class = BoardForm
    template_name = 'board/form.html'

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
        # 공지사항 권한 검증
        if form.instance.is_notice and not self.request.user.is_staff:
            messages.error(self.request, '공지사항은 관리자만 수정할 수 있습니다.')
            return self.form_invalid(form)
        
        # 일반 유저의 경우 첨부파일/이미지 수정 방지
        if not self.request.user.is_staff:
            original = self.get_object()
            form.instance.attachment = original.attachment
            form.instance.image = original.image
        
        # 첨부파일/이미지 삭제 처리 (관리자만)
        if self.request.user.is_staff:
            if form.cleaned_data.get('delete_attachment'):
                if form.instance.attachment:
                    form.instance.attachment.delete(save=False)
                form.instance.attachment = None
            if form.cleaned_data.get('delete_image'):
                if form.instance.image:
                    form.instance.image.delete(save=False)
                form.instance.image = None
        
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('board:detail', kwargs={'pk': self.object.pk})

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
    
    # 관리자만 댓글 작성 가능
    if not request.user.is_staff:
        messages.error(request, '답변은 관리자만 작성할 수 있습니다.')
        return redirect('board:detail', pk=pk)
    
    content = request.POST.get('content', '').strip()
    if not content:
        messages.error(request, '답변 내용을 입력하세요.')
        return redirect('board:detail', pk=pk)
    Comment.objects.create(board=board, author=request.user, content=content)
    messages.success(request, '답변이 등록되었습니다.')
    return redirect('board:detail', pk=pk)

@login_required
def edit_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    
    # 관리자만 댓글 수정 가능
    if not request.user.is_staff:
        return HttpResponseForbidden('답변은 관리자만 수정할 수 있습니다.')
    
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if not content:
            messages.error(request, '답변 내용을 입력하세요.')
            return render(request, 'board/edit_comment.html', {'comment': comment})
        comment.content = content
        comment.save()
        messages.success(request, '답변이 수정되었습니다.')
        return redirect('board:detail', pk=comment.board.pk)
    return render(request, 'board/edit_comment.html', {'comment': comment})

@login_required
@require_POST
def delete_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    
    # 관리자만 댓글 삭제 가능
    if not request.user.is_staff:
        return HttpResponseForbidden('답변은 관리자만 삭제할 수 있습니다.')
    
    board_pk = comment.board.pk
    comment.delete()
    messages.success(request, '답변이 삭제되었습니다.')
    return redirect('board:detail', pk=board_pk)

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