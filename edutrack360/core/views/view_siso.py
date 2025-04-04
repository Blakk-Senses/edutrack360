from django.views.decorators.csrf import csrf_exempt

import csv
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from collections import defaultdict
import json
from itertools import chain
from rest_framework.response import Response
from core.models import (District, Teacher, Notification, 
    StudentMark, Profile, School, SchoolSubmission, 
    Circuit)
import io
from collections import defaultdict
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
)
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from django.db.models import Count, Avg, F, Q, Max
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.views.decorators.http import require_POST
from core.forms import NotificationForm

User = get_user_model()

def circuit_overview(request):
    return render(request, 'dashboard/siso_dashboard.html')


@login_required
@user_passes_test(lambda u: u.role == "siso")  # Ensure only SISO can access
def get_notifications(request):
    siso = request.user  # Get the logged-in SISO
    notifications = Notification.objects.filter(recipient=siso, is_read=False).order_by("-created_at")

    data = [
        {
            "id": n.id,
            "message": n.message,
            "created_at": n.created_at.strftime("%Y-%m-%d %H:%M"),
            "is_read": n.is_read,
        }
        for n in notifications
    ]

    return JsonResponse({"notifications": data}, status=200)

@require_POST
@login_required
@user_passes_test(lambda u: u.role == "siso")
def mark_notification_as_read(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, recipient=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({"success": "Notification marked as read"}, status=200)
    except Notification.DoesNotExist:
        return JsonResponse({"error": "Notification not found"}, status=404)
    


@login_required
def notifications(request):
    user = request.user

    # Ensure only SISO users can access
    if not user.is_authenticated or user.role != "siso" or not user.circuit:
        return redirect("homepage")  # Redirect if unauthorized

    if request.method == 'POST':
        recipient_id = request.POST.get("recipient")  # Get recipient from form
        message = request.POST.get("message")

        if recipient_id == "all":
            # Send to all headteachers in the SISO's circuit
            headteachers = User.objects.filter(school__circuit=user.circuit, role="Headteacher")
            for headteacher in headteachers:
                Notification.objects.create(
                    sender=user,
                    recipient=headteacher,
                    message=message
                )
            messages.success(request, "Notification sent to all Headteachers!")
        else:
            # Send to a specific headteacher
            try:
                recipient = User.objects.get(id=recipient_id, role="Headteacher")
                Notification.objects.create(
                    sender=user,
                    recipient=recipient,
                    message=message
                )
                messages.success(request, f"Notification sent to {recipient.school.name}!")
            except User.DoesNotExist:
                messages.error(request, "Invalid recipient selection.")

        return redirect('siso:notifications')  # Redirect after sending

    # Fetch all notifications sent by this SISO
    notifications = Notification.objects.filter(sender=user).order_by('-created_at')

    return render(request, 'siso/notifications.html', {'notifications': notifications})



@login_required
def get_headteachers_by_circuit(request):
    """Fetch all headteachers in the SISO's circuit."""
    user = request.user

    # Ensure only SISO users can access
    if not user.is_authenticated or user.role != "siso" or not user.circuit:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    # Get headteachers in the SISO's circuit
    headteachers = User.objects.filter(school__circuit=user.circuit, role="headteacher")

    # Format data with full name
    headteachers_data = [
        {
            "id": ht.id,
            "name": f"{ht.first_name} {ht.last_name}" if ht.first_name and ht.last_name else ht.staff_id,  # Full name fallback to staff_id
            "school": ht.school.name
        }
        for ht in headteachers
    ]

    return JsonResponse({"headteachers": headteachers_data}, status=200)

@login_required
def get_available_terms(request):
    """Returns available academic terms and years in an object format with 'id' and 'name'."""
    
    academic_year_str = request.GET.get("academic_year", "2024/2025")  # Default to current year format
    if "/" in academic_year_str:
        try:
            base_year = int(academic_year_str.split("/")[0])  # Extract base year (e.g., 2024)
        except ValueError:
            return JsonResponse({"error": "Invalid academic year format"}, status=400)
    else:
        try:
            base_year = int(academic_year_str)  # Fallback if single year is provided
            academic_year_str = f"{base_year}/{base_year + 1}"
        except ValueError:
            return JsonResponse({"error": "Invalid academic year format"}, status=400)

    academic_years = [{"id": year, "name": f"{year}/{year+1}"} for year in range(2020, 2050)]
    terms = [{"id": i + 1, "name": term} for i, term in enumerate(["Term 1", "Term 2", "Term 3"])]

    return JsonResponse({"terms": terms, "academic_years": academic_years, "selected_academic_year": academic_year_str})


def circuit_performance_analysis(request):
    #context = get_circuit_performance_context(request)
    return render(request, 'siso/circuit_performance_analysis.html')






