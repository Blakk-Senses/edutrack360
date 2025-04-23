from django.urls import path
from core.views.dashboards import (
    siso_dashboard, cis_dashboard, cis_registration,
    teacher_dashboard, headteacher_dashboard,
    subject_teacher_dashboard, class_teacher_dashboard,
)

app_name = 'dashboards'

urlpatterns = [
    path('register/cis/', cis_registration, name='cis_registration'),
    path('siso/', siso_dashboard, name='siso_dashboard'),
    path('cis/', cis_dashboard, name='cis_dashboard'),
    path('teacher/', teacher_dashboard, name='teacher_dashboard'),
    path('headteacher/', headteacher_dashboard, name='headteacher_dashboard'),
    path('class-teacher/', class_teacher_dashboard, name='class_teacher_dashboard'),
    path('subject-teacher/', subject_teacher_dashboard, name='subject_teacher_dashboard'),
]