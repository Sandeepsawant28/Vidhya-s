import os
import sys
from pathlib import Path

import dj_database_url
from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent

# Where local data lives (database, backups, logs).
# Windows shop PC: C:\ProgramData\LiquorShop
# Render or other Linux hosts: a "data" folder inside the project
if os.name == 'nt':
    _default_data = os.path.join(os.environ.get('PROGRAMDATA', r'C:\ProgramData'), 'LiquorShop')
else:
    _default_data = str(BASE_DIR / 'data')
DATA_DIR = os.environ.get('LIQUOR_SHOP_DATA_DIR', _default_data)

try:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'backups'), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'logs'), exist_ok=True)
except Exception:
    DATA_DIR = os.path.join(Path.home(), '.liquorshop_data')
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'backups'), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'logs'), exist_ok=True)

# Secret key: use the environment variable if set (needed on Render),
# otherwise a key saved in the data folder.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
SECRET_KEY_FILE = os.path.join(DATA_DIR, 'secret_key.txt')
if not SECRET_KEY and os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, 'r', encoding='utf-8') as f:
        SECRET_KEY = f.read().strip()
if not SECRET_KEY:
    SECRET_KEY = get_random_secret_key()
    try:
        with open(SECRET_KEY_FILE, 'w', encoding='utf-8') as f:
            f.write(SECRET_KEY)
    except Exception as e:
        print(f"Warning: Could not save secret key to file: {e}")

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.FirstRunSetupMiddleware',
]

ROOT_URLCONF = 'liquor_shop.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.shop_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'liquor_shop.wsgi.application'

# Database: local SQLite file by default.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(DATA_DIR, 'db.sqlite3'),
        'OPTIONS': {
            'timeout': 30,
            'init_command': 'PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON;',
        },
    }
}

# If DATABASE_URL is set (Neon on Render), use that instead.
# This block MUST stay below the DATABASES block above.
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=0, ssl_require=True)
    }

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 6}},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(DATA_DIR, 'staticfiles')
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = DEBUG

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_SAVE_EVERY_REQUEST = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Extra settings that only apply on Render (HTTPS behind a proxy).
RENDER_HOST = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_HOST:
    CSRF_TRUSTED_ORIGINS = ['https://' + RENDER_HOST]
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Send warnings and errors to the console (Render shows these in Logs).
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {'django': {'handlers': ['console'], 'level': 'WARNING'}},
}