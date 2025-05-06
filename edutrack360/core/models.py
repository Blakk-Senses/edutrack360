from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import MinLengthValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db import models
from .managers import UserManager  # Assuming you have a custom user manager.
from django.conf import settings
from django.utils import timezone



from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.core.validators import MinLengthValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from core.managers import UserManager  # Ensure you have a custom manager


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('cis', 'Chief Inspector of Schools'),
        ('siso', 'School Improvement Support Officer'),
        ('headteacher', 'Headteacher'),
        ('teacher', 'Teacher'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        verbose_name="User Role",
        help_text="Designates the role assigned to the user."
    )

    school = models.ForeignKey(
        'core.School',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='staff_members'
    )

    staff_id = models.CharField(max_length=20, unique=True, db_index=True)  # Now CharField to allow '00000000'

    license_number = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        validators=[MinLengthValidator(5)]
    )

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=50, null=True, blank=True)
    middle_name = models.CharField(max_length=50, null=True, blank=True)
    last_name = models.CharField(max_length=50, null=True, blank=True)

    district = models.ForeignKey(
        'core.District',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )

    circuit = models.ForeignKey(
        'core.Circuit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )

    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', _('Enter a valid phone number.'))],
    )

    last_login = models.DateTimeField(blank=True, null=True, verbose_name='last login')
    is_staff = models.BooleanField(default=False, verbose_name='staff status')
    is_active = models.BooleanField(default=True, verbose_name='active')
    is_superuser = models.BooleanField(default=False, verbose_name='superuser status')
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name='date joined')
    first_appointment_date = models.DateField(null=True, blank=True)
    assigned_classes = models.CharField(max_length=255, null=True, blank=True)
    password_changed = models.BooleanField(default=False)

    USERNAME_FIELD = 'staff_id'
    REQUIRED_FIELDS = ['email']  # staff_id is the USERNAME_FIELD, email is required manually

    objects = UserManager()

    def clean_email(self):
        if not self.email:
            raise ValidationError(_("Email is required."))
        if len(self.email) < 8:
            raise ValidationError(_("Email is too short. It must be at least 8 characters long."))

    def clean(self):
        super().clean()

        # Clean the email field
        self.clean_email()

        # Check if the role is valid
        if self.role not in dict(self.ROLE_CHOICES):
            raise ValidationError(_("Invalid role. Choose from the predefined roles."))

        # For non-admin roles, check the required fields
        if self.role != 'admin':  # Only non-admin users need these fields
            if not self.first_name or not self.last_name:
                raise ValidationError(_("First name and last name are required for non-admin users."))
            if not self.license_number:
                raise ValidationError(_("License number is required for non-admin users."))

            # If the district is not set in the form, inherit it from the logged-in user
            if not self.district and self.role != 'admin' and hasattr(self, 'user') and self.user:
                self.district = self.user.district  # Inherit district from the logged-in user
            
            # Now, check if district is still None (if not set from the form or inherited)
            if not self.district:
                raise ValidationError(_("District is required for non-admin users."))

            # Circuit check for SISO, Headteacher, and Teacher roles
            if self.role in ['siso', 'headteacher', 'teacher'] and not self.circuit:
                raise ValidationError(_("Circuit is required for SISO, Headteacher, and Teacher users."))
            
            # School check for Headteacher role
            if self.role == 'headteacher' and not self.school:
                raise ValidationError(_("School is required for Headteacher users."))


def __str__(self):
    return f"{self.first_name or ''} {self.last_name or ''} ({self.staff_id})"



    def __str__(self):
        return f"{self.first_name or ''} {self.last_name or ''} ({self.staff_id})"


