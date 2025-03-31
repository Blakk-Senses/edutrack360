from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.db.models import Count, Avg, F, Q, Max
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse, HttpResponse
from core.models import (
    Department, Subject, Result, Teacher,  
    ClassTeacher, SubjectTeacher, ClassGroup, StudentMark 
)
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
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from reportlab.platypus import Image
from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from core.forms import TeacherRegistrationForm
from django.contrib import messages
import pandas as pd
from django.core.files.storage import default_storage
import csv
from django.views.decorators.csrf import csrf_exempt
import json
from io import BytesIO
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.conf import settings
import logging
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.views import View

logger = logging.getLogger(__name__)


User = get_user_model()



@csrf_exempt
def save_last_page(request):
    """Save the last visited page in Django session."""
    if request.method == "POST":
        data = json.loads(request.body)
        request.session["last_page"] = data.get("last_page")
        return JsonResponse({"status": "success"})
    return JsonResponse({"error": "Invalid request"}, status=400)

def get_last_page(request):
    """Retrieve the last visited page from session."""
    last_page = request.session.get("last_page", None)
    return JsonResponse({"last_page": last_page})

#---------------- SUBJECT MANAGEMENT -----------------------

def subject_management(request):
    return render(request, 'school/subject_management.html')

def add_subject_to_department(request):
    if request.method == "POST":
        department_id = request.POST.get('department')
        subject_name = request.POST.get('subject_name')

        if not department_id or not subject_name:
            return JsonResponse({"error": "Department and subject name are required"}, status=400)

        department = Department.objects.get(id=department_id)
        
        # First, create the subject without assigning department
        subject = Subject.objects.create(name=subject_name)

        # Then, use `.set()` to assign the department
        subject.department.set([department])  # ✅ Correct way for ManyToManyField

        return JsonResponse({"message": "Subject added successfully"})

    return JsonResponse({"error": "Invalid request"}, status=400)


@login_required
def assign_teacher_to_subject(request, teacher_id, subject_id):
    teacher = get_object_or_404(Teacher, id=teacher_id, school=request.user.school)
    subject = get_object_or_404(Subject, id=subject_id)

    # 🚨 Prevent assigning a subject if the teacher is already a class teacher anywhere in the school
    if teacher.assigned_classes.exists():
        return JsonResponse({"error": "Teacher is already assigned as a class teacher and cannot be a subject teacher."}, status=400)

    if request.method == 'POST':
        assigned_class_ids = request.POST.getlist('assigned_class_ids')  # Get multiple class IDs
        assigned_classes = ClassGroup.objects.filter(id__in=assigned_class_ids, school=request.user.school)

        # Assign subject to teacher
        teacher.assigned_subjects.add(subject)

        # Create SubjectTeacher relationship
        subject_teacher, _ = SubjectTeacher.objects.get_or_create(teacher=teacher, subject=subject)

        # Assign multiple classes
        subject_teacher.class_groups.set(assigned_classes)  # Set instead of add


        if assigned_classes:
            subject_teacher.class_groups.add(assigned_classes)  # Explicitly save classes

        teacher.save()
        return JsonResponse({"message": "Subject and class assigned successfully!"})

    return JsonResponse({"error": "Invalid request"}, status=400)


@login_required
def remove_teacher_from_subject(request, teacher_id, subject_id):
    user_school = request.user.school
    if not user_school:
        return JsonResponse({"error": "User is not associated with any school"}, status=400)

    teacher = get_object_or_404(Teacher, id=teacher_id, school=user_school)
    subject = get_object_or_404(Subject, id=subject_id, department__school=user_school)

    if request.method == 'POST':
        data = json.loads(request.body)
        class_ids = data.get("classes", [])

        subject_teacher = SubjectTeacher.objects.filter(teacher=teacher, subject=subject).first()

        if not subject_teacher:
            return JsonResponse({"error": "Teacher is not assigned to this subject"}, status=400)

        if class_ids:
            subject_teacher.assigned_classes.remove(*class_ids)

        # If no more classes assigned to this subject-teacher pair
        if subject_teacher.assigned_classes.count() == 0:
            subject_teacher.delete()
            teacher.assigned_subjects.remove(subject)

        return JsonResponse({"message": "Teacher removed from subject successfully!"})

    return JsonResponse({"error": "Invalid request method"}, status=400)

