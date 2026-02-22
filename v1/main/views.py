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
    """루트 URL: V2 신규홈(home_dashboard)으로 이동"""
    return redirect('main:home_dashboard')

def home_v1(request):
    """
    홈 페이지 (표시사항 작성 기능 포함)
    로그인 없이 누구나 접근 가능
    label_id 파라미터가 있으면 해당 라벨 데이터 로드
    """
    # UI 모드를 V1으로 설정 (이후 페이지들이 V1 스타일을 사용하도록)
    request.session['ui_mode'] = 'v1'
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
                'my_label_name': current_label.my_label_name or '',
                'prdlst_nm': current_label.prdlst_nm or '',
                'ingredient_info': current_label.ingredient_info or '',
                'prdlst_dcnm': current_label.prdlst_dcnm or '',
                'prdlst_report_no': current_label.prdlst_report_no or '',
                'report_no_verify_YN': current_label.report_no_verify_YN or 'N',  # 검증 상태 추가
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
        
        # 라벨명 설정
        label_name = data.get('label_name', '').strip()
        if label_name:
            # 사용자가 입력한 라벨명 사용
            label.my_label_name = label_name
        elif not is_update:
            # 신규 생성 시만 자동 생성
            label.my_label_name = data.get('prdlst_nm', '표시사항') + '_' + timezone.now().strftime('%Y%m%d')
        # is_update이고 label_name이 비어있으면 기존 값 유지
        
        # 기본 정보
        label.prdlst_nm = data.get('prdlst_nm', '')
        label.ingredient_info = data.get('ingredient_info', '')
        label.prdlst_dcnm = data.get('prdlst_dcnm', '')
        
        # 품목보고번호 변경 감지 및 검증 상태 관리
        new_prdlst_report_no = data.get('prdlst_report_no', '')
        new_verify_status = data.get('report_no_verify_YN', 'N')  # 클라이언트에서 보낸 검증 상태
        
        print(f"🔍 [DEBUG] 품목보고번호 처리:")
        print(f"  - 새 번호: {new_prdlst_report_no}")
        print(f"  - 새 검증상태: {new_verify_status}")
        print(f"  - is_update: {is_update}")
        
        if is_update:
            # 기존 라벨 업데이트 시
            orig_label = MyLabel.objects.get(my_label_id=label_id)
            print(f"  - 기존 번호: {orig_label.prdlst_report_no}")
            print(f"  - 기존 검증상태: {orig_label.report_no_verify_YN}")
            
            label.prdlst_report_no = new_prdlst_report_no
            
            if orig_label.prdlst_report_no != new_prdlst_report_no:
                # 품목보고번호가 변경된 경우
                print(f"  ✅ 번호 변경됨 - 새 검증상태 사용: {new_verify_status}")
                # 클라이언트에서 새 번호에 대한 검증 상태를 보냈으면 사용, 없으면 'N'
                label.report_no_verify_YN = new_verify_status if new_verify_status else 'N'
            else:
                # 품목보고번호가 변경되지 않은 경우
                print(f"  ⚠️ 번호 유지")
                # 클라이언트에서 검증 상태를 보냈으면 그것을 사용, 없으면 기존 상태 유지
                if new_verify_status and new_verify_status != 'N':
                    print(f"  ✅ 새 검증상태 사용: {new_verify_status}")
                    label.report_no_verify_YN = new_verify_status
                else:
                    print(f"  ✅ 기존 검증상태 유지: {orig_label.report_no_verify_YN}")
                    label.report_no_verify_YN = orig_label.report_no_verify_YN
        else:
            # 신규 생성 시
            print(f"  ✅ 신규 생성 - 검증상태: {new_verify_status}")
            label.prdlst_report_no = new_prdlst_report_no
            # 클라이언트에서 검증 상태를 보냈으면 사용, 없으면 'N'
            label.report_no_verify_YN = new_verify_status if new_verify_status else 'N'
        
        print(f"  💾 최종 저장 값: report_no={label.prdlst_report_no}, verify_YN={label.report_no_verify_YN}")
        print(f"")  # 빈 줄
        
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


# ============================================================
# V2 대시보드 홈
# ============================================================

