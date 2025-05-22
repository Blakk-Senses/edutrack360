
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponseForbidden
from core.models import (
    ResultUploadDeadline, School, StudentMark, 
    Result, SubjectTeacher, ClassTeacher,
)
from django.contrib import messages
from datetime import timedelta
from django.utils import timezone
import json
from decimal import Decimal
from django.db.models import Avg
from django.urls import reverse_lazy
from collections import defaultdict
from statistics import mean


User = get_user_model()

#------------ ADMIN DASHBOARD -----------------------

@login_required
def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')

def cis_registration(request):
    # Ensure the user is an authenticated admin to access this page
    if not request.user.is_authenticated or request.user.role != 'admin':
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    admin_user = request.user  # Get the admin user object
    district = admin_user.district  # Get the district associated with the admin user

    # Handling form submission when the request method is POST
    if request.method == "POST":
        # Extract form data from the request
        staff_id = request.POST.get('staff_id')
        license_number = request.POST.get('license_number')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number', '') 
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        # Check if the passwords match
        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return redirect('cis_registration')

        # Check if a CIS user is already assigned to the district
        if User.objects.filter(role='cis', district=district).exists():
            messages.error(request, "A CIS user is already assigned to this district.")
            return redirect('cis_registration')
        
        # Create the new CIS user
        user = User.objects.create_user(
            staff_id=staff_id,
            license_number=license_number,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            password=password1,  
            role='cis',  
            district=district,  
        )
        
        # Assign the newly created user as the CIS user for the district
        district.cis = user
        district.save()

        # Success message for CIS user registration
        messages.success(request, "CIS user registered successfully.")
        return redirect('dashboards:cis_registration')  

    # Handle GET request - rendering the registration form
    return render(request, 'dashboards/cis_registration.html', {'district': district})


#------------ CIS DASHBOARD -----------------------

