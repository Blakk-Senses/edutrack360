# myapp/urls.py
from django.urls import path
from core.views.view_cis import (
    add_school, generate_reports,
    cis_send_notifications, user_management,
    download_district_report, get_siso, fetch_circuits_and_schools,
    download_circuit_report, download_school_report, 
    get_circuits, send_notification, get_notifications,
    download_bulk_upload_template, bulk_upload_schools,
    delete_siso, reassign_siso, assign_siso, create_circuit,
    siso_management, school_management, school_list,
    
)

app_name = 'cis'

urlpatterns = [ 
    path('generate-reports/', generate_reports, name='generate_reports'), 
    path('download-report/', download_district_report, name='download_district_report'),
    path('download-school-report/<int:school_id>/', download_school_report, name='download_school_report'),
    path('download-circuit-report/<int:circuit_id>/', download_circuit_report, name='download_circuit_report'),
    path('download_template/', download_bulk_upload_template, name='download_bulk_upload_template'),

    
    path('school-management/', school_management, name='school_management'),
    path('add-school/', add_school, name='add_school'),
    path('schools/', school_list, name='school_list'),
    path('bulk-upload-school/', bulk_upload_schools, name='bulk_upload_schools'),
    path('get-siso/', get_siso, name='get_siso'),
    path('siso-management/', siso_management, name='siso_management'),
    path('create-circuit/', create_circuit, name='create_circuit'),
    path('delete-siso/', delete_siso, name='delete_siso'),
    path('assign-siso/', assign_siso, name='assign_siso'),
    path('reassign-siso/', reassign_siso, name='reassign_siso'),
    path('get-circuits/', get_circuits, name='get_circuits'), 
    path('fetch-circuits-and-schools/<int:district_id>/', fetch_circuits_and_schools, name='fetch_circuits_and_schools'), 

    path('send-notifications/', cis_send_notifications, name='cis_send_notifications'),
    path('user-management/', user_management, name='user_management'),

    path('send-notification/', send_notification, name='send_notification'),
    path('get-notifications/', get_notifications, name='get_notifications'),
    

    

]