@login_required
def get_classes_by_teacher_and_subject(request):
    teacher_id = request.GET.get("teacher_id")
    subject_id = request.GET.get("subject_id")

    if not teacher_id or not subject_id:
        return JsonResponse({"error": "Both teacher and subject are required"}, status=400)

    try:
        subject_teacher = SubjectTeacher.objects.get(teacher_id=teacher_id, subject_id=subject_id)
        class_groups = subject_teacher.assigned_classes.all()
        classes = [{"id": cls.id, "name": cls.name} for cls in class_groups]
        return JsonResponse({"classes": classes})
    except SubjectTeacher.DoesNotExist:
        return JsonResponse({"classes": []})


@login_required
def get_subjects_by_teacher(request, teacher_id):  # <-- changed
    user_school = request.user.school

    if not teacher_id or not user_school:
        return JsonResponse({"error": "Invalid request"}, status=400)

    teacher = get_object_or_404(Teacher, id=teacher_id, school=user_school)
    subjects = teacher.assigned_subjects.all()

    return JsonResponse([{"id": s.id, "name": s.name} for s in subjects], safe=False)  # <-- changed to list directly




@login_required
def get_subjects_by_department(request):
    """Fetch subjects based on the selected department."""
    department_id = request.GET.get("department_id")

    if not department_id:
        return JsonResponse({"error": "Department ID is required"}, status=400)

    subjects = Subject.objects.filter(department__id=department_id).values("id", "name")
    return JsonResponse({"subjects": list(subjects)})

#----------------------------------------------------

@login_required
def get_departments(request):
    """Fetch departments belonging to the logged-in user's school."""
    if not hasattr(request.user, "school") or request.user.school is None:
        return JsonResponse({"departments": []})  # Return empty list instead of error

    school = request.user.school
    departments = Department.objects.filter(school=school).values("id", "name")
    return JsonResponse({"departments": list(departments)})



@login_required
def get_teachers(request):
    """Fetch teachers belonging to the logged-in user's school."""
    user_school = request.user.school

    if not user_school:
        return JsonResponse({"teachers": []})  # Return an empty list if no school is linked

    teachers = Teacher.objects.filter(school=user_school).values("id", "user__first_name", "user__last_name")
    return JsonResponse({"teachers": list(teachers)})



# ----------------- CLASS MANAGEMENT -----------------------
def class_management(request):
    teachers = Teacher.objects.all()  # Get teachers
    classes = ClassGroup.objects.all()  # Get classes
    subjects = Subject.objects.all()  # Get classes

    return render(request, 'school/class_management.html', {
        'teachers': teachers,
        'classes': classes,
        'subjects': subjects,
    })


@login_required
def add_class_to_department(request):
    if request.method == "POST":
        department_id = request.POST.get("department")
        class_name = request.POST.get("class_name")

        if not department_id or not class_name:
            return JsonResponse({"error": "Department and class name are required."}, status=400)

        try:
            # Get the logged-in user's school
            user_school = request.user.school  

            # Ensure department belongs to the user's school
            department = Department.objects.get(id=department_id, schools=user_school)

            # Create the class and assign it to both the department and school
            new_class = ClassGroup.objects.create(name=class_name, department=department, school=user_school)

            return JsonResponse({"message": f"Class '{new_class.name}' added to {department.name} successfully!"})

        except Department.DoesNotExist:
            return JsonResponse({"error": "Department not found or does not belong to your school."}, status=404)

    return JsonResponse({"error": "Invalid request."}, status=400)


