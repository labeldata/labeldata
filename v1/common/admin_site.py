from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
import calendar
import json
from v1.label.models import MyLabel, MyIngredient
from v1.board.models import Board, Comment
from .models import UserActivityLog, CATEGORY_CHOICES, ACTION_CHOICES


class CustomAdminSite:
    """
    대시보드 통계 및 분석 기능을 제공하는 클래스
    - URL: /dashboard/
    - 권한: staff_member_required (views.py의 dashboard_view에서 제어)
    - 기능: 사용자 통계, 콘텐츠 현황, 활동 분석, 차트 데이터 생성
    """
    
    def get_period_dates(self, period, selected_year=None):
        """기간 선택에 따른 시작일/종료일 계산"""
        from datetime import datetime
        
        now = timezone.now()
        current_year = now.year
        # 선택된 연도가 있으면 사용, 없으면 현재 연도 사용
        target_year = selected_year if selected_year else current_year
        current_quarter = (now.month - 1) // 3 + 1  # 1, 2, 3, 4분기
        current_half = 1 if now.month <= 6 else 2  # 1: 상반기, 2: 하반기
        
        # 분기별 처리
        if period.startswith('quarter'):
            if period == 'quarter':
                quarter_num = current_quarter
            else:
                quarter_num = int(period.replace('quarter', ''))
            
            # 분기 시작/종료 월 계산
            quarter_start_month = (quarter_num - 1) * 3 + 1
            quarter_end_month = quarter_num * 3
            
            # 기간 시작일
            period_start = now.replace(year=target_year, month=quarter_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
            # 기간 종료일: 해당 분기 마지막 달의 마지막 날
            last_day_of_quarter = calendar.monthrange(target_year, quarter_end_month)[1]
            period_end = now.replace(year=target_year, month=quarter_end_month, day=last_day_of_quarter, hour=23, minute=59, second=59, microsecond=999999)
            
            # 이전 분기 계산
            prev_quarter_num = quarter_num - 1 if quarter_num > 1 else 4
            prev_quarter_start_month = (prev_quarter_num - 1) * 3 + 1
            prev_quarter_end_month = prev_quarter_num * 3
            prev_year = target_year if prev_quarter_num < 4 else target_year - 1
            
            previous_period_start = now.replace(year=prev_year, month=prev_quarter_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day_of_prev_quarter = calendar.monthrange(prev_year, prev_quarter_end_month)[1]
            previous_period_end = now.replace(year=prev_year, month=prev_quarter_end_month, day=last_day_of_prev_quarter, hour=23, minute=59, second=59, microsecond=999999)
            
            period_display = f"{target_year}년 {quarter_num}분기"
            
        # 반기별 처리
        elif period.startswith('half_year'):
            if period == 'half_year':
                half_num = current_half
            else:
                half_num = int(period.replace('half_year', ''))
            
            # 반기 시작/종료 월
            half_start_month = 1 if half_num == 1 else 7
            half_end_month = 6 if half_num == 1 else 12
            
            period_start = now.replace(year=target_year, month=half_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day_of_half = calendar.monthrange(target_year, half_end_month)[1]
            period_end = now.replace(year=target_year, month=half_end_month, day=last_day_of_half, hour=23, minute=59, second=59, microsecond=999999)
            
            # 이전 반기
            prev_half_num = 1 if half_num == 2 else 2
            prev_half_start_month = 1 if prev_half_num == 1 else 7
            prev_half_end_month = 6 if prev_half_num == 1 else 12
            prev_year = target_year if half_num == 1 else target_year - 1
            
            previous_period_start = now.replace(year=prev_year, month=prev_half_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day_of_prev_half = calendar.monthrange(prev_year, prev_half_end_month)[1]
            previous_period_end = now.replace(year=prev_year, month=prev_half_end_month, day=last_day_of_prev_half, hour=23, minute=59, second=59, microsecond=999999)
            
            period_display = f"{target_year}년 {'상반기' if half_num == 1 else '하반기'}"
            
        # 연도별 처리
        elif period.startswith('year'):
            if period == 'year':
                year_num = current_year
            else:
                year_num = int(period.replace('year', ''))
            
            period_start = now.replace(year=year_num, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = now.replace(year=year_num, month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
            
            previous_period_start = now.replace(year=year_num - 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            previous_period_end = now.replace(year=year_num - 1, month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
            
            period_display = f"{year_num}년"
            
        # 기본 기간 (week, month)
        else:
            period_days = {
                'week': 7,
                'month': 30,
            }
            days = period_days.get(period, 7)
            
            # 선택된 연도가 있으면 해당 연도 기준으로 계산
            if selected_year:
                # 해당 연도의 동일 기간 (현재 월/일 기준)
                try:
                    reference_date = now.replace(year=target_year)
                except ValueError:
                    # 2월 29일 같은 경우 예외 처리
                    reference_date = now.replace(year=target_year, day=28)
                period_end = reference_date
                period_start = reference_date - timedelta(days=days)
                previous_period_start = period_start - timedelta(days=days)
                previous_period_end = period_start
            else:
                period_start = now - timedelta(days=days)
                period_end = now
                previous_period_start = now - timedelta(days=days * 2)
                previous_period_end = period_start
            
            period_display = f"{period_start.strftime('%m/%d')} ~ {period_end.strftime('%m/%d')}"
        
        return period_start, period_end, previous_period_start, previous_period_end, period_display

    def calculate_change_rate(self, current, previous):
        """이전 기간 대비 증감률 계산"""
        if previous == 0:
            return 0.0 if current == 0 else 100.0
        return round(((current - previous) / previous) * 100, 1)

    def get_total_stats(self):
        """전체 누적 통계"""
        # 전체 사용자
        total_users = User.objects.count()
        
        # 전체 표시사항 (기간별 증감 계산)
        total_labels = MyLabel.objects.filter(delete_YN='N').count()
        
        # 전체 원료 (기간별 증감 계산)
        total_ingredients = MyIngredient.objects.filter(delete_YN='N').count()
        
        # 전체 게시글
        total_boards = Board.objects.count()
        
        return {
            'total_users': total_users,
            'total_labels': total_labels,
            'total_ingredients': total_ingredients,
            'total_boards': total_boards,
        }

    def get_period_stats(self, period_start, period_end, previous_period_start, previous_period_end):
        """기간별 통계 (WAU, 신규 가입자 등)"""
        now = timezone.now()
        
        # 주간 활성 사용자 (WAU) - 최근 7일간 로그인한 사용자
        wau_start = now - timedelta(days=7)
        wau = User.objects.filter(last_login__gte=wau_start).count()
        prev_wau = User.objects.filter(
            last_login__gte=wau_start - timedelta(days=7),
            last_login__lt=wau_start
        ).count()
        
        # 기간 내 신규 가입자
        new_users = User.objects.filter(
            date_joined__gte=period_start,
            date_joined__lte=period_end
        ).count()
        prev_new_users = User.objects.filter(
            date_joined__gte=previous_period_start,
            date_joined__lte=previous_period_end
        ).count()
        
        # 기간 내 신규 표시사항
        new_labels = MyLabel.objects.filter(
            delete_YN='N',
            create_datetime__gte=period_start,
            create_datetime__lte=period_end
        ).count()
        prev_new_labels = MyLabel.objects.filter(
            delete_YN='N',
            create_datetime__gte=previous_period_start,
            create_datetime__lte=previous_period_end
        ).count()
        
        # 기간 내 신규 원료
        new_ingredients = MyIngredient.objects.filter(
            delete_YN='N',
            update_datetime__gte=period_start,
            update_datetime__lte=period_end
        ).count()
        prev_new_ingredients = MyIngredient.objects.filter(
            delete_YN='N',
            update_datetime__gte=previous_period_start,
            update_datetime__lte=previous_period_end
        ).count()
        
        # 삭제된 데이터
        deleted_labels = MyLabel.objects.filter(delete_YN='Y').count()
        deleted_ingredients = MyIngredient.objects.filter(delete_YN='Y').count()
        
        return {
            'wau': wau,
            'wau_change': self.calculate_change_rate(wau, prev_wau),
            'new_users': new_users,
            'new_users_change': self.calculate_change_rate(new_users, prev_new_users),
            'new_labels': new_labels,
            'new_labels_change': self.calculate_change_rate(new_labels, prev_new_labels),
            'new_ingredients': new_ingredients,
            'new_ingredients_change': self.calculate_change_rate(new_ingredients, prev_new_ingredients),
            'deleted_labels': deleted_labels,
            'deleted_ingredients': deleted_ingredients,
        }

    def get_category_stats(self, period_start, previous_period_start):
        """기능별 사용 통계 - 새로운 구조"""
        from .models import UserActivityLog
        
        category_stats = []
        
        # 새로운 구조: 순서대로 정의
        feature_config = [
            # 메인 기능 (7개)
            {'title': '표시사항 저장', 'actions': ['label_save']},
            {'title': '원료 저장', 'actions': ['ingredient_save']},
            {'title': '영양성분 계산기', 'actions': ['calculator_calc', 'calculator_save']},
            {'title': '제품 조회(국내)', 'actions': ['search_domestic']},
            {'title': '제품 조회(수입)', 'actions': ['search_import']},
            {'title': '식품첨가물 조회', 'actions': ['search_additive']},
            {'title': '게시판 등록', 'actions': ['board_post', 'board_comment']},
        ]
    def get_category_stats(self, period_start, period_end, previous_period_start, previous_period_end):
        """기능별 사용 통계 - 새로운 구조"""
        from .models import UserActivityLog
        
        category_stats = []
        
        # 새로운 구조: 순서대로 정의
        feature_config = [
            # 메인 기능 (7개)
            {'title': '표시사항 저장', 'actions': ['label_save']},
            {'title': '원료 저장', 'actions': ['ingredient_save']},
            {'title': '영양성분 계산기', 'actions': ['calculator_calc', 'calculator_save']},
            {'title': '제품 조회(국내)', 'actions': ['search_domestic']},
            {'title': '제품 조회(수입)', 'actions': ['search_import']},
            {'title': '식품첨가물 조회', 'actions': ['search_additive']},
            {'title': '게시판 등록', 'actions': ['board_post', 'board_comment']},
            
            # 조회 복사 (2개)
            {'title': '검색에서 표시사항 복사', 'actions': ['search_label_copy'], 'parent': '조회 복사'},
            {'title': '검색에서 내원료 복사', 'actions': ['search_ingredient_copy'], 'parent': '조회 복사'},
            
            # 표시사항 작성 세부기능 (9개)
            {'title': '품목보고번호 검증', 'actions': ['validation_report'], 'parent': '표시사항 작성'},
            {'title': '알레르기 감지', 'actions': ['allergen_auto_detect'], 'parent': '표시사항 작성'},
            {'title': '원재료 표로 입력', 'actions': ['ingredient_table_input'], 'parent': '표시사항 작성'},
            {'title': '원재료 빠른 등록', 'actions': ['ingredient_quick_register'], 'parent': '표시사항 작성'},
            {'title': '주의문구 빠른 등록', 'actions': ['caution_quick_add'], 'parent': '표시사항 작성'},
            {'title': '기타문구 빠른 등록', 'actions': ['other_text_quick_add'], 'parent': '표시사항 작성'},
            {'title': '맞춤항목 등록', 'actions': ['custom_field_use'], 'parent': '표시사항 작성'},
            {'title': '간편/상세 전환', 'actions': ['mode_switch'], 'parent': '표시사항 작성'},
            {'title': '선택 복사', 'actions': ['selection_copy'], 'parent': '표시사항 작성'},
            
            # 미리보기 팝업 세부기능 (7개)
            {'title': '표 설정', 'actions': ['preview_table_settings'], 'parent': '미리보기 팝업'},
            {'title': '항목 순서', 'actions': ['preview_order'], 'parent': '미리보기 팝업'},
            {'title': '텍스트 변환', 'actions': ['preview_text_transform'], 'parent': '미리보기 팝업'},
            {'title': '분리배출마크', 'actions': ['preview_recycling_mark'], 'parent': '미리보기 팝업'},
            {'title': '규정 검증', 'actions': ['validation_nutrition'], 'parent': '미리보기 팝업'},
            {'title': 'PDF 저장', 'actions': ['preview_pdf_save'], 'parent': '미리보기 팝업'},
            {'title': '설정 저장', 'actions': ['preview_settings_save'], 'parent': '미리보기 팝업'},
        ]
        
        # UserActivityLog가 있는 경우
        if UserActivityLog.objects.exists():
            for config in feature_config:
                # 현재 기간 통계
                current_count = UserActivityLog.objects.filter(
                    action__in=config['actions'],
                    created_at__gte=period_start,
                    created_at__lte=period_end
                ).count()
                
                # 이전 기간 통계
                previous_count = UserActivityLog.objects.filter(
                    action__in=config['actions'],
                    created_at__gte=previous_period_start,
                    created_at__lte=previous_period_end
                ).count()
                
                change = self.calculate_change_rate(current_count, previous_count)
                
                stat = {
                    'title': config['title'],
                    'current': current_count,
                    'previous': previous_count,
                    'change': change
                }
                
                if 'parent' in config:
                    stat['parent'] = config['parent']
                
                category_stats.append(stat)
        else:
            # UserActivityLog가 없는 경우 기본값 반환
            for config in feature_config:
                stat = {
                    'title': config['title'],
                    'current': 0,
                    'previous': 0,
                    'change': 0.0
                }
                if 'parent' in config:
                    stat['parent'] = config['parent']
                category_stats.append(stat)
        
        return category_stats

    def get_recent_data(self):
        """최근 활동 데이터"""
        return {
            'recent_users': User.objects.order_by('-date_joined')[:10],
            'recent_labels': MyLabel.objects.filter(delete_YN='N').select_related('user_id').order_by('-update_datetime')[:10],
            'recent_ingredients': MyIngredient.objects.filter(delete_YN='N').select_related('user_id').order_by('-update_datetime')[:10],
            'recent_boards': Board.objects.select_related('author').order_by('-created_at')[:10],
        }
