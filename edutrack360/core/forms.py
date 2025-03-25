from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from datetime import datetime
from core.models import (
    Circuit, School, Student, 
    Subject, ClassGroup, Department, Result, Teacher, User

)
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import MinLengthValidator, RegexValidator

User = get_user_model()  

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'department']


class AddSchoolForm(forms.ModelForm):
    # Headteacher details
    headteacher_staff_id = forms.CharField(max_length=50, label="Headteacher Staff ID")
    headteacher_first_name = forms.CharField(max_length=50, label="Headteacher First Name")
    headteacher_last_name = forms.CharField(max_length=50, label="Headteacher Last Name")
    headteacher_license_number = forms.CharField(max_length=50, label="Headteacher License Number")
    headteacher_email = forms.EmailField(label="Headteacher Email")
    headteacher_phone_number = forms.CharField(max_length=50, label="Headteacher Phone Number")
    headteacher_password = forms.CharField(widget=forms.PasswordInput(), label="Headteacher Password")

    circuit = forms.ModelChoiceField(queryset=Circuit.objects.none(), label="Circuit", required=True)

    class Meta:
        model = School
        fields = ['name', 'school_code', 'circuit']

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Ensure request is available to filter circuits
        if request and hasattr(request.user, 'assigned_district'):
            self.fields['circuit'].queryset = Circuit.objects.filter(district=request.user.assigned_district)

    def clean(self):
        cleaned_data = super().clean()

        # Ensure email uniqueness for headteacher
        email = cleaned_data.get('headteacher_email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")

        # Ensure school code uniqueness
        school_code = cleaned_data.get('school_code')
        if school_code and School.objects.filter(school_code=school_code).exists():
            raise forms.ValidationError("A school with this code already exists.")

        return cleaned_data

    def save_headteacher(self, school_instance):
        cleaned_data = self.cleaned_data
        
        # Create the headteacher user and assign the school and district
        headteacher = User.objects.create(
            staff_id=cleaned_data['headteacher_staff_id'],
            first_name=cleaned_data['headteacher_first_name'],
            last_name=cleaned_data['headteacher_last_name'],
            license_number=cleaned_data['headteacher_license_number'],
            email=cleaned_data['headteacher_email'],
            phone_number=cleaned_data['headteacher_phone_number'],
            role='headteacher',
            district=school_instance.district,  # Assign the district from the school
            school=school_instance,  # Assign the school itself
            password=make_password(cleaned_data['headteacher_password'])
        )
        return headteacher

class BulkUploadForm(forms.Form):
    csv_file = forms.FileField(label="Upload CSV File")


class CreateCircuitForm(forms.ModelForm):
    siso = forms.ModelChoiceField(queryset=User.objects.none(), required=False, label="SISO")

    class Meta:
        model = Circuit
        fields = ['name']

    def __init__(self, *args, **kwargs):
        district = kwargs.pop('district', None)
        super().__init__(*args, **kwargs)
        if district:
            self.fields['siso'].queryset = User.objects.filter(district=district, role='siso')


class AssignSISOForm(forms.ModelForm):
    staff_id = forms.CharField(max_length=50, label="Staff ID")
    license_number = forms.CharField(max_length=50, label="License Number")
    first_name = forms.CharField(max_length=50, label="First Name")
    last_name = forms.CharField(max_length=50, label="Last Name")
    email = forms.EmailField(label="Email Address")
    phone_number = forms.CharField(max_length=15, required=False, label="Phone Number")
    password = forms.CharField(widget=forms.PasswordInput(), label="Password")
    circuit = forms.ModelChoiceField(queryset=Circuit.objects.none(), label="Assign to Circuit")

    class Meta:
        model = User
        fields = [
            'staff_id', 'license_number', 'first_name', 'last_name', 'email', 
            'phone_number', 'password', 'circuit', 'role'
        ]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the logged-in user
        super().__init__(*args, **kwargs)

        if user and user.assigned_district:
            self.fields['circuit'].queryset = Circuit.objects.filter(district=user.assigned_district)

        print("Available circuits:", list(self.fields['circuit'].queryset.values_list("id", "name")))

    def clean_circuit(self):
        circuit = self.cleaned_data.get("circuit")
        if circuit not in self.fields["circuit"].queryset:
            raise forms.ValidationError("Selected circuit is not available for this district.")
        return circuit

    def save(self, user, commit=True):
        siso_user = super().save(commit=False)
        siso_user.role = 'siso'
        siso_user.district = user.assigned_district
        siso_user.set_password(self.cleaned_data['password'])

        if commit:
            siso_user.save()
            # Assign the circuit's siso field
            circuit = self.cleaned_data.get("circuit")
            if circuit:
                circuit.siso = siso_user
                circuit.save()
        
        return siso_user


class ReassignSISOForm(forms.Form):
    siso = forms.ModelChoiceField(queryset=User.objects.none(), label="Select SISO")
    circuit = forms.ModelChoiceField(queryset=Circuit.objects.none(), label="Select New Circuit")

    def __init__(self, *args, **kwargs):
        district = kwargs.pop('district', None)
        super().__init__(*args, **kwargs)
        if district:
            self.fields['siso'].queryset = User.objects.filter(district=district, role='siso')
            self.fields['circuit'].queryset = Circuit.objects.filter(district=district)

class DeleteSISOForm(forms.Form):
    siso = forms.ModelChoiceField(queryset=User.objects.none(), label="Select SISO to Delete")

    def __init__(self, *args, **kwargs):
        district = kwargs.pop('district', None)
        super().__init__(*args, **kwargs)
        if district:
            self.fields['siso'].queryset = User.objects.filter(district=district, role='siso')


class ResultUploadForm(forms.Form):
    class_group = forms.ModelChoiceField(queryset=ClassGroup.objects.all())
    subject = forms.ModelChoiceField(queryset=Subject.objects.none())  # Initially empty
    student_name = forms.CharField(max_length=255)
    mark = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)
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
