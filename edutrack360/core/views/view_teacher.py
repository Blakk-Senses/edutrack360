from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponse, Http404, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
import csv
import pandas as pd
from django.core.files.storage import default_storage
from django.contrib import messages
import json
import io
from decimal import Decimal
from django.db.models import Count, Q
from django.contrib.auth.decorators import login_required
from core.forms import ResultUploadForm 
from core.models import (
    Subject, Student, StudentMark, SubjectTeacher, ClassGroup,
    Department, Result, ClassTeacher, Teacher,
)
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.textlabels import Label
from reportlab.lib.colors import HexColor

import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from django.http import HttpResponse
from django.db.models import Avg
from django.shortcuts import render
import json
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST


User = get_user_model()

def upload_subject_results(request):
    return render(request, 'teacher/subject_upload_results.html')

def upload_class_results(request):
    return render(request, 'teacher/class_upload_results.html')

def progress_trends(request):
    return render(request, 'teacher/progress_trends.html')

def settings(request):
    return render(request, 'teacher/settings.html')



# Helper function for error handling
def error_response(message, status=400):
    return JsonResponse({"error": message}, status=status)

@login_required
def get_departments(request):
    """Fetch all departments belonging to the logged-in user's school."""
    if not hasattr(request.user, "school") or request.user.school is None:
        return JsonResponse({"departments": []})  # Return empty list instead of error

    departments = Department.objects.filter(schools=request.user.school).values("id", "name")
    return JsonResponse({"departments": list(departments)})

@login_required
def get_class_department(request, class_group_id):
    try:
        class_group = ClassGroup.objects.get(id=class_group_id)
        return JsonResponse({"department_id": class_group.department.id})
    except ClassGroup.DoesNotExist:
        return JsonResponse({"error": "Class group not found"}, status=404)
    

@login_required
def get_classes(request):
    """Fetch all class groups for the logged-in user's school."""
    try:
        classes = ClassGroup.objects.filter(school=request.user.school).values("id", "name")
        return JsonResponse({"classes": list(classes)})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def get_classes_by_department(request, department_id):
    """Fetch classes based on the selected department."""
    try:
        department = Department.objects.get(id=department_id, schools=request.user.school)
        classes = ClassGroup.objects.filter(department=department).values("id", "name")
        return JsonResponse({"classes": list(classes)})
    except Department.DoesNotExist:
        return JsonResponse({"error": "Invalid department selection"}, status=400)


@login_required
def get_subjects_by_department(request, department_id):
    """Fetch subjects based on the selected department."""
    try:
        department = Department.objects.get(id=department_id)
        subjects = department.subjects.values("id", "name")  # Use related_name from ManyToManyField
        return JsonResponse({"subjects": list(subjects)})
    except Department.DoesNotExist:
        return JsonResponse({"error": "Invalid department selection"}, status=400)



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


#-------------------- SUBJECT TEACHER -------------------