def home_dashboard(request):
    """
    V2 메인 대시보드 홈 페이지 (신규홈, 메인 주소)
    - 비로그인 게스트: 서비스 소개 + 로그인/회원가입 유도 (대시보드만 접속 가능)
    - 로그인 사용자: 제품·협업·진행상태 통계 요약 및 최근 활동 표시
    """
    # UI 모드를 V2로 설정
    request.session['ui_mode'] = 'v2'

    # ── 비로그인 게스트: 빈 context로 게스트용 화면 렌더링 ──────
    if not request.user.is_authenticated:
        context = {
            'is_guest': True,
            'my_count': 0,
            'collab_count': 0,
            'starred_count': 0,
            'status_counts': {'DRAFT': 0, 'REQUESTING': 0, 'SUBMITTED': 0,
                              'REVIEW': 0, 'PENDING': 0, 'CONFIRMED': 0},
            'progress_pct': 0,
            'confirmed_count': 0,
            'total_with_meta': 0,
            'recent_labels': [],
            'unread_notif_count': 0,
            'expiring_count': 0,
        }
        return render(request, 'main/home_v2_dashboard.html', context)

    # ── 로그인 사용자: 개인화 통계 조회 ────────────────────────
    from v1.products.models import ProductMetadata, ProductShare, ProductNotification
    from django.db.models import Q, Count
    from django.utils import timezone

    user = request.user

    # ── 내 제품 관련 통계 ──────────────────────────────────────
    my_labels = MyLabel.objects.filter(user_id=user, delete_YN='N')
    my_count = my_labels.count()

    # 공유받은 제품 (협업 중)
    now = timezone.now()
    shared_ids = list(
        ProductShare.objects.filter(
            recipient_user=user,
            is_active=True,
        ).filter(
            Q(share_end_date__isnull=True) | Q(share_end_date__gt=now)
        ).values_list('label_id', flat=True)
    )
    collab_count = len(set(shared_ids))

    # 즐겨찾기 수 (내 제품 + 공유받은 제품 포함 — product_explorer ALL 기준과 동일)
    starred_count = ProductMetadata.objects.filter(
        Q(label__user_id=user) | Q(label__my_label_id__in=shared_ids),
        is_starred=True
    ).count()

    # 상태별 카운트 (내 제품 기준)
    status_counts = {'DRAFT': 0, 'REQUESTING': 0, 'SUBMITTED': 0,
                     'REVIEW': 0, 'PENDING': 0, 'CONFIRMED': 0}
    for meta in ProductMetadata.objects.filter(label__user_id=user, label__delete_YN='N').values('status'):
        s = meta['status'] or 'DRAFT'
        if s in status_counts:
            status_counts[s] += 1

    # 총 완료(승인 완료) 비율
    total_with_meta = sum(status_counts.values())
    confirmed_count = status_counts.get('CONFIRMED', 0)
    progress_pct = int(confirmed_count / total_with_meta * 100) if total_with_meta else 0

    # ── 최근 수정 제품 5개 ──────────────────────────────────────
    recent_labels = my_labels.order_by('-update_datetime')[:5]

    # ── 읽지 않은 알림 수 ──────────────────────────────────────
    try:
        unread_notif_count = ProductNotification.objects.filter(
            recipient=user, is_read=False
        ).count()
    except Exception:
        unread_notif_count = 0

    # ── 만료 임박 문서 (30일 이내) ──────────────────────────────
    from v1.products.models import ProductDocument
    expiring_count = 0
    try:
        expiry_threshold = now + timezone.timedelta(days=30)
        expiring_count = ProductDocument.objects.filter(
            label__user_id=user,
            is_active=True,
            expiry_date__isnull=False,
            expiry_date__lte=expiry_threshold,
            expiry_date__gte=now.date(),
        ).count()
    except Exception:
        expiring_count = 0

    context = {
        'is_guest': False,
        'my_count': my_count,
        'collab_count': collab_count,
        'starred_count': starred_count,
        'status_counts': status_counts,
        'progress_pct': progress_pct,
        'confirmed_count': confirmed_count,
        'total_with_meta': total_with_meta,
        'recent_labels': recent_labels,
        'unread_notif_count': unread_notif_count,
        'expiring_count': expiring_count,
    }
    return render(request, 'main/home_v2_dashboard.html', context)


