"""
URL configuration for edutrack360 project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views.view_common import (
    homepage, unified_login, logout_view, admin_login,
)
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', homepage, name='homepage'),
    path('login/admin/', admin_login, name='admin_login'),

    path('login/user/', unified_login, name='login'),
    path('logout/', logout_view, name='logout'),


    # --- DASHBOARD ROUTES ---
    path('dashboards/', include('core.urls.dashboards', namespace='dashboards')),  # Move dashboard URLs to a separate file
    
    # --- APP-SPECIFIC ROUTES ---
    path('cis/', include('core.urls.cis', namespace='cis')),
    path('siso/', include('core.urls.siso', namespace='siso')),
    path('school/', include('core.urls.school', namespace='school')),
    path('teacher/', include('core.urls.teacher', namespace='teacher')),

    # --- PASSWORD MANAGEMENT ---
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='commons/password_reset.html'), name='password_reset'),
    path('password_reset_done/', auth_views.PasswordResetDoneView.as_view(template_name='commons/password_reset_done.html'), name='password_reset_done'),
    path('password_reset_confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='commons/password_reset_confirm.html'), name='password_reset_confirm'),
    path('password_reset_complete/', auth_views.PasswordResetCompleteView.as_view(template_name='commons/password_reset_complete.html'), name='password_reset_complete'),
    
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