def get_subject_performance_context(request):
    """Generates subject performance analysis for a subject teacher with added chart data."""

    filter_options = json.loads(get_available_terms(request).content)
    academic_year = request.GET.get("academic_year", "").strip()
    selected_term = request.GET.get("term", "all")
    selected_subject = request.GET.get("subject", "all")
    selected_class = request.GET.get("class_group", "all")

    valid_years = [year["name"] for year in filter_options["academic_years"]]
    academic_year = academic_year if academic_year in valid_years else filter_options["selected_academic_year"]

    base_year = int(academic_year.split("/")[0])
    prev_1 = f"{base_year - 1}/{base_year}"
    prev_2 = f"{base_year - 2}/{base_year - 1}"
    academic_years = [prev_2, prev_1, academic_year]

    all_terms = [t["name"] for t in filter_options["terms"]]
    selected_term = selected_term if selected_term in all_terms else "Term 1"

    if selected_term == "Term 1":
        term_sequence = [("Term 2", prev_1), ("Term 3", prev_1), ("Term 1", academic_year)]
    elif selected_term == "Term 2":
        term_sequence = [("Term 3", prev_1), ("Term 1", academic_year), ("Term 2", academic_year)]
    else:
        term_sequence = [("Term 1", academic_year), ("Term 2", academic_year), ("Term 3", academic_year)]

    terms_to_fetch = [t[0] for t in term_sequence]
    term_keys = [f"{t} ({y})" for t, y in term_sequence]

    teacher = request.user.teacher_profile
    assigned_teachings = SubjectTeacher.objects.filter(teacher=teacher).select_related("subject").prefetch_related("assigned_classes")
    assigned_subjects = {st.subject.name for st in assigned_teachings}
    assigned_subject_ids = {st.subject.id for st in assigned_teachings}
    assigned_classes = {cg.id for st in assigned_teachings for cg in st.assigned_classes.all()}

    if selected_subject != "all":
        subject_obj = Subject.objects.filter(name=selected_subject).first()
        if subject_obj:
            assigned_subjects, assigned_subject_ids = {selected_subject}, {subject_obj.id}
        else:
            assigned_subjects, assigned_subject_ids = set(), set()

    if selected_class != "all":
        try:
            selected_class_id = int(selected_class)
            if selected_class_id in assigned_classes:
                assigned_classes = {selected_class_id}
        except ValueError:
            pass

    if not assigned_subjects or not assigned_classes:
        return render(request, "teacher/subject_performance_analysis.html", {
            "student_rows": [], "class_average_row": {},
            "term_trend": {}, "academic_trend": {},
            "terms": all_terms, "academic_years": valid_years,
            "selected_year": academic_year, "selected_term": selected_term,
            "selected_subject": selected_subject, "selected_class": selected_class,
            "subjects": list(assigned_subjects), "assigned_classes": [],
            "score_buckets": {}, "heatmap_data": [],
            "term_chart": {}, "year_chart": {},
        })

    # 🧍 Student Performance
    selected_marks = StudentMark.objects.filter(
        class_group_id__in=assigned_classes,
        academic_year=academic_year,
        term=selected_term,
        subject_id__in=assigned_subject_ids,
        student__school_id=teacher.school.id
    ).select_related("student", "subject").order_by("student__last_name")

    student_rows = []
    class_scores = []

    for mark in selected_marks:
        if mark.subject.name != selected_subject:
            continue
        student_name = f"{mark.student.last_name} {mark.student.first_name}"
        score = float(mark.mark) if isinstance(mark.mark, Decimal) else mark.mark
        student_rows.append({"name": student_name, "mark": round(score, 2)})
        class_scores.append(score)

    class_average_row = {
        "name": "Class Average",
        "mark": round(sum(class_scores) / len(class_scores), 2) if class_scores else "-"
    }

    # 📊 Term and Year Trends
    q_terms = Q()
    for term, year in term_sequence:
        q_terms |= Q(term=term, academic_year=year)

    trend_marks = StudentMark.objects.filter(
        class_group_id__in=assigned_classes,
        subject_id__in=assigned_subject_ids,
        student__school_id=teacher.school.id
    ).filter(q_terms).select_related("student", "subject")

    term_aggregates = {key: [] for key in term_keys}
    year_aggregates = {year: [] for year in academic_years}

    for mark in trend_marks:
        if mark.subject.name != selected_subject:
            continue
        score = float(mark.mark) if isinstance(mark.mark, Decimal) else mark.mark
        key = f"{mark.term} ({mark.academic_year})"
        if key in term_aggregates:
            term_aggregates[key].append(score)
        year_aggregates[mark.academic_year].append(score)

    term_trend = {
        "Subject": selected_subject,
        **{key: round(sum(v) / len(v), 2) if v else "-" for key, v in term_aggregates.items()}
    }

    academic_trend = {
        "Subject": selected_subject,
        **{year: round(sum(v) / len(v), 2) if v else "-" for year, v in year_aggregates.items()}
    }

    # 🎯 Score Buckets
    score_buckets = {
        "80-100": 0,
        "55-79": 0,
        "50-54": 0,
        "40-49": 0,
        "0-39": 0
    }

    for mark in class_scores:
        if mark >= 80:
            score_buckets["80-100"] += 1
        elif mark >= 55:
            score_buckets["55-79"] += 1
        elif mark >= 50:
            score_buckets["50-54"] += 1
        elif mark >= 40:
            score_buckets["40-49"] += 1
        else:
            score_buckets["0-39"] += 1

    heatmap_data = [{"name": row["name"], "mark": float(row["mark"])} for row in student_rows]

    # 📈 Line Chart Labels & Data
    term_labels = list(term_trend.keys())[1:]
    term_values = [float(val) if isinstance(val, (int, float, Decimal)) else None for val in list(term_trend.values())[1:]]

    year_labels = list(academic_trend.keys())[1:]
    year_values = [float(val) if isinstance(val, (int, float, Decimal)) else None for val in list(academic_trend.values())[1:]]

    class_groups = {cg.id: cg.name for cg in ClassGroup.objects.filter(id__in=assigned_classes)}

    return {
        "student_rows": student_rows,
        "class_average_row": class_average_row,
        "term_trend": term_trend,
        "academic_trend": academic_trend,
        "terms": all_terms,
        "academic_years": valid_years,
        "selected_year": academic_year,
        "selected_term": selected_term,
        "selected_subject": selected_subject,
        "selected_class": selected_class,
        "subjects": list(assigned_subjects),
        "assigned_classes": [{"id": cid, "name": class_groups[cid]} for cid in assigned_classes],

        "bucket_80_100": score_buckets.get("80-100", 0),
        "bucket_55_79": score_buckets.get("55-79", 0),
        "bucket_50_54": score_buckets.get("50-54", 0),
        "bucket_40_49": score_buckets.get("40-49", 0),
        "bucket_0_39": score_buckets.get("0-39", 0),

        "score_buckets": score_buckets,
        "heatmap_data": heatmap_data,
        "term_chart": {"labels": term_labels, "data": term_values},
        "year_chart": {"labels": year_labels, "data": year_values},
    }