@login_required
def assign_teacher_to_class(request):
    """Assign a teacher to a class while preventing conflicts with subject teacher roles."""
    user_school = request.user.school
    if not user_school:
        return JsonResponse({"error": "User is not associated with any school"}, status=400)

    if request.method == 'POST':
        teacher_id = request.POST.get('teacher')
        department_id = request.POST.get('department')
        class_id = request.POST.get('class')

        # 🎯 Validate teacher, department, and class
        teacher = get_object_or_404(Teacher, id=teacher_id, school=user_school)
        department = get_object_or_404(Department, id=department_id, schools=user_school)
        class_obj = get_object_or_404(ClassGroup, id=class_id, department=department)

        # 🚨 Prevent assigning a class if the teacher is already a subject teacher
        if teacher.assigned_subjects.exists():
            return JsonResponse({"error": "Teacher is already assigned as a subject teacher and cannot be a class teacher."}, status=400)

        # ✅ Assign the teacher to the class
        ClassTeacher.objects.get_or_create(teacher=teacher, assigned_class=class_obj)

        return JsonResponse({"message": "Teacher assigned successfully!"})

    return JsonResponse({"error": "Invalid request method"}, status=400)




@login_required
def remove_teacher_from_class(request):
    """Remove a teacher from a class and disassociate completely."""
    user_school = request.user.school
    if not user_school:
        return JsonResponse({"error": "User is not associated with any school"}, status=400)

    if request.method == 'POST':
        teacher_id = request.POST.get('remove-teacher')
        class_id = request.POST.get('remove-class')

        # Ensure both teacher and class exist in the same school
        teacher = get_object_or_404(Teacher, id=teacher_id, school=user_school)

        # Fetch the department using the class_id and ensure it belongs to the user's school
        department = get_object_or_404(Department, schools=user_school, id=class_id)

        # Fetch the ClassGroup based on the department and ensure it's in the same school
        class_obj = get_object_or_404(ClassGroup, id=class_id, department=department)

        # Remove teacher-class association completely
        deleted_count, _ = ClassTeacher.objects.filter(teacher=teacher, assigned_class=class_obj).delete()

        if deleted_count > 0:
            return JsonResponse({"message": "Teacher removed successfully!"})
        return JsonResponse({"error": "Teacher was not assigned to this class"}, status=400)

    # If GET request is still necessary, return a JSON response for teacher data (optional)
    teachers = Teacher.objects.filter(school=user_school)
    
    return JsonResponse({
        "teachers": list(teachers.values("id", "user__first_name", "user__last_name"))
    })


@login_required
def get_classes_by_department(request):
    """Fetch classes based on department, ensuring it belongs to the user's school."""
    department_id = request.GET.get("department_id")  # ✅ Ensure correct query parameter
    user_school = request.user.school

    if not department_id:
        return JsonResponse({"error": "Department ID is required"}, status=400)

    try:
        department = Department.objects.get(id=department_id, schools__in=[user_school])  # ✅ Fix school filter
        classes = ClassGroup.objects.filter(department=department).values("id", "name")

        return JsonResponse({"classes": list(classes)})
    except Department.DoesNotExist:
        return JsonResponse({"error": "Invalid department selection"}, status=400)
    

@login_required
def get_teacher_classes(request):
    teacher_id = request.GET.get('teacher_id')
    user_school = request.user.school

    if not teacher_id or not user_school:
        return JsonResponse({'error': 'Missing teacher or school info'}, status=400)

    teacher = get_object_or_404(Teacher, id=teacher_id, school=user_school)

    try:
        class_teacher = ClassTeacher.objects.select_related('assigned_class').get(teacher=teacher)
        assigned_class = class_teacher.assigned_class
        return JsonResponse({
            'class': {
                'id': assigned_class.id,
                'name': assigned_class.name
            }
        })
    except ClassTeacher.DoesNotExist:
        return JsonResponse({'class': None})  # Teacher has no class

# ------------------ TEACHER MANAGEMENT --------------------

def teacher_management(request):
    school = request.user.school  # Assuming User has a ForeignKey to School
    departments = Department.objects.filter(schools=school)

    return render(request, 'school/teacher_management.html', {
        'departments': departments
    })



