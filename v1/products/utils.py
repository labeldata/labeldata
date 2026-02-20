"""
제품 관리 유틸리티

V2는 이제 V1 MyLabel을 직접 사용합니다.
동기화 로직은 더 이상 필요하지 않습니다.
"""

from django.db.models import Q
from django.utils import timezone

from v1.label.models import MyLabel, LabelIngredient


# ==================== V1 데이터 어댑터 (조회 전용) ====================

class V1LabelAdapter:
    """V1 MyLabel 데이터 조회 헬퍼 (읽기 전용)"""
    
    @staticmethod
    def get_label_ingredients(label):
        """라벨의 원재료/영양성분 조회"""
        ingredients = LabelIngredient.objects.filter(
            my_label_id=label.my_label_id
        ).values_list('rawmtrl_name', 'rawmtrl_amount', 'unit')
        
        return [
            {
                'name': ing[0],
                'amount': ing[1],
                'unit': ing[2],
            }
            for ing in ingredients
        ]
    
    @staticmethod
    def get_user_labels(user, search_query=''):
        """
        사용자의 V1 MyLabel 조회
        
        Args:
            user: 사용자 객체
            search_query: 검색어
        
        Returns:
            MyLabel QuerySet
        """
        labels = MyLabel.objects.filter(creator=user)
        
        if search_query:
            labels = labels.filter(
                Q(product_name__icontains=search_query) |
                Q(product_code__icontains=search_query)
            )
        
        return labels
