from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Case, When, Value, IntegerField
from .models import Board, Comment

class BoardListView(ListView):
    model = Board
    template_name = 'board/list.html'
    context_object_name = 'boards'
    paginate_by = 10

    def get_queryset(self):
        return Board.objects.annotate(
            is_notice=Case(
                When(category='공지사항', then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        ).order_by('-is_notice', '-created_at')

class BoardDetailView(DetailView):
    model = Board
    template_name = 'board/detail.html'

    def get(self, request, *args, **kwargs):
        board = self.get_object()
        input_password = request.session.get(f'board_{board.pk}_password') or request.GET.get('password')

        if not board.is_public:
            if board.author and request.user.is_authenticated and board.author == request.user:
                pass
            elif request.user.is_authenticated and request.user.is_staff:
                pass
            elif request.user.is_authenticated:
                pass
            else:
                if not input_password or input_password != board.password:
                    return render(request, 'board/password_modal.html', {'board': board})
                request.session[f'board_{board.pk}_password'] = input_password

        board.views += 1
        board.save()
        return super().get(request, *args, **kwargs)

class CheckPasswordView(View):
    def post(self, request, pk):
        board = get_object_or_404(Board, pk=pk)
        password = request.POST.get('password')
        if board.password == password:
            request.session[f'board_{board.pk}_password'] = password
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'message': '비밀번호가 틀렸습니다.'})

class BoardCreateView(CreateView):
    model = Board
    fields = ['title', 'content', 'category', 'is_public', 'password', 'attachment']
    template_name = 'board/form.html'
    success_url = reverse_lazy('board:list')

    def form_valid(self, form):
        if self.request.user.is_authenticated:
            form.instance.author = self.request.user
            form.instance.password = None
        elif not form.instance.is_public and not form.cleaned_data.get('password'):
            form.add_error('password', '비공개 게시글에는 비밀번호가 필요합니다.')
            return self.form_invalid(form)
        return super().form_valid(form)

class BoardUpdateView(UpdateView):
    model = Board
    fields = ['title', 'content', 'category', 'is_public', 'attachment']
    template_name = 'board/form.html'
    success_url = reverse_lazy('board:list')

    def get(self, request, *args, **kwargs):
        board = self.get_object()
        input_password = request.session.get(f'board_{board.pk}_password') or request.GET.get('password')
        if board.author and request.user.is_authenticated and board.author == request.user:
            return super().get(request, *args, **kwargs)
        elif request.user.is_authenticated and request.user.is_staff:
            return super().get(request, *args, **kwargs)
        elif not board.author and not board.is_public:
            if input_password and input_password == board.password:
                request.session[f'board_{board.pk}_password'] = input_password
                return super().get(request, *args, **kwargs)
            return render(request, 'board/password_modal.html', {'board': board, 'action': 'edit'})
        return HttpResponseForbidden()

    def post(self, request, *args, **kwargs):
        board = self.get_object()
        input_password = request.session.get(f'board_{board.pk}_password')
        if board.author and request.user.is_authenticated and board.author == request.user:
            return super().post(request, *args, **kwargs)
        elif request.user.is_authenticated and request.user.is_staff:
            return super().post(request, *args, **kwargs)
        elif not board.author and not board.is_public and input_password == board.password:
            return super().post(request, *args, **kwargs)
        return HttpResponseForbidden()

class BoardDeleteView(DeleteView):
    model = Board
    template_name = 'board/confirm_delete.html'
    success_url = reverse_lazy('board:list')

    def get(self, request, *args, **kwargs):
        board = self.get_object()
        input_password = request.session.get(f'board_{board.pk}_password') or request.GET.get('password')
        if board.author and request.user.is_authenticated and board.author == request.user:
            return super().get(request, *args, **kwargs)
        elif request.user.is_authenticated and request.user.is_staff:
            return super().get(request, *args, **kwargs)
        elif not board.author and not board.is_public:
            if input_password and input_password == board.password:
                request.session[f'board_{board.pk}_password'] = input_password
                return super().get(request, *args, **kwargs)
            return render(request, 'board/password_modal.html', {'board': board, 'action': 'delete'})
        return HttpResponseForbidden()

    def post(self, request, *args, **kwargs):
        board = self.get_object()
        input_password = request.session.get(f'board_{board.pk}_password')
        if board.author and request.user.is_authenticated and board.author == request.user:
            return super().post(request, *args, **kwargs)
        elif request.user.is_authenticated and request.user.is_staff:
            return super().post(request, *args, **kwargs)
        elif not board.author and not board.is_public and input_password == board.password:
            return super().post(request, *args, **kwargs)
        return HttpResponseForbidden()

@login_required
@require_POST
def add_comment(request, pk):
    board = get_object_or_404(Board, pk=pk)
    if request.user.is_staff:
        content = request.POST.get('content')
        if content:
            Comment.objects.create(board=board, author=request.user, content=content)
    return redirect('board:detail', pk=pk)

@login_required
def edit_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if request.user.is_staff:
        if request.method == 'POST':
            content = request.POST.get('content')
            if content:
                comment.content = content
                comment.save()
                return redirect('board:detail', pk=comment.board.pk)
        return render(request, 'board/edit_comment.html', {'comment': comment})
    return redirect('board:detail', pk=comment.board.pk)

@login_required
@require_POST
def delete_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if request.user.is_staff:
        board_pk = comment.board.pk
        comment.delete()
        return redirect('board:detail', pk=board_pk)
    return redirect('board:detail', pk=comment.board.pk)