from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)

from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.contrib.auth import get_user_model
from core.models import Teacher, SubjectTeacher, ClassTeacher

User = get_user_model()

#------------- HOMEPAGE -------------------
def homepage(request):
    return render(request, 'commons/homepage.html')

#----------------- LOGIN ------------------


def unified_login(request):
    if request.method == "POST":
        staff_id = request.POST.get('staff_id')
        password = request.POST.get('password')

        user = authenticate(request, username=staff_id, password=password)

        if user is not None:
            login(request, user)

            if user.role == 'teacher':
                try:
                    teacher = user.teacher_profile  # Get the Teacher profile linked to the user

                    # Check if teacher is a Subject Teacher
                    if SubjectTeacher.objects.filter(teacher=teacher).exists():
                        return redirect('dashboards:subject_teacher_dashboard')

                    # Check if teacher is a Class Teacher
                    if ClassTeacher.objects.filter(teacher=teacher).exists():
                        return redirect('dashboards:class_teacher_dashboard')

                    # If neither, send to general teacher dashboard
                    return redirect('dashboards:teacher_dashboard')

                except Teacher.DoesNotExist:
                    # Teacher profile not found, redirect accordingly
                    return redirect('dashboards:teacher_dashboard')

            elif user.role == 'headteacher':
                return redirect('dashboards:headteacher_dashboard') 
            elif user.role == 'siso':
                return redirect('dashboards:siso_dashboard') 
            elif user.role == 'cis':
                return redirect('dashboards:cis_dashboard')  
            else:
                return redirect('homepage') 
        else:
            context = {'error': 'Invalid Staff ID or password'}
            return render(request, 'commons/login.html', context)

    return render(request, 'commons/login.html')


#------------- LOGOUT --------------------

def logout_view(request):
    logout(request)
    return redirect('login')

#---------- PASSWORD RESET ------------------------

class CustomPasswordResetView(PasswordResetView):
    template_name = 'commons/password_reset.html'
    email_template_name = 'commons/password_reset_email.html'
    subject_template_name = 'password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

# Password reset done view
class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'commons/password_reset_done.html'

# Password reset confirm view
class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'commons/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

# Password reset complete view
class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'commons/password_reset_complete.html'