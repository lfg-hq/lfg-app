import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-your-secret-key-here'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["lfg.run", "*"]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'channels',
    'chat',
    'accounts',
    'marketing',
    'projects',
    'subscriptions',
    'coding',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'LFG.urls'

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
                'subscriptions.context_processors.user_credits',
            ],
        },
    },
]

WSGI_APPLICATION = 'LFG.wsgi.application'
ASGI_APPLICATION = 'LFG.asgi.application'

# Channel layers configuration
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
        # For production, consider using Redis:
        # 'BACKEND': 'channels_redis.core.RedisChannelLayer',
        # 'CONFIG': {
        #     "hosts": [(os.environ.get('REDIS_HOST', 'redis'), 6379)],
        # },
    },
}

DATABASES = {
    # 'default': {
    #     'ENGINE': 'django.db.backends.postgresql',
    #     'NAME': os.environ.get('POSTGRES_DB', 'easylogs_dev'),
    #     'USER': os.environ.get('POSTGRES_USER', 'postgres'),
    #     'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'Test0123!'),
    #     'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
    #     'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    # },
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Use SQLite for testing
import sys
if 'test' in sys.argv:
    DATABASES['default'] = DATABASES['sqlite']

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
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "static",  # Your JS files location
]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files (User uploaded content)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# File storage for chat attachments
FILE_STORAGE_PATH = os.path.join(MEDIA_ROOT, 'file_storage')
os.makedirs(FILE_STORAGE_PATH, exist_ok=True)

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS settings
CORS_ALLOW_ALL_ORIGINS = True

# Security settings
X_FRAME_OPTIONS = 'SAMEORIGIN'  # Allow pages to be displayed in frames on the same origin

# AI Provider Selection Feature
AI_PROVIDER_DEFAULT = 'openai'  # Default provider 
# AI_PROVIDER_DEFAULT = 'anthropic'  # Alternate provider 

# Kubernetes SSH server settings
K8S_SSH_HOST = os.environ.get('K8S_SSH_HOST', '127.0.0.1')
K8S_SSH_PORT = int(os.environ.get('K8S_SSH_PORT', 22))
K8S_SSH_USERNAME = os.environ.get('K8S_SSH_USERNAME', 'root')
K8S_SSH_KEY_FILE = os.environ.get('K8S_SSH_KEY_FILE', os.path.expanduser('~/.ssh/id_rsa'))
K8S_SSH_KEY_STRING = os.environ.get('K8S_SSH_KEY_STRING', None)  # SSH private key as a string
K8S_SSH_KEY_PASSPHRASE = os.environ.get('K8S_SSH_KEY_PASSPHRASE', None)

# Authentication URLs
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/chat/'  # Redirect to chat page after successful login
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Authentication backends
# AUTHENTICATION_BACKENDS = [
#     'accounts.backends.EmailBackend',  # Custom email backend
#     'django.contrib.auth.backends.ModelBackend',  # Default Django backend
# ]

# Email Configuration
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # For development - outputs to console
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'  # For production
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@lfg.run')

# GitHub OAuth Settings
# You should set these in environment variables or .env file
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID', '')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET', '') 

# Kubernetes API Configuration
K8S_API_HOST = os.getenv('K8S_CLUSTER_HOST', "https://178.156.148.88:6443")
K8S_NODE_SSH_HOST = os.getenv('K8S_NODE_SSH_HOST', "178.156.138.23")
K8S_API_TOKEN = os.getenv('K8S_PERMANENT_TOKEN', "")
K8S_CA_CERT = os.getenv('K8S_CA_CERTIFICATE', "")
K8S_VERIFY_SSL = False  # Disabled by default since CA cert verification is problematic
K8S_DEFAULT_NAMESPACE = "lfg"
SSH_USERNAME=os.getenv('SSH_USERNAME', 'root')
SSH_KEY_STRING=os.getenv('SSH_KEY_STRING', None)
