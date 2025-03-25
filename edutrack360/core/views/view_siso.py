from django.views.decorators.csrf import csrf_exempt

import csv
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from core.models import District, Teacher, Notification, PerformanceSummary, Profile, School, SchoolSubmission, Circuit
from django.db.models import Count, Avg
from django.http import JsonResponse, HttpResponse

User = get_user_model()

def circuit_overview(request):
    return render(request, 'siso_dashboard.html')

def download_circuit_report(request, circuit_id):
    # Generate and return the circuit report
    return HttpResponse(f"Downloading Circuit Report for ID: {circuit_id}")

# Generate Reports
def siso_generate_reports(request):
    return render(request, 'generate_reports.html')

# Send Notifications
def siso_send_notifications(request):
    return render(request, 'send_notifications.html')

@login_required
def send_notification(request):
    if request.method == "POST":
        recipient_id = request.POST.get("recipient_id")
        message = request.POST.get("message")
        
        if recipient_id and message:
            recipient = User.objects.get(id=recipient_id)
            Notification.objects.create(sender=request.user, recipient=recipient, message=message)
            return JsonResponse({"status": "success", "message": "Notification sent!"})
    
    return JsonResponse({"status": "error", "message": "Invalid request"})

@login_required
def get_notifications(request):
    """Fetch unread notifications for the logged-in user."""
    notifications = Notification.objects.filter(recipient=request.user, is_read=False).order_by("-created_at")
    data = [{"id": n.id, "sender": n.sender.username, "message": n.message, "created_at": n.created_at} for n in notifications]
    return JsonResponse({"notifications": data})


@login_required
def view_notifications(request):
    # Retrieve notifications for the logged-in user
    notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')

    return render(request, 'view_notifications.html', {'notifications': notifications})
