from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.db.models import Count, Avg, F, Q
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse, HttpResponse
from core.models import (
    Department, Subject, Result, Teacher,  
    ClassTeacher, SubjectTeacher, ClassGroup, StudentMark 
)
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4, letter, landscape
from reportlab.pdfgen import canvas
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
    """Remove a teacher from a subject or specific classes, handling class assignments properly."""
    user_school = request.user.school
    if not user_school:
        return JsonResponse({"error": "User is not associated with any school"}, status=400)

    teacher = get_object_or_404(Teacher, id=teacher_id, school=user_school)
    subject = get_object_or_404(Subject, id=subject_id, department__school=user_school)

    if request.method == 'POST':
        data = json.loads(request.body)
        class_ids = data.get("classes", [])  # List of class IDs to remove

        # Find the SubjectTeacher relationship
        subject_teacher = SubjectTeacher.objects.filter(teacher=teacher, subject=subject).first()

        if not subject_teacher:
            return JsonResponse({"error": "Teacher is not assigned to this subject"}, status=400)

        if class_ids:
            # Remove only selected classes
            subject_teacher.assigned_classes.remove(*class_ids)

            # If no more classes are assigned, delete the SubjectTeacher entry
            if subject_teacher.assigned_classes.count() == 0:
                subject_teacher.delete()
        else:
            # If no specific classes were provided, remove all assignments and delete the relationship
            subject_teacher.assigned_classes.clear()
            subject_teacher.delete()

        # Check if the teacher is only teaching that subject in any remaining class and remove them from assigned_subjects if necessary
        if subject_teacher.assigned_classes.count() == 0:
            teacher.assigned_subjects.remove(subject)

        return JsonResponse({"message": "Teacher removed from subject successfully!"})

    return JsonResponse({"error": "Invalid request method"}, status=400)



@login_required
def get_subjects_by_teacher(request):
    """Fetch subjects assigned to a specific teacher."""
    teacher_id = request.GET.get("teacher_id")
    user_school = request.user.school  # Ensure user belongs to a school

    if not teacher_id or not user_school:
        return JsonResponse({"error": "Invalid request"}, status=400)

    teacher = get_object_or_404(Teacher, id=teacher_id, school=user_school)

    # Ensure 'assigned_subjects' is the correct related name in your model
    subjects = teacher.assigned_subjects.all()  

    return JsonResponse({"subjects": [{"id": s.id, "name": s.name} for s in subjects]})



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
    """Fetch classes assigned to a teacher."""
    teacher_id = request.GET.get("teacher_id")  # Ensure consistency
    user_school = request.user.school

    if not teacher_id:
        return JsonResponse({"error": "Teacher ID is required"}, status=400)

    teacher = get_object_or_404(Teacher, id=teacher_id, school=user_school)

    # Ensure 'ClassTeacher' model exists and has correct relations
    teacher_classes = ClassTeacher.objects.filter(teacher=teacher).values(
        "assigned_class__id", "assigned_class__name"
    )

    return JsonResponse({"classes": list(teacher_classes)})  # Return structured data


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


# ----------------- PROGRESS AND TRENDS -------------------------------

def progress_trends(request):
    return render(request, 'school/school_reports.html')


def get_available_terms(request):
    """Returns available academic terms and years in an object format with 'id' and 'name'."""
    
    # Generate academic years with id and name
    academic_years = [{"id": year[0], "name": year[0]} for year in [(f"{y}/{y+1}", f"{y}/{y+1}") for y in range(2020, 2150)]]

    # Generate terms with id and name
    terms = [{"id": i + 1, "name": term} for i, term in enumerate(["Term 1", "Term 2", "Term 3"])]

    return JsonResponse({"terms": terms, "academic_years": academic_years})

def get_performance_data(request):
    term = request.GET.get("term")
    academic_year = request.GET.get("academic_year")
    school = request.user.school  # Get school from logged-in user

    data = {}

    # Fetch only marks from students in the logged-in user's school
    marks = StudentMark.objects.filter(term=term, academic_year=academic_year, student__school=school)

    for mark in marks:
        if not mark.department:  # Handle cases where department is null
            continue

        dept_name = mark.department.name  # Ensure department belongs to this school
        class_name = mark.class_group.name
        subject_name = mark.subject.name

        if dept_name not in data:
            data[dept_name] = {}

        if class_name not in data[dept_name]:
            data[dept_name][class_name] = {}

        if subject_name not in data[dept_name][class_name]:
            data[dept_name][class_name][subject_name] = []

        data[dept_name][class_name][subject_name].append(float(mark.mark))

    # Compute averages
    for dept in data:
        for class_group in data[dept]:
            for subject in data[dept][class_group]:
                data[dept][class_group][subject] = round(
                    sum(data[dept][class_group][subject]) / len(data[dept][class_group][subject]), 2
                )

    return JsonResponse({"departments": data})


def get_trend_data(request):
    class_group = request.GET.get("class_group")
    academic_year = request.GET.get("academic_year")
    school = request.user.school  # Get logged-in user's school

    terms = ["Term 1", "Term 2", "Term 3"]
    trend_data = {}

    for term in terms:
        marks = StudentMark.objects.filter(
            class_group__name=class_group, 
            academic_year=academic_year, 
            term=term, 
            student__school=school  # Filter by school
        )
        avg_mark = marks.aggregate(avg=Avg("mark"))["avg"]
        trend_data[term] = round(avg_mark, 2) if avg_mark else 0

    return JsonResponse({class_group: trend_data})

def get_school_performance(request):
    academic_year = request.GET.get("academic_year")
    term = request.GET.get("term")
    school = request.user.school

    previous_terms = {
        "Term 1": ["Term 1", "Term 2", "Term 3"],  # If Term 1, get last 3 terms
        "Term 2": ["Term 2", "Term 3", "Term 1"],
        "Term 3": ["Term 3", "Term 1", "Term 2"],
    }

    terms_to_fetch = previous_terms.get(term, ["Term 1", "Term 2", "Term 3"])
    
    performance_data = {}

    for t in terms_to_fetch:
        marks = StudentMark.objects.filter(academic_year=academic_year, term=t, student__school=school)
        avg_mark = marks.aggregate(avg=Avg("mark"))["avg"]
        performance_data[t] = round(avg_mark, 2) if avg_mark else 0

    return JsonResponse(performance_data)


def generate_school_report_pdf(request):
    academic_year = request.GET.get("academic_year")
    term = request.GET.get("term")
    school = request.user.school

    # Fetch school-wide performance data
    school_performance = get_school_performance(request).content.decode("utf-8")
    
    # Fetch department-wise performance
    department_performance = get_performance_data(request).content.decode("utf-8")

    # Fetch class trend data
    class_trend_data = get_trend_data(request).content.decode("utf-8")

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{school.name}_performance_trends_{term}_{academic_year}.pdf"'

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(letter))

    pdf.setTitle(f"{school.name} Performance Report - {academic_year} {term}")
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(200, 550, f"{school.name} Performance Report")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(200, 530, f"Academic Year: {academic_year}, Term: {term}")

    # Draw a simple table (example, you can format it better)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, 500, "School Performance Summary")
    
    y_position = 480
    for term, score in eval(school_performance).items():
        pdf.drawString(50, y_position, f"{term}: {score}%")
        y_position -= 20

    pdf.drawString(50, y_position - 20, "Departmental Performance")
    y_position -= 40

    for dept, data in eval(department_performance)["departments"].items():
        pdf.drawString(50, y_position, f"Department: {dept}")
        y_position -= 20
        for class_group, subjects in data.items():
            pdf.drawString(70, y_position, f"Class: {class_group}")
            y_position -= 20
            for subject, avg_score in subjects.items():
                pdf.drawString(90, y_position, f"{subject}: {avg_score}%")
                y_position -= 20
        y_position -= 20

    pdf.showPage()
    pdf.save()

    buffer.seek(0)
    response.write(buffer.getvalue())
    return response