@login_required
def cis_dashboard(request):
    # Ensure the user is a CIS (Circuit Information System) user and is assigned to a district
    user = request.user
    if user.role != "cis" or not user.district:
        return redirect("homepage")

    # Get the district and associated schools
    district = user.district
    schools_in_district = School.objects.filter(district=district)

    # Load filter options for academic years and terms from the shared helper
    filter_options = json.loads(get_available_terms(request).content)
    available_years = [year["name"] for year in filter_options.get("academic_years", [])]
    available_terms = [term["name"] for term in filter_options.get("terms", [])]

    # Get selected academic year and term from the request
    academic_year = request.GET.get("academic_year", "").strip()
    term = request.GET.get("term", "").strip()

    # Validate and select the academic year and term
    selected_year = academic_year if academic_year in available_years else filter_options.get("selected_academic_year")
    selected_term = term if term in available_terms else filter_options.get("selected_term", "Term 1")

    # If no valid academic year or term, show an error message
    if not selected_year or not selected_term:
        return render(request, "dashboards/cis_dashboard.html", {
            "error": "No academic data available.",
            "academic_years": available_years,
            "terms": available_terms,
        })

    # Get relevant marks for students in the selected district, academic year, and term
    marks_qs = StudentMark.objects.filter(
        student__school__in=schools_in_district,
        academic_year=selected_year,
        term=selected_term,
        subject__results__status="Submitted"
    ).select_related("student__school", "subject")

    # De-duplicate marks by student-subject pair to avoid over-counting
    seen = set()
    cleaned_marks = []
    for m in marks_qs:
        key = (m.student.id, m.subject.id)
        if key not in seen:
            seen.add(key)
            cleaned_marks.append({
                "student_id": m.student.id,
                "school_name": m.student.school.name,
                "subject_name": m.subject.name,
                "mark": m.mark
            })

    # === Stats ===
    total_schools = schools_in_district.count()  # Total number of schools in the district
    total_teachers = sum(
        school.staff_members.filter(role__in=["teacher", "headteacher"]).count()
        for school in schools_in_district
    )  # Total number of teachers in the district
    total_students_assessed = len(set(entry["student_id"] for entry in cleaned_marks))  
    total_district_average = round(mean([entry["mark"] for entry in cleaned_marks]), 2) if cleaned_marks else 0  

    # === Grouped Averages ===
    school_marks = defaultdict(list)
    subject_marks = defaultdict(list)

    for entry in cleaned_marks:
        school_marks[entry["school_name"]].append(entry["mark"])  # Group marks by school
        subject_marks[entry["subject_name"]].append(entry["mark"])  # Group marks by subject

    # Best and worst performing schools based on average score
    best_performing_schools = sorted([
        {"school": school, "average_score": round(mean(marks), 2)}
        for school, marks in school_marks.items()
    ], key=lambda x: x["average_score"], reverse=True)[:5]

    weakest_performing_schools = sorted([
        {"school": school, "average_score": round(mean(marks), 2)}
        for school, marks in school_marks.items()
    ], key=lambda x: x["average_score"])[:5]

    # Best and worst performing subjects based on average score
    best_performing_subjects = sorted([
        {"subject": subject, "average_score": round(mean(marks), 2)}
        for subject, marks in subject_marks.items()
    ], key=lambda x: x["average_score"], reverse=True)[:5]

    weakest_performing_subjects = sorted([
        {"subject": subject, "average_score": round(mean(marks), 2)}
        for subject, marks in subject_marks.items()
    ], key=lambda x: x["average_score"])[:5]

    # Performance trend data across schools
    trend_data = [
        {"school": school, "score": round(mean(marks), 2)}
        for school, marks in school_marks.items()
    ]

    # Fetch headteacher results submissions for the selected academic year and term
    headteacher_results = Result.objects.filter(
        school__in=schools_in_district,
        academic_year=selected_year,
        term=selected_term,
        status="Submitted"
    )

    # Prepare formatted notifications for result submissions
    notifications = headteacher_results.values(
        "school__name", "school__headteacher__first_name", "school__headteacher__last_name",
        "term", "academic_year", "class_group__name", "subject__name"
    ).distinct().order_by("-academic_year", "-term")[:10]

    formatted_notifications = [
        f"{entry['school__headteacher__first_name']} {entry['school__headteacher__last_name']} submitted {entry['class_group__name']} {entry['subject__name']} results for {entry['school__name']} ({entry['term']} {entry['academic_year']})"
        for entry in notifications
        if entry["school__headteacher__first_name"] and entry["school__headteacher__last_name"]
    ]

    # Handle AJAX requests and return data as JSON
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "total_schools": total_schools,
            "total_teachers": total_teachers,
            "total_students_assessed": total_students_assessed,
            "total_district_average": total_district_average,
            "best_performing_schools": best_performing_schools,
            "weakest_performing_schools": weakest_performing_schools,
            "best_performing_subjects": best_performing_subjects,
            "weakest_performing_subjects": weakest_performing_subjects,
            "performance_trends": trend_data,
            "notifications": formatted_notifications,
        })

    # Return the rendered dashboard template with data
    return render(request, "dashboards/cis_dashboard.html", {
        "academic_years": available_years,
        "terms": available_terms,
        "selected_year": selected_year,
        "selected_term": selected_term,
        "total_schools": total_schools,
        "total_teachers": total_teachers,
        "total_students_assessed": total_students_assessed,
        "total_district_average": total_district_average,
        "best_performing_schools": best_performing_schools,
        "weakest_performing_schools": weakest_performing_schools,
        "best_performing_subjects": best_performing_subjects,
        "weakest_performing_subjects": weakest_performing_subjects,
        "performance_trends": trend_data,
        "notifications": formatted_notifications,
    })



#------------ SISO DASHBOARD -----------------------

