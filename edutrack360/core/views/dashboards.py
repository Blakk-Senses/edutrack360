
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.http import HttpResponse, JsonResponse
from core.models import (
    District, Teacher, PerformanceSummary, Profile, 
    School, SchoolSubmission, Circuit, StudentMark, Result, SubjectTeacher, 
    ClassTeacher, Subject, Student
)
import json
from decimal import Decimal
from django.db.models import Avg, Count, Max
from django.http import HttpResponse
from django.urls import reverse_lazy


User = get_user_model()

#------------ ADMIN DASHBOARD -----------------------

@login_required
def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')

#------------ CIS DASHBOARD -----------------------

@login_required(login_url=lambda: reverse_lazy('dashboards:cis_dashboard'))
def cis_dashboard(request):
    district = None  # Initialize district
    district_name = 'Unknown'

    # Check if the user has the role 'cis'
    if hasattr(request.user, 'assigned_district') and request.user.role == 'cis':
        # Get the district assigned to the user
        district = request.user.assigned_district
        district_name = district.name if district else "Unknown"

    # Total schools in the district
    total_schools = district.schools_in_districts.count() if district else 0

    # Total number of teachers and headteachers in the district
    total_teachers = User.objects.filter(
        school__district=district,  # Directly link to school and then district
        role__in=['teacher', 'headteacher']
    ).count() if district else 0

    # Aggregated district-level performance
    district_performance = (
        PerformanceSummary.objects.filter(district=district).aggregate(average_grade=Avg('average_score'))
        if district
        else {'average_grade': None}
    )

    # Performance data over years
    performance_data = (
        PerformanceSummary.objects.filter(district=district)
        .values('year')
        .annotate(average_grade=Avg('average_score'))
        if district
        else []
    )

    # Top-performing schools
    top_schools = (
        School.objects.filter(district=district)
        .annotate(performance_score=Avg('performance_summaries__average_score'))
        .order_by('-performance_score')[:10]
        if district
        else []
    )

    # Submission status counts
    if district:
        successful_submissions = SchoolSubmission.objects.filter(school__district=district, status='submitted').count()
        pending_submissions = SchoolSubmission.objects.filter(school__district=district, status='pending').count()
        not_submitted = SchoolSubmission.objects.filter(school__district=district, status='not_submitted').count()
    else:
        successful_submissions = pending_submissions = not_submitted = 0

    district_summary = {
        'submitted': successful_submissions,
        'pending': pending_submissions,
        'not_submitted': not_submitted,
    }

    pie_chart_data = {
        'labels': ['Submitted', 'Pending Approval', 'Not Submitted'],
        'data': [successful_submissions, pending_submissions, not_submitted],
        'colors': ['#28a745', '#fd7e14', '#dc3545'],
    }

    context = {
        'user': request.user,
        'district_name': district_name,
        'total_schools': total_schools,
        'total_teachers': total_teachers,
        'avg_district_performance': district_performance['average_grade'] or 'N/A',
        'performance_data': performance_data,
        'top_schools': [
            {
                'name': school.name,
                'performance_score': f"{school.performance_score:.2f}%" if school.performance_score else "N/A"
            } for school in top_schools
        ],
        'district_summary': district_summary,
        'pie_chart_data': pie_chart_data,
    }
    return render(request, 'dashboards/cis_dashboard.html', context)


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
    marks_qs = StudentMark.objects.filter(
        student__school=school,
        academic_year=selected_year,
        term=selected_term
    )

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

    result_uploads = (
        Result.objects.filter(
            school=school,
            academic_year=selected_year,
            term=selected_term
        )
        .select_related("teacher", "subject", "class_group")
        .order_by("-id")[:10]
    )

    notifications = [
        f"{upload.teacher.first_name} {upload.teacher.last_name} uploaded {upload.subject.name} for {upload.class_group.name}"
        for upload in result_uploads
    ]


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
        })

    return render(request, "dashboards/class_teacher_dashboard.html", {
        "assigned_class": assigned_class,
        "academic_years": all_years,
        "terms": all_terms,
        "selected_year": selected_year,
        "selected_term": selected_term,
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


    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "total_students_assessed": total_students_assessed,
            "average_class_performance": round(average_class_performance, 2),
            "best_students": [{"name": f"{s['student__first_name']} {s['student__last_name']}", "mark": s["avg_mark"]} for s in best_students],
            "weakest_students": [{"name": f"{s['student__first_name']} {s['student__last_name']}", "mark": s["avg_mark"]} for s in weakest_students],
            "performance_distribution": score_buckets,
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
    })




@login_required
def teacher_dashboard(request):
    return render(request, 'dashboards/teacher_dashboard.html')

