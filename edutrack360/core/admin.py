from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import (
    User, District, Circuit, School, 
    Notification, Teacher, Result, 
    PerformanceSummary, Reminder, ClassGroup, 
    Subject, Department, ClassTeacher, SubjectTeacher, StudentMark,
    Student,
)
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django import forms
from django.contrib.auth.hashers import make_password

class UserAdminForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            'staff_id', 'license_number', 'email', 'first_name',
            'last_name', 'password', 'role', 'district', 'school', 'circuit'
        ]
        widgets = {
            'password': forms.PasswordInput(render_value=True)  # Ensures password input field hides text
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Hide fields initially
        self.fields['district'].widget.attrs['style'] = 'display:none;'
        self.fields['school'].widget.attrs['style'] = 'display:none;'
        self.fields['circuit'].widget.attrs['style'] = 'display:none;'

        # Populate field choices dynamically
        self.fields['district'].queryset = District.objects.all()
        self.fields['school'].queryset = School.objects.all()
        self.fields['circuit'].queryset = Circuit.objects.all()

        # Show fields based on role
        if self.instance.pk:  # Only for editing existing users
            if self.instance.role == 'cis':
                self.fields['district'].widget = forms.Select()
            elif self.instance.role == 'siso':
                self.fields['circuit'].widget = forms.Select()
            elif self.instance.role in ['headteacher', 'teacher']:
                self.fields['school'].widget = forms.Select()

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')

        if role == "cis" and not cleaned_data.get("district"):
            raise ValidationError("CIS users must be assigned to a district.")
        if role == "siso" and not cleaned_data.get("circuit"):
            raise ValidationError("SISO users must be assigned to a circuit.")
        if role in ["headteacher", "teacher"] and not cleaned_data.get("school"):
            raise ValidationError(f"{role} must be assigned to a school.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)

        # Hash password before saving
        if self.cleaned_data.get('password'):
            user.password = make_password(self.cleaned_data['password'])

        if commit:
            user.save()
        return user

class UserAdmin(admin.ModelAdmin):
    form = UserAdminForm
    list_display = [
        'staff_id', 'license_number', 'email', 'role', 'first_name', 'last_name',
        'district', 'circuit', 'school'
    ]
    search_fields = ['staff_id', 'email', 'first_name', 'last_name']
    list_filter = ['role', 'district', 'circuit', 'school']

    def get_assigned_circuit(self, obj):
        return obj.circuit.name if obj.circuit else "No Circuit Assigned"
    get_assigned_circuit.short_description = "Circuit"

    class Media:
        js = ('js/user_dynamic_fields.js',)  # Ensures dynamic field behavior in admin

    fieldsets = (
        (None, {
            'fields': (
                'staff_id', 'license_number', 'email', 'first_name', 'last_name',
                'password', 'role', 'district', 'circuit', 'school'
            ),
        }),
        ('Permissions', {
            'fields': ('is_staff', 'is_active', 'is_superuser'),
        }),
    )

    def save_model(self, request, obj, form, change):
        """Ensure password is hashed before saving"""
        if form.cleaned_data.get('password') and not obj.password.startswith('pbkdf2_sha256$'):
            obj.password = make_password(form.cleaned_data['password'])
        super().save_model(request, obj, form, change)

admin.site.register(User, UserAdmin)


class DistrictAdmin(admin.ModelAdmin):
    list_display = ('name', 'region', 'get_assigned_cis')
    search_fields = ('name', 'region')
    list_filter = ('region',)

    def get_assigned_cis(self, obj):
        if obj.cis:  # Directly access the `cis` field
            return f"{obj.cis.first_name} {obj.cis.last_name}"  # Full name
        return "No CIS assigned"
    get_assigned_cis.short_description = 'Assigned CIS'  # Column header in the admin list view # Column header name in the admin list view

    def save_model(self, request, obj, form, change):
        # Allow saving the District without requiring a CIS user to be assigned
        super().save_model(request, obj, form, change)

admin.site.register(District, DistrictAdmin)

# Registering the Circuit model
@admin.register(Circuit)
class CircuitAdmin(admin.ModelAdmin):
    list_display = ('name', 'district', 'siso_display')
    search_fields = ('name', 'district__name')

    def siso_display(self, obj):
        return f"{obj.siso.first_name} {obj.siso.last_name}" if obj.siso else "No SISO"
    siso_display.short_description = 'SISO'

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'school_code', 'circuit', 'district', 'headteacher_display', 'departments_display')
    search_fields = ('name', 'circuit__name', 'district__name')

    def headteacher_display(self, obj):
        return f"{obj.headteacher.first_name} {obj.headteacher.last_name}" if obj.headteacher else "No Headteacher"
    headteacher_display.short_description = 'Headteacher'

    def departments_display(self, obj):
        return ", ".join([dept.name for dept in obj.department.all()]) if obj.department.exists() else "No Department"
    departments_display.short_description = 'Departments'


# Registering the Result model
class ResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'mark', 'class_group', 'teacher', 'term', 'academic_year')
    search_fields = ('student_name', 'subject', 'class_group', 'term')
    list_filter = ('term', 'academic_year',)
    
