"""
Django settings for config project.
"""
from pathlib import Path
from decouple import config, UndefinedValueError
import datetime

# Build paths inside the project like this: BASE_DIR / 'subdir'.
try:
    BASE_DIR = Path(__file__).resolve().parent.parent
except NameError:
    BASE_DIR = Path.cwd()

# Load sensitive information from .env
try:
    SECRET_KEY = config('DJANGO_SECRET_KEY', default='your-secret-key')
    DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)
    ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='127.0.0.1,localhost').split(',')

except UndefinedValueError as e:
    raise Exception("Missing environment variable: {}".format(e))


# ── 자리만 채워 둔 비밀로는 운영에 뜨지 않는다 ──────────────────────────────
#
# 위의 try/except 는 "환경변수가 없으면 뜨지 마라" 는 뜻으로 쓴 그물이다.
# 그런데 같은 줄의 `default=` 가 그 그물을 무력화하고 있었다 — .env 가 통째로
# 빠져도 예외가 나지 않고, **소스에 적힌 그 값으로 그냥 뜬다.**
#
# 무엇이 걸려 있나.
#
#     SECRET_KEY   세션·CSRF 토큰·비밀번호 재설정 링크가 전부 이 값에서 나온다.
#                  소스를 본 사람은 남의 세션을 만들 수 있다.
#     DB_PASSWORD  말 그대로 DB 다.
#
# `default=` 를 그냥 지우지 않는 까닭은 **개발 PC 를 멈추지 않기 위해서**다.
# 로컬 .env 에는 DB_ 항목이 없고 로컬 MySQL 은 그 기본값으로 붙어 있다.
# 그래서 기본값은 남기되 **DEBUG 가 꺼진 곳에서만 거부**한다. 운영에서 이
# 값이 쓰이는 상황은 언제나 사고이고, 개발에서는 언제나 정상이다.
#
# 거부는 조용히 하지 않는다. 여기서 멈추는 편이, 그 비밀로 몇 달 더 도는
# 것보다 낫다.
_PLACEHOLDER_SECRETS = {
    'DJANGO_SECRET_KEY': 'your-secret-key',
    'DB_PASSWORD': 'labeldata1!',
}


def _reject_placeholder(name, value):
    """운영(DEBUG=False)에서 소스에 적힌 기본값이 쓰이면 뜨지 못하게 한다."""
    if DEBUG:
        return value
    if value == _PLACEHOLDER_SECRETS.get(name):
        raise Exception(
            "{0} 가 .env 에 없습니다. 지금 소스에 적힌 기본값으로 뜨려 하고 "
            "있는데, 그 값은 저장소를 볼 수 있는 사람이면 누구나 압니다. "
            ".env 에 {0} 를 넣고 다시 띄우세요.".format(name)
        )
    return value


SECRET_KEY = _reject_placeholder('DJANGO_SECRET_KEY', SECRET_KEY)

# 커스텀 에러 페이지 테스트를 위한 설정 (개발 시에만 사용)
# 실제 운영에서는 DEBUG=False로 설정하면 자동으로 커스텀 에러 페이지가 작동합니다
SHOW_CUSTOM_ERROR_PAGES = config('SHOW_CUSTOM_ERROR_PAGES', default=False, cast=bool)

STATIC_BUILD_DATE = datetime.datetime.now().strftime('%Y%m%d%H%M')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django_bootstrap5',  # django-bootstrap5 사용
    'v1.main',           # Main 앱 (홈 페이지) ⚠️ 반드시 포함 필요!
    'v1.label',          # Label 앱
    'v1.disposition',    # Action 앱
    'v1.common',         # Common 앱
    'v1.user_management',
    'v1.board',          # Board 앱
    'v1.products',       # 제품 관리 (documents, collaboration, sharing 통합됨)
    'v1.bom',            # BOM 구조 관리
    'v1.regulatory',     # 부적합.처분 알림
    'v1.activity_log',   # 사용자 활동 로그
    'v1.label_editor',   # 라벨 에디터 (Figma-like)
    'v1.mobile',         # 모바일 앱 API
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'v1.config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'v1.common.context_processors.static_build_date',
                'v1.common.context_processors.guest_flag',
                'v1.common.context_processors.guest_promotion',
                'v1.common.context_processors.board_notifications',
                'v1.common.context_processors.ui_mode',
                'v1.common.context_processors.regulatory_alerts',
                'v1.common.context_processors.upload_limit',
            ],
        },
    },
]

