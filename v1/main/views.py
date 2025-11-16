from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from v1.disposition.models import AdministrativeDisposition, CrawlingSetting  # import 경로 수정
from v1.disposition.forms import DispositionForm  # import 경로 수정
from v1.label.models import FoodType, FoodItem, CountryList  # 데모 페이지용 추가

def home(request):
    """
    홈 페이지 (표시사항 작성 기능 포함)
    로그인 없이 누구나 접근 가능
    """
    # 식품유형 데이터를 가져옵니다.
    food_groups = FoodType.objects.values_list('food_group', flat=True).distinct().order_by('food_group')
    food_types = list(FoodType.objects.values('food_type', 'food_group').order_by('food_type'))
    
    # 국가 목록을 가져옵니다.
    countries = CountryList.objects.all().order_by('country_name_ko')

    context = {
        'food_groups': food_groups,
        'food_types': food_types,
        'countries': countries,
    }
    return render(request, 'main/home.html', context)

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

@require_http_methods(["POST"])
def save_label(request):
    """
    홈 페이지에서 작성한 표시사항을 저장하는 API
    로그인한 사용자는 바로 저장, 비로그인 사용자는 로그인 페이지로 안내
    """
    # 비로그인 사용자 체크
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'requires_login': True,
            'message': '표시사항을 저장하려면 로그인이 필요합니다. 지금 바로 가입하고 저장하세요!',
            'login_url': '/user-management/login/?next=/'
        })
    
    try:
        data = json.loads(request.body)
        
        # 필수 필드 체크
        if not data.get('prdlst_nm'):
            return JsonResponse({'success': False, 'error': '제품명은 필수입니다.'}, status=400)
        
        # 세션에 데이터 저장
        request.session['demo_label_data'] = data
        
        # label_creation 페이지로 리다이렉트하도록 URL 반환
        return JsonResponse({
            'success': True,
            'redirect_url': '/label/create-new/',
            'message': '표시사항 작성 페이지로 이동합니다.'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': '잘못된 데이터 형식입니다.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


