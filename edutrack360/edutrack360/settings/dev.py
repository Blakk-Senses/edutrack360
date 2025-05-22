# edutrack360/settings/dev.py

from .base import *

DEBUG = True

SECRET_KEY = 'django-insecure-dev-key-123'

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'edutrack360',
        'USER': 'edutrack_user',
        'PASSWORD': 'selinam7',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
