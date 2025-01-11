from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import AdministrativeAction
from .forms import ActionForm

@login_required
def action_list(request):
    actions = AdministrativeAction.objects.all().order_by('-action_date')
    return render(request, 'action/action_list.html', {'actions': actions})

@login_required
def action_create(request):
    if request.method == 'POST':
        form = ActionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('action:action_list')
    else:
        form = ActionForm()
    return render(request, 'action/action_form.html', {'form': form})

@login_required
def action_detail(request, action_id):
    action = get_object_or_404(AdministrativeAction, id=action_id)
    return render(request, 'action/action_detail.html', {'action': action})

@login_required
def action_delete(request, action_id):
    action = get_object_or_404(AdministrativeAction, id=action_id)
    if request.method == 'POST':
        action.delete()
        return redirect('action:action_list')
    return render(request, 'action/action_confirm_delete.html', {'action': action})