@login_required
def siso_dashboard(request):
    # Ensure the user is a SISO and has a circuit assigned
    user = request.user
    if user.role != "siso" or not user.circuit:
        return redirect("homepage")

    # Get the circuit and associated schools
    circuit = user.circuit
    schools_in_circuit = School.objects.filter(circuit=circuit)

    # Load filter options for academic years and terms from the shared helper
    filter_options = json.loads(get_available_terms(request).content)
    available_years = [year["name"] for year in filter_options.get("academic_years", [])]
    available_terms = [term["name"] for term in filter_options.get("terms", [])]

    # Get selected academic year and term from the request
    academic_year = request.GET.get("academic_year", "").strip()
    term = request.GET.get("term", "").strip()

    # Validate and select the academic year and term
    selected_year = academic_year if academic_year in available_years else filter_options.get("selected_academic_year")
    selected_term = term if term in available_terms else filter_options.get("selected_term", "Term 1")

    # If no valid academic year or term, show an error message
    if not selected_year or not selected_term:
        return render(request, "dashboards/siso_dashboard.html", {
            "error": "No academic data available.",
            "academic_years": available_years,
            "terms": available_terms,
        })

    # Get relevant marks for students in the selected circuit, academic year, and term
    marks_qs = StudentMark.objects.filter(
        student__school__in=schools_in_circuit,
        academic_year=selected_year,
        term=selected_term,
        subject__results__status="Submitted"
    ).select_related("student__school", "subject")

    # De-duplicate marks by student-subject pair
    seen = set()
    cleaned_marks = []
    for m in marks_qs:
        key = (m.student.id, m.subject.id)
        if key not in seen:
            seen.add(key)
            cleaned_marks.append({
                "student_id": m.student.id,
                "school_name": m.student.school.name,
                "subject_name": m.subject.name,
                "mark": m.mark
            })

    # Dashboard stats
    total_schools = schools_in_circuit.count()
    total_teachers = sum(
        school.staff_members.filter(role__in=["teacher", "headteacher"]).count()
        for school in schools_in_circuit
    )
    total_students_assessed = len(set(entry["student_id"] for entry in cleaned_marks))
    total_circuit_average = round(mean([entry["mark"] for entry in cleaned_marks]), 2) if cleaned_marks else 0

    # Group marks by school and subject
    school_marks = defaultdict(list)
    subject_marks = defaultdict(list)

    for entry in cleaned_marks:
        school_marks[entry["school_name"]].append(entry["mark"])
        subject_marks[entry["subject_name"]].append(entry["mark"])

    # Get best and worst performing schools
    best_performing_schools = sorted([
        {"school": school, "average_score": round(mean(marks), 2)}
        for school, marks in school_marks.items()
    ], key=lambda x: x["average_score"], reverse=True)[:5]

    weakest_performing_schools = sorted([
        {"school": school, "average_score": round(mean(marks), 2)}
        for school, marks in school_marks.items()
    ], key=lambda x: x["average_score"])[:5]

    # Get best and worst performing subjects
    best_performing_subjects = sorted([
        {"subject": subject, "average_score": round(mean(marks), 2)}
        for subject, marks in subject_marks.items()
    ], key=lambda x: x["average_score"], reverse=True)[:5]

    weakest_performing_subjects = sorted([
        {"subject": subject, "average_score": round(mean(marks), 2)}
        for subject, marks in subject_marks.items()
    ], key=lambda x: x["average_score"])[:5]

    # Performance trend data across schools
    trend_data = [
        {"school": school, "score": round(mean(marks), 2)}
        for school, marks in school_marks.items()
    ]

    # Result submission notifications from headteachers
    headteacher_results = Result.objects.filter(
        school__in=schools_in_circuit,
        academic_year=selected_year,
        term=selected_term,
        status="Submitted"
    )

    # Prepare formatted notifications for result submissions
    notifications = headteacher_results.values(
        "school__name", "school__headteacher__first_name", "school__headteacher__last_name",
        "term", "academic_year", "class_group__name", "subject__name"
    ).distinct().order_by("-academic_year", "-term")[:10]

    formatted_notifications = [
        f"{entry['school__headteacher__first_name']} {entry['school__headteacher__last_name']} submitted {entry['class_group__name']} {entry['subject__name']} results for {entry['school__name']} ({entry['term']} {entry['academic_year']})"
        for entry in notifications
        if entry["school__headteacher__first_name"] and entry["school__headteacher__last_name"]
    ]

    # Get the result upload deadline for the district
    deadline_obj = ResultUploadDeadline.objects.filter(district=circuit.district).first()

    # Prepare deadline status based on remaining time
    if deadline_obj:
        deadline_date = deadline_obj.deadline_date
        time_remaining = deadline_date - timezone.now().date()

        notification_color = "danger" if time_remaining <= timedelta(days=14) else "info"

        deadline_status = {
            "status": notification_color,
            "message": f"Result upload deadline is {time_remaining.days} days away.",
            "deadline_date": deadline_date,
        }
    else:
        deadline_status = None
        time_remaining = None

    # Handle AJAX requests and return data as JSON
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "total_schools": total_schools,
            "total_teachers": total_teachers,
            "total_students_assessed": total_students_assessed,
            "total_circuit_average": total_circuit_average,
            "best_performing_schools": best_performing_schools,
            "weakest_performing_schools": weakest_performing_schools,
            "best_performing_subjects": best_performing_subjects,
            "weakest_performing_subjects": weakest_performing_subjects,
            "performance_trends": trend_data,
            "notifications": formatted_notifications,
            "deadline_status": deadline_status,
            "time_remaining": time_remaining.days if time_remaining else None,
        })

    # Return the rendered dashboard template with data
    return render(request, "dashboards/siso_dashboard.html", {
        "academic_years": available_years,
        "terms": available_terms,
        "selected_year": selected_year,
        "selected_term": selected_term,
        "total_schools": total_schools,
        "total_teachers": total_teachers,
        "total_students_assessed": total_students_assessed,
        "total_circuit_average": total_circuit_average,
        "best_performing_schools": best_performing_schools,
        "weakest_performing_schools": weakest_performing_schools,
        "best_performing_subjects": best_performing_subjects,
        "weakest_performing_subjects": weakest_performing_subjects,
        "performance_trends": trend_data,
        "notifications": formatted_notifications,
        "deadline_status": deadline_status,
    })


#--------------- HEADTEACHER DASHBOARD -----------------

@login_required
def headteacher_dashboard(request):
    # Get the currently logged-in user
    user = request.user

    # Ensure the user is attached to a school
    if not hasattr(user, 'school'):
        return redirect("homepage")

    school = user.school

    # Fetch available academic years and terms using a shared helper
    filter_options = json.loads(get_available_terms(request).content)
    available_years = [year["name"] for year in filter_options.get("academic_years", [])]
    available_terms = [term["name"] for term in filter_options.get("terms", [])]

    # Extract selected academic year and term from query params or use defaults
    academic_year = request.GET.get("academic_year")
    selected_year = academic_year if academic_year in available_years else filter_options.get("selected_academic_year")

    term = request.GET.get("term")
    selected_term = term if term in available_terms else filter_options.get("selected_term", "Term 1")

    # If no valid academic year or term is available, return an error
    if not selected_year or not selected_term:
        error_msg = "No academic data available."
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"error": error_msg})
        return render(request, "dashboards/headteacher_dashboard.html", {
            "error": error_msg,
            "available_years": available_years,
            "available_terms": available_terms,
        })

    # Query marks for students in the selected school, year, and term
    marks_qs = StudentMark.objects.select_related('student', 'subject', 'class_group') \
                                    .filter(student__school=school, academic_year=selected_year, term=selected_term)

    # Count distinct students with marks
    total_students_assessed = marks_qs.values("student").distinct().count()

    # Calculate average school-wide mark
    total_school_average = marks_qs.aggregate(avg=Avg("mark"))["avg"] or 0

    # Count total teachers in the school
    total_teachers = school.teachers.count()

    # Get top 2 best-performing subjects based on average mark
    best_performing_subjects = list(
        marks_qs.values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:2]
    )

    # Get bottom 2 subjects by average mark
    weakest_performing_subjects = list(
        marks_qs.values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("avg_mark")[:2]
    )

    # Top 3 classes with highest average mark
    best_performing_classes = list(
        marks_qs.values("class_group__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:3]
    )

    # Prepare performance trends per class
    class_performance_trends = (
        marks_qs.values("class_group__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("class_group__name")
    )

    # Convert class trend data to JSON-friendly format
    trend_data = [
        {"class_name": entry["class_group__name"], "score": float(entry["avg_mark"])}
        for entry in class_performance_trends
    ]

    # Get recent result uploads by teachers for notification display
    upload_entries = (
        Result.objects
        .filter(
            school=school,
            academic_year=selected_year,
            term=selected_term
        )
        .values(
            "teacher__first_name",
            "teacher__last_name",
            "subject__name",
            "class_group__name",
            "term",
            "academic_year"
        )
        .distinct()
        .order_by("-academic_year", "-term")[:10]
    )

    # Format upload entries into human-readable notification strings
    notifications = [
        f"{entry['teacher__first_name']} {entry['teacher__last_name']} uploaded {entry['subject__name']} for {entry['class_group__name']} ({entry['term']} {entry['academic_year']})"
        for entry in upload_entries
        if entry["teacher__first_name"] and entry["teacher__last_name"]
    ]

    # Get deadline for result uploads for the school's district
    deadline_obj = ResultUploadDeadline.objects.filter(district=school.district).first()

    # If deadline exists, prepare a status message and color code based on urgency
    if deadline_obj:
        deadline_date = deadline_obj.deadline_date
        time_remaining = deadline_date - timezone.now().date()

        if time_remaining <= timedelta(days=14):
            notification_color = "danger"  # Red: urgent deadline
        else:
            notification_color = "info"  # Blue: not urgent

        deadline_status = {
            "status": notification_color,
            "message": f"Result upload deadline is {time_remaining.days} days away.",
            "deadline_date": deadline_date,
        }
    else:
        deadline_status = None

    # If the request is AJAX, return a JSON response
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "total_students_assessed": total_students_assessed,
            "total_school_average": round(total_school_average, 2),
            "total_teachers": total_teachers,
            "best_performing_subjects": [
                {"subject": s["subject__name"], "average_score": float(s["avg_mark"])} for s in best_performing_subjects
            ],
            "worst_performing_subjects": [
                {"subject": s["subject__name"], "average_score": float(s["avg_mark"])} for s in weakest_performing_subjects
            ],
            "best_performing_classes": [
                {"class_name": c["class_group__name"], "average_score": float(c["avg_mark"])} for c in best_performing_classes
            ],
            "performance_trends": trend_data,
            "notifications": notifications,
            "deadline_status": deadline_status,
            "time_remaining": time_remaining.days if deadline_obj else None
        })

    # Otherwise, render the full dashboard page with all the computed data
    return render(request, "dashboards/headteacher_dashboard.html", {
        "academic_years": available_years,
        "terms": available_terms,
        "selected_year": selected_year,
        "selected_term": selected_term,
        "total_students_assessed": total_students_assessed,
        "total_school_average": round(total_school_average, 2),
        "total_teachers": total_teachers,
        "best_performing_subjects": best_performing_subjects,
        "weakest_performing_subjects": weakest_performing_subjects,
        "best_performing_classes": best_performing_classes,
        "performance_trends": trend_data,
        "notifications": notifications,
        "deadline_status": deadline_status,
    })