@login_required
def manual_upload(request):
    if request.method == "POST":
        form = TeacherRegistrationForm(
            request.POST,
            school=request.user.school,
            district=request.user.district,  # Pass district
            circuit=request.user.circuit  # Pass circuit
        )

        if form.is_valid():
            user = form.save()  # Commit directly since department is removed
            return JsonResponse({"success": True, "message": "Teacher registered successfully!"})
        else:
            return JsonResponse({"success": False, "errors": form.errors}, status=400)

    return JsonResponse({}, status=400)  # Return a proper response



@login_required
def bulk_upload_teachers(request):
    """Handles bulk teacher upload via CSV or Excel, ensuring validation."""
    if request.method == "POST" and request.FILES.get("file"):
        file = request.FILES["file"]
        file_extension = os.path.splitext(file.name)[1].lower()

        # Validate file type
        if not is_valid_file_type(file_extension):
            return JsonResponse({"success": False, "error": "Invalid file type! Only .csv, .xls, and .xlsx files are allowed."}, status=400)

        # Save and load the file (CSV or Excel)
        file_path = default_storage.save(f"uploads/{file.name}", file)
        df = load_file(file_extension, default_storage.path(file_path))

        if df is None:
            return JsonResponse({"success": False, "error": "Error reading the file. Ensure it's a valid CSV or Excel file."}, status=400)

        # Validate and process rows
        user = request.user
        teachers_created, skipped_entries = process_bulk_teachers(df, user)

        response_data = {
            "success": True,
            "message": f"{teachers_created} teachers uploaded successfully!",
            "skipped_entries": skipped_entries,  # Include skipped entries for frontend debugging
        }

        if skipped_entries:
            response_data["warning"] = "Some rows were skipped due to validation errors."

        return JsonResponse(response_data)

    return JsonResponse({"success": False, "error": "Invalid request"}, status=400)



def is_valid_file_type(file_extension):
    """Check if the uploaded file is of a valid type."""
    return file_extension in [".csv", ".xls", ".xlsx"]

def load_file(file_extension, file_path):
    """Load CSV or Excel file into a pandas DataFrame."""
    try:
        if file_extension == ".csv":
            return pd.read_csv(file_path, dtype=str)  # Read all columns as strings to prevent data loss
        elif file_extension in [".xls", ".xlsx"]:
            return pd.read_excel(file_path, dtype=str)
    except Exception as e:
        logger.error(f"Error loading file: {str(e)}")
        return None



def process_bulk_teachers(df, user):
    """Process and create teacher records from the DataFrame."""
    required_columns = ["staff_id", "license_number", "first_name", "last_name", "email", "phone_number", "password1", "password2"]

    # Validate required columns
    if not all(col in df.columns for col in required_columns):
        raise ValueError("Invalid file format. Please use the provided template.")

    df = df.fillna("")  # Prevent NaN values
    teachers_created = 0
    skipped_entries = []

    existing_staff_ids = set(User.objects.values_list("staff_id", flat=True))
    existing_emails = set(User.objects.values_list("email", flat=True))

    for index, row in df.iterrows():
        staff_id = str(row["staff_id"]).strip()
        email = str(row["email"]).strip().lower()
        phone_number = str(row["phone_number"]).strip()
        password1 = str(row["password1"]).strip()
        password2 = str(row["password2"]).strip()

        # Skip duplicates
        if staff_id in existing_staff_ids or email in existing_emails:
            skipped_entries.append(f"Row {index+2}: Duplicate staff_id ({staff_id}) or email ({email}).")
            continue

        # Validate row data
        error = validate_teacher_row(staff_id, email, phone_number, password1, password2, index + 2)
        if error:
            skipped_entries.append(error)
            continue

        # ✅ Create & Save User First
        new_user = User(
            staff_id=staff_id,
            license_number=row["license_number"],
            email=email,
            first_name=row["first_name"],
            last_name=row["last_name"],
            phone_number=phone_number,
            role="teacher",
            school=user.school,  # Assign school from logged-in user
            circuit=user.circuit,
            district=user.district
        )
        new_user.set_password(password1)
        new_user.save()  # ✅ Save User First

        # ✅ Now, create and save Teacher instance
        Teacher.objects.create(user=new_user, school=user.school)  # ✅ Ensure 'user' is saved before linking

        teachers_created += 1

    return teachers_created, skipped_entries



