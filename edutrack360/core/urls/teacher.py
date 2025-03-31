from django.urls import path
from core.views.view_teacher import (
    subject_performance_analysis, settings, get_classes_by_department,
    get_available_terms, get_departments, get_subjects_by_department,
    manual_upload_result, bulk_upload_results, download_result_template,
    get_classes, get_class_department, download_subject_analysis_pdf,
    class_performance_analysis, download_class_performance_pdf,
    upload_class_results, upload_subject_results, view_uploaded_files,
    delete_result_entry, delete_result_file, view_result_entries
    
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

    path('settings/', settings, name='settings'),
    
    path("subject-performance-analysis/", subject_performance_analysis, name="subject_performance_analysis"),
    path("subject-performance/download/", download_subject_analysis_pdf, name="download_subject_analysis_pdf"),
    
    
    path("class-performance/analysis/", class_performance_analysis, name="class_performance_analysis"),
    path("class-performance/download/", download_class_performance_pdf, name="download_class_performance_pdf"),

    path("files/", view_uploaded_files, name="view_uploaded_files"),
    path("files/<int:year>/<slug:term>/<int:subject_id>/<int:class_id>/delete/", delete_result_file, name="delete_result_file"),
    path("entry/<int:result_id>/delete/", delete_result_entry, name="delete_result_entry"),
    path("files/<slug:year>/<slug:term>/<int:subject_id>/<int:class_id>/view/", view_result_entries, name="view_result_entries"),



]


