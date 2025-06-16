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
    DEBUG = config('DJANGO_DEBUG', default=True, cast=bool)  # 원래대로 복원
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
    'django_bootstrap5',  # django-bootstrap5 사용
    'v1.label',          # Label 앱
    'v1.disposition',    # Action 앱
    'v1.common',         # Common 앱
    'v1.user_management',
    'v1.board',          # Board 앱
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
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
    STATIC_ROOT = config('STATIC_ROOT', default='d:/projects/labeldata/staticfiles')
else:
    STATIC_ROOT = config('STATIC_ROOT', default='/home/labeldata/mysite/staticfiles')

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = config('MEDIA_ROOT', default='d:/projects/labeldata/media')

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