def validate_teacher_row(staff_id, email, phone_number, password1, password2, row_num):
    """Validate a single row of teacher data."""
    if not all([staff_id, email, phone_number, password1, password2]):
        return f"Row {row_num}: Missing required fields."

    # Validate email format
    try:
        validate_email(email)
    except ValidationError:
        return f"Row {row_num}: Invalid email format ({email})."

    # Validate phone number
    if not phone_number.isdigit() or len(phone_number) < 10:
        return f"Row {row_num}: Invalid phone number ({phone_number})."

    # Validate password matching and strength
    if password1 != password2:
        return f"Row {row_num}: Passwords do not match."
    if len(password1) < 8:
        return f"Row {row_num}: Password too short."

    return None


def create_teacher_user(row, user):
    """Create a User instance (but do not save)."""
    return User(
        staff_id=row["staff_id"],
        license_number=row["license_number"],
        email=row["email"].strip().lower(),
        first_name=row["first_name"],
        last_name=row["last_name"],
        phone_number=row["phone_number"],
        role="teacher",
        school=user.school,
        circuit=user.circuit,
        district=user.district
    )


def download_teacher_template(request, file_format):
    """Generate teacher upload template."""
    headers = ["staff_id", "license_number", "first_name", "last_name", "email", "phone_number", "password1", "password2"]

    if file_format == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="bulk_teacher_upload_template.csv"'

        writer = csv.writer(response)
        writer.writerow(headers)
        return response

    elif file_format == "excel":
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="bulk_teacher_upload_template.xlsx"'

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Teacher Template"
        sheet.append(headers)  # ✅ Add headers

        workbook.save(response)
        return response

    else:
        return HttpResponse("Invalid file format", status=400)


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


@login_required
def get_departments(request):
    """Fetch departments belonging to the logged-in user's school."""
    if not hasattr(request.user, "school") or request.user.school is None:
        return JsonResponse({"error": "User has no associated school."}, status=400)
    
    school = request.user.school
    departments = Department.objects.filter(schools=school).values("id", "name")
    return JsonResponse({"departments": list(departments)})
    

#-------------- PERFORMANCE ANALYSIS -------------------


def school_performance_analysis(request):
    context = get_school_performance_context(request)
    return render(request, 'school/school_performance_analysis.html', context)


