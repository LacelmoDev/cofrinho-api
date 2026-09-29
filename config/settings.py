import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def env_bool(nome, padrao=False):
    return os.environ.get(nome, str(padrao)).strip().lower() in ('1', 'true', 'yes', 'sim')


def env_lista(nome, padrao=''):
    return [x.strip() for x in os.environ.get(nome, padrao).split(',') if x.strip()]


DEBUG = env_bool('DEBUG', False)
SECRET_KEY = os.environ.get('SECRET_KEY') or ('dev-inseguro-nao-usar-em-producao' if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError('Define SECRET_KEY nas variáveis de ambiente.')

ALLOWED_HOSTS = ['*'] if DEBUG else env_lista('ALLOWED_HOSTS')
# O Render define esta variável sozinho com o endereço público do serviço.
if os.environ.get('RENDER_EXTERNAL_HOSTNAME'):
    ALLOWED_HOSTS.append(os.environ['RENDER_EXTERNAL_HOSTNAME'])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'contas',
    'sync',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

# DATABASE_URL vazio (como vem no .env.example) conta como "não definido": usa SQLite local.
DATABASES = {
    'default': dj_database_url.parse(
        os.environ.get('DATABASE_URL') or f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = 'contas.Utilizador'

LANGUAGE_CODE = 'pt-pt'
TIME_ZONE = 'Africa/Luanda'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------- API ----------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['contas.autenticacao.BearerAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.ScopedRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'auth': '20/min', 'codigo': '5/min', 'sync': '60/min'},
    'EXCEPTION_HANDLER': 'config.erros.tratar_excecao',
    'NUM_PROXIES': int(os.environ.get('NUM_PROXIES', '0' if DEBUG else '1')),
}

# Sessões de login (por dispositivo): expiram após tantos dias sem uso
SESSAO_DIAS_INATIVIDADE = 90

# ---------- CORS ----------
CORS_ALLOWED_ORIGINS = env_lista('CORS_ALLOWED_ORIGINS')
if DEBUG:
    CORS_ALLOWED_ORIGIN_REGEXES = [r'^http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+):\d+$']

# ---------- Email (Brevo) ----------
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
BREVO_SENDER_EMAIL = os.environ.get('BREVO_SENDER_EMAIL', '')
BREVO_SENDER_NAME = os.environ.get('BREVO_SENDER_NAME', 'Cofrinho AO')

# ---------- Segurança em produção ----------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'consola': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['consola'], 'level': 'INFO'},
}