class Region(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
class District(models.Model):
    name = models.CharField(max_length=100)
    region = models.ForeignKey('core.Region', on_delete=models.CASCADE, related_name='districts')  # if using FK
    # region = models.CharField(max_length=100)  # if sticking to CharField

    cis = models.OneToOneField(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_district_cis',
        limit_choices_to={'role': 'cis'},
    )

    admin = models.OneToOneField(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_district_admin',
        limit_choices_to={'role': 'admin'},
    )

    def clean(self):
        errors = {}
        if self.cis and District.objects.filter(cis=self.cis).exclude(id=self.id).exists():
            errors['cis'] = ValidationError("This CIS is already assigned to another district.")
        if self.admin and District.objects.filter(admin=self.admin).exclude(id=self.id).exists():
            errors['admin'] = ValidationError("This Admin is already assigned to another district.")
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name

class Circuit(models.Model):
    name = models.CharField(max_length=100)
    district = models.ForeignKey(
        District, 
        on_delete=models.CASCADE,
        blank=True, null=True, 
        related_name='circuits')
    siso = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='assigned_circuit',
        limit_choices_to={'role': 'siso'},
        null=True,
        blank=True
    )

    def clean(self):
        if self.siso and Circuit.objects.filter(siso=self.siso).exclude(id=self.id).exists():
            raise ValidationError(f"The SISO {self.siso} is already assigned to another circuit.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class School(models.Model):
    name = models.CharField(max_length=200)
    school_code = models.IntegerField(unique=True)
    circuit = models.ForeignKey(
        Circuit, 
        on_delete=models.CASCADE,
        blank=True, null=True, 
        related_name='schools'
    )
    district = models.ForeignKey(
        District, 
        on_delete=models.CASCADE,
        blank=True, null=True, 
        related_name='schools_in_districts'
    )
    headteacher = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        related_name='school_headteacher',
        limit_choices_to={'role': 'headteacher'},
        null=True,
        blank=True
    )
    department = models.ManyToManyField(  # Change from ForeignKey to ManyToManyField
        'core.Department', 
        blank=True,
        related_name="schools"
    )

    def __str__(self):
        return self.name


class Student(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    class_group = models.ForeignKey(
        'core.ClassGroup', 
        on_delete=models.CASCADE,
        blank=True, null=True, 
        related_name='students'
    )
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='students')
    circuit = models.ForeignKey(Circuit, on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, blank=True, related_name='students')

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.school.name}"

    @property
    def department(self):
        """Fetch department dynamically from the class_group."""
        return self.class_group.department.all() if self.class_group else None

class Teacher(models.Model):
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        blank=False, 
        null=False, 
        limit_choices_to={'role': 'teacher'},
        related_name='teacher_profile'
    )
    school = models.ForeignKey(
        School, 
        on_delete=models.CASCADE,
        blank=True, null=True, 
        related_name='teachers'
    )
    assigned_classes = models.ManyToManyField(
        'core.ClassGroup', 
        related_name='teachers_assigned_classes',  # Changed this to a unique name
        blank=True
    )
    assigned_subjects = models.ManyToManyField(
        'core.Subject', 
        related_name='teachers_assigned_subjects',  # Changed this to a unique name
        blank=True
    )

    def remove_subject(self, subject, headteacher):
        """Remove a subject from the teacher, ensuring only the headteacher can do so."""
        if self.school.headteacher != headteacher:
            raise PermissionError("Only the headteacher of this school can remove subjects.")
        
        self.assigned_subjects.remove(subject)

    def assign_class(self, class_obj, headteacher):
        """Assign a class to the teacher, ensuring only the headteacher can do so."""
        if self.school.headteacher != headteacher:
            raise PermissionError("Only the headteacher of this school can assign classes.")
        
        # Check if the teacher is already a subject teacher for this class
        if self.assigned_subjects.exists() and self.assigned_classes.filter(id=class_obj.id).exists():
            raise PermissionError(f"Teacher cannot be both a class teacher and a subject teacher for {class_obj.name}.")
        
        self.assigned_classes.add(class_obj)

    def assign_subject(self, subject, headteacher):
        """Assign a subject to the teacher, ensuring only the headteacher can do so."""
        if self.school.headteacher != headteacher:
            raise PermissionError("Only the headteacher of this school can assign subjects.")
        
        # Check if the teacher is already a class teacher for any class the subject is assigned to
        if self.assigned_classes.exists() and self.assigned_subjects.filter(id=subject.id).exists():
            raise PermissionError(f"Teacher cannot be both a subject teacher and a class teacher for any class.")
        
        self.assigned_subjects.add(subject)


    def remove_class(self, class_obj, headteacher):
        """Remove a class from the teacher, ensuring only the headteacher can do so."""
        if self.school.headteacher != headteacher:
            raise PermissionError("Only the headteacher of this school can remove classes.")
        
        self.assigned_classes.remove(class_obj)

    def clean(self):
        if self.user.role != "teacher":
            raise ValidationError("Only users with the 'teacher' role can be assigned to the Teacher model.")
    
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"


class SubjectTeacher(models.Model):
    teacher = models.ForeignKey(
        Teacher, 
        on_delete=models.CASCADE, 
        related_name="subject_teacher_profile_set"  # Changed this to avoid conflict
    )
    subject = models.ForeignKey(
        'core.Subject', 
        on_delete=models.CASCADE,
        related_name='subject_teachers_set'  # Changed this to avoid conflict
    )
    assigned_classes = models.ManyToManyField(
        'core.ClassGroup',
        related_name="subject_teachers_set", blank=True  # Changed this to avoid conflict
    )
    managed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'headteacher'},
        related_name="assigned_subject_teachers"
    )

    def __str__(self):
        return f"{self.teacher} - {self.subject}"

