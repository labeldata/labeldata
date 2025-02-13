from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import AdministrativeDisposition, CrawlingSetting
from .forms import DispositionForm
import requests
from bs4 import BeautifulSoup


@login_required
def crawl_dispositions(request, setting_id):
    """크롤링 실행"""
    setting = get_object_or_404(CrawlingSetting, id=setting_id)
    try:
        response = requests.get(setting.target_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select('table.tbl_type01 tbody tr')

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 5:  # 데이터가 충분하지 않은 경우 스킵
                continue

            # 데이터 매핑
            disposition_date = cols[0].get_text(strip=True)
            disposition_name = cols[1].get_text(strip=True)
            company_name = cols[2].get_text(strip=True)
            address = cols[3].get_text(strip=True)
            details = cols[4].get_text(strip=True)

            # 데이터 저장
            AdministrativeDisposition.objects.update_or_create(
                company_name=company_name,
                disposition_name=disposition_name,
                disposition_date=disposition_date,
                defaults={
                    'registration_number': None,
                    'details': details,
                }
            )

        messages.success(request, f"{setting.local_gov_name} 크롤링 완료!")
    except Exception as e:
        messages.error(request, f"크롤링 실패: {e}")
    return redirect('disposition:disposition_list')


@login_required
def disposition_list(request):
    """행정처분 목록"""
    dispositions = AdministrativeDisposition.objects.all().order_by('-disposition_date')
    return render(request, 'disposition/disposition_list.html', {'dispositions': dispositions})


@login_required
def disposition_create(request):
    """행정처분 생성"""
    if request.method == 'POST':
        form = DispositionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "행정처분이 성공적으로 생성되었습니다.")
            return redirect('disposition:disposition_list')
    else:
        form = DispositionForm()
    return render(request, 'disposition/disposition_form.html', {'form': form})


@login_required
def disposition_detail(request, disposition_id):
    """행정처분 상세보기"""
    disposition = get_object_or_404(AdministrativeDisposition, id=disposition_id)
    return render(request, 'disposition/disposition_detail.html', {'disposition': disposition})


@login_required
def disposition_delete(request, disposition_id):
    """행정처분 삭제"""
    disposition = get_object_or_404(AdministrativeDisposition, id=disposition_id)
    if request.method == 'POST':
        disposition.delete()
        messages.success(request, "행정처분이 삭제되었습니다.")
        return redirect('disposition:disposition_list')
    return render(request, 'disposition/disposition_confirm_delete.html', {'disposition': disposition})