WSGI_APPLICATION = 'v1.config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME', default='labeldb'),
        'USER': config('DB_USER', default='labeldata'),
        'PASSWORD': _reject_placeholder(
            'DB_PASSWORD', config('DB_PASSWORD', default='labeldata1!')),
        'HOST': config('DB_HOST', default='127.0.0.1'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"
        },
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = config('LANGUAGE_CODE', default='ko-kr')
TIME_ZONE = config('TIME_ZONE', default='Asia/Seoul')
USE_I18N = True
USE_TZ = True

# Static files 설정 개선
STATIC_URL = '/static/'

# 배포본에서만 주석을 걷어낸다 (v1.common.staticfiles).
#
# 우리 JS·CSS 주석은 "왜 그렇게 했는지" 를 적어 둔 팀의 자산인데, /static/ 은
# 로그인 없이 누구나 받는다. 소스에는 그대로 두고 collectstatic 이 옮길 때만
# 지운다. 무언가 깨지면 STATIC_MINIFY=0 으로 원본이 그대로 나간다.
STATIC_MINIFY = config('STATIC_MINIFY', default=not DEBUG, cast=bool)
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'v1.common.staticfiles.CommentStrippingStaticFilesStorage',
    },
}

# DEBUG 상태와 관계없이 정적 파일 경로 설정
STATICFILES_DIRS = [
    BASE_DIR / 'static'
]

if DEBUG:
    STATIC_ROOT = config('STATIC_ROOT', default=str(BASE_DIR.parent / 'staticfiles'))
else:
    STATIC_ROOT = config('STATIC_ROOT', default='/home/labeldata/mysite/staticfiles')

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = config('MEDIA_ROOT', default=str(BASE_DIR.parent / 'media'))

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login settings
LOGIN_URL = '/user-management/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = LOGIN_URL

# Security settings
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)

# 세션 설정
SESSION_COOKIE_AGE = 43200  # 12시간 (12 * 60 * 60 초)
SESSION_SAVE_EVERY_REQUEST = False  # 세션 내용 변경 시에만 저장 (CPU 절약)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # 브라우저 닫아도 세션 유지 (12시간까지)

# 파일 기반 캐시 — 수거검사 공개 목록 캐싱용 (스케줄러 실행 시 무효화)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': str(BASE_DIR.parent / 'django_cache'),
        'TIMEOUT': 60 * 60 * 6,  # 기본 TTL 6시간 (스케줄러 미실행 시 안전망)
        'OPTIONS': {'MAX_ENTRIES': 500},
    },
    # 속도 제한은 **따로 둔다.**
    #
    # default 는 MAX_ENTRIES 가 500 이라 자리가 차면 오래된 것을 버린다.
    # 세는 값이 그렇게 버려지면 제한이 조용히 풀린다 — 제한이 있다고 믿는데
    # 없는 것이 제일 나쁘다.
    #
    # 파일 캐시라 증가가 원자적이지 않다. 여러 일꾼이 같은 순간에 세면
    # 몇 번은 흘린다. 그래도 무제한으로 두드리는 것은 확실히 막는다 —
    # 정확한 회계가 목적이 아니라 대량 수집을 성가시게 만드는 것이 목적이다.
    'ratelimit': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': str(BASE_DIR.parent / 'django_cache_ratelimit'),
        'TIMEOUT': 60 * 60,
        'OPTIONS': {'MAX_ENTRIES': 20000},
    },
}
RATELIMIT_USE_CACHE = 'ratelimit'

# Django 기본 데이터베이스 세션 사용 (권한 문제로 현재 작동하지 않음)
# SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # 기본값

# 조회수 기능 활성화 여부 (데이터베이스 권한 문제 시 False로 설정)
ENABLE_VIEW_COUNT = config('ENABLE_VIEW_COUNT', default=True, cast=bool)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': 'django_errors.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}


