from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from core.forms import CustomPasswordResetForm
from django.contrib import messages
from django.contrib.auth.views import PasswordResetConfirmView
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.contrib.auth import get_user_model
from core.models import Teacher, SubjectTeacher, ClassTeacher

User = get_user_model()

#------------- HOMEPAGE -------------------
def homepage(request):
    return render(request, 'commons/homepage.html')

#----------------- LOGIN ------------------

def admin_login(request):
    """
    Admin login view that authenticates based on email and password.
    """
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        
        # Authenticate the user using the custom backend
        user = authenticate(request, username=email, password=password)

        if user is not None and user.role == 'admin':  # Check if user is admin after authentication
            # Successful login
            login(request, user)
            return redirect('dashboards:cis_registration')  # Adjust as necessary for the admin dashboard
        else:
            # Authentication failed or not an admin user
            messages.error(request, "Invalid email or password, or you are not authorized to log in.")
    
    return render(request, 'commons/admin_login.html')




def unified_login(request):
    if request.method == "POST":
        staff_id = request.POST.get('staff_id')
        password = request.POST.get('password')

        user = authenticate(request, username=staff_id, password=password)

        if user is not None:
            login(request, user)

            if user.role == 'teacher':
                try:
                    teacher = user.teacher_profile

                    if SubjectTeacher.objects.filter(teacher=teacher).exists():
                        return redirect('dashboards:subject_teacher_dashboard')

                    if ClassTeacher.objects.filter(teacher=teacher).exists():
                        return redirect('dashboards:class_teacher_dashboard')

                    return redirect('dashboards:teacher_dashboard')

                except Teacher.DoesNotExist:
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
            # Add 'error' key on failed login
            context = {'error': 'Invalid Staff ID or password'}
            return render(request, 'commons/login.html', context)

    # Ensure 'error' is present even for GET requests
    return render(request, 'commons/login.html', {'error': None})



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
    form_class = CustomPasswordResetForm


# Password reset done view
class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'commons/password_reset_done.html'

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'commons/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

    def form_valid(self, form):
        response = super().form_valid(form)

        user = form.user  # The user who reset the password

        # Optional: update a flag like password_changed
        user.password_changed = True
        user.save(update_fields=['password_changed'])

        # Send confirmation email
        subject = 'Your password has been reset'
        message = render_to_string('commons/password_reset_confirmation_email.html', {
            'user': user,
        })
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )

        return response


# Password reset complete view
class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'commons/password_reset_complete.html'