def get_school_performance_context(request):
    """Generates school-wide performance analysis including departmental class performance."""
    print("🔍 Starting school performance context generation...")

    # Load filters
    filter_options = json.loads(get_available_terms(request).content)
    academic_year = request.GET.get("academic_year", "").strip()
    selected_term = request.GET.get("term", "all")

    valid_years = [year["name"] for year in filter_options["academic_years"]]
    academic_year = academic_year if academic_year in valid_years else filter_options["selected_academic_year"]

    all_terms = [t["name"] for t in filter_options["terms"]]
    selected_term = selected_term if selected_term in all_terms else "Term 1"

    user = request.user
    if not hasattr(user, 'school') or user.role != 'headteacher':
        return redirect("homepage")

    school = user.school
    print("📥 Filters applied - Academic Year:", academic_year, "| Term:", selected_term)

    selected_marks = StudentMark.objects.filter(
        academic_year=academic_year,
        term=selected_term,
        student__school=school
    ).select_related("subject", "student__class_group", "student")

    print("🧾 Total marks fetched:", selected_marks.count())

    # ➕ Build Department → Subject → Class → [Marks]
    dept_structure = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for mark in selected_marks:
        subject = mark.subject
        subject_name = subject.name
        class_name = mark.student.class_group.name
        for dept in subject.department.all():
            dept_name = dept.name
            dept_structure[dept_name][subject_name][class_name].append(float(mark.mark))

    # ✅ Fixed: Store each department inside the loop
    departments = {}
    subject_averages = {}
    for dept_name, subjects in dept_structure.items():
        all_class_names = set()
        dept_subjects = {}
        averages = {}
        for subject_name, classes in subjects.items():
            class_avgs = {}
            all_scores = []
            for class_name, scores in classes.items():
                all_class_names.add(class_name)
                avg = round(sum(scores) / len(scores), 2)
                class_avgs[class_name] = avg
                all_scores.extend(scores)
            dept_subjects[subject_name] = class_avgs
            averages[subject_name] = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0
        departments[dept_name] = {
            "subjects": dept_subjects,
            "all_classes": sorted(all_class_names)
        }
        subject_averages[dept_name] = averages

    print("🏫 Departmental class performance computed.")

    # 📚 Subject-wide averages (for bucket analysis)
    subjects = defaultdict(list)
    for mark in selected_marks:
        subjects[mark.subject.name].append(float(mark.mark))
    for subject, marks in subjects.items():
        subjects[subject] = round(sum(marks) / len(marks), 2) if marks else "-"

    # 🎯 Score buckets
    all_scores = [score for score in subjects.values() if isinstance(score, (int, float))]
    score_buckets = {
        "80-100": sum(1 for s in all_scores if s >= 80),
        "55-79": sum(1 for s in all_scores if 55 <= s < 80),
        "50-54": sum(1 for s in all_scores if 50 <= s < 55),
        "40-49": sum(1 for s in all_scores if 40 <= s < 50),
        "0-39":  sum(1 for s in all_scores if s < 40),
    }

    # 📈 Term & Academic Trend
    base_year = int(academic_year.split("/")[0])
    prev_1 = f"{base_year - 1}/{base_year}"
    prev_2 = f"{base_year - 2}/{base_year - 1}"
    academic_years = [prev_2, prev_1, academic_year]

    if selected_term == "Term 1":
        term_sequence = [("Term 2", prev_1), ("Term 3", prev_1), ("Term 1", academic_year)]
    elif selected_term == "Term 2":
        term_sequence = [("Term 3", prev_1), ("Term 1", academic_year), ("Term 2", academic_year)]
    else:
        term_sequence = [("Term 1", academic_year), ("Term 2", academic_year), ("Term 3", academic_year)]

    term_keys = [f"{t} ({y})" for t, y in term_sequence]
    q_terms = Q()
    for term, year in term_sequence:
        q_terms |= Q(term=term, academic_year=year)

    trend_marks = StudentMark.objects.filter(student__school=school).filter(q_terms)

    term_aggregates = {key: [] for key in term_keys}
    year_aggregates = {year: [] for year in academic_years}

    for mark in trend_marks:
        score = float(mark.mark)
        key = f"{mark.term} ({mark.academic_year})"
        if key in term_aggregates:
            term_aggregates[key].append(score)
        if mark.academic_year in year_aggregates:
            year_aggregates[mark.academic_year].append(score)

    term_trend = {
        "School": school.name,
        **{key: round(sum(v) / len(v), 2) if v else "-" for key, v in term_aggregates.items()}
    }
    academic_trend = {
        "School": school.name,
        **{year: round(sum(v) / len(v), 2) if v else "-" for year, v in year_aggregates.items()}
    }

    term_labels = list(term_trend.keys())[1:]
    term_values = [float(val) if isinstance(val, (int, float)) else None for val in list(term_trend.values())[1:]]
    year_labels = list(academic_trend.keys())[1:]
    year_values = [float(val) if isinstance(val, (int, float)) else None for val in list(academic_trend.values())[1:]]

    print("✅ Finished generating full context.")

    return {
        "subjects": subjects,
        "departments": departments,
        "subject_averages": subject_averages,
        "term_trend": term_trend,
        "academic_trend": academic_trend,
        "terms": all_terms,
        "academic_years": valid_years,
        "selected_year": academic_year,
        "selected_term": selected_term,

        "bucket_80_100": score_buckets["80-100"],
        "bucket_55_79": score_buckets["55-79"],
        "bucket_50_54": score_buckets["50-54"],
        "bucket_40_49": score_buckets["40-49"],
        "bucket_0_39": score_buckets["0-39"],
        "score_buckets": score_buckets,

        "term_chart": {"labels": term_labels, "data": term_values},
        "year_chart": {"labels": year_labels, "data": year_values},
    }


