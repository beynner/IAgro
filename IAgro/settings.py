import os
# Load .env if present to populate environment variables early
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = os.environ['SECRET_KEY']
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8002',
    'http://127.0.0.1:8002',
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'sankhya_integration',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'sankhya_integration.middleware.ControleInatividadeMiddleware',
]

ROOT_URLCONF = 'IAgro.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'sankhya_integration.context_processors.app_version_processor', 
                'sankhya_integration.context_processors.environment_badge',
            ],
        },
    },
]

WSGI_APPLICATION = 'IAgro.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

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

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'images'),
]

# Default primary key field type for models (Django 3.2+)
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Sankhya integration config
SANKHYA_CONFIG = {
    # Habilita gravação no Oracle para lançamentos assistidos
    'WRITE_ENABLED': True,
    # Configurações de automação de fluxo
    'AUTO_FLOWS': {
        'DUPLICATE_CLASSIFICATION': True,  # AUTO duplicar TOP 11→26
        'DUPLICATE_ON_SAVE': True,        # Duplicar automaticamente ao salvar item
        'DUPLICATE_METHOD': 'python',     # Via Python, não trigger
        'CREATE_VALE_COMPRA': False,      # Será implementado na tela Comercial
        'SEPARATE_INTERFACES': True,       # Portal=TOP11, Classificação=TOP26
    },
    # Sobrescreve parâmetros financeiros usados ao faturar vale
    'PARAMS': {
        'FINANCEIRO_TIPO_TITULO': 9,
    },
}

# Headers de segurança — ajustados por ambiente via variáveis de ambiente
if DEBUG:
    # Em desenvolvimento (HTTP local): desativa headers que bloqueiam requests sem HTTPS
    SECURE_CROSS_ORIGIN_OPENER_POLICY = None
    SECURE_CROSS_ORIGIN_EMBEDDER_POLICY = None
else:
    # Em produção: ativa proteções conforme configuração do servidor
    SECURE_SSL_REDIRECT            = os.getenv('SECURE_SSL_REDIRECT', 'False') == 'True'
    SECURE_HSTS_SECONDS            = int(os.getenv('SECURE_HSTS_SECONDS', '0'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'False') == 'True'
    SECURE_HSTS_PRELOAD            = os.getenv('SECURE_HSTS_PRELOAD', 'False') == 'True'
    SECURE_CONTENT_TYPE_NOSNIFF    = True
    SESSION_COOKIE_SECURE          = os.getenv('SESSION_COOKIE_SECURE', 'False') == 'True'
    CSRF_COOKIE_SECURE             = os.getenv('CSRF_COOKIE_SECURE', 'False') == 'True'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'sankhya_integration': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Versão da Aplicação
APP_VERSION = '1.1.1'  # Atualize conforme necessário
