# myapp/urls.py
from django.urls import path
from core.views.view_siso import (
    download_circuit_report, circuit_overview, 
    siso_generate_reports, siso_send_notifications,
    view_notifications, send_notification, get_notifications
)

app_name = 'siso'

urlpatterns = [ 
    path('circuit-overview/', circuit_overview, name='circuit_overview'),
    path('generate-reports/', siso_generate_reports, name='siso_generate_reports'),
    path('send-notifications/', siso_send_notifications, name='siso_send_notifications'),
    path('view-notifications/', view_notifications, name='view_notifications'),
    path('download-circuit-report/<int:circuit_id>/', download_circuit_report, name='download_circuit_report'),
    path('send-notification/', send_notification, name='send_notification'),
    path('get-notifications/', get_notifications, name='get_notifications'),

]