@login_required
def subject_performance_analysis(request):
    context = get_subject_performance_context(request)
    return render(request, "teacher/subject_performance_analysis.html", context)


@login_required
def download_subject_analysis_pdf(request):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=120)
    elements = []
    styles = getSampleStyleSheet()
    subtitle_style = styles['Heading4']

    # ✅ Get context
    context = get_subject_performance_context(request)

    subject = context['selected_subject']
    term = context['selected_term']
    year = context['selected_year']
    class_id = context['selected_class']
    class_group = ClassGroup.objects.get(id=class_id).name
    school_name = f"School: {request.user.school.name}"  # ✅ Prefixed text

    # --- Student Performance Table
    elements.append(Paragraph("Student Performance", subtitle_style))
    student_data = [["Student Name", subject]]
    for row in context["student_rows"]:
        student_data.append([row["name"], row["mark"]])
    student_data.append([context["class_average_row"]["name"], context["class_average_row"]["mark"]])

    student_table = Table(student_data, colWidths=[250, 100])
    student_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#eeeeee")),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.extend([student_table, Spacer(1, 20)])

    # --- Term Trend Table
    elements.append(Paragraph("Termly Performance Trend", subtitle_style))
    term_data = [list(context["term_trend"].keys()), list(context["term_trend"].values())]
    term_table = Table(term_data, colWidths=[100] * len(term_data[0]))
    term_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.extend([term_table, Spacer(1, 20)])


    # --- Yearly Trend Table
    elements.append(Paragraph("Yearly Performance Trend", subtitle_style))
    year_data = [list(context["academic_trend"].keys()), list(context["academic_trend"].values())]
    year_table = Table(year_data, colWidths=[100] * len(year_data[0]))
    year_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.extend([year_table, Spacer(1, 20)])

    # --- Score Buckets Table
    elements.append(Paragraph("Score Distribution (Buckets)", subtitle_style))
    bucket_data = [["Score Range", "Number of Students"]]
    for bucket, count in context["score_buckets"].items():
        bucket_data.append([bucket, count])

    bucket_table = Table(bucket_data, colWidths=[150, 150])
    bucket_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.extend([bucket_table, Spacer(1, 20)])

    # --- Build with header
    def draw_custom_header(c, subject, school_name, class_group, academic_year, term):
        page_width, page_height = A4
        teal = colors.HexColor("#f2f2f2")
        white = colors.black

        # Top Teal Banner
        c.setFillColor(teal)
        c.rect(0, page_height - 60, page_width, 60, fill=1, stroke=0)

        # Title - Centered
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 18)
        title_text = "Subject Performance Report"
        title_width = c.stringWidth(title_text, "Helvetica-Bold", 18)
        c.drawString((page_width - title_width) / 2, page_height - 35, title_text)

        # School Name - Centered
        c.setFont("Helvetica", 12)
        school_width = c.stringWidth(school_name, "Helvetica", 12)
        c.drawString((page_width - school_width) / 2, page_height - 52, school_name)

        # Lower Info Bar - Centered Items
        c.setFillColor(teal)
        c.rect(0, page_height - 85, page_width, 25, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 10)

        info_text = f"Class: {class_group}    |    Academic Year: {academic_year}    |    Term: {term}"
        info_width = c.stringWidth(info_text, "Helvetica-Bold", 10)
        c.drawString((page_width - info_width) / 2, page_height - 70, info_text)

    doc.build(elements, onFirstPage=lambda c, d: draw_custom_header(c, subject, school_name, class_group, year, term))
    buffer.seek(0)

    # ✅ Build clean filename: "Basic5_Math_Performance_Analysis_2024_2025_Term1.pdf"
    safe_subject = subject.replace(" ", "")
    safe_class = class_group.replace(" ", "")
    safe_year = str(year).replace("/", "_")
    filename = f"{safe_class}_{safe_subject}_Performance_Analysis_{safe_year}_{term}.pdf"

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response







#------------------ CLASS TEACHER -----------------------

