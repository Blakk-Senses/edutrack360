
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.http import HttpResponse, JsonResponse
from core.models import (
    District, Teacher, PerformanceSummary, Profile, 
    School, SchoolSubmission, Circuit, StudentMark, Result, SubjectTeacher, 
    ClassTeacher, Subject,
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

@login_required(login_url=lambda: reverse_lazy('dashboards:siso_dashboard'))
def siso_dashboard(request):
    circuit = None  # Initialize circuit
    circuit_name = 'Unknown'

    # Check if the user has the role 'siso'
    if hasattr(request.user, 'circuit') and request.user.role == 'siso':
        circuit = request.user.circuit
        circuit_name = circuit.name if circuit else "Unknown"

    total_schools = circuit.schools.count() if circuit else 0


    # Teacher count per school
    total_teachers = User.objects.filter(
        school__circuit=circuit,
        role__in=['teacher', 'headteacher']
    ).count() if circuit else 0

    # Aggregated circuit-level performance
    circuit_performance = (
        PerformanceSummary.objects.filter(circuit=circuit).aggregate(average_grade=Avg('average_score'))
        if circuit
        else {'average_grade': None}
    )

    # Performance data over years
    performance_data = (
        PerformanceSummary.objects.filter(circuit=circuit)
        .values('year')
        .annotate(average_grade=Avg('average_score'))
        if circuit
        else []
    )

    # Top-performing schools
    top_schools = (
        School.objects.filter(circuit=circuit)
        .annotate(performance_score=Avg('performance_summaries__average_score'))
        .order_by('-performance_score')[:10]
        if circuit
        else []
    )

    # Submission status counts
    if circuit:
        successful_submissions = SchoolSubmission.objects.filter(school__circuit=circuit, status='submitted').count()
        pending_submissions = SchoolSubmission.objects.filter(school__circuit=circuit, status='pending').count()
        not_submitted = SchoolSubmission.objects.filter(school__circuit=circuit, status='not_submitted').count()
    else:
        successful_submissions = pending_submissions = not_submitted = 0

    circuit_summary = {
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
        'circuit_name': circuit_name,
        'total_schools': total_schools,
        'total_teachers': total_teachers,
        'avg_circuit_performance': circuit_performance['average_grade'] or 'N/A',
        'performance_data': performance_data,
        'top_schools': [
            {
                'name': school.name,
                'performance_score': f"{school.performance_score:.2f}%" if school.performance_score else "N/A"
            } for school in top_schools
        ],
        'circuit_summary': circuit_summary,
        'pie_chart_data': pie_chart_data,
    }

    return render(request, 'dashboards/siso_dashboard.html', context)

def download_circuit_report(request, circuit_id):
    # Generate and return the circuit report
    return HttpResponse(f"Downloading Circuit Report for ID: {circuit_id}")

#--------------- HEADTEACHER DASHBOARD -----------------

def headteacher_dashboard(request):
    # Get the current school from the logged-in user
    school = request.user.school

    # Get the latest academic year from available student marks
    current_academic_year = (
        StudentMark.objects.filter(student__school=school)
        .aggregate(latest_year=Max("academic_year"))["latest_year"]
    )

    # Get the latest term within the current academic year
    current_term = (
        StudentMark.objects.filter(student__school=school, academic_year=current_academic_year)
        .aggregate(latest_term=Max("term"))["latest_term"]
    )

    # Ensure term and academic year exist
    if not current_academic_year or not current_term:
        return render(request, "dashboards/headteacher_dashboard.html", {
            "error": "No data available yet for this academic year."
        })

    # ✅ Total Students Assessed (Distinct Count of Students)
    total_students_assessed = (
        StudentMark.objects.filter(
            student__school=school,
            term=current_term,
            academic_year=current_academic_year
        ).values("student").distinct().count()
    )

    # ✅ Total School Average
    total_school_average = (
        StudentMark.objects.filter(
            student__school=school,
            term=current_term,
            academic_year=current_academic_year
        ).aggregate(Avg("mark"))["mark__avg"] or 0
    )

    # ✅ Best & Worst Performing Subjects
    subject_averages = (
        StudentMark.objects.filter(
            student__school=school,
            term=current_term,
            academic_year=current_academic_year
        )
        .values("subject__name", "subject__department__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:3]
    )

    best_performing_subjects = subject_averages[:2]
    worst_performing_subjects = subject_averages[:2]

    # ✅ Best 3 Performing Classes
    class_averages = (
        StudentMark.objects.filter(
            student__school=school,
            term=current_term,
            academic_year=current_academic_year
        )
        .values("class_group__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:3]
    )

    best_performing_classes = class_averages[:3]

    # ✅ School Performance Trends (Data for Chart.js)
    performance_trends = (
        StudentMark.objects.filter(student__school=school)
        .values("academic_year", "term")
        .annotate(avg_mark=Avg("mark"))
        .order_by("academic_year", "term")
    )

    trend_data = {
        "dates": [f"{entry['academic_year']} T{entry['term']}" for entry in performance_trends],
        "scores": [entry["avg_mark"] for entry in performance_trends],
    }

    # ✅ Notifications (Recent Uploads)
    notifications = (
        Result.objects.filter(
            student__school=school,
            term=current_term,
            academic_year=current_academic_year
        )
        .values("teacher__last_name", "subject__name", "student__class_group__name")
        .order_by("-id")[:10]
    )

    context = {
        "total_students_assessed": total_students_assessed,
        "total_school_average": round(total_school_average, 2),
        "best_performing_subjects": best_performing_subjects,
        "worst_performing_subjects": worst_performing_subjects,
        "best_performing_classes": best_performing_classes,
        "performance_trends": trend_data,
        "notifications": notifications,
    }

    return render(request, "dashboards/headteacher_dashboard.html", context)


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
        print("No teacher profile found.")
        return redirect('homepage')

    try:
        class_teacher = ClassTeacher.objects.get(teacher=teacher)
    except ClassTeacher.DoesNotExist:
        print(f"No ClassTeacher mapping for teacher: {teacher}")
        return redirect('homepage')

    assigned_class = class_teacher.assigned_class
    print(f"Assigned class: {assigned_class}")

    # Load filter options
    filter_options = json.loads(get_available_terms(request).content)
    all_years = [year["name"] for year in filter_options.get("academic_years", [])]
    all_terms = [term["name"] for term in filter_options.get("terms", [])]

    # Get selected filters with fallbacks
    academic_year = request.GET.get("academic_year")
    selected_year = academic_year if academic_year in all_years else filter_options.get("selected_academic_year")

    term = request.GET.get("term")
    selected_term = term if term in all_terms else filter_options.get("selected_term", "Term 1")

    print(f"Selected Year: {selected_year}")
    print(f"Selected Term: {selected_term}")

    # Query base
    student_marks = StudentMark.objects.filter(class_group=assigned_class)

    if selected_year:
        student_marks = student_marks.filter(academic_year=selected_year)
    if selected_term:
        student_marks = student_marks.filter(term=selected_term)

    print(f"Filtered StudentMark count: {student_marks.count()}")

    average_class_performance = student_marks.aggregate(avg_mark=Avg("mark"))["avg_mark"]
    print(f"Raw average mark: {average_class_performance}")

    average_class_performance = average_class_performance or 0

    best_students = (
        student_marks.values("student__first_name", "student__last_name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:3]
    )
    print("Best students:", list(best_students))

    weakest_students = (
        student_marks.values("student__first_name", "student__last_name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("avg_mark")[:3]
    )
    print("Weakest students:", list(weakest_students))

    top_subjects = (
        student_marks.values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:3]
    )
    print("Top subjects:", list(top_subjects))

    lowest_subjects = (
        student_marks.values("subject__name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("avg_mark")[:3]
    )
    print("Lowest subjects:", list(lowest_subjects))

    performance_trends = (
        student_marks.values("term")
        .annotate(avg_mark=Avg("mark"))
        .order_by("term")
    )
    print("Performance trends:", list(performance_trends))
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
    student_marks = StudentMark.objects.all()

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
        student_marks.values("student__first_name", "student__last_name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("-avg_mark")[:3]
    )
    weakest_students = (
        student_marks.values("student__first_name", "student__last_name")
        .annotate(avg_mark=Avg("mark"))
        .order_by("avg_mark")[:3]
    )

    # Performance trends
    performance_trends = (
        student_marks.values("term")
        .annotate(avg_mark=Avg("mark"))
        .order_by("term")
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "total_students_assessed": total_students_assessed,
            "average_class_performance": round(average_class_performance, 2),
            "best_students": [{"name": f"{s['student__first_name']} {s['student__last_name']}", "mark": s["avg_mark"]} for s in best_students],
            "weakest_students": [{"name": f"{s['student__first_name']} {s['student__last_name']}", "mark": s["avg_mark"]} for s in weakest_students],
            "performance_trends": list(performance_trends),
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

