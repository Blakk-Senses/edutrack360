# myapp/urls.py
from django.urls import path
from core.views.view_school import (
    class_management,teacher_management, submit_results, school_performance,
    progress_trends, assign_teacher_to_subject, remove_teacher_from_subject, 
    assign_teacher_to_class, remove_teacher_from_class, get_teacher_classes,
    bulk_upload_teachers,download_teacher_template, save_last_page, 
    get_last_page, manual_upload, get_classes_by_department, add_class_to_department,
    school_performance_analysis, get_available_terms, get_teachers,
    get_subjects_by_department, get_departments, get_trend_data, get_performance_data,
    get_school_performance, generate_pdf, generate_school_report_pdf, view_result,
    submit_result, query_result, add_subject_to_department, subject_management,
    get_subjects_by_teacher,
    

)

app_name = 'school'

urlpatterns = [ 
    
    path('available_terms/', get_available_terms, name='get_available_terms'),
    path('get_departments/', get_departments, name='get_departments'),
    path('get_teachers/', get_teachers, name='get_teachers'),
    path('departments/', get_departments, name='get_departments' ),
    path('save_last_page/', save_last_page, name='save_last_page'),
    path('get_last_page/', get_last_page, name='get_last_page'),

    path('class_management/', class_management, name='class_management'),
    path('add_class_to_department/', add_class_to_department, name='add_class_to_department'),
    path('get_classes_by_department/', get_classes_by_department, name='get_classes_by_department'),
    path('get_teacher_classes/', get_teacher_classes, name='get_teacher_classes'),
    path('assign_teacher_to_class/', assign_teacher_to_class, name='assign_teacher_to_class'),
    path('remove_teacher_from_class/', remove_teacher_from_class, name='remove_teacher_from_class'),
    
    path('subject_management/', subject_management, name='subject_management'),
    path('assign_teacher_to_subject/<int:teacher_id>/<int:subject_id>/', assign_teacher_to_subject, name='assign_teacher_to_subject'),
    path('remove_teacher_from_subject/<int:teacher_id>/<int:subject_id>/', remove_teacher_from_subject, name='remove_teacher_from_subject'),
    path('add_subject_to_department/', add_subject_to_department, name='add_subject_to_department'),
    path("get_subjects_by_department/", get_subjects_by_department, name="get_subjects_by_department"),
    path("get_subjects_by_teacher/", get_subjects_by_teacher, name="get_subjects_by_teacher"),
    
    path('teacher_management/', teacher_management, name='teacher_management'),
    path('manual_upload/', manual_upload, name='manual_upload'),
    path('bulk_upload_teachers/', bulk_upload_teachers, name='bulk_upload_teachers'),
    path('download_teacher_template/<str:file_format>/', download_teacher_template, name='download_teacher_template'),
    
    path('school_performance/', school_performance, name='school_performance'),
    path('performance_analysis/', school_performance_analysis, name='school_performance_analysis'),
    path('download_report/', generate_pdf, name='download_report'),

    path('progress_trends/', progress_trends, name='progress_trends'),
    path('trend_data/', get_trend_data, name='get_trend_data' ),
    path('performance/', get_school_performance, name='get_school_performance' ),
    path('performance_data/', get_performance_data, name='get_performance_data' ),
    path('download_trends_report/', generate_school_report_pdf, name='generate_school_report_pdf'),

    path('submit_results/', submit_results, name='submit_results'),
    path('view_results/<int:result_id>/', view_result, name='view_results'),
    path('submit_results/<int:result_id>/', submit_result, name='submit_results'),
    path('query_results/<int:result_id>/', query_result, name='query_results'),
]