def get_class_performance_context(request):
    """Generates class performance analysis for a class teacher with academic year and term filters."""
    print("🔍 Starting class performance context generation...")

    filter_options = json.loads(get_available_terms(request).content)
    print("📋 Filter options fetched:", filter_options)

    academic_year = request.GET.get("academic_year", "").strip()
    selected_term = request.GET.get("term", "all")
    print("📥 Raw GET academic_year:", academic_year, "| term:", selected_term)

    valid_years = [year["name"] for year in filter_options["academic_years"]]
    academic_year = academic_year if academic_year in valid_years else filter_options["selected_academic_year"]
    print("✅ Valid academic_year selected:", academic_year)

    all_terms = [t["name"] for t in filter_options["terms"]]
    selected_term = selected_term if selected_term in all_terms else "Term 1"
    print("✅ Valid selected_term:", selected_term)

    teacher = request.user.teacher_profile
    class_teacher = ClassTeacher.objects.filter(teacher=teacher).select_related("assigned_class").first()

    if not class_teacher:
        print("❌ No class teacher assigned to this teacher.")
        return {
            "student_rows": [],
            "class_average_row": {},
            "term_trend": {},
            "academic_trend": {},
            "terms": all_terms,
            "academic_years": valid_years,
            "selected_year": academic_year,
            "selected_term": selected_term,
            "subjects": [],
            "assigned_classes": [],
            "score_buckets": {},
            "heatmap_data": [],
            "term_chart": {},
            "year_chart": {},
        }

    assigned_class = class_teacher.assigned_class
    print("🏫 Assigned class:", assigned_class.name)

    selected_marks = StudentMark.objects.filter(
        class_group=assigned_class,
        academic_year=academic_year,
        term=selected_term,
        student__school=teacher.school
    ).select_related("student", "subject").order_by("student__last_name")
    print("🧾 Total marks fetched:", selected_marks.count())

    students = {}
    subjects = set()

    for mark in selected_marks:
        student_key = f"{mark.student.last_name} {mark.student.first_name}"
        if student_key not in students:
            students[student_key] = {"name": student_key, "marks": {}, "avg": 0}
        students[student_key]["marks"][mark.subject.name] = float(mark.mark)
        subjects.add(mark.subject.name)

    print("👩‍🎓 Total unique students:", len(students))
    print("📚 Subjects found:", sorted(subjects))

    subjects = sorted(subjects)
    subject_totals = {subject: [] for subject in subjects}
    student_rows = []

    for student_data in students.values():
        marks = []
        for subject in subjects:
            mark = student_data["marks"].get(subject, "-")
            student_data["marks"][subject] = round(mark, 2) if isinstance(mark, (int, float)) else "-"
            if isinstance(mark, (int, float)):
                marks.append(mark)
                subject_totals[subject].append(mark)
        student_data["avg"] = round(sum(marks) / len(marks), 2) if marks else "-"
        student_rows.append(student_data)

    print("🧮 Completed student row generation.")

    class_average_row = {"name": "Subject Average", "marks": {}}
    subject_avgs = []
    for subject in subjects:
        scores = subject_totals[subject]
        avg = round(sum(scores) / len(scores), 2) if scores else "-"
        class_average_row["marks"][subject] = avg
        if isinstance(avg, (int, float)):
            subject_avgs.append(avg)
    class_average_row["avg"] = round(sum(subject_avgs) / len(subject_avgs), 2) if subject_avgs else "-"
    print("📊 Class subject averages:", class_average_row)

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

    trend_marks = StudentMark.objects.filter(
        class_group=assigned_class,
        student__school=teacher.school
    ).filter(q_terms).select_related("subject")
    print("📈 Trend marks count:", trend_marks.count())

    term_aggregates = {key: [] for key in term_keys}
    year_aggregates = {year: [] for year in academic_years}

    for mark in trend_marks:
        score = float(mark.mark)
        key = f"{mark.term} ({mark.academic_year})"
        if key in term_aggregates:
            term_aggregates[key].append(score)
        year_aggregates[mark.academic_year].append(score)

    term_trend = {
        "Class": assigned_class.name,
        **{key: round(sum(v) / len(v), 2) if v else "-" for key, v in term_aggregates.items()}
    }
    academic_trend = {
        "Class": assigned_class.name,
        **{year: round(sum(v) / len(v), 2) if v else "-" for year, v in year_aggregates.items()}
    }

    print("📉 Term trend:", term_trend)
    print("📅 Academic trend:", academic_trend)

    term_labels = list(term_trend.keys())[1:]
    term_values = [float(val) if isinstance(val, (int, float)) else None for val in list(term_trend.values())[1:]]

    year_labels = list(academic_trend.keys())[1:]
    year_values = [float(val) if isinstance(val, (int, float)) else None for val in list(academic_trend.values())[1:]]

    all_scores = [score for sublist in subject_totals.values() for score in sublist]
    score_buckets = {
        "80-100": sum(1 for s in all_scores if s >= 80),
        "55-79": sum(1 for s in all_scores if 55 <= s < 80),
        "50-54": sum(1 for s in all_scores if 50 <= s < 55),
        "40-49": sum(1 for s in all_scores if 40 <= s < 50),
        "0-39":  sum(1 for s in all_scores if s < 40),
    }
    print("🎯 Score buckets:", score_buckets)

    heatmap_data = [{"name": row["name"], "mark": float(row["avg"])} for row in student_rows if isinstance(row["avg"], (int, float))]
    print("🔥 Heatmap data generated. Total:", len(heatmap_data))

    print("✅ Finished generating context.")
    return {
        "student_rows": student_rows,
        "class_average_row": class_average_row,
        "term_trend": term_trend,
        "academic_trend": academic_trend,
        "terms": all_terms,
        "academic_years": valid_years,
        "selected_year": academic_year,
        "selected_term": selected_term,
        "subjects": subjects,
        "assigned_classes": [{"id": assigned_class.id, "name": assigned_class.name}],

        "bucket_80_100": score_buckets["80-100"],
        "bucket_55_79": score_buckets["55-79"],
        "bucket_50_54": score_buckets["50-54"],
        "bucket_40_49": score_buckets["40-49"],
        "bucket_0_39": score_buckets["0-39"],

        "score_buckets": score_buckets,
        "heatmap_data": heatmap_data,
        "term_chart": {"labels": term_labels, "data": term_values},
        "year_chart": {"labels": year_labels, "data": year_values},
    }



