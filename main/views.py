from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from disposition.models import AdministrativeDisposition, CrawlingSetting  # import 경로 수정
from disposition.forms import DispositionForm  # import 경로 수정

def home(request):
    return render(request, 'main/home.html')

@login_required
def disposition_list(request):
    dispositions = AdministrativeDisposition.objects.all().order_by('-disposition_date')
    return render(request, 'disposition/disposition_list.html', {'dispositions': dispositions})


@login_required
def disposition_list(request):
    dispositions = AdministrativeDisposition.objects.all().order_by('-disposition_date')
    return render(request, 'disposition/disposition_list.html', {'dispositions': dispositions})

@login_required
def disposition_detail(request, disposition_id):
    disposition = get_object_or_404(AdministrativeDisposition, id=disposition_id)
    return render(request, 'disposition/disposition_detail.html', {'disposition': disposition})

@login_required
def disposition_create(request):
    if request.method == "POST":
        form = DispositionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '행정처분 정보가 등록되었습니다.')
            return redirect('disposition:disposition_list')
    else:
        form = DispositionForm()
    return render(request, 'disposition/disposition_form.html', {'form': form})

@login_required
def disposition_delete(request, disposition_id):
    disposition = get_object_or_404(AdministrativeDisposition, id=disposition_id)
    disposition.delete()
    messages.success(request, '행정처분 정보가 삭제되었습니다.')
    return redirect('disposition:disposition_list')

@login_required
def crawl_dispositions(request, setting_id):
    setting = get_object_or_404(CrawlingSetting, id=setting_id)
    # 크롤링 로직 구현
    messages.success(request, f'{setting.location} 지역의 행정처분 정보 크롤링이 시작되었습니다.')
    return redirect('admin:disposition_crawlingsetting_changelist')