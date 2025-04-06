# myapp/urls.py
from django.urls import path
from core.views.view_siso import (
    circuit_performance_analysis, circuit_overview, notifications,
    get_notifications,mark_notification_as_read, get_headteachers_by_circuit,
    download_circuit_performance_pdf,

)

app_name = 'siso'

urlpatterns = [ 
    #path('schools/', get_siso_schools, name='get_siso_schools'),

    path('circuit/overview/', circuit_overview, name='circuit_overview'),
    path('circuit/performance/analysis/', circuit_performance_analysis, name='circuit_performance_analysis'),
    path('performance/download/', download_circuit_performance_pdf, name='download_circuit_performance_pdf'),



    path('notifications/send/', notifications, name='notifications'),
    path('notifications/', get_notifications, name='get_notifications'),
    path('notifications/headteachers/', get_headteachers_by_circuit, name='get_headteachers_by_circuit'),
    path('notifications/mark-as-read/<int:notification_id>/', mark_notification_as_read, name='mark_notification_as_read'),


]