@login_required
def download_school_performance_pdf(request):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=120, bottomMargin=50)
    elements = []
    styles = getSampleStyleSheet()
    subtitle_style = styles['Heading4']

    context = get_school_performance_context(request)
    year = context['selected_year']
    term = context['selected_term']
    departments = context["departments"]
    score_buckets = context['score_buckets']
    term_trend = context['term_trend']
    academic_trend = context['academic_trend']
    school_name = f"School: {request.user.school.name}"

    # --- Department-wise Tables + Charts ---
    for dept, dept_data in departments.items():
        elements.append(Paragraph(f"{dept}", subtitle_style))
        table_data = [["Subject"] + dept_data["all_classes"]]

        for subject, class_scores in dept_data["subjects"].items():
            row = [subject] + [class_scores.get(cls, "-") for cls in dept_data["all_classes"]]
            table_data.append(row)

        max_cols = len(dept_data["all_classes"]) + 1
        col_widths = [100] + [(A4[0] - 120) / (max_cols - 1)] * (max_cols - 1)

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]))
        elements.extend([table, Spacer(1, 10)])

        subjects = list(dept_data["subjects"].keys())
        class_names = dept_data["all_classes"]
        data = []
        for cls in class_names:
            row = [dept_data["subjects"][subj].get(cls, 0) or 0 for subj in subjects]
            data.append(row)

        if data and any(any(v > 0 for v in row) for row in data):
            fig, ax = plt.subplots(figsize=(8, 4))
            x = range(len(subjects))
            width = 0.8 / len(data)

            for i, row in enumerate(data):
                offset = i * width
                ax.bar([pos + offset for pos in x], row, width, label=class_names[i])

            ax.set_xticks([pos + width * (len(data)/2) for pos in x])
            ax.set_xticklabels(subjects, rotation=45, ha='right')
            ax.set_ylabel('Average Score')
            ax.set_title(f"{dept} Class-wise Subject Performance")
            ax.legend()

            img_buffer = io.BytesIO()
            plt.tight_layout()
            canvas = FigureCanvas(fig)
            canvas.print_png(img_buffer)
            plt.close(fig)

            img_buffer.seek(0)
            img = Image(img_buffer, width=480, height=240)
            elements.extend([img, Spacer(1, 20)])

    # --- Score Buckets ---
    elements.append(Paragraph("Score Distribution Buckets", subtitle_style))
    bucket_table_data = [
        ["Score Range", "Number of Students"],
        ["80-100", score_buckets["80-100"]],
        ["55-79", score_buckets["55-79"]],
        ["50-54", score_buckets["50-54"]],
        ["40-49", score_buckets["40-49"]],
        ["0-39", score_buckets["0-39"]],
    ]
    bucket_table = Table(bucket_table_data, colWidths=[120, 120])
    bucket_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.extend([bucket_table, Spacer(1, 20)])

    # ✅ FIXED — Trend Table Helpers
    def wrap_labels_and_values(data_dict):
        keys = list(data_dict.keys())
        values = [str(v) for v in data_dict.values()]
        return [keys, values]

    def get_fixed_col_widths(data_dict):
        keys = list(data_dict.keys())
        widths = []
        for key in keys:
            length = len(str(key))
            width = 140 if "School" in str(key) else max(60, length * 6)
            widths.append(width)
        return widths

    # --- Term Trend Table ---
    elements.append(Paragraph("Termly Performance Trend", subtitle_style))
    term_data = wrap_labels_and_values(term_trend)
    term_col_widths = get_fixed_col_widths(term_trend)
    term_table = Table(term_data, colWidths=term_col_widths)
    term_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.extend([term_table, Spacer(1, 20)])

    # --- Year Trend Table ---
    elements.append(Paragraph("Academic Year Performance Trend", subtitle_style))
    year_data = wrap_labels_and_values(academic_trend)
    year_col_widths = get_fixed_col_widths(academic_trend)
    year_table = Table(year_data, colWidths=year_col_widths)
    year_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.extend([year_table, Spacer(1, 20)])

    # --- Header/Footer ---
    def draw_custom_header(c, school_name, academic_year, term):
        page_width, page_height = A4
        banner_color = colors.HexColor("#f2f2f2")
        text_color = colors.black

        c.setFillColor(banner_color)
        c.rect(0, page_height - 60, page_width, 60, fill=1, stroke=0)
        c.setFillColor(text_color)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(page_width / 2, page_height - 35, "School Performance Report")

        c.setFont("Helvetica", 12)
        c.drawCentredString(page_width / 2, page_height - 52, school_name)

        c.setFillColor(banner_color)
        c.rect(0, page_height - 85, page_width, 25, fill=1, stroke=0)
        c.setFillColor(text_color)
        c.setFont("Helvetica-Bold", 10)
        info_text = f"Academic Year: {academic_year}    |    Term: {term}"
        c.drawCentredString(page_width / 2, page_height - 70, info_text)

    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.drawCentredString(A4[0] / 2, 30, f"Page {doc.page}")
        canvas.restoreState()

    # --- Build PDF ---
    doc.build(
        elements,
        onFirstPage=lambda c, d: [draw_custom_header(c, school_name, year, term), draw_footer(c, d)],
        onLaterPages=draw_footer
    )

    buffer.seek(0)
    safe_year = str(year).replace("/", "_")
    filename = f"{school_name}_Performance_{safe_year}_{term}.pdf"

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename={filename}"
    return response