class ClassTeacher(models.Model):
    teacher = models.ForeignKey(
        Teacher, 
        on_delete=models.CASCADE, 
        related_name="class_teacher_profile_set"  # Changed this to avoid conflict
    )
    assigned_class = models.ForeignKey(
        'core.ClassGroup',
        on_delete=models.CASCADE,
        related_name='class_teachers_set'  # Changed this to avoid conflict
    )
    managed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'headteacher'},
        related_name="assigned_class_teachers"
    )

    def __str__(self):
        return f"{self.teacher} - Class Teacher of {self.assigned_class}"


class Department(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Reminder(models.Model):
    sender = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        blank=True, null=True, 
        related_name='sent_reminders'
    )
    recipient = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='received_reminders', 
        null=True, 
        blank=True
    )
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reminder to {self.recipient.role} - {self.subject}"


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        blank=True, null=True, 
        related_name='profile'
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    license_number = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Profile of {self.user.get_full_name()}"


class SchoolSubmission(models.Model):
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('pending', 'Pending Approval'),
        ('not_submitted', 'Not Submitted'),
    ]
    
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_submitted')
    submission_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.school.name} - {self.status}"


from django.utils import timezone
from datetime import timedelta

class Notification(models.Model):
    sender = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        blank=True, null=True, 
        related_name="sent_notifications"
    )
    recipient = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        blank=True, null=True, 
        related_name="received_notifications"
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)  # Field for expiration date
    is_expired = models.BooleanField(default=False)  # Flag for expired notifications

    def __str__(self):
        return f"Notification from {self.sender} to {self.recipient}"

    def save(self, *args, **kwargs):
        # If expiration is set, ensure it is set based on the created date or a custom expiration period
        if self.expires_at is None and self.created_at:
            self.expires_at = self.created_at + timedelta(days=7)  # Set expiration to 7 days from creation
        super().save(*args, **kwargs)

    def check_expiry(self):
        """Check if notification is expired based on current time."""
        if self.expires_at and timezone.now() > self.expires_at:
            self.is_expired = True
            self.save()

    @classmethod
    def get_expired_notifications(cls):
        """Get all expired notifications."""
        return cls.objects.filter(is_expired=True)
    
    @classmethod
    def get_active_notifications(cls):
        """Get all active notifications."""
        return cls.objects.filter(is_expired=False)

    @classmethod
    def get_notifications_for_siso(cls, siso_user):
        """Get all notifications for a specific SISO, including all their assigned headteachers."""
        # Assuming the SISO user is linked to schools in some way
        headteachers = siso_user.schools.all()  # Adjust based on the real relation
        return cls.objects.filter(recipient__in=headteachers)



class PerformanceSummary(models.Model):
    class_group = models.ForeignKey(
        'core.ClassGroup',  # Fixed naming issue
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='performance_summaries'
    )
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='performance_summaries'
    )
    circuit = models.ForeignKey(
        Circuit,
        on_delete=models.CASCADE,
        blank=True, null=True,
        related_name='performance_summaries'
    )
    district = models.ForeignKey(
        District,
        on_delete=models.CASCADE,
        blank=True, null=True,
        related_name='performance_summaries'
    )
    department = models.ManyToManyField(
        'core.Department',
        blank=True,
        related_name="performance_summaries"
    )
    term = models.CharField(max_length=20)
    ACADEMIC_YEAR_CHOICES = [
        (f"{year}/{year+1}", f"{year}/{year+1}") for year in range(2000, 2100)
    ]

    academic_year = models.CharField(
        max_length=9,
        choices=ACADEMIC_YEAR_CHOICES,
        default=f"{timezone.now().year}/{timezone.now().year+1}"
    )
    average_score = models.DecimalField(max_digits=5, decimal_places=2)

    def __str__(self):
        level = "District" if self.district else "Circuit" if self.circuit else "School"
        departments = ", ".join(dept.name for dept in self.department.all())  # Handle ManyToManyField
        return f"{level} Summary - {departments} - {self.term} {self.year}"
    


class ResultUploadDeadline(models.Model):
    ACADEMIC_YEAR_CHOICES = [
        (f"{year}/{year+1}", f"{year}/{year+1}") for year in range(2000, 2100)
    ]

    district = models.ForeignKey(District, on_delete=models.CASCADE)
    
    term = models.CharField(max_length=20)
    
    academic_year = models.CharField(
        max_length=9,
        choices=ACADEMIC_YEAR_CHOICES,
        default=f"{timezone.now().year}/{timezone.now().year + 1}"
    )
    
    deadline_date = models.DateField()
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('district', 'academic_year', 'term')

    def __str__(self):
        return f"{self.district} - {self.academic_year} {self.term}"
    

