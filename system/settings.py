import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'django-insecure-%f+8@2=fd4+e3zam7_hi)wdgc+0!1^zt567227o+k6ew_^v_!4'
DEBUG = True
ALLOWED_HOSTS = []
INSTALLED_APPS = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'django.contrib.humanize',
        'widget_tweaks',
        
        'core.apps.CoreConfig',
        'client_accounts.apps.ClientAccountsConfig',
        'loans.apps.LoansConfig',
        'reports.apps.ReportsConfig',
        ]

MIDDLEWARE = [
        'django.middleware.security.SecurityMiddleware', 
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware', 
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
        'core.middleware.CSPMiddleware',
]
ROOT_URLCONF = 'system.urls'
TEMPLATES = [
        {
                'BACKEND': 'django.template.backends.django.DjangoTemplates', 
                'DIRS': [BASE_DIR / 'templates'], 
                'APP_DIRS': True, 
                'OPTIONS': 
                        {'context_processors': [
                                'django.template.context_processors.debug', 
                                'django.template.context_processors.request', 
                                'django.contrib.auth.context_processors.auth', 
                                'django.contrib.messages.context_processors.messages', 
                                'core.views.add_current_datetime', 
                                'core.context_processors.navigation_context',
                                ]
                        }
        }
]
WSGI_APPLICATION = 'system.wsgi.application'
DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'haliqur_investments', 'USER': 'postgres', 'PASSWORD': 'Haliqur@2025', 'HOST': 'localhost', 'PORT': '5432'}}
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}, {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}, {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
# system/settings.py - Add these CSP settings
# Content Security Policy settings for development
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
    "'unsafe-eval'",  # Allow eval()
    "'unsafe-inline'",  # Allow inline scripts
    "https://cdn.jsdelivr.net",
    "https://code.jquery.com",
    "https://cdn.datatables.net",
)
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",  # Allow inline styles
    "https://cdn.jsdelivr.net",
    "https://cdn.datatables.net",
    "https://cdnjs.cloudflare.com",
)
CSP_FONT_SRC = ("'self'", "https://cdnjs.cloudflare.com", "https://fonts.gstatic.com")
CSP_IMG_SRC = ("'self'", "data:", "https:", "http:")
CSP_CONNECT_SRC = ("'self'",)

# If using django-csp package
CSP_REPORT_ONLY = False  # Set to True to test without blocking