@login_required
def get_departments(request):
    """Fetch departments belonging to the logged-in user's school."""
    if not hasattr(request.user, "school") or request.user.school is None:
        return JsonResponse({"error": "User has no associated school."}, status=400)
    
    school = request.user.school
    departments = Department.objects.filter(schools=school).values("id", "name")
    return JsonResponse({"departments": list(departments)})
    

#-------------- PERFORMANCE ANALYSIS -------------------


def school_performance(request):
    return render(request, 'school/school_performance_analysis.html')

def school_performance_analysis(request):
    """Generates tabular performance trend data per class under each department."""
    filter_options = json.loads(get_available_terms(request).content)
    academic_year = request.GET.get("academic_year")
    selected_term = request.GET.get("term", "all")
    school = request.user.school

    terms = [t["name"] for t in filter_options["terms"]]
    if selected_term != "all":
        terms = [selected_term]  # If a specific term is selected, filter only that term

    data = {}

    for department in school.department.all():  # Assuming school has a related_name "department"
        data[department.name] = {}

        # ✅ Fix: Fetch class groups related to this department
        for class_group in ClassGroup.objects.filter(department=department):
            data[department.name][class_group.name] = {"subjects": [], "trend_data": {}, "term_averages": {}}

            subjects = StudentMark.objects.filter(
                class_group=class_group,
                academic_year=academic_year,
                student__school=school
            ).values_list("subject__name", flat=True).distinct()

            data[department.name][class_group.name]["subjects"] = subjects

            for term in terms:
                data[department.name][class_group.name]["trend_data"][term] = {}
                subject_totals = []

                for subject in subjects:
                    marks = StudentMark.objects.filter(
                        class_group=class_group,
                        academic_year=academic_year,
                        term=term,
                        subject__name=subject,
                        student__school=school
                    ).aggregate(avg=Avg("mark"))

                    avg_mark = round(marks["avg"], 2) if marks["avg"] else 0
                    data[department.name][class_group.name]["trend_data"][term][subject] = avg_mark

                    if avg_mark > 0:
                        subject_totals.append(avg_mark)

                data[department.name][class_group.name]["term_averages"][term] = round(
                    sum(subject_totals) / len(subject_totals), 2
                ) if subject_totals else 0

            total_averages = {
                subject: round(
                    sum(data[department.name][class_group.name]["trend_data"][term].get(subject, 0) for term in terms) / len(terms), 2
                ) for subject in subjects
            }

            overall_average = round(sum(total_averages.values()) / len(total_averages), 2) if total_averages else 0

            data[department.name][class_group.name]["total_averages"] = total_averages
            data[department.name][class_group.name]["overall_average"] = overall_average

    return render(request, "school/school_performance_analysis.html", {
        "data": data,
        "terms": terms,
        "academic_years": filter_options["academic_years"],
        "selected_year": academic_year,
        "selected_term": selected_term
    })

