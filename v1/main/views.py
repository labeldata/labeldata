from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from v1.disposition.models import AdministrativeDisposition, CrawlingSetting  # import 경로 수정
from v1.disposition.forms import DispositionForm  # import 경로 수정
from v1.label.models import FoodType, FoodItem, CountryList, MyLabel  # 데모 페이지용 추가
from django.core.serializers import serialize

def home(request):
    """
    홈 페이지 (표시사항 작성 기능 포함)
    로그인 없이 누구나 접근 가능
    label_id 파라미터가 있으면 해당 라벨 데이터 로드
    """
    # 식품유형 데이터를 가져옵니다.
    food_groups = FoodType.objects.values_list('food_group', flat=True).distinct().order_by('food_group')
    food_types = list(FoodType.objects.values('food_type', 'food_group').order_by('food_type'))
    
    # 국가 목록을 가져옵니다.
    countries = CountryList.objects.all().order_by('country_name_ko')
    
    # label_id 파라미터로 전달된 라벨 데이터 로드
    current_label = None
    current_label_id = None
    current_label_json = None
    label_id = request.GET.get('label_id')
    
    if label_id and request.user.is_authenticated:
        try:
            current_label = MyLabel.objects.get(my_label_id=label_id, user_id=request.user)
            current_label_id = label_id
            # JSON 직렬화
            current_label_json = json.dumps({
                'prdlst_nm': current_label.prdlst_nm or '',
                'ingredient_info': current_label.ingredient_info or '',
                'prdlst_dcnm': current_label.prdlst_dcnm or '',
                'prdlst_report_no': current_label.prdlst_report_no or '',
                'content_weight': current_label.content_weight or '',
                'weight_calorie': current_label.weight_calorie or '',
                'country_of_origin': current_label.country_of_origin or '',
                'storage_method': current_label.storage_method or '',
                'frmlc_mtrqlt': current_label.frmlc_mtrqlt or '',
                'pog_daycnt': current_label.pog_daycnt or '',
                'rawmtrl_nm_display': current_label.rawmtrl_nm_display or '',
                'bssh_nm': current_label.bssh_nm or '',
                'distributor_address': current_label.distributor_address or '',
                'repacker_address': current_label.repacker_address or '',
                'importer_address': current_label.importer_address or '',
                'cautions': current_label.cautions or '',
                'additional_info': current_label.additional_info or '',
                'allergens': current_label.allergens or '',
                # 체크박스 상태 추가
                'chk_prdlst_nm': bool(current_label.prdlst_nm),
                'chk_ingredient_info': bool(current_label.ingredient_info),
                'chk_prdlst_dcnm': bool(current_label.prdlst_dcnm),
                'chk_prdlst_report_no': bool(current_label.prdlst_report_no),
                'chk_content_weight': bool(current_label.content_weight),
                'chk_country_of_origin': bool(current_label.country_of_origin),
                'chk_storage_method': bool(current_label.storage_method),
                'chk_expiry_date': bool(current_label.pog_daycnt),
                'chk_rawmtrl_nm_display': bool(current_label.rawmtrl_nm_display),
                'chk_caution': bool(current_label.cautions),
                'chk_other_info': bool(current_label.additional_info),
                'chk_packaging_material': bool(current_label.frmlc_mtrqlt),
                'chk_manufacturer': bool(current_label.bssh_nm),
                'chk_distributor': bool(current_label.distributor_address),
                'chk_subdivider': bool(current_label.repacker_address),
                'chk_importer': bool(current_label.importer_address),
                'chk_recycling_mark': False,  # 기본값
            })
        except MyLabel.DoesNotExist:
            pass

    context = {
        'food_groups': food_groups,
        'food_types': food_types,
        'countries': countries,
        'current_label': current_label,
        'current_label_id': current_label_id,
        'current_label_json': current_label_json,
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
        from v1.label.models import MyLabel
        from django.utils import timezone
        
        data = json.loads(request.body)
        
        # label_id가 있으면 기존 라벨 업데이트, 없으면 신규 생성
        label_id = data.get('label_id')
        if label_id:
            try:
                label = MyLabel.objects.get(my_label_id=label_id, user_id=request.user)
                is_update = True
            except MyLabel.DoesNotExist:
                label = MyLabel(user_id=request.user)
                is_update = False
        else:
            label = MyLabel(user_id=request.user)
            is_update = False
        
        # 필수 필드 체크
        if not data.get('prdlst_nm'):
            return JsonResponse({'success': False, 'error': '제품명은 필수입니다.'}, status=400)
        
        # 라벨명 설정 (신규 생성 시만)
        if not is_update:
            label.my_label_name = data.get('prdlst_nm', '표시사항') + '_' + timezone.now().strftime('%Y%m%d')
        
        # 기본 정보
        label.prdlst_nm = data.get('prdlst_nm', '')
        label.ingredient_info = data.get('ingredient_info', '')
        label.prdlst_dcnm = data.get('prdlst_dcnm', '')
        label.prdlst_report_no = data.get('prdlst_report_no', '')
        label.content_weight = data.get('content_weight', '')
        label.weight_calorie = data.get('weight_calorie', '')
        
        # 원산지 및 보관/포장
        label.country_of_origin = data.get('country_of_origin', '')
        label.storage_method = data.get('storage_method', '')
        label.frmlc_mtrqlt = data.get('packaging_material', '')
        label.pog_daycnt = data.get('expiry_date', '')
        
        # 원재료명
        label.rawmtrl_nm = data.get('rawmtrl_nm', '')
        label.rawmtrl_nm_display = data.get('rawmtrl_nm_display', '')
        
        # 제조원 등 주소 정보
        label.bssh_nm = data.get('manufacturer', '')
        label.distributor_address = data.get('distributor', '')
        label.repacker_address = data.get('subdivider', '')
        label.importer_address = data.get('importer', '')
        
        # 주의사항 및 기타
        label.cautions = data.get('caution', '')
        label.additional_info = data.get('other_info', '')
        
        # 영양성분 정보
        label.nutrition_text = data.get('nutrition_text', '')
        label.serving_size = data.get('serving_size', '')
        label.serving_size_unit = data.get('serving_size_unit', '')
        label.units_per_package = data.get('units_per_package', '')
        label.nutrition_display_unit = data.get('nutrition_display_unit', '')
        
        # 영양성분 상세
        label.calories = data.get('calories', '')
        label.calories_unit = data.get('calories_unit', 'kcal')
        label.natriums = data.get('natriums', '')
        label.natriums_unit = data.get('natriums_unit', 'mg')
        label.carbohydrates = data.get('carbohydrates', '')
        label.carbohydrates_unit = data.get('carbohydrates_unit', 'g')
        label.sugars = data.get('sugars', '')
        label.sugars_unit = data.get('sugars_unit', 'g')
        label.fats = data.get('fats', '')
        label.fats_unit = data.get('fats_unit', 'g')
        label.trans_fats = data.get('trans_fats', '')
        label.trans_fats_unit = data.get('trans_fats_unit', 'g')
        label.saturated_fats = data.get('saturated_fats', '')
        label.saturated_fats_unit = data.get('saturated_fats_unit', 'g')
        label.cholesterols = data.get('cholesterols', '')
        label.cholesterols_unit = data.get('cholesterols_unit', 'mg')
        label.proteins = data.get('proteins', '')
        label.proteins_unit = data.get('proteins_unit', 'g')
        
        # 추가 영양성분
        label.dietary_fiber = data.get('dietary_fiber', '')
        label.dietary_fiber_unit = data.get('dietary_fiber_unit', 'g')
        label.calcium = data.get('calcium', '')
        label.calcium_unit = data.get('calcium_unit', 'mg')
        label.iron = data.get('iron', '')
        label.iron_unit = data.get('iron_unit', 'mg')
        
        # 식품 분류 정보
        label.food_group = data.get('food_group', '')
        label.food_type = data.get('food_type', '')
        
        # 알레르기 정보 저장 (원재료 사용 알레르기만 DB 저장)
        ingredient_allergens = data.get('ingredient_allergens', '')
        if ingredient_allergens:
            label.allergens = ingredient_allergens
        
        # 교차오염 알레르기는 caution에 추가
        cross_contamination = data.get('cross_contamination_allergens', '')
        if cross_contamination:
            cross_allergens_list = [a.strip() for a in cross_contamination.split(',') if a.strip()]
            if cross_allergens_list:
                cross_text = f"이 제품은 {', '.join(cross_allergens_list)}를 사용한 제품과 같은 제조시설에서 제조하고 있습니다."
                # 기존 caution이 있으면 줄바꿈 추가
                if label.cautions and label.cautions.strip():
                    label.cautions = label.cautions.strip() + '\n' + cross_text
                else:
                    label.cautions = cross_text
        
        # 저장
        label.save()
        
        # 저장 후 현재 페이지 유지 (신규/업데이트 모두)
        return JsonResponse({
            'success': True,
            'redirect_url': f'/?label_id={label.my_label_id}',
            'message': '표시사항이 저장되었습니다.',
            'label_id': label.my_label_id,
            'stay_on_page': True
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': '잘못된 데이터 형식입니다.'}, status=400)
    except Exception as e:
        import traceback
        print(f"Error saving label: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': f'저장 중 오류가 발생했습니다: {str(e)}'}, status=500)
