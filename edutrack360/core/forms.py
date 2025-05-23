from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from datetime import datetime
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordResetForm
from core.models import (
    Circuit, School, Subject, ClassGroup, Result, Teacher, 
    Notification, School, Circuit, Department, District,

)
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import MinLengthValidator, RegexValidator

User = get_user_model()  

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'department']

class AddSchoolForm(forms.ModelForm):
    circuit = forms.ModelChoiceField(
        queryset=Circuit.objects.none(),
        label="Circuit",
        required=True
    )

    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Available Departments"
    )

    class Meta:
        model = School
        fields = ['name', 'school_code', 'circuit', 'departments']

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Limit circuits to those within the user's district
        if request and hasattr(request.user, 'district'):
            self.fields['circuit'].queryset = Circuit.objects.filter(
                district=request.user.district
            )
            self.request = request  # Save request for validation use

    def clean(self):
        cleaned_data = super().clean()

        # Safety check for circuit tampering
        circuit = cleaned_data.get('circuit')
        if circuit and hasattr(self.request.user, 'district'):
            if circuit.district != self.request.user.district:
                raise ValidationError("Selected circuit does not belong to your district.")


        # Duplicate school code check
        school_code = cleaned_data.get('school_code')
        if school_code and School.objects.filter(school_code=school_code).exists():
            raise ValidationError("A school with this code already exists.")

        return cleaned_data





class ResultUploadForm(forms.Form):
    class_group = forms.ModelChoiceField(queryset=ClassGroup.objects.all())
    subject = forms.ModelChoiceField(queryset=Subject.objects.none())  # Initially empty
    student_name = forms.CharField(max_length=255)

    # Assessment breakdown fields
    cat1 = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=30)
    project_work = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=20)
    cat2 = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=30)
    group_work = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=20)
    exam_score = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)

    academic_year = forms.ChoiceField(choices=Result.ACADEMIC_YEAR_CHOICES)
    term = forms.ChoiceField(choices=[("Term 1", "Term 1"), ("Term 2", "Term 2"), ("Term 3", "Term 3")])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "class_group" in self.data:
            try:
                class_group_id = int(self.data.get("class_group"))
                class_group = ClassGroup.objects.get(id=class_group_id)
                self.fields["subject"].queryset = class_group.department.subjects.all()
            except (ValueError, TypeError, ClassGroup.DoesNotExist):
                self.fields["subject"].queryset = Subject.objects.none()
        else:
            self.fields["subject"].queryset = Subject.objects.none()




class TeacherRegistrationForm(UserCreationForm):
    staff_id = forms.IntegerField()
    license_number = forms.CharField(max_length=50)
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField()
    phone_number = forms.CharField(
        max_length=15,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number.')],
    )

    class Meta:
        model = User  
        fields = [
            "staff_id", "license_number", "first_name", "last_name",
            "email", "phone_number", "password1", "password2"
        ]

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop("school", None)  
        self.district = kwargs.pop("district", None)  # Capture district
        self.circuit = kwargs.pop("circuit", None)  # Capture circuit
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        self.instance.role = "teacher"  # Ensure role is set
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = "teacher"
        user.school = self.school
        user.district = self.district  # Assign district
        user.circuit = self.circuit  # Assign circuit

        if commit:
            user.save()
            Teacher.objects.create(user=user, school=self.school)  
        return user


class NotificationForm(forms.ModelForm):
    recipient = forms.ModelChoiceField(
        queryset=User.objects.filter(role='Headteacher'),  # Filter based on role if needed
        required=False,  # Optional if "All" is selected
        empty_label="Select a Headteacher"
    )
    message = forms.CharField(widget=forms.Textarea, required=True)
    send_to_all = forms.BooleanField(required=False, initial=False, label="Send to All Headteachers")

    class Meta:
        model = Notification
        fields = ['recipient', 'message', 'send_to_all']

    def clean(self):
        cleaned_data = super().clean()
        send_to_all = cleaned_data.get('send_to_all')
        recipient = cleaned_data.get('recipient')

        if send_to_all and recipient is not None:
            raise forms.ValidationError("Cannot select a specific recipient when sending to all Headteachers.")
        return cleaned_data



class CustomPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        """Override to silently check for existing emails."""
        active_users = User._default_manager.filter(email__iexact=email, is_active=True)
        return (u for u in active_users if u.has_usable_password())