# 이메일 발송 설정 (실제 서비스에서는 환경변수로 관리 권장)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='administrator@ezlabeling.com')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='xeenovaeuejedgji')
EMAIL_USE_TLS = True
# 보내는 사람 주소: Gmail은 인증 계정과 동일해야 스팸 처리 방지
# Gmail Workspace 계정은 별칭 전송 가능하지만 일반 계정은 HOST_USER와 일치 필요
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='administrator@ezlabeling.com')
# 표시용 발신자명 (이메일 클라이언트에서 "EzLabeling <administrator@...>" 형태로 표시)
EMAIL_FROM_DISPLAY  = 'EzLabeling <administrator@ezlabeling.com>'
# 시스템 공개 URL (이메일 내 링크에 사용)
SITE_URL = config('SITE_URL', default='https://www.ezlabeling.com')

# ── 부적합.처분 알림 설정 ──────────────────────────────────────────────────────
# OpenAI API Key (gpt-4o-mini 사용)
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')

# 표시사항 사진 판독에 쓸 모델.
#
# 기본은 gpt-4o-mini 다. 작은 글씨가 빽빽한 라벨에서 정확도가 아쉬우면
# .env 에 OCR_MODEL=gpt-4o 를 넣어 올릴 수 있다 - 한글 소자 판독이 눈에 띄게
# 낫지만 호출 비용이 10배가 넘는다. 다른 AI 기능(검증·문서분석)은 이 값을
# 쓰지 않는다. 판독만 바꾼다.
OCR_MODEL = config('OCR_MODEL', default='gpt-4o-mini')

# 주의사항·기타표시사항을 사진에서 읽을 것인가. 기본은 **읽는다.**
#
# 한동안 껐었다. 이 두 칸은 무엇을 해도 흔들렸다 - 상용 문구 목록을 프롬프트에
# 실으면 그 문장을 지어내고, 빼면 새 문장을 지어내고, 전용 칸을 만들면 알레르기
# 칸을 망쳤다(편차 80 이상). 화면에 빠른 입력 버튼 스물여덟 개가 있으니 손으로
# 채우는 편이 낫다고 봤다.
#
# 그런데 운영에서 그 판단이 뒤집혔다. 라벨에 실제로 인쇄된 주의사항·기타표시사항은
# 버튼 목록에 없는 문장이 많고, 사진을 올린 사람은 **그 칸이 왜 비어 있는지**부터
# 물었다. 안내 문구를 붙여도 "사진에 있는데 왜 안 읽나" 는 그대로였다.
#
# 지어낼 위험은 그대로지만, 이 값이 확인 창을 건너뛰는 일은 없다 - 사용자가
# 체크한 항목만 칸에 들어가고 저장은 따로 누른다. 읽어서 보여 주고 지우게 하는
# 쪽이, 안 읽고 처음부터 치게 하는 쪽보다 낫다.
#
# 되돌리려면 `.env` 에 OCR_READ_FREETEXT=False 를 넣는다. 측정 화면
# (/label/ocr-lab/)에서는 이 값과 무관하게 껐다 켜서 견줄 수 있다.
OCR_READ_FREETEXT = config('OCR_READ_FREETEXT', default=True, cast=bool)

# 사진에서 **글자 원문만** 뽑는 Google Cloud Vision.
#
# 판독(VLM)과 별개다. VLM 은 레이아웃 이해가 탁월한 대신 긴 문자열의 축자
# 전사를 못 하고, OCR 은 정확히 반대다 - 그 원문으로 판독값이 사진에 실제로
# 있던 글자인지 대조하려는 것이다 (OCR_UPGRADE_PLAN.md §13).
#
# 인증은 둘 중 하나면 된다. **API 키가 있으면 그걸 먼저 쓴다.**
#
#   GOOGLE_VISION_API_KEY                 붙이기 쉽다. 키에 "Cloud Vision API
#                                         로만" 제한을 반드시 걸 것
#   GOOGLE_VISION_SERVICE_ACCOUNT_JSON    JSON 본문 또는 파일 경로. 비워 두면
#                                         FCM 것을 쓴다 (대개 같은 프로젝트)
#
# 어느 쪽이든 그 프로젝트에서 **Cloud Vision API 를 켜 두어야** 한다.
#
# 둘 다 안 넣어도 판독은 지금 그대로 돈다. 원문은 곁들이는 것이지 있어야 하는
# 것이 아니다.
GOOGLE_VISION_API_KEY = config('GOOGLE_VISION_API_KEY', default='')
GOOGLE_VISION_SERVICE_ACCOUNT_JSON = config(
    'GOOGLE_VISION_SERVICE_ACCOUNT_JSON', default='')

