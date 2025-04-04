# myapp/urls.py
from django.urls import path
from core.views.view_school import (
    class_management,teacher_management, assign_teacher_to_subject, 
    remove_teacher_from_subject, assign_teacher_to_class, remove_teacher_from_class, 
    get_teacher_classes, bulk_upload_teachers,download_teacher_template, save_last_page, 
    get_last_page, manual_upload, get_classes_by_department, add_class_to_department,
    school_performance_analysis, get_available_terms, get_teachers,
    get_subjects_by_department, get_departments, headteacher_view_result,
    school_performance_analysis, headteacher_result_overview,
    submit_result, query_result, add_subject_to_department, subject_management,
    get_subjects_by_teacher, download_school_performance_pdf,
    get_classes_by_teacher_and_subject, get_headteacher_notifications, 
    mark_notification_as_read,
    

)

app_name = 'school'

urlpatterns = [ 
    
    path('available_terms/', get_available_terms, name='get_available_terms'),
    path('departments/', get_departments, name='get_departments'),
    path('teachers/', get_teachers, name='get_teachers'),
    path('save_last_page/', save_last_page, name='save_last_page'),
    path('get_last_page/', get_last_page, name='get_last_page'),

    path('class/management/', class_management, name='class_management'),
    path('department/class/add/', add_class_to_department, name='add_class_to_department'),
    path('classes/department/', get_classes_by_department, name='get_classes_by_department'),
    path('teacher/classes/', get_teacher_classes, name='get_teacher_classes'),
    path('teacher/class/assign/', assign_teacher_to_class, name='assign_teacher_to_class'),
    path('teacher/class/remove/', remove_teacher_from_class, name='remove_teacher_from_class'),
    
    path('subject/management/', subject_management, name='subject_management'),
    path("subjects/add/", add_subject_to_department, name="add_subject_to_department"),
    path("subjects/<int:teacher_id>/<int:subject_id>/assign/", assign_teacher_to_subject, name="assign_teacher_to_subject"),
    path("subjects/<int:teacher_id>/<int:subject_id>/remove/", remove_teacher_from_subject, name="remove_teacher_from_subject"),
    path("subjects/classes/", get_classes_by_teacher_and_subject, name="get_classes_by_teacher_and_subject"),
    path("subjects/teacher/<int:teacher_id>/", get_subjects_by_teacher, name="get_subjects_by_teacher"),
    path("subjects/department/", get_subjects_by_department, name="get_subjects_by_department"),
    
    path('teacher/management/', teacher_management, name='teacher_management'),
    path('manual/upload/', manual_upload, name='manual_upload'),
    path('bulk/upload-teachers/', bulk_upload_teachers, name='bulk_upload_teachers'),
    path('download-teacher-template/<str:file_format>/', 
        download_teacher_template, name='download_teacher_template'
    ),
    
    path('performance/analysis/', school_performance_analysis, name='school_performance_analysis'),
    path('performance/download/', download_school_performance_pdf, name='download_school_performance_pdf'),


    path('results/',headteacher_result_overview, name='headteacher_result_overview'),
    
    path(
        'results/<str:year>/<str:term>/<int:subject_id>/<int:class_id>/', 
        headteacher_view_result, name='headteacher_view_result'
    ),

    path('results/submit/', submit_result, name='submit_result'),
    path('results/query/', query_result, name='query_result'),

    path('notifications/in/', get_headteacher_notifications, name='get_headteacher_notifications'),
    path('notifications/mark-as-read/<int:notification_id>/', mark_notification_as_read, name='mark_notification_as_read'),

]