#------------ TEACHER DASHBOARDS -----------------------
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
def class_teacher_dashboard(request):
    # Get the current user and check if they have a teacher profile
    user = request.user
    teacher = getattr(user, 'teacher_profile', None)

    # If the user is not a teacher, redirect to the homepage
    if not teacher:
        return redirect('homepage')

    # Try to retrieve the class assignment for the teacher
    try:
        class_teacher = ClassTeacher.objects.get(teacher=teacher)
    except ClassTeacher.DoesNotExist:
        # If no class assignment exists, redirect to the homepage
        return redirect('homepage')

    # Get the class that the teacher is assigned to
    assigned_class = class_teacher.assigned_class

    # Load filter options for academic years and terms from the shared helper
    filter_options = json.loads(get_available_terms(request).content)
    all_years = [year["name"] for year in filter_options.get("academic_years", [])]
    all_terms = [term["name"] for term in filter_options.get("terms", [])]

    # Get selected filters for academic year and term, with fallbacks
    academic_year = request.GET.get("academic_year")
    selected_year = academic_year if academic_year in all_years else filter_options.get("selected_academic_year")

    term = request.GET.get("term")
    selected_term = term if term in all_terms else filter_options.get("selected_term", "Term 1")

    # Base query for retrieving student marks
    student_marks = StudentMark.objects.filter(class_group=assigned_class)

    # Filter student marks by selected academic year, if provided
    if selected_year:
        student_marks = student_marks.filter(academic_year=selected_year)
    
    # Filter student marks by selected term, if provided
    if selected_term:
        student_marks = student_marks.filter(term=selected_term)

    # Calculate average class performance
    average_class_performance = student_marks.aggregate(avg_mark=Avg("mark"))["avg_mark"]
    average_class_performance = average_class_performance or 0

    # Get the top 3 students with the highest marks
    best_students = (
        student_marks.values("student__last_name", "student__first_name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:3]
    )

    # Get the top 3 students with the lowest marks
    weakest_students = (
        student_marks.values("student__last_name", "student__first_name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("avg_mark")[:3]
    )

    # Get the top 3 subjects with the highest average marks
    top_subjects = (
        student_marks.values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:3]
    )

    # Get the bottom 3 subjects with the lowest average marks
    lowest_subjects = (
        student_marks.values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("avg_mark")[:3]
    )

    # Get the performance trends for each subject
    performance_trends = (
        student_marks
        .values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("subject__name")
    )

    # Convert any Decimal marks to float for consistency in the response
    for trend in performance_trends:
        if isinstance(trend.get("avg_mark"), Decimal):
            trend["avg_mark"] = float(trend["avg_mark"])

    # Get the current result upload deadline for the teacher's school district
    deadline_obj = ResultUploadDeadline.objects.filter(district=teacher.school.district).first()

    # Prepare deadline status with color-coding based on remaining time
    if deadline_obj:
        deadline_date = deadline_obj.deadline_date
        time_remaining = deadline_date - timezone.now().date()

        # Set color for the deadline status based on remaining days
        if time_remaining <= timedelta(days=14):
            notification_color = "danger"  # Urgent deadline (Red)
        else:
            notification_color = "info"  # Non-urgent (Blue/Teal)

        deadline_status = {
            "status": notification_color,
            "message": f"Result upload deadline is {time_remaining.days} days away.",
            "deadline_date": deadline_date,
        }
    else:
        deadline_status = None

    # If the request was made with AJAX, return a JsonResponse
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "total_students_assessed": student_marks.values("student").distinct().count(),
            "average_class_performance": round(average_class_performance, 2),
            "best_students": [
                {
                    "name": f"{s['student__last_name']} {s['student__first_name']}",
                    "mark": round(s["avg_mark"], 2) if s["avg_mark"] is not None else None
                } for s in best_students
            ],
            "weakest_students": [
                {
                    "name": f"{s['student__last_name']} {s['student__first_name']}",
                    "mark": round(s["avg_mark"], 2) if s["avg_mark"] is not None else None
                } for s in weakest_students
            ],
            "top_performing_subject": {
                "subject__name": top_subjects[0]["subject__name"],
                "avg_mark": round(top_subjects[0]["avg_mark"], 2)
            } if top_subjects else None,
            "bottom_performing_subject": {
                "subject__name": lowest_subjects[0]["subject__name"],
                "avg_mark": round(lowest_subjects[0]["avg_mark"], 2)
            } if lowest_subjects else None,
            "performance_trends": list(performance_trends),
            "deadline_status": deadline_status,
            "time_remaining": time_remaining.days if deadline_obj else None
        })

    # Return the rendered dashboard with necessary data
    return render(request, "dashboards/class_teacher_dashboard.html", {
        "assigned_class": assigned_class,
        "academic_years": all_years,
        "terms": all_terms,
        "selected_year": selected_year,
        "selected_term": selected_term,
        "deadline_status": deadline_status,
    })




