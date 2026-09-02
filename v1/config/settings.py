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
                'v1.common.context_processors.board_notifications',
                'v1.common.context_processors.ui_mode',
                'v1.common.context_processors.regulatory_alerts',
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
        'PASSWORD': config('DB_PASSWORD', default='labeldata1!'),
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
    }
}

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

# 주의사항·기타표시사항을 사진에서 읽을 것인가. 기본은 **읽지 않는다.**
#
# 이 두 칸은 무엇을 해도 흔들렸다 - 상용 문구 목록을 프롬프트에 실으면 그
# 문장을 지어내고, 빼면 새 문장을 지어내고, 전용 칸을 만들면 알레르기 칸을
# 망쳤다(편차 80 이상). 그런데 이 두 칸에는 이미 화면에 빠른 입력 버튼
# 스물여덟 개가 있어서 두어 번 눌러 정확한 문장을 넣을 수 있다.
# 지어낸 문구가 법적 표시물에 들어가는 위험이 버튼 두 번보다 크다.
#
# 나중에 모델이 나아지면 되돌릴 자리다. 측정 화면(/label/ocr-lab/)에서는
# 이 값과 무관하게 켜서 견줄 수 있다.
OCR_READ_FREETEXT = config('OCR_READ_FREETEXT', default=False, cast=bool)

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

# OpenAI 의 분당 토큰 한도(TPM). 정답지 측정이 판독 사이를 얼마나 쉴지 계산하는
# 데 쓴다 (ocr_lab.pace_seconds).
#
# 기본 200,000 은 gpt-4o-mini 의 사용 등급 1 값이다. 판독 한 번이 6~7만
# 토큰이니 **분당 세 번**이 한계고, 그보다 빨리 부르면 429 다.
#
# 등급이 오르면 이 값을 함께 올려야 측정이 빨라진다. 안 올리면 필요 없는
# 대기로 시간만 쓴다 - 5장 3회 A/B 가 11분에서 2분이 될 수도 있다.
OCR_TPM_LIMIT = config('OCR_TPM_LIMIT', default=200000, cast=int)

# 식품안전나라 OpenAPI Key (https://openapi.foodsafetykorea.go.kr)
FOODSAFETY_API_KEY = config('FOODSAFETY_API_KEY', default='')

# 서비스 ID (foodsafetykorea.go.kr OpenAPI)
# I2620: 수입식품 부적합, I0030: 국내식품 부적합 (확인 필요 시 변경)
FOODSAFETY_IMPORT_SERVICE_ID  = config('FOODSAFETY_IMPORT_SERVICE_ID',  default='I2620')
FOODSAFETY_DOMESTIC_SERVICE_ID = config('FOODSAFETY_DOMESTIC_SERVICE_ID', default='I0030')

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
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=True, cast=bool)

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
