from django.urls import path
from core.views.view_cis import (
    manual_school_upload, mark_notification_as_read, get_departments,
    user_management, get_siso_current_circuit,
    get_user_sisos, fetch_circuits_and_schools, create_user, get_roles,
    user_search, set_result_upload_deadline, download_district_performance_pdf,
    get_user_circuits, send_notification, get_notifications,
    download_school_template, bulk_upload_schools, get_schools,
    reassign_siso, assign_siso, create_circuit,
    siso_management, school_management, district_performance_analysis,
    
)

app_name = 'cis'

urlpatterns = [
    path('district/performance/analysis/', district_performance_analysis, name='district_performance_analysis'),
    path('performance/download/', download_district_performance_pdf, name='download_district_performance_pdf'), 

    path('school/management/', school_management, name='school_management'),
    path('school/manual/upload/', manual_school_upload, name='manual_school_upload'),
    #path('schools/', school_list, name='school_list'),
    path('school/bulk/upload/', bulk_upload_schools, name='bulk_upload_schools'),
    path('school/download-template/<str:file_format>/', download_school_template, name='download_school_template'),
    path('departments/', get_departments, name='get_departments'),


    path('sisos/', get_user_sisos, name='get_user_sisos'),
    path('siso/management/', siso_management, name='siso_management'),
    path('circuit/create/', create_circuit, name='create_circuit'),
    path('siso/assign/', assign_siso, name='assign_siso'),
    path('siso/reassign/', reassign_siso, name='reassign_siso'),
    path('circuits/', get_user_circuits, name='get_user_circuits'),
    path('siso/current-circuit/<int:siso_id>/', get_siso_current_circuit, name='get_siso_current_circuit'),
    path('fetch-circuits-and-schools/<int:district_id>/', fetch_circuits_and_schools, name='fetch_circuits_and_schools'), 

    path('user/management/', user_management, name='user_management'),
    path('user/search/', user_search, name='user_search'),
    path('user/create/', create_user, name='create_user'),
    path('user/roles/', get_roles, name='get_roles'),
    path('schools/', get_schools, name='get_schools'),

    path('send-notification/', send_notification, name='send_notification'),
    path('notifications/', get_notifications, name='get_notifications'),
    path('result/deadline/', set_result_upload_deadline, name='set_result_upload_deadline'),
    path('notifications/mark-as-read/<int:notification_id>/', mark_notification_as_read, name='mark_notification_as_read'),

]