# 판독값을 사진의 글자 원문과 대조할 것인가. 기본은 **끔**.
#
# 켜면 판독 한 번에 Vision 호출이 하나 더 붙는다 - 비용(월 1,000건 무료)과
# 시간이 늘고, 무엇보다 지금 100점인 칸들에 새 판단이 얹힌다. 값을 바꾸지는
# 않고 확신도만 내리지만, 그래도 앞뒤를 재 보고 켠다.
#
# 측정 화면(/label/ocr-lab/)에서는 이 값과 무관하게 켜서 견줄 수 있다.
OCR_GROUND = config('OCR_GROUND', default=False, cast=bool)

# OCR 원문을 판독에 **함께 넣을 것인가.** 기본은 끔.
#
# 켜면 조각 이미지를 빼고 원문을 대신 싣는다. 조각은 오직 글자를 읽으려고
# 붙인 것인데 그 일은 OCR 이 더 잘한다(정답지 5장, 긴 칸 회수율 0.977).
# VLM 에게는 어느 값이 어느 항목인가만 맡긴다 - 거기서는 100점·편차 0 이다.
#
#   토큰   6~7만 -> 1.5~2만 (약 70% 절감)
#   정확도 자유 문구 두 칸(25~52점)에서 오를 것으로 본다
#
# **측정 없이 켜지 마시오.** 판독의 핵심 경로를 바꾸는 일이고, 지금 100점인
# 칸들이 흔들릴 수 있다. /label/ocr-lab/ 에서 이 옵션을 켜고 끈 결과를 견준
# 뒤에 켠다.
OCR_HYBRID = config('OCR_HYBRID', default=False, cast=bool)

# 원문을 넣을 때 **조각 이미지까지 뺄 것인가.** 기본은 빼지 않는다.
#
# 토큰은 조각을 빼야 줄지만(6~7만 -> 1.5~2만), 측정이 그 대가를 보여 줬다.
#
#     rawmtrl_nm       80.2 -> 99.4    원문이 이겼다
#     nutrition_basis 100.0 -> 37.0    조각을 뺀 대가
#     recycling_mark  100.0 -> 84.8
#     storage_method  100.0 -> 88.9
#
# 무너진 셋은 **배치를 봐야 읽히는 칸**이다 - 표의 머리글, 도형, 표 칸.
# 원문은 줄을 늘어놓을 뿐 그 구조를 담지 못한다.
#
# 그래서 정확도(OCR_HYBRID)와 토큰 절감(이 값)을 갈라 둔다. 아끼려면 켜되
# 먼저 재라.
OCR_HYBRID_DROP_TILES = config('OCR_HYBRID_DROP_TILES', default=False, cast=bool)

# 제조원·유통전문판매원·소분원·수입원이 수상하면 **그 네 줄만** 다시 읽는다.
#
# 넷은 거의 언제나 다른 회사인데 라벨에서는 한 표 안에 붙어 찍히고, 넷이 전부
# "업체명 + 주소" 로 똑같이 생겼다. 값만 보고는 어느 칸의 것인지 알 수 없어서
# 두 칸에 같은 회사가 들어와도 그 자리에서는 아무도 모른다.
#
# 켜 두는 이유는 **틀린 낌새가 보일 때만 돌기 때문**이다(ocr_company.
# needs_recheck). 값이 멀쩡하면 한 번도 돌지 않아 평소 비용은 그대로다.
OCR_COMPANY_RECHECK = config('OCR_COMPANY_RECHECK', default=True, cast=bool)

# 업소 항목을 **늘** 한 번 더 읽는다.
#
# 위의 RECHECK 는 "수상할 때만" 이다. 그것으로는 지어낸 주소를 못 잡는다 —
# 회사 이름은 맞고 주소만 틀리면 어떤 규칙에도 안 걸린다. 실제로 "안양시
# 동안구 흥안대로 405" 가 "양주시 도하로 405" 로 나왔는데, 형식도 멀쩡하고
# 그런 도로명도 실제로 있어서 값만 보고는 알 수가 없었다.
#
# 두 번 읽어 견주는 것이 지금 할 수 있는 유일한 확인이다. 판독 한 번에
# 네 줄만 묻는 짧은 호출이 하나 더 붙는다 — 비용이 문제가 되면 끈다.
OCR_COMPANY_VERIFY = config('OCR_COMPANY_VERIFY', default=True, cast=bool)