admin.site.register(Result, ResultAdmin)

# Registering the PerformanceSummary model
class PerformanceSummaryAdmin(admin.ModelAdmin):
    list_display = ('school', 'circuit', 'district', 'term', 'academic_year', 'average_score')
    search_fields = ('school__name', 'circuit__name', 'district__name', 'term', 'year')
    list_filter = ('term', 'academic_year', 'school', 'circuit', 'district')

admin.site.register(PerformanceSummary, PerformanceSummaryAdmin)

# Registering the Reminder model
class RecipientRoleListFilter(admin.SimpleListFilter):
    title = 'Recipient Role'
    parameter_name = 'recipient_role'

    def lookups(self, request, model_admin):
        # Provide the options based on ROLE_CHOICES
        return [
            ('cis', 'Chief Inspector of Schools'),
            ('siso', 'School Improvement Support Officer'),
            ('headteacher', 'Headteacher'),
            ('teacher', 'Teacher'),
        ]

    def queryset(self, request, queryset):
        # Filter based on the selected role
        if self.value():
            return queryset.filter(recipient_role=self.value())
        return queryset

class ReminderAdmin(admin.ModelAdmin):
    list_display = ('sender', 'get_recipient_role', 'subject', 'created_at')
    
    def get_recipient_role(self, obj):
        return obj.get_recipient_role_display()  # This gives the human-readable value of recipient_role
    get_recipient_role.short_description = 'Recipient Role'
    
    # Use custom filter instead of direct field filtering
    list_filter = (RecipientRoleListFilter,)

admin.site.register(Reminder, ReminderAdmin)


# Registering the Class model
class ClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'get_department')  # Use the correct method
    search_fields = ('name', 'school__name',)
    list_filter = ('school',)

    def get_department(self, obj):
        return obj.department.name if obj.department else "No Department"  # Directly get the name

    get_department.short_description = 'Department'  # Set column name in Django admin

admin.site.register(ClassGroup, ClassAdmin)


# Registering the Subject model
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_departments')
    search_fields = ('name', 'display_departments')
    list_filter = ('name', )

    def display_departments(self, obj):
        # Retrieve the department names and join them with commas
        return ", ".join([department.name for department in obj.department.all()])
    display_departments.short_description = 'Departments'  # Optional: Sets the column header to "Departments"

admin.site.register(Subject, SubjectAdmin)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'message', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name',)  # Display department names in the admin panel
    search_fields = ('name',)  



# Custom admin configuration for Teacher model
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('user', 'school',)
    search_fields = ('user__first_name', 'user__last_name', 'school__name')
    list_filter = ('school', 'user__role')

admin.site.register(Teacher, TeacherAdmin)

# Custom admin configuration for SubjectTeacher model
class SubjectTeacherAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'subject', 'get_assigned_classes')
    search_fields = ('teacher__user__first_name', 'teacher__user__last_name', 'subject__name')
    
    # Method to display the assigned classes
    def get_assigned_classes(self, obj):
        return ", ".join([assigned_class.name for assigned_class in obj.assigned_classes.all()])
    get_assigned_classes.short_description = _('Assigned Classes')

admin.site.register(SubjectTeacher, SubjectTeacherAdmin)

# Custom admin configuration for ClassTeacher model
class ClassTeacherAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'assigned_class')
    search_fields = ('teacher__user__first_name', 'teacher__user__last_name', 'assigned_class__name')
    list_filter = ('assigned_class',)

admin.site.register(ClassTeacher, ClassTeacherAdmin)


@admin.register(StudentMark)
class StudentMarkAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'class_group', 'term', 'academic_year', 'mark')
    list_filter = ('term', 'academic_year', 'class_group', 'subject')
    search_fields = ('student__first_name', 'student__last_name', 'subject__name')
    autocomplete_fields = ('student', 'subject', 'class_group')
    ordering = ('academic_year', 'term', 'student')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('student', 'subject', 'class_group')
    

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'school', 'class_group', 'circuit', 'district')
    list_filter = ('school', 'class_group', 'circuit', 'district')
    search_fields = ('first_name', 'last_name', 'school__name')
    autocomplete_fields = ('school', 'class_group', 'circuit', 'district')
    ordering = ('last_name', 'first_name')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('school', 'class_group', 'circuit', 'district')