from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.db.models import Avg
import json

@login_required
def subject_teacher_dashboard(request):
    # Get the current user and check if they have a teacher profile
    user = request.user
    teacher = getattr(user, 'teacher_profile', None)

    # If the user is not a subject teacher, redirect to the homepage
    if not teacher:
        return redirect('homepage')

    # Get the subjects and classes assigned to the teacher
    subject_teachers = SubjectTeacher.objects.filter(teacher=teacher)
    assigned_subjects = [st.subject for st in subject_teachers]
    assigned_classes = set(class_obj for st in subject_teachers for class_obj in st.assigned_classes.all())

    # Load filter options for academic years and terms from the shared helper
    filter_options = json.loads(get_available_terms(request).content)

    # Get selected filters from the request
    subject_id = request.GET.get("subject_id")
    class_id = request.GET.get("class_id")
    academic_year = request.GET.get("academic_year")
    term = request.GET.get("term")

    # Validate and select the academic year
    valid_years = [year["name"] for year in filter_options["academic_years"]]
    academic_year = academic_year if academic_year in valid_years else filter_options["selected_academic_year"]

    # Validate and select the term
    all_terms = [t["name"] for t in filter_options["terms"]]
    selected_term = term if term in all_terms else "Term 1"

    # Filter StudentMark data based on assigned subjects and classes
    student_marks = StudentMark.objects.filter(
        subject__in=assigned_subjects,
        class_group__in=assigned_classes
    )

    # Apply further filtering based on the selected filters
    if subject_id:
        student_marks = student_marks.filter(subject_id=subject_id)
    if class_id:
        student_marks = student_marks.filter(class_group_id=class_id)
    if academic_year:
        student_marks = student_marks.filter(academic_year=academic_year)
    if term:
        student_marks = student_marks.filter(term=term)

    # Get the total number of students assessed and average class performance
    total_students_assessed = student_marks.count()
    average_class_performance = round(student_marks.aggregate(avg_mark=Avg("mark"))["avg_mark"] or 0, 2)

    # Get the best and weakest students based on average marks
    best_students = (
        student_marks.values("student__last_name", "student__first_name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:3]
    )
    weakest_students = (
        student_marks.values("student__last_name", "student__first_name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("avg_mark")[:3]
    )

    # Calculate performance distribution across score buckets
    score_buckets = {
        "80-100": 0,
        "55-79": 0,
        "50-54": 0,
        "40-49": 0,
        "0-39": 0
    }

    # Assign student marks to their corresponding score buckets
    for mark in student_marks.values_list("mark", flat=True):
        if mark >= 80:
            score_buckets["80-100"] += 1
        elif 55 <= mark <= 79:
            score_buckets["55-79"] += 1
        elif 50 <= mark <= 54:
            score_buckets["50-54"] += 1
        elif 40 <= mark <= 49:
            score_buckets["40-49"] += 1
        else:
            score_buckets["0-39"] += 1

    # Get the current result upload deadline for the teacher's school district
    deadline_obj = ResultUploadDeadline.objects.filter(district=teacher.school.district).first()

    # Prepare the deadline status based on the remaining time
    if deadline_obj:
        deadline_date = deadline_obj.deadline_date
        time_remaining = deadline_date - timezone.now().date()

        # Set notification color based on urgency (less than 14 days remaining is urgent)
        if time_remaining <= timedelta(days=14):
            notification_color = "danger"  # Urgent deadline (Red)
        else:
            notification_color = "info"  # Non-urgent (Blue/Teal)

        deadline_status = {
            "status": notification_color,
            "message": f"Result upload deadline is {time_remaining.days} days away.",
            "deadline_date": deadline_date,
        }
    else:
        deadline_status = None
        time_remaining = None

    # If the request is an AJAX request, return the data as a JSON response
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "total_students_assessed": total_students_assessed,
            "average_class_performance": average_class_performance,
            "best_students": [
                {
                    "name": f"{s['student__first_name']} {s['student__last_name']}",
                    "mark": round(s["avg_mark"], 2)
                } for s in best_students
            ],
            "weakest_students": [
                {
                    "name": f"{s['student__first_name']} {s['student__last_name']}",
                    "mark": round(s["avg_mark"], 2)
                } for s in weakest_students
            ],
            "performance_distribution": score_buckets,
            "deadline_status": deadline_status,
            "time_remaining": time_remaining.days if deadline_obj else None
        })

    # Return the rendered dashboard page with the appropriate data
    return render(request, "dashboards/subject_teacher_dashboard.html", {
        "assigned_subjects": assigned_subjects,
        "assigned_classes": assigned_classes,
        "selected_subject": subject_id,
        "selected_class": class_id,
        "terms": all_terms,
        "academic_years": valid_years,
        "selected_year": academic_year,
        "selected_term": selected_term,
        "deadline_status": deadline_status,
    })


@login_required
def teacher_dashboard(request):
    return render(request, 'dashboards/teacher_dashboard.html')

