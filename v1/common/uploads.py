"""
올릴 수 있는 파일의 크기 — 한곳에서 정한다.

한도가 화면마다 달랐다. 문서함 50 MB, 표시사항 사진 10 MB, 원료 사진 10 MB,
시안 20 MB, 판독 실험실 10 MB, 편집기 5 MB. 같은 성적서를 문서함에는 올릴 수
있는데 표시사항 사진으로는 못 올렸고, 왜 안 되는지 화면마다 다른 말을 했다.

**두 가지를 가른다.**

    한 파일   그 요청 하나가 서버 메모리와 시간을 얼마나 쓰는가
    한 사람   그 계정이 디스크를 통틀어 얼마나 쓰는가

앞의 것은 등급과 무관하다 — 돈을 낸다고 서버가 더 견디지는 않는다. 뒤의 것은
쌓여 있는 동안 자리를 차지하므로 저량 한도(quota.STOCK)로 센다.
"""
from django.conf import settings

# 한 파일의 상한. 성적서 스캔본이 20 MB 를 넘는 일이 있어 30 MB 로 둔다.
# 이보다 크면 요청 자체가 오래 걸려 서버가 끊는다(PythonAnywhere 300초).
MAX_UPLOAD_MB = getattr(settings, 'MAX_UPLOAD_MB', 30)
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


# 받아도 되는 확장자.
#
# 화면의 `accept=` 는 파일 선택창의 필터일 뿐 강제가 아니다 — 요청을 직접
# 만들면 무엇이든 온다. 특히 `.html`·`.svg` 는 같은 오리진에서 inline 으로
# 렌더되므로(media_access 의 static_serve 는 Content-Disposition 을 붙이지
# 않는다) 그 파일을 여는 사람 — 대개 요청자 — 의 브라우저에서 돈다.
ALLOWED_UPLOAD_EXTS = (
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp',
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.hwp', '.hwpx', '.txt', '.csv', '.zip',
)


def _mb(size):
    return size / 1024.0 / 1024.0


def stored_bytes(user):
    """
    이 사람이 올려 둔 파일의 합. 지운 것은 빼고 센다.

    문서함(ProductDocument)과 요청받아 제출된 파일(DocumentSubmission)을 함께
    센다 — 디스크는 그 둘을 가리지 않는다.
    """
    from django.db.models import Sum

    from v1.products.models import DocumentSubmission, ProductDocument

    total = ProductDocument.objects.filter(
        label__user_id=user, active_yn=True).aggregate(
            n=Sum('file_size'))['n'] or 0
    # 요청해서 받은 파일도 이 사람 디스크에 쌓인다. 요청을 건 사람이 주인이다
    total += DocumentSubmission.objects.filter(
        request__requester=user, active_yn=True).aggregate(
            n=Sum('file_size'))['n'] or 0
    return int(total)


def check(user, uploaded, kind='파일'):
    """
    이 파일을 받아도 되는가.

    Returns: 안 되면 사람에게 할 말(문자열), 되면 None.

    **왜 안 되는지 그 자리에서 말한다.** "파일이 큽니다" 만으로는 사용자가
    무엇을 해야 하는지 모른다 — 얼마나 큰지, 한도가 얼마인지, 무엇을 하면
    되는지까지 적는다.
    """
    if uploaded is None:
        return '%s가 없습니다.' % kind

    import os

    ext = os.path.splitext(getattr(uploaded, 'name', '') or '')[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTS:
        return ('%s 확장자(%s)는 올릴 수 없습니다. '
                '올릴 수 있는 것: %s'
                % (kind, ext or '없음', ', '.join(ALLOWED_UPLOAD_EXTS)))

    size = getattr(uploaded, 'size', 0) or 0
    if size > MAX_UPLOAD_BYTES:
        return ('%s 하나는 %d MB 까지 올릴 수 있습니다 (지금 %.1f MB). '
                '사진이면 해상도를 줄이거나, 여러 장으로 나눠 올려 주세요.'
                % (kind, MAX_UPLOAD_MB, _mb(size)))

    from v1.common import quota

    limit = quota.limit_for(user, 'storage')
    if limit:
        used = stored_bytes(user)
        if used + size > limit * 1024 * 1024:
            return ('올린 파일이 %d MB 한도에 닿았습니다 (지금 %.0f MB). '
                    '문서함에서 오래된 파일을 지우거나 요금제를 올려 주세요.'
                    % (limit, _mb(used)))
    return None
