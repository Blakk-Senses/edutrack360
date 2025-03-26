from django.urls import path
from core.views.view_teacher import (
    subject_performance_analysis,progress_trends,
    settings, get_classes_by_department,
    get_available_terms, get_departments, get_subjects_by_department,
    manual_upload_result, bulk_upload_results, download_result_template,
    get_classes, get_class_department, download_subject_analysis_pdf,
    class_performance_analysis, download_class_performance_pdf,
    upload_class_results, upload_subject_results, result_management,
    view_result_file, confirm_result_file, delete_result_file,
    
)

app_name = 'teacher'

urlpatterns = [ 

    path('departments/', get_departments, name='get_departments'),
    path('departments/<int:department_id>/classes/', get_classes_by_department, name='get_classes_by_department'),
    path('departments/<int:department_id>/subjects/', get_subjects_by_department, name='get_subjects_by_department'),
    path('available-terms/', get_available_terms, name='get_available_terms'),
    path('classes/', get_classes, name='get_classes'),
    path('classes/<int:class_group_id>/department/', get_class_department, name='get_class_department'),


    path('upload-class-result/', upload_class_results, name='upload_class_results'),
    path('upload-subject-result/', upload_subject_results, name='upload_subject_results'),
    path('upload-result/manual/', manual_upload_result, name='manual_upload'),

    path('upload-result/bulk/', bulk_upload_results, name='bulk_upload'),
    path('upload-result/template/', download_result_template, name='download_result_template'),


    path('progress_trends/', progress_trends, name='progress_trends'),
    path('settings/', settings, name='settings'),
    
    path("subject-performance-analysis/", subject_performance_analysis, name="subject_performance_analysis"),
    path("subject-performance/download/", download_subject_analysis_pdf, name="download_subject_analysis_pdf"),
    
    
    path("class-performance-analysis/", class_performance_analysis, name="class_performance_analysis"),
    path("class-performance/download/", download_class_performance_pdf, name="download_class_performance_pdf"),

    path('manage-results/', result_management, name='result_management'),
    # urls.py
    path('view/<str:academic_year>/<str:term>/<int:class_id>/<int:subject_id>/', view_result_file, name='view_result_file'),
    path('confirm/<str:academic_year>/<str:term>/<int:class_id>/<int:subject_id>/', confirm_result_file, name='confirm_result_file'),
    path('delete/<str:academic_year>/<str:term>/<int:class_id>/<int:subject_id>/', delete_result_file, name='delete_result_file'),


]