# ── 한도 ──────────────────────────────────────────────────────────────
#
# 두 가지를 섞지 않는다.
#
#   서버 보호 한도   등급과 무관하다. 돈을 낸다고 서버가 더 견디지는 않는다
#   요금 한도        등급별로 다르다. v1/common/quota.py 가 본다

# 한 번에 붙여넣어 받을 수 있는 줄 수. 서버 보호 한도다.
PASTE_MAX_ROWS = config('PASTE_MAX_ROWS', default=2000, cast=int)

# 기능별 요금 한도를 코드를 고치지 않고 덮어쓰는 자리.
# 기본값은 quota.FEATURES 에 있고, 지금은 쓰는 사람을 막지 않도록 넉넉하다.
# 요금제를 실제로 열 때 여기에 적어 내리면 배포 없이 바뀐다.
#
#   QUOTA_LIMITS = {
#       'ingredient':  {'free': 300,  'paid': 20000},
#       'ocr_label':   {'free': 5,    'paid': 300},
#       'ocr_compare': {'free': 2,    'paid': 100},
#   }
QUOTA_LIMITS = {}

# OpenAI 의 분당 토큰 한도(TPM). 정답지 측정이 판독 사이를 얼마나 쉴지 계산하는
# 데 쓴다 (ocr_lab.pace_seconds).
#
# 기본 200,000 은 gpt-4o-mini 의 사용 등급 1 값이다. 판독 한 번이 6~7만
# 토큰이니 **분당 세 번**이 한계고, 그보다 빨리 부르면 429 다.
#
# 등급이 오르면 이 값을 함께 올려야 측정이 빨라진다. 안 올리면 필요 없는
# 대기로 시간만 쓴다 - 5장 3회 A/B 가 11분에서 2분이 될 수도 있다.
OCR_TPM_LIMIT = config('OCR_TPM_LIMIT', default=200000, cast=int)

# 규정 검증(AI) 버튼을 화면에 보일 것인가. 기본은 **끔**.
#
# 규칙 기반 검증과 결과가 크게 다르지 않다는 판단으로 감췄다. 기능은 그대로
# 남아 있다 — 버튼만 안 보인다. 판정 코드(ai_validation_service), 엔드포인트
# (/label/<id>/validate/ai-review/), 화면 쪽 호출(runAiValidation)이 모두
# 그대로이므로, 이 값을 켜면 곧바로 다시 쓸 수 있다.
#
# AI 전용으로만 보는 항목이 둘 있다(원재료 표시 순서, 제품명-원재료 일치성).
# 그 둘이 필요해지면 여기를 켠다.
SHOW_AI_VALIDATION = config('SHOW_AI_VALIDATION', default=False, cast=bool)

# 식품안전나라 OpenAPI Key (https://openapi.foodsafetykorea.go.kr)
FOODSAFETY_API_KEY = config('FOODSAFETY_API_KEY', default='')

# 서비스 ID (foodsafetykorea.go.kr OpenAPI)
# I2620: 수입식품 부적합, I0030: 국내식품 부적합 (확인 필요 시 변경)
FOODSAFETY_IMPORT_SERVICE_ID  = config('FOODSAFETY_IMPORT_SERVICE_ID',  default='I2620')
FOODSAFETY_DOMESTIC_SERVICE_ID = config('FOODSAFETY_DOMESTIC_SERVICE_ID', default='I0030')

# 식약처 식품영양성분DB (data.go.kr, 개발계정)
# https://apis.data.go.kr/1471000/FoodNtrCpntDbInfo02/getFoodNtrCpntDbInq02
# 값은 **URL 인코딩된 채로** 둔다 — requests 의 params 로 넘기면 % 가 다시
# 인코딩돼 인증이 깨지므로, 적재 커맨드가 쿼리스트링에 직접 붙인다.
MFDS_NUTRITION_API_KEY = config('MFDS_NUTRITION_API_KEY', default='')

# RapidFuzz 매칭 임계값 (0~100, 기본 72)
REGULATORY_MATCH_THRESHOLD = config('REGULATORY_MATCH_THRESHOLD', default=72, cast=int)

# iframe 설정: SAMEORIGIN으로 설정하여 같은 도메인 내 iframe 로드 허용
X_FRAME_OPTIONS = 'SAMEORIGIN'