def generate_pdf(request):
    """Generates a PDF for school performance analysis"""

    # 🛑 Get school name, term, and academic year
    school_name = request.user.school.name  # Assuming user has a related school model
    term = request.GET.get("term", "all")  # Match filtering
    academic_year = request.GET.get("academic_year")

    # 🛑 Fetch the same performance data
    filter_options = json.loads(get_available_terms(request).content)
    terms = [t["name"] for t in filter_options["terms"]]
    if term != "all":
        terms = [term]

    school = request.user.school
    data = {}

    for department in school.department.all():
        data[department.name] = {}

        for class_group in ClassGroup.objects.filter(department=department):
            data[department.name][class_group.name] = {"subjects": [], "trend_data": {}, "term_averages": {}}

            subjects = StudentMark.objects.filter(
                class_group=class_group,
                academic_year=academic_year,
                student__school=school
            ).values_list("subject__name", flat=True).distinct()

            data[department.name][class_group.name]["subjects"] = subjects

            for term in terms:
                data[department.name][class_group.name]["trend_data"][term] = {}
                subject_totals = []

                for subject in subjects:
                    marks = StudentMark.objects.filter(
                        class_group=class_group,
                        academic_year=academic_year,
                        term=term,
                        subject__name=subject,
                        student__school=school
                    ).aggregate(avg=Avg("mark"))

                    avg_mark = round(marks["avg"], 2) if marks["avg"] else 0
                    data[department.name][class_group.name]["trend_data"][term][subject] = avg_mark

                    if avg_mark > 0:
                        subject_totals.append(avg_mark)

                data[department.name][class_group.name]["term_averages"][term] = round(
                    sum(subject_totals) / len(subject_totals), 2
                ) if subject_totals else 0

            total_averages = {
                subject: round(
                    sum(data[department.name][class_group.name]["trend_data"][term].get(subject, 0) for term in terms) / len(terms), 2
                ) for subject in subjects
            }

            overall_average = round(sum(total_averages.values()) / len(total_averages), 2) if total_averages else 0

            data[department.name][class_group.name]["total_averages"] = total_averages
            data[department.name][class_group.name]["overall_average"] = overall_average

    # 🛑 Generate PDF
    response = HttpResponse(content_type="application/pdf")
    filename = f"{school_name}_Performance_{term}_{academic_year}.pdf".replace(" ", "_")
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # 🛑 Title
    p.setFont("Helvetica-Bold", 14)
    p.drawCentredString(width / 2, height - 50, f"{school_name} Performance Report")

    # 🛑 Term & Academic Year
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2, height - 80, f"Term: {term} | Academic Year: {academic_year}")

    # 🛑 Loop through departments, classes, and subjects
    y_pos = height - 120
    p.setFont("Helvetica-Bold", 12)

    for department, classes in data.items():
        p.drawString(50, y_pos, f"{department} Department")
        y_pos -= 20

        for class_group, details in classes.items():
            p.drawString(70, y_pos, f"Class: {class_group}")
            y_pos -= 20

            for term in terms:
                p.drawString(90, y_pos, f"Term: {term}")
                y_pos -= 20

                for subject, avg in details["trend_data"][term].items():
                    p.drawString(110, y_pos, f"{subject}: {avg}%")
                    y_pos -= 20

                p.drawString(110, y_pos, f"Term Avg: {details['term_averages'][term]}%")
                y_pos -= 20

            p.drawString(90, y_pos, f"Overall Average: {details['overall_average']}%")
            y_pos -= 30  # Extra space after class

        y_pos -= 30  # Extra space after department

    p.showPage()
    p.save()
    return response


#------------------- Submit Results -----------------------


def submit_results(request):
    return render(request, 'school/submit_results.html')


def view_result(request, result_id):
    """Displays the detailed result."""
    result = get_object_or_404(Result, id=result_id)
    return render(request, 'results/submit_results.html', {'result': result})


def submit_result(request, result_id):
    result = get_object_or_404(Result, id=result_id)
    
    # Check if the result is already submitted
    if result.status == "Submitted":
        messages.warning(request, "This result has already been submitted.")
        return redirect("school:view_results")

    # Submit the result
    result.status = "Submitted"
    result.save()
    
    # Add notification
    messages.success(request, f"{result.subject.name} ({result.class_group}) has been submitted.")

    return redirect("school:view_results")

def query_result(request, result_id):
    if request.method == "POST":
        result = get_object_or_404(Result, id=result_id)
        query_reason = request.POST.get("query_reason", "")

        # Check if the result is already queried
        if result.status == "Queried":
            messages.warning(request, "This result has already been queried.")
            return redirect("school:view_results")

        # Query the result
        result.status = "Queried"
        result.save()

        # Add notification
        messages.error(request, f"{result.subject.name} ({result.class_group}) has been queried: {query_reason}")

        return redirect("school:view_results")