#------------------- Submit Results -----------------------


def submit_results(request):
    return render(request, 'school/submit_results.html')


@login_required
@user_passes_test(lambda u: u.role == "headteacher")  # adjust according to your role system
def headteacher_result_overview(request):
    grouped_results = (
        Result.objects
        .values("academic_year", "term", "subject__id", "subject__name", "class_group__id", "class_group__name")
        .annotate(
            total_entries=Count("id"),
            latest_upload=Max("submitted_at"),
            status=F("status")  # assuming all entries in a group have same status
        )
        .order_by("-latest_upload")
    )

    # Process for template slugs
    files = []
    for f in grouped_results:
        f["year_slug"] = f["academic_year"].replace("/", "-")
        f["term_slug"] = slugify(f["term"])
        files.append(f)

    paginator = Paginator(files, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "school/result_review.html", {"page_obj": page_obj})

@login_required
@user_passes_test(lambda u: u.role == "headteacher")
def headteacher_view_result(request, year, term, subject_id, class_id):
    year = str(year).replace('-', '/')
    term = term.replace('-', ' ').title()

    results = Result.objects.filter(
        academic_year=year,
        term=term,
        subject_id=subject_id,
        class_group_id=class_id
    ).select_related("student", "subject", "class_group")

    if not results.exists():
        return render(request, "school/view_result.html", {
            "results": [], "subject": None, "class_group": None, "year": year, "term": term
        })

    subject = results[0].subject
    class_group = results[0].class_group

    return render(request, "school/view_result.html", {
        "results": results,
        "subject": subject,
        "class_group": class_group,
        "year": year,
        "term": term
    })


@require_POST
@login_required
@user_passes_test(lambda u: u.role == "headteacher")
def submit_result(request):
    year = request.POST.get("year").replace("-", "/")
    term = request.POST.get("term").replace("-", " ").title()
    subject_id = request.POST.get("subject_id")
    class_id = request.POST.get("class_id")

    Result.objects.filter(
        academic_year=year,
        term=term,
        subject_id=subject_id,
        class_group_id=class_id
    ).update(
        status="Submitted",
        approved_at=timezone.now()
    )
    return redirect("school:headteacher_result_overview")  # or wherever appropriate


@require_POST
@login_required
@user_passes_test(lambda u: u.role == "headteacher")
def query_result(request):
    year = request.POST.get("year").replace("-", "/")
    term = request.POST.get("term").replace("-", " ").title()
    subject_id = request.POST.get("subject_id")
    class_id = request.POST.get("class_id")
    reason = request.POST.get("reason", "")

    Result.objects.filter(
        academic_year=year,
        term=term,
        subject_id=subject_id,
        class_group_id=class_id
    ).update(
        status="Queried",
        query_reason=reason
    )
    return redirect("school:headteacher_result_overview")