CSRF_TRUSTED_ORIGINS = ['https://*.ngrok-free.dev'] # 외부 접속용 앱 허용
# ── 모바일 앱 API 설정 ─────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
}

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000').split(',')
# 기본값이 True 였다. **없으면 열린다**는 뜻이라, 환경변수를 안 넣은 서버는
# 모든 출처에 API 를 열어 준 채로 돈다. 기본값은 닫힌 쪽이어야 한다 —
# 열어야 하는 곳에서 명시적으로 켠다.
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)

# 앱 API 가 **JWT 를 실제로 검사할 것인가.**
#
# login 이 토큰을 발급하는데 mobile/views.py 는 그것을 한 번도 보지 않았다 —
# 소유자 판정을 URL 의 device_id 하나로만 했다. device_id 는 경로에 들어 있어
# 로그에 그대로 남고, 값을 클라이언트가 정하며, 일부 기기는 같은 모델끼리
# 겹치는 Android Build.ID 를 쓰고 있다.
#
# 켜려면 **앱이 Authorization 헤더를 보내야 한다.** 그 판을 배포한 뒤 여기를
# True 로 올린다. 그전에 켜면 모든 사용자가 그 자리에서 앱을 못 쓴다.
# (토큰을 보낸 요청은 이 값과 무관하게 지금도 검사한다.)
MOBILE_REQUIRE_AUTH = config('MOBILE_REQUIRE_AUTH', default=False, cast=bool)

# 비회원 키워드 최대 수
MOBILE_GUEST_MAX_RULES = 5
# 회원 키워드 최대 수
MOBILE_MEMBER_MAX_RULES = 30

# Cloudflare Turnstile
TURNSTILE_SITE_KEY = config('TURNSTILE_SITE_KEY', default='')
TURNSTILE_SECRET_KEY = config('TURNSTILE_SECRET_KEY', default='')

# GAS(구글 스프레드시트) 등 외부 연동용 수거검사 export API 공유 비밀키
# .env에 INSPECTION_EXPORT_API_KEY=<임의의 긴 랜덤 문자열> 로 설정
INSPECTION_EXPORT_API_KEY = config('INSPECTION_EXPORT_API_KEY', default='')
# 품목제조보고 export API(v1/products/views.py:product_export_api)도 이 키를 공유해서 사용한다.

# 비회원 보관함 최대 개수
MOBILE_GUEST_MAX_BOOKMARKS = 5
# 회원 보관함 최대 개수
MOBILE_MEMBER_MAX_BOOKMARKS = 50

# 기기당 보관되는 알림 이력 최대 개수 (초과 시 오래된 것부터 삭제)
MOBILE_MAX_NOTIFICATIONS = 100

# 표시사항 AI검증(OpenAI 호출) 비용 관리 — 계정별 rate limit
# (v1/label/services/ai_rate_limit.py). 운영해보고 너무 빡빡하면 .env에서
# 조정. 동일 라벨 내용 재요청은 이 한도와 별개로 캐시(AI_VALIDATION_RESULT_CACHE_TTL)
# 로 우선 처리되어 OpenAI 재호출 자체가 없다.
AI_VALIDATION_MINUTE_LIMIT = config('AI_VALIDATION_MINUTE_LIMIT', default=15, cast=int)
# 무료 계정 일일 한도 — UserProfile.paid_yn=False
AI_VALIDATION_FREE_DAILY_LIMIT = config('AI_VALIDATION_FREE_DAILY_LIMIT', default=10, cast=int)
# 유료 계정 일일 한도 — UserProfile.paid_yn=True (요금제 생기면 여기만 조정)
AI_VALIDATION_PAID_DAILY_LIMIT = config('AI_VALIDATION_PAID_DAILY_LIMIT', default=50, cast=int)
AI_VALIDATION_RESULT_CACHE_TTL = config('AI_VALIDATION_RESULT_CACHE_TTL', default=60 * 15, cast=int)

# FCM HTTP v1 API 설정
# Firebase Console → 프로젝트 설정 → 서비스 계정 → 새 비공개 키 생성 → JSON 파일 내용을
# 한 줄 문자열로 .env에 저장하거나, 파일 경로를 지정
FCM_PROJECT_ID = config('FCM_PROJECT_ID', default='labeldata-mobile')
FCM_SERVICE_ACCOUNT_JSON = config('FCM_SERVICE_ACCOUNT_JSON', default='')