@login_required
def class_performance_analysis(request):
    context = get_class_performance_context(request)
    return render(request, "teacher/class_performance_analysis.html", context)


@login_required
def download_class_performance_pdf(request):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=120, bottomMargin=50)
    elements = []
    styles = getSampleStyleSheet()
    subtitle_style = styles['Heading4']

    # ✅ Get context
    context = get_class_performance_context(request)
    year = context['selected_year']
    term = context['selected_term']
    subject_list = context["subjects"]
    performance_rows = context['student_rows']
    term_trend = context['term_trend']
    academic_trend = context['academic_trend']
    score_buckets = context['score_buckets']

    # 🧠 Get class and school details
    teacher = Teacher.objects.get(user=request.user)
    class_teacher = ClassTeacher.objects.get(teacher=teacher)
    class_group = class_teacher.assigned_class
    school_name = f"School: {request.user.school.name}"

    # --- Compute Subject Averages ---
    subject_totals = {subject: 0 for subject in subject_list}
    subject_counts = {subject: 0 for subject in subject_list}

    for row in performance_rows:
        for subject in subject_list:
            mark = row["marks"].get(subject)
            if isinstance(mark, (int, float)):
                subject_totals[subject] += mark
                subject_counts[subject] += 1

    subject_averages = {
        subject: round(subject_totals[subject] / subject_counts[subject], 1)
        if subject_counts[subject] > 0 else "-"
        for subject in subject_list
    }

    # --- Student Subject Performance Table
    elements.append(Paragraph("Student Subject Performance", subtitle_style))
    table_data = [["Student Name"] + subject_list + ["Average"]]

    for row in performance_rows:
        row_data = [row["name"]]
        for subject in subject_list:
            row_data.append(row["marks"].get(subject, "-"))
        row_data.append(row["avg"])
        table_data.append(row_data)

    # ✅ Append Subject Average row
    avg_row = ["Subject Average"]
    for subject in subject_list:
        avg_row.append(subject_averages.get(subject, "-"))
    avg_row.append("-")  # Final column for Average of averages (not needed here)
    table_data.append(avg_row)

    max_subjects = len(subject_list)
    available_width = A4[0] - 100
    col_widths = [120] + [available_width / (max_subjects + 1)] * max_subjects + [50]

    student_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    student_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, len(table_data) - 1), (-1, len(table_data) - 1), 'Helvetica-Bold'),  # Subject average row
        ('BACKGROUND', (0, len(table_data) - 1), (-1, len(table_data) - 1), colors.HexColor("#f9f9f9")),
    ]))
    elements.extend([student_table, Spacer(1, 20)])

    # --- Score Bucket Table (2 columns)
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
    elements.extend([bucket_table, Spacer(1, 10)])

    # --- Score Bucket Bar Chart
    drawing = Drawing(400, 180)
    bar = VerticalBarChart()
    bar.x = 50
    bar.y = 30
    bar.height = 120
    bar.width = 300
    bar.data = [[
        score_buckets["80-100"],
        score_buckets["55-79"],
        score_buckets["50-54"],
        score_buckets["40-49"],
        score_buckets["0-39"],
    ]]
    bar.categoryAxis.categoryNames = ["80-100", "55-79", "50-54", "40-49", "0-39"]
    bar.barWidth = 15
    bar.strokeColor = colors.black
    bar.valueAxis.valueMin = 0
    bar.bars[0].fillColor = colors.HexColor("#4a90e2")
    drawing.add(bar)
    elements.extend([Paragraph("Score Bucket Bar Chart", subtitle_style), drawing, Spacer(1, 20)])

    # --- Term Trend Table
    elements.append(Paragraph("Termly Performance Trend", subtitle_style))
    term_data = [list(term_trend.keys()), list(term_trend.values())]
    term_table = Table(term_data, colWidths=[100] * len(term_data[0]))
    term_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.extend([term_table, Spacer(1, 20)])

    # --- Yearly Trend Table
    elements.append(Paragraph("Yearly Performance Trend", subtitle_style))
    year_data = [list(academic_trend.keys()), list(academic_trend.values())]
    year_table = Table(year_data, colWidths=[100] * len(year_data[0]))
    year_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.extend([year_table, Spacer(1, 20)])

    # --- Header and Footer
    def draw_custom_header(c, school_name, class_group_name, academic_year, term):
        page_width, page_height = A4
        banner_color = colors.HexColor("#f2f2f2")
        text_color = colors.black

        c.setFillColor(banner_color)
        c.rect(0, page_height - 60, page_width, 60, fill=1, stroke=0)
        c.setFillColor(text_color)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(page_width / 2, page_height - 35, "Class Performance Report")

        c.setFont("Helvetica", 12)
        c.drawCentredString(page_width / 2, page_height - 52, school_name)

        c.setFillColor(banner_color)
        c.rect(0, page_height - 85, page_width, 25, fill=1, stroke=0)
        c.setFillColor(text_color)
        c.setFont("Helvetica-Bold", 10)
        info_text = f"Class: {class_group_name}    |    Academic Year: {academic_year}    |    Term: {term}"
        c.drawCentredString(page_width / 2, page_height - 70, info_text)

    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.drawCentredString(A4[0] / 2, 30, f"Page {doc.page}")
        canvas.restoreState()

    # --- Build PDF
    doc.build(
        elements,
        onFirstPage=lambda c, d: [draw_custom_header(c, school_name, class_group.name, year, term), draw_footer(c, d)],
        onLaterPages=draw_footer
    )

    buffer.seek(0)
    safe_class = class_group.name.replace(" ", "")
    safe_year = str(year).replace("/", "_")
    filename = f"{safe_class}_Class_Performance_{safe_year}_{term}.pdf"

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename={filename}"
    return response