# Pseudocode only for now
class ResultUploadNotification(models.Model):
    result = models.ForeignKey('core.Result', on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE)  # Headteacher
    is_seen = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)




class ClassGroup(models.Model):  # Renamed from Class to ClassGroup
    name = models.CharField(max_length=50)
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='classes'
    )
    department = models.ForeignKey(
        'core.Department',
        on_delete=models.CASCADE,
        blank=True, null=True,
        related_name='classes'
    )

    def __str__(self):
        return f"{self.name} ({self.school.name if self.school else 'No School'})"


class Subject(models.Model):
    name = models.CharField(max_length=255)
    department = models.ManyToManyField(
        'core.Department',
        blank=True,
        related_name="subjects"
    )
    def __str__(self):
        return self.name

class Result(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Submitted', 'Submitted'),
        ('Queried', 'Queried')
    ]

    ACADEMIC_YEAR_CHOICES = [
        (f"{year}/{year+1}", f"{year}/{year+1}") for year in range(2020, 2050)
    ]

    academic_year = models.CharField(
        max_length=9,
        choices=ACADEMIC_YEAR_CHOICES,
        default=f"{timezone.now().year}/{timezone.now().year+1}"
    )
    class_group = models.ForeignKey(
        'core.ClassGroup',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='results'
    )
    subject = models.ForeignKey(
        'core.Subject',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='results'
    )
    term = models.CharField(max_length=20)
    
    student = models.ForeignKey(
        'core.Student', 
        on_delete=models.CASCADE, 
        blank=True, null=True, 
        related_name="results"
    )
    cat1 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    project_work = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    cat2 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    group_work = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    total_ca = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    ca_50 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    exam_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    exam_50 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    final_mark = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    position = models.PositiveIntegerField(null=True, blank=True)
    remark = models.CharField(max_length=50, null=True, blank=True)

    teacher = models.ForeignKey(
        'core.User',
        on_delete=models.CASCADE,
        blank=True, null=True,
        limit_choices_to={'role': 'teacher'},
        related_name='results'
    )
    school = models.ForeignKey(
        'core.School',
        on_delete=models.CASCADE,
        blank=True, null=True,
        related_name="results"
    )
    circuit = models.ForeignKey(
        'core.Circuit',
        on_delete=models.CASCADE,
        related_name="results",
        null=True, blank=True
    )
    district = models.ForeignKey(
        'core.District',
        on_delete=models.CASCADE,
        related_name="results",
        null=True, blank=True
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='Pending'
    )
    query_reason = models.TextField(blank=True, null=True)
    
    submitted_at = models.DateTimeField(auto_now_add=True)  # Track submission timestamp
    approved_at = models.DateTimeField(null=True, blank=True)  # Track approval timestamp

    def __str__(self):
        return f"{self.student.first_name} {self.student.last_name} - {self.subject.name} - {self.term} {self.academic_year}"



class StudentMark(models.Model):
    TERM_CHOICES = [
        ('Term 1', 'Term 1'),
        ('Term 2', 'Term 2'),
        ('Term 3', 'Term 3'),
    ]

    term = models.CharField(
        max_length=20,
        choices=TERM_CHOICES,
        blank=True,
        null=True,
        db_index=True
    )

    ACADEMIC_YEAR_CHOICES = [
        (f"{year}/{year+1}", f"{year}/{year+1}") for year in range(2000, 2100)
    ]

    academic_year = models.CharField(
        max_length=9,
        choices=ACADEMIC_YEAR_CHOICES,
        default=f"{timezone.now().year}/{timezone.now().year+1}",
        db_index=True
    )

    student = models.ForeignKey(
        Student, 
        on_delete=models.CASCADE,
        blank=True, 
        null=True,
        related_name='marks'
    )

    subject = models.ForeignKey(
        'core.Subject',
        on_delete=models.CASCADE,
        blank=True, 
        null=True,
        related_name="marks",
        db_index=True
    )

    department = models.ManyToManyField(  # Changed from ForeignKey to ManyToManyField
        'core.Department',
        blank=True,
        related_name="marks"
    )

    class_group = models.ForeignKey(
        'core.ClassGroup', 
        on_delete=models.CASCADE,
        blank=True, 
        null=True,
        related_name='marks'
    )

    mark = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00  # Added default value
    )

    def __str__(self):
        return f"{self.student.first_name} {self.student.last_name} - {self.subject.name}: {self.mark}"

    @property
    def school(self):
        return self.student.school

    @property
    def circuit(self):
        return self.student.circuit

    @property
    def district(self):
        return self.student.district
