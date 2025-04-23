
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


User = get_user_model()

#------------ ADMIN DASHBOARD -----------------------

@login_required
def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')

def cis_registration(request):
    if not request.user.is_authenticated or request.user.role != 'admin':
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    admin_user = request.user
    district = admin_user.district

    # Handling form submission
    if request.method == "POST":
        staff_id = request.POST.get('staff_id')
        license_number = request.POST.get('license_number')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number', '')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        # Check if passwords match
        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return redirect('cis_registration')

        # Check if CIS is already assigned to the district
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
            role='cis',  # fixed to 'cis'
            district=district,
        )
        
        # assign the user
        district.cis = user
        district.save()


        # Successful creation message
        messages.success(request, "CIS user registered successfully.")
        return redirect('dashboards:cis_registration')  # Redirect to your desired page

    # Rendering the registration form (GET request)
    return render(request, 'dashboards/cis_registration.html', {'district': district})


#------------ CIS DASHBOARD -----------------------

@login_required
def cis_dashboard(request):
    user = request.user

    # Ensure only CIS users can access
    if user.role != "cis" or not user.district:
        return redirect("homepage")

    district = user.district
    schools_in_district = School.objects.filter(district=district)

    # Get available academic years and terms
    filter_options = json.loads(get_available_terms(request).content)
    available_years = [year["name"] for year in filter_options.get("academic_years", [])]
    available_terms = [term["name"] for term in filter_options.get("terms", [])]

    # Ensure correct academic year and term are extracted
    academic_year = request.GET.get("academic_year", "").strip()
    term = request.GET.get("term", "").strip()

    # Ensure selected values are valid, else use defaults
    selected_year = academic_year if academic_year in available_years else filter_options.get("selected_academic_year")
    selected_term = term if term in available_terms else filter_options.get("selected_term", "Term 1")

    if not selected_year or not selected_term:
        return render(request, "dashboards/cis_dashboard.html", {
            "error": "No academic data available.",
            "academic_years": available_years,
            "terms": available_terms,
        })

    # Apply filters correctly in queries for marks
    marks_qs = StudentMark.objects.filter(
        student__school__in=schools_in_district,  # Filter by schools in the district
        academic_year=selected_year,  # Filter by academic year
        term=selected_term,  # Filter by term
        subject__results__status="Submitted"  # Only include submitted results
    ).distinct()

    # Dashboard Stats
    total_schools = schools_in_district.count()
    total_teachers = sum(
        school.staff_members.filter(role__in=["teacher", "headteacher"]).count()
        for school in schools_in_district
    )
    total_students_assessed = marks_qs.values('student').distinct().count()
    total_district_average = marks_qs.aggregate(avg=Avg("mark"))["avg"] or 0

    # Best and weakest performing schools
    best_performing_schools = list(
        marks_qs.values("student__school__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:5]
    )
    for school in best_performing_schools:
        school["school"] = school.pop("student__school__name")
        school["average_score"] = round(school.pop("avg_mark"), 2)

    weakest_performing_schools = list(
        marks_qs.values("student__school__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("avg_mark")[:5]
    )
    for school in weakest_performing_schools:
        school["school"] = school.pop("student__school__name")
        school["average_score"] = round(school.pop("avg_mark"), 2)

    # Best and weakest performing subjects
    best_performing_subjects = list(
        marks_qs.values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:5]
    )
    for subject in best_performing_subjects:
        subject["subject"] = subject.pop("subject__name")
        subject["average_score"] = round(subject.pop("avg_mark"), 2)

    weakest_performing_subjects = list(
        marks_qs.values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("avg_mark")[:5]
    )
    for subject in weakest_performing_subjects:
        subject["subject"] = subject.pop("subject__name")
        subject["average_score"] = round(subject.pop("avg_mark"), 2)

    # Performance Trends Data
    district_performance_trends = (
        marks_qs.values("student__school__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("student__school__name")
    )
    trend_data = [
        {"school": entry["student__school__name"], "score": round(entry["avg_mark"], 2)}
        for entry in district_performance_trends
    ]

    # Filtered Notifications
    headteacher_results = Result.objects.filter(
        school__in=schools_in_district,
        academic_year=selected_year,
        term=selected_term,
        status="Submitted"
    )

    notifications = (
        headteacher_results
        .values("school__name", "school__headteacher__first_name", "school__headteacher__last_name", "term", "academic_year", "class_group__name", "subject__name")
        .distinct()
        .order_by("-academic_year", "-term")[:10]
    )

    formatted_notifications = [
        f"{entry['school__headteacher__first_name']} {entry['school__headteacher__last_name']} submitted {entry['class_group__name']} {entry['subject__name']} results for {entry['school__name']} ({entry['term']} {entry['academic_year']})"
        for entry in notifications
        if entry["school__headteacher__first_name"] and entry["school__headteacher__last_name"]
    ]

    # Handle AJAX request correctly
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "total_schools": total_schools,
            "total_teachers": total_teachers,
            "total_students_assessed": total_students_assessed,
            "total_district_average": round(total_district_average, 2),
            "best_performing_schools": best_performing_schools,
            "weakest_performing_schools": weakest_performing_schools,
            "best_performing_subjects": best_performing_subjects,
            "weakest_performing_subjects": weakest_performing_subjects,
            "performance_trends": trend_data,
            "notifications": formatted_notifications,
        })

    # Pass selected filters back to the template
    return render(request, "dashboards/cis_dashboard.html", {
        "academic_years": available_years,
        "terms": available_terms,
        "selected_year": selected_year,
        "selected_term": selected_term,
        "total_schools": total_schools,
        "total_teachers": total_teachers,
        "total_students_assessed": total_students_assessed,
        "total_district_average": round(total_district_average, 2),
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
    user = request.user

    # Ensure only SISO users can access
    if user.role != "siso" or not user.circuit:
        return redirect("homepage")

    circuit = user.circuit
    schools_in_circuit = School.objects.filter(circuit=circuit)

    # Get available academic years and terms
    filter_options = json.loads(get_available_terms(request).content)
    available_years = [year["name"] for year in filter_options.get("academic_years", [])]
    available_terms = [term["name"] for term in filter_options.get("terms", [])]

    # Ensure correct academic year and term are extracted
    academic_year = request.GET.get("academic_year", "").strip()
    term = request.GET.get("term", "").strip()

    # Ensure selected values are valid, else use defaults
    selected_year = academic_year if academic_year in available_years else filter_options.get("selected_academic_year")
    selected_term = term if term in available_terms else filter_options.get("selected_term", "Term 1")

    if not selected_year or not selected_term:
        return render(request, "dashboards/siso_dashboard.html", {
            "error": "No academic data available.",
            "academic_years": available_years,
            "terms": available_terms,
        })

    # Apply filters correctly in queries for marks
    marks_qs = StudentMark.objects.filter(
        student__school__in=schools_in_circuit,  # Filter by schools in the circuit
        academic_year=selected_year,  # Filter by academic year
        term=selected_term,  # Filter by term
        subject__results__status="Submitted"  # Only include submitted results
    ).distinct()

    # Dashboard Stats
    total_schools = schools_in_circuit.count()
    total_teachers = sum(
        school.staff_members.filter(role__in=["teacher", "headteacher"]).count()
        for school in schools_in_circuit
    )
    total_students_assessed = marks_qs.values('student').distinct().count()
    total_circuit_average = marks_qs.aggregate(avg=Avg("mark"))["avg"] or 0

    # Best and weakest performing schools
    best_performing_schools = list(
        marks_qs.values("student__school__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:2]
    )
    for school in best_performing_schools:
        school["school"] = school.pop("student__school__name")
        school["average_score"] = round(school.pop("avg_mark"), 2)

    weakest_performing_schools = list(
        marks_qs.values("student__school__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("avg_mark")[:2]
    )
    for school in weakest_performing_schools:
        school["school"] = school.pop("student__school__name")
        school["average_score"] = round(school.pop("avg_mark"), 2)

    # Best and weakest performing subjects
    best_performing_subjects = list(
        marks_qs.values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:3]
    )
    for subject in best_performing_subjects:
        subject["subject"] = subject.pop("subject__name")
        subject["average_score"] = round(subject.pop("avg_mark"), 2)

    weakest_performing_subjects = list(
        marks_qs.values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("avg_mark")[:3]
    )
    for subject in weakest_performing_subjects:
        subject["subject"] = subject.pop("subject__name")
        subject["average_score"] = round(subject.pop("avg_mark"), 2)

    # Performance Trends Data
    circuit_performance_trends = (
        marks_qs.values("student__school__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("student__school__name")
    )
    trend_data = [
        {"school": entry["student__school__name"], "score": round(entry["avg_mark"], 2)}
        for entry in circuit_performance_trends
    ]

    # Filtered Notifications
    headteacher_results = Result.objects.filter(
        school__in=schools_in_circuit,
        academic_year=selected_year,
        term=selected_term,
        status="Submitted"
    )

    notifications = (
        headteacher_results
        .values("school__name", "school__headteacher__first_name", "school__headteacher__last_name", "term", "academic_year", "class_group__name", "subject__name")
        .distinct()
        .order_by("-academic_year", "-term")[:10]
    )

    formatted_notifications = [
        f"{entry['school__headteacher__first_name']} {entry['school__headteacher__last_name']} submitted {entry['class_group__name']} {entry['subject__name']} results for {entry['school__name']} ({entry['term']} {entry['academic_year']})"
        for entry in notifications
        if entry["school__headteacher__first_name"] and entry["school__headteacher__last_name"]
    ]

    
    # 🎯 Get the current result upload deadline for the school district
    deadline_obj = ResultUploadDeadline.objects.filter(district=circuit.district).first()

    # Prepare deadline status
    if deadline_obj:
        deadline_date = deadline_obj.deadline_date
        time_remaining = deadline_date - timezone.now().date()

        # Set color based on the remaining time
        if time_remaining <= timedelta(days=14):
            notification_color = "danger"  # Red background for urgent deadlines
        else:
            notification_color = "info"  # Teal/Blue for other cases

        deadline_status = {
            "status": notification_color,
            "message": f"Result upload deadline is {time_remaining.days} days away.",
            "deadline_date": deadline_date,
        }
    else:
        deadline_status = None

    # Handle AJAX request correctly
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "total_schools": total_schools,
            "total_teachers": total_teachers,
            "total_students_assessed": total_students_assessed,
            "total_circuit_average": round(total_circuit_average, 2),
            "best_performing_schools": best_performing_schools,
            "weakest_performing_schools": weakest_performing_schools,
            "best_performing_subjects": best_performing_subjects,
            "weakest_performing_subjects": weakest_performing_subjects,
            "performance_trends": trend_data,
            "notifications": formatted_notifications,
            "deadline_status": deadline_status,
            "time_remaining": time_remaining.days if deadline_obj else None
        })

    # Pass selected filters back to the template
    return render(request, "dashboards/siso_dashboard.html", {
        "academic_years": available_years,
        "terms": available_terms,
        "selected_year": selected_year,
        "selected_term": selected_term,
        "total_schools": total_schools,
        "total_teachers": total_teachers,
        "total_students_assessed": total_students_assessed,
        "total_circuit_average": round(total_circuit_average, 2),
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
    user = request.user
    if not hasattr(user, 'school'):
        return redirect("homepage")

    school = user.school

    # 🎯 Use shared helper for filter options
    filter_options = json.loads(get_available_terms(request).content)
    available_years = [year["name"] for year in filter_options.get("academic_years", [])]
    available_terms = [term["name"] for term in filter_options.get("terms", [])]

    # 🎯 Extract selected year/term with fallback
    academic_year = request.GET.get("academic_year")
    selected_year = academic_year if academic_year in available_years else filter_options.get("selected_academic_year")

    term = request.GET.get("term")
    selected_term = term if term in available_terms else filter_options.get("selected_term", "Term 1")

    if not selected_year or not selected_term:
        error_msg = "No academic data available."
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"error": error_msg})
        return render(request, "dashboards/headteacher_dashboard.html", {
            "error": error_msg,
            "available_years": available_years,
            "available_terms": available_terms,
        })

    # 🎯 Filter marks school-wide by selected filters
    marks_qs = StudentMark.objects.select_related('student', 'subject', 'class_group') \
                                    .filter(student__school=school, academic_year=selected_year, term=selected_term)

    total_students_assessed = marks_qs.values("student").distinct().count()
    total_school_average = marks_qs.aggregate(avg=Avg("mark"))["avg"] or 0
    total_teachers = school.teachers.count()

    best_performing_subjects = list(
        marks_qs.values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:2]
    )

    weakest_performing_subjects = list(
        marks_qs.values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("avg_mark")[:2]
    )

    best_performing_classes = list(
        marks_qs.values("class_group__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:3]
    )

    class_performance_trends = (
        marks_qs.values("class_group__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("class_group__name")
    )

    trend_data = [
        {"class_name": entry["class_group__name"], "score": float(entry["avg_mark"])}
        for entry in class_performance_trends
    ]

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

    notifications = [
        f"{entry['teacher__first_name']} {entry['teacher__last_name']} uploaded {entry['subject__name']} for {entry['class_group__name']} ({entry['term']} {entry['academic_year']})"
        for entry in upload_entries
        if entry["teacher__first_name"] and entry["teacher__last_name"]
    ]


    # 🎯 Get the current result upload deadline for the school district
    deadline_obj = ResultUploadDeadline.objects.filter(district=school.district).first()

    # Prepare deadline status
    if deadline_obj:
        deadline_date = deadline_obj.deadline_date
        time_remaining = deadline_date - timezone.now().date()

        # Set color based on the remaining time
        if time_remaining <= timedelta(days=14):
            notification_color = "danger"  # Red background for urgent deadlines
        else:
            notification_color = "info"  # Teal/Blue for other cases

        deadline_status = {
            "status": notification_color,
            "message": f"Result upload deadline is {time_remaining.days} days away.",
            "deadline_date": deadline_date,
        }
    else:
        deadline_status = None


    # Return AJAX response if requested
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
    user = request.user
    teacher = getattr(user, 'teacher_profile', None)

    if not teacher:
        return redirect('homepage')

    try:
        class_teacher = ClassTeacher.objects.get(teacher=teacher)
    except ClassTeacher.DoesNotExist:
        return redirect('homepage')

    assigned_class = class_teacher.assigned_class

    # Load filter options
    filter_options = json.loads(get_available_terms(request).content)
    all_years = [year["name"] for year in filter_options.get("academic_years", [])]
    all_terms = [term["name"] for term in filter_options.get("terms", [])]

    # Get selected filters with fallbacks
    academic_year = request.GET.get("academic_year")
    selected_year = academic_year if academic_year in all_years else filter_options.get("selected_academic_year")

    term = request.GET.get("term")
    selected_term = term if term in all_terms else filter_options.get("selected_term", "Term 1")

    # Query base
    student_marks = StudentMark.objects.filter(class_group=assigned_class)

    if selected_year:
        student_marks = student_marks.filter(academic_year=selected_year)
    if selected_term:
        student_marks = student_marks.filter(term=selected_term)

    average_class_performance = student_marks.aggregate(avg_mark=Avg("mark"))["avg_mark"]

    average_class_performance = average_class_performance or 0

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

    top_subjects = (
        student_marks.values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:3]
    )

    lowest_subjects = (
        student_marks.values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("avg_mark")[:3]
    )

    performance_trends = (
        student_marks
        .values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("subject__name")
    )

    # Before returning JsonResponse
    for trend in performance_trends:
        if isinstance(trend.get("avg_mark"), Decimal):
            trend["avg_mark"] = float(trend["avg_mark"])

    # 🎯 Get the current result upload deadline for the school district
    deadline_obj = ResultUploadDeadline.objects.filter(district=teacher.school.district).first()

    # Prepare deadline status
    if deadline_obj:
        deadline_date = deadline_obj.deadline_date
        time_remaining = deadline_date - timezone.now().date()

        # Set color based on the remaining time
        if time_remaining <= timedelta(days=14):
            notification_color = "danger"  # Red background for urgent deadlines
        else:
            notification_color = "info"  # Teal/Blue for other cases

        deadline_status = {
            "status": notification_color,
            "message": f"Result upload deadline is {time_remaining.days} days away.",
            "deadline_date": deadline_date,
        }
    else:
        deadline_status = None


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

    return render(request, "dashboards/class_teacher_dashboard.html", {
        "assigned_class": assigned_class,
        "academic_years": all_years,
        "terms": all_terms,
        "selected_year": selected_year,
        "selected_term": selected_term,
        "deadline_status": deadline_status,
    })



@login_required
def subject_teacher_dashboard(request):
    user = request.user
    teacher = getattr(user, 'teacher_profile', None)

    if not teacher:
        return redirect('homepage')  # Redirect if not a subject teacher

    # Get assigned subjects and classes
    subject_teachers = SubjectTeacher.objects.filter(teacher=teacher)
    assigned_subjects = [st.subject for st in subject_teachers]
    assigned_classes = set(class_obj for st in subject_teachers for class_obj in st.assigned_classes.all())

    # Get selected filters from request
    filter_options = json.loads(get_available_terms(request).content)
    subject_id = request.GET.get("subject_id")
    class_id = request.GET.get("class_id")
    academic_year = request.GET.get("academic_year")
    term = request.GET.get("term")

    valid_years = [year["name"] for year in filter_options["academic_years"]]
    academic_year = academic_year if academic_year in valid_years else filter_options["selected_academic_year"]

    all_terms = [t["name"] for t in filter_options["terms"]]
    selected_term = term if term in all_terms else "Term 1"

    # Filter StudentMark data
    student_marks = StudentMark.objects.filter(
        subject__in=assigned_subjects,
        class_group__in=assigned_classes
    )

    if subject_id:
        student_marks = student_marks.filter(subject_id=subject_id)
    if class_id:
        student_marks = student_marks.filter(class_group_id=class_id)
    if academic_year:
        student_marks = student_marks.filter(academic_year=academic_year)
    if term:
        student_marks = student_marks.filter(term=term)


    total_students_assessed = student_marks.count()
    average_class_performance = student_marks.aggregate(avg_mark=Avg("mark"))["avg_mark"] or 0

    # Best and weakest students
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

    # Performance distribution by score bucket
    score_buckets = {
        "80-100": 0,
        "55-79": 0,
        "50-54": 0,
        "40-49": 0,
        "0-39": 0
    }

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

        
    # 🎯 Get the current result upload deadline for the school district
    deadline_obj = ResultUploadDeadline.objects.filter(district=teacher.school.district).first()

    # Prepare deadline status
    if deadline_obj:
        deadline_date = deadline_obj.deadline_date
        time_remaining = deadline_date - timezone.now().date()

        # Set color based on the remaining time
        if time_remaining <= timedelta(days=14):
            notification_color = "danger"  # Red background for urgent deadlines
        else:
            notification_color = "info"  # Teal/Blue for other cases

        deadline_status = {
            "status": notification_color,
            "message": f"Result upload deadline is {time_remaining.days} days away.",
            "deadline_date": deadline_date,
        }
    else:
        deadline_status = None

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "total_students_assessed": total_students_assessed,
            "average_class_performance": round(average_class_performance, 2),
            "best_students": [{"name": f"{s['student__first_name']} {s['student__last_name']}", "mark": s["avg_mark"]} for s in best_students],
            "weakest_students": [{"name": f"{s['student__first_name']} {s['student__last_name']}", "mark": s["avg_mark"]} for s in weakest_students],
            "performance_distribution": score_buckets,
            "deadline_status": deadline_status,
            "time_remaining": time_remaining.days if deadline_obj else None
        })

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

