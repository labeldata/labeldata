"""
공개데이터 수집용 날짜 검증 헬퍼.

식약처 공개데이터에는 허가일자가 5015-07-10 처럼 잘못 신고된 건이 섞여 들어온다.
수집기가 update_or_create 로 API 값을 그대로 덮어쓰기 때문에, DB 를 손으로 고쳐도
다음 수집 때 되돌아간다. 저장 시점에 걸러야 한다.

모델을 import 하지 않는 순수 함수 모듈이라 어느 앱에서든 가져다 쓸 수 있다.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# 반드시 과거(또는 오늘)여야 하는 yyyymmdd 필드명.
# 유통기한·소비기한(expirde_*)은 정상적으로 미래 날짜이므로 넣지 않는다.
PAST_ONLY_DATE_FIELDS = {
    'prms_dt',        # 허가일자        (FoodItem)
    'last_updt_dtm',  # 최종수정일자    (FoodItem / InspectionResult)
    'procs_dtm',      # 수입신고일자    (ImportedFood)
    'tkawydtm',       # 수거일자        (InspectionResult)
}

MIN_YEAR = 1900


def sanitize_past_date(value, context: str = '수집'):
    """
    과거여야 하는 yyyymmdd 값을 검증한다.

    - 정상  : 그대로 반환
    - 미래 / MIN_YEAR 이전 / 실재하지 않는 날짜 : '' 반환 (로그 남김)
    - 형식이 8자리 숫자가 아니면 판단하지 않고 원본 유지
      (API 형식이 바뀌었을 때 조용히 지워버리지 않기 위함)
    """
    v = str(value or '').strip()
    if len(v) != 8 or not v.isdigit():
        return value

    try:
        parsed = datetime.strptime(v, '%Y%m%d').date()
    except ValueError:
        logger.warning('[%s] 실재하지 않는 날짜로 제외: %s', context, v)
        return ''

    if parsed > datetime.now().date():
        logger.warning('[%s] 미래 날짜로 제외: %s', context, v)
        return ''
    if parsed.year < MIN_YEAR:
        logger.warning('[%s] %d년 이전 날짜로 제외: %s', context, MIN_YEAR, v)
        return ''
    return v