#---------------UPLOAD RESULTS----------------------------

def can_teacher_upload_result(teacher, class_group, subject):
    has_subject_access = teacher.assigned_subjects.filter(id=subject.id).exists()
    is_class_teacher = ClassTeacher.objects.filter(
        teacher=teacher,
        assigned_class=class_group
    ).exists()
    subject_in_class_dept = subject.department.filter(id=class_group.department.id).exists() if class_group.department else False
    return has_subject_access or (is_class_teacher and subject_in_class_dept)


@login_required
def manual_upload_result(request):
    """Manually uploads a single result entry."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    form = ResultUploadForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"error": "Invalid form submission", "details": form.errors}, status=400)

    subject = form.cleaned_data["subject"]
    class_group = form.cleaned_data["class_group"]
    student_name = form.cleaned_data["student_name"]
    mark = form.cleaned_data["mark"]
    academic_year = form.cleaned_data["academic_year"]
    term = form.cleaned_data["term"]

    teacher = request.user.teacher_profile

    # Shared permission logic
    if not can_teacher_upload_result(teacher, class_group, subject):
        return JsonResponse({"error": "Unauthorized: You are not allowed to upload results for this subject."}, status=403)

    # Split full name into first and last name
    name_parts = student_name.split(maxsplit=1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    # Fetch or create student with teacher's school, circuit, and district
    student, created = Student.objects.get_or_create(
        first_name=first_name,
        last_name=last_name,
        school=request.user.school,  # Ensure student gets the teacher's school
        defaults={
            "class_group": class_group,
            "circuit": request.user.circuit,  # Assign teacher's circuit
            "district": request.user.district  # Assign teacher's district
        }
    )

    # If student exists but class is different, update class_group
    if not created and student.class_group != class_group:
        student.class_group = class_group
        student.save()

    # Create result entry with school, circuit, and district
    Result.objects.create(
        academic_year=academic_year,
        class_group=class_group,
        subject=subject,
        term=term,
        student=student,
        mark=mark,
        teacher=request.user,
        school=request.user.school,
        circuit=request.user.circuit,  # Include circuit in result
        district=request.user.district,  # Include district in result
        status="Pending"
    )

    return JsonResponse({"message": "Result uploaded successfully!"}, status=201)



@login_required
def bulk_upload_results(request):
    """Handles bulk upload of results from CSV/XLSX."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    file = request.FILES.get("file")
    if not file:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    try:
        if file.name.endswith(".csv"):
            df = pd.read_csv(file, dtype=str)
        elif file.name.endswith((".xls", ".xlsx")):
            df = pd.read_excel(file, dtype=str)
        else:
            return JsonResponse({"error": "Invalid file format. Please upload CSV or Excel."}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Failed to read file: {str(e)}"}, status=400)

    errors = []
    valid_results = []

    valid_years = {f"{year}/{year+1}" for year in range(2020, 2050)}
    valid_terms = {"Term 1", "Term 2", "Term 3"}

    teacher = request.user.teacher_profile
    teacher_school = request.user.school
    teacher_circuit = request.user.circuit
    teacher_district = request.user.district

    existing_students = {
        f"{s.first_name} {s.last_name}".strip(): s
        for s in Student.objects.filter(school=teacher_school)
    }

    for index, row in df.iterrows():
        first_name = str(row.get("First Name") or "").strip()
        last_name = str(row.get("Last Name") or "").strip()
        student_name = f"{first_name} {last_name}".strip()
        class_name = str(row.get("Class") or "").strip()
        subject_name = str(row.get("Subject") or "").strip()
        academic_year = str(row.get("Academic Year") or "").strip()
        term = str(row.get("Term") or "").strip()
        mark = row.get("Mark") or ""

        if not all([student_name, class_name, subject_name, academic_year, term, mark]):
            errors.append({"row": index + 1, "error": "Missing required fields."})
            continue

        if academic_year not in valid_years:
            errors.append({"row": index + 1, "error": f"Invalid academic year: {academic_year}"})
            continue

        if term not in valid_terms:
            errors.append({"row": index + 1, "error": f"Invalid term: {term}"})
            continue

        try:
            class_group = ClassGroup.objects.select_related("department").get(name=class_name)
        except ClassGroup.DoesNotExist:
            errors.append({"row": index + 1, "error": f"Invalid class: {class_name}"})
            continue

        try:
            subject = Subject.objects.get(name=subject_name, department=class_group.department)
        except Subject.DoesNotExist:
            errors.append({"row": index + 1, "error": f"Invalid subject '{subject_name}' for class {class_name}"})
            continue

        # ✅ Shared authorization logic (subject teacher OR class teacher in department)
        if not can_teacher_upload_result(teacher, class_group, subject):
            errors.append({
                "row": index + 1,
                "error": "Unauthorized: You are not allowed to upload results for this subject."
            })
            continue

        # Validate mark
        try:
            mark = float(mark)
            if not (0 <= mark <= 100):
                raise ValueError
        except ValueError:
            errors.append({"row": index + 1, "error": "Mark must be a number between 0 and 100."})
            continue

        student_key = student_name
        student = existing_students.get(student_key)

        if not student:
            student, _ = Student.objects.get_or_create(
                first_name=first_name,
                last_name=last_name,
                school=teacher_school,
                defaults={
                    "class_group": class_group,
                    "circuit": teacher_circuit,
                    "district": teacher_district
                }
            )
            existing_students[student_key] = student

        if student.class_group != class_group:
            student.class_group = class_group
            student.save()

        valid_results.append(
        Result(
            academic_year=academic_year,
            class_group=class_group,
            subject=subject,
            term=term,
            student=student,
            mark=mark,
            teacher=request.user,
            school=teacher_school,
            circuit=teacher_circuit,
            district=teacher_district,
            status="Pending"
        )
    )


    if valid_results:
        inserted_results = Result.objects.bulk_create(valid_results)

        for result in inserted_results:
            StudentMark.objects.update_or_create(
                student=result.student,
                subject=result.subject,
                academic_year=result.academic_year,
                term=result.term,
                class_group=result.class_group,
                defaults={"mark": result.mark}
            )

    return JsonResponse({
        "message": "Bulk upload completed",
        "errors": [f"Row {e['row']}: {e['error']}" for e in errors]
    }, status=201)

TERM_MAPPING = {"1": "Term 1", "2": "Term 2", "3": "Term 3"}

@login_required
def download_result_template(request):
    """Generates a dynamic CSV or Excel template for bulk result uploads."""
    file_format = request.GET.get("file_format", "csv")
    class_id = request.GET.get("class")
    subject_id = request.GET.get("subject")
    academic_year = request.GET.get("academic_year")
    term_code = request.GET.get("term")
    student_count = request.GET.get("student_count", "0")

    if not all([class_id, subject_id, academic_year, term_code]):
        return JsonResponse({"error": "Missing required query parameters"}, status=400)

    # Academic year format validation
    try:
        academic_year = int(academic_year)
        formatted_academic_year = f"{academic_year}/{academic_year + 1}"
    except ValueError:
        return JsonResponse({"error": "Invalid academic year format"}, status=400)

    # Term mapping
    term = TERM_MAPPING.get(term_code)
    if not term:
        return JsonResponse({"error": "Invalid term code"}, status=400)

    # Student count validation
    try:
        student_count = int(student_count)
        if student_count < 1:
            return JsonResponse({"error": "Student count must be at least 1"}, status=400)
    except ValueError:
        return JsonResponse({"error": "Invalid student count"}, status=400)

    # Fetch class group and subject
    try:
        class_group = ClassGroup.objects.select_related("department").get(id=class_id)
        subject = Subject.objects.get(id=subject_id, department=class_group.department)
    except (ClassGroup.DoesNotExist, Subject.DoesNotExist):
        return JsonResponse({"error": "Invalid class or subject"}, status=400)

    # 🔒 Permission check
    teacher = request.user.teacher_profile
    if not can_teacher_upload_result(teacher, class_group, subject):
        return JsonResponse({"error": "Unauthorized to generate template for this subject and class"}, status=403)

    class_name = class_group.name
    subject_name = subject.name

    headers = ["First Name", "Last Name", "Class", "Subject", "Academic Year", "Term", "Mark"]
    template_data = [
        ["", "", class_name, subject_name, formatted_academic_year, term, ""]
        for _ in range(student_count)
    ]

    if file_format == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="bulk_result_upload_template.csv"'

        writer = csv.writer(response)
        writer.writerow(headers)
        writer.writerows(template_data)
        return response

    elif file_format == "xlsx":
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="bulk_result_upload_template.xlsx"'

        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        for row in template_data:
            ws.append(row)
        wb.save(response)
        return response

    return JsonResponse({"error": "Invalid file format"}, status=400)


#------------------ RESULT MANAGEMENT -------------------


@login_required
def result_management(request):
    user = request.user
    teacher = getattr(user, "teacher_profile", None)

    if not teacher:
        return render(request, "results/no_access.html")

    result_qs = Result.objects.none()

    class_teacher_qs = ClassTeacher.objects.filter(teacher=teacher)
    if class_teacher_qs.exists():
        assigned_class = class_teacher_qs.first().assigned_class
        result_qs = Result.objects.filter(class_group=assigned_class)
    else:
        subject_teacher_qs = SubjectTeacher.objects.filter(teacher=teacher)
        if subject_teacher_qs.exists():
            filters = Q()
            for st in subject_teacher_qs:
                filters |= Q(subject=st.subject, class_group__in=st.assigned_classes.all(), teacher=user)
            result_qs = Result.objects.filter(filters)

    if not result_qs.exists():
        return render(request, "results/no_access.html")

    grouped_files = (
        result_qs
        .values("academic_year", "term", "class_group", "subject")
        .annotate(
            total=Count("id"),
            confirmed=Count("id", filter=Q(status="Submitted"))
        )
    )

    result_files = []
    for group in grouped_files:
        status = "Submitted" if group["total"] == group["confirmed"] else "Pending"
        class_group = ClassGroup.objects.get(id=group["class_group"])
        subject = Subject.objects.get(id=group["subject"])

        result_files.append({
            "academic_year": group["academic_year"],
            "term": group["term"],
            "class_group_id": class_group.id,
            "class_group_name": class_group.name,
            "subject_id": subject.id,
            "subject_name": subject.name,
            "status": status,
            "total_students": group["total"],
        })

    paginator = Paginator(result_files, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "teacher/result_management.html", {
        "page_obj": page_obj
    })


@login_required
def view_result_file(request, academic_year, term, class_group_id, subject_id):
    user = request.user
    teacher = getattr(user, "teacher_profile", None)
    if not teacher:
        return HttpResponseForbidden("Access denied.")

    class_group = get_object_or_404(ClassGroup, id=class_group_id)
    subject = get_object_or_404(Subject, id=subject_id)

    if ClassTeacher.objects.filter(teacher=teacher, assigned_class=class_group).exists():
        results = Result.objects.filter(
            academic_year=academic_year,
            term=term,
            class_group=class_group,
            subject=subject
        )
    elif SubjectTeacher.objects.filter(
        teacher=teacher,
        subject=subject,
        assigned_classes=class_group
    ).exists():
        results = Result.objects.filter(
            academic_year=academic_year,
            term=term,
            class_group=class_group,
            subject=subject,
            teacher=request.user
        )
    else:
        return HttpResponseForbidden("Unauthorized access.")

    return render(request, "teacher/view_result_file.html", {
        "results": results,
        "class_group": class_group,
        "subject": subject,
        "academic_year": academic_year,
        "term": term,
    })


@login_required
@require_POST
def confirm_result_file(request):
    academic_year = request.POST.get("academic_year")
    term = request.POST.get("term")
    class_group_id = request.POST.get("class_group_id")
    subject_id = request.POST.get("subject_id")

    teacher = getattr(request.user, "teacher_profile", None)
    if not teacher:
        return JsonResponse({"error": "Access denied"}, status=403)

    class_group = get_object_or_404(ClassGroup, id=class_group_id)
    subject = get_object_or_404(Subject, id=subject_id)

    if ClassTeacher.objects.filter(teacher=teacher, assigned_class=class_group).exists():
        result_qs = Result.objects.filter(
            academic_year=academic_year,
            term=term,
            class_group=class_group,
            subject=subject
        )
    elif SubjectTeacher.objects.filter(
        teacher=teacher,
        subject=subject,
        assigned_classes=class_group
    ).exists():
        result_qs = Result.objects.filter(
            academic_year=academic_year,
            term=term,
            class_group=class_group,
            subject=subject,
            teacher=request.user
        )
    else:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    updated = result_qs.update(status="Submitted")
    return JsonResponse({"message": f"{updated} result(s) confirmed."}, status=200)


@login_required
@require_POST
def delete_result_file(request):
    academic_year = request.POST.get("academic_year")
    term = request.POST.get("term")
    class_group_id = request.POST.get("class_group_id")
    subject_id = request.POST.get("subject_id")

    teacher = getattr(request.user, "teacher_profile", None)
    if not teacher:
        return JsonResponse({"error": "Access denied"}, status=403)

    class_group = get_object_or_404(ClassGroup, id=class_group_id)
    subject = get_object_or_404(Subject, id=subject_id)

    if ClassTeacher.objects.filter(teacher=teacher, assigned_class=class_group).exists():
        result_qs = Result.objects.filter(
            academic_year=academic_year,
            term=term,
            class_group=class_group,
            subject=subject
        )
    elif SubjectTeacher.objects.filter(
        teacher=teacher,
        subject=subject,
        assigned_classes=class_group
    ).exists():
        result_qs = Result.objects.filter(
            academic_year=academic_year,
            term=term,
            class_group=class_group,
            subject=subject,
            teacher=request.user
        )
    else:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    deleted, _ = result_qs.delete()
    return JsonResponse({"message": f"{deleted} result(s) deleted permanently."}, status=200)
