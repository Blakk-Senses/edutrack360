# --- Standard Library ---
import json
from io import BytesIO
from collections import defaultdict

# --- Django Core ---
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST

# --- ReportLab for PDF ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
)

# --- Matplotlib for Charts ---
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import FigureCanvasPdf as FigureCanvas

# --- Internal App Imports ---
from core.models import (
    Notification, StudentMark, School,
)

User = get_user_model()

def circuit_overview(request):
    return render(request, 'dashboard/siso_dashboard.html')


@login_required
@user_passes_test(lambda u: u.role == "siso")  # Ensure only SISO can access
def get_notifications(request):
    siso = request.user  # Get the logged-in SISO
    notifications = Notification.objects.filter(recipient=siso, is_read=False).order_by("-created_at")

    data = [
        {
            "id": n.id,
            "message": n.message,
            "created_at": n.created_at.strftime("%Y-%m-%d %H:%M"),
            "is_read": n.is_read,
        }
        for n in notifications
    ]

    return JsonResponse({"notifications": data}, status=200)

@require_POST
@login_required
@user_passes_test(lambda u: u.role == "siso")
def mark_notification_as_read(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, recipient=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({"success": "Notification marked as read"}, status=200)
    except Notification.DoesNotExist:
        return JsonResponse({"error": "Notification not found"}, status=404)
    


@login_required
def notifications(request):
    user = request.user

    # Ensure only SISO users can access
    if not user.is_authenticated or user.role != "siso" or not user.circuit:
        return redirect("homepage")  # Redirect if unauthorized

    if request.method == 'POST':
        recipient_id = request.POST.get("recipient")  # Get recipient from form
        message = request.POST.get("message")

        if recipient_id == "all":
            # Send to all headteachers in the SISO's circuit
            headteachers = User.objects.filter(school__circuit=user.circuit, role="Headteacher")
            for headteacher in headteachers:
                Notification.objects.create(
                    sender=user,
                    recipient=headteacher,
                    message=message
                )
            messages.success(request, "Notification sent to all Headteachers!")
        else:
            # Send to a specific headteacher
            try:
                recipient = User.objects.get(id=recipient_id, role="Headteacher")
                Notification.objects.create(
                    sender=user,
                    recipient=recipient,
                    message=message
                )
                messages.success(request, f"Notification sent to {recipient.school.name}!")
            except User.DoesNotExist:
                messages.error(request, "Invalid recipient selection.")

        return redirect('siso:notifications')  # Redirect after sending

    # Fetch all notifications sent by this SISO
    notifications = Notification.objects.filter(sender=user).order_by('-created_at')

    return render(request, 'siso/notifications.html', {'notifications': notifications})



@login_required
def get_headteachers_by_circuit(request):
    """Fetch all headteachers in the SISO's circuit."""
    user = request.user

    # Ensure only SISO users can access
    if not user.is_authenticated or user.role != "siso" or not user.circuit:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    # Get headteachers in the SISO's circuit
    headteachers = User.objects.filter(school__circuit=user.circuit, role="headteacher")

    # Format data with full name
    headteachers_data = [
        {
            "id": ht.id,
            "name": f"{ht.first_name} {ht.last_name}" if ht.first_name and ht.last_name else ht.staff_id,  # Full name fallback to staff_id
            "school": ht.school.name
        }
        for ht in headteachers
    ]

    return JsonResponse({"headteachers": headteachers_data}, status=200)

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


def circuit_performance_analysis(request):
    context = get_circuit_performance_context(request)
    return render(request, 'siso/circuit_performance_analysis.html', context)


def get_circuit_performance_context(request):
    print("🔍 Starting circuit performance context generation...")

    # Load filters
    filter_options = json.loads(get_available_terms(request).content)
    academic_year = request.GET.get("academic_year", "").strip()
    selected_term = request.GET.get("term", "all")

    valid_years = [year["name"] for year in filter_options["academic_years"]]
    academic_year = academic_year if academic_year in valid_years else filter_options["selected_academic_year"]

    all_terms = [t["name"] for t in filter_options["terms"]]
    selected_term = selected_term if selected_term in all_terms else "Term 1"

    user = request.user
    if not hasattr(user, 'circuit') or user.role != 'siso':
        return redirect("homepage")

    schools_in_circuit = School.objects.filter(circuit=user.circuit)
    print(f"🏫 Schools found in circuit: {schools_in_circuit.count()}")

    selected_marks = StudentMark.objects.filter(
        student__school__in=schools_in_circuit,
        academic_year=academic_year,
        term=selected_term,
        subject__results__status="Submitted"
    ).select_related("student__school", "student__class_group", "subject")

    selected_marks = deduplicate_marks(selected_marks)

    print("🧾 Total submitted marks fetched:", len(selected_marks))

    school_departments = {}
    school_subject_averages = {}
    school_subjects = {}
    school_chart_data = {}

    for school in schools_in_circuit:
        school_marks = [m for m in selected_marks if m.student.school_id == school.id]

        dept_structure = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for mark in school_marks:
            subject = mark.subject
            class_name = mark.student.class_group.name
            for dept in subject.department.all():
                dept_structure[dept.name][subject.name][class_name].append(float(mark.mark))

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

        subjects = defaultdict(list)
        for mark in school_marks:
            subjects[mark.subject.name].append(float(mark.mark))
        for subject, marks in subjects.items():
            subjects[subject] = round(sum(marks) / len(marks), 2) if marks else "-"

        chart_data_per_school = {}
        for dept_name, dept_data in departments.items():
            subject_charts = []
            labels = dept_data["all_classes"]
            for subject_name, class_avg_dict in dept_data["subjects"].items():
                data = [class_avg_dict.get(class_name, 0) for class_name in labels]
                subject_charts.append({
                    "label": subject_name,
                    "data": data
                })
            chart_data_per_school[dept_name] = {
                "labels": labels,
                "datasets": subject_charts
            }

        school_departments[school.name] = departments
        school_subject_averages[school.name] = subject_averages
        school_subjects[school.name] = subjects
        school_chart_data[school.name] = chart_data_per_school

    print("📊 Per-school breakdowns and charts generated.")

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
        student__school__in=schools_in_circuit
    ).filter(q_terms, subject__results__status="Submitted").select_related("student", "subject")

    trend_marks = deduplicate_marks(trend_marks)

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
        "School": "Circuit",
        **{key: round(sum(v) / len(v), 2) if v else "-" for key, v in term_aggregates.items()}
    }

    academic_trend = {
        "School": "Circuit",
        **{year: round(sum(v) / len(v), 2) if v else "-" for year, v in year_aggregates.items()}
    }

    school_term_trends = {}
    for school in schools_in_circuit:
        school_marks = [m for m in trend_marks if m.student.school_id == school.id]
        aggregates = {key: [] for key in term_keys}
        for mark in school_marks:
            key = f"{mark.term} ({mark.academic_year})"
            if key in aggregates:
                aggregates[key].append(float(mark.mark))
        school_term_trends[school.name] = {
            "School": school.name,
            **{k: round(sum(v) / len(v), 2) if v else "-" for k, v in aggregates.items()}
        }

    term_labels = term_keys
    year_labels = academic_years

    term_values = [float(term_trend[k]) if isinstance(term_trend[k], (int, float)) else None for k in term_labels]
    year_values = [float(academic_trend[y]) if isinstance(academic_trend[y], (int, float)) else None for y in year_labels]

    term_chart_datasets = [
        {
            "label": school_data["School"],
            "data": [school_data[k] if isinstance(school_data[k], (int, float)) else None for k in term_labels]
        }
        for school_data in school_term_trends.values()
    ]
    term_chart_datasets.append({
        "label": "Circuit",
        "data": term_values
    })

    print("✅ Circuit-wide trends generated successfully.")

    return {
        "school_departments": school_departments,
        "school_subject_averages": school_subject_averages,
        "school_subjects": school_subjects,
        "school_chart_data": school_chart_data,

        "term_trend": term_trend,
        "academic_trend": academic_trend,
        "school_term_trends": list(school_term_trends.values()),

        "term_chart": {
            "labels": term_labels,
            "datasets": term_chart_datasets
        },
        "year_chart": {
            "labels": year_labels,
            "datasets": [
                {
                    "label": "Circuit",
                    "data": year_values
                }
            ]
        },

        "terms": all_terms,
        "academic_years": valid_years,
        "selected_year": academic_year,
        "selected_term": selected_term,
    }


def deduplicate_marks(marks_queryset):
    seen = set()
    result = []
    for m in marks_queryset:
        key = (m.student.id, m.subject.id)
        if key not in seen:
            seen.add(key)
            result.append(m)
    return result


@login_required
def download_circuit_performance_pdf(request):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=120, bottomMargin=50)
    elements = []
    styles = getSampleStyleSheet()
    subtitle_style = styles['Heading4']

    # Get circuit-wide performance context
    context = get_circuit_performance_context(request)
    academic_year = context['selected_year']
    term = context['selected_term']
    school_departments = context['school_departments']
    term_trend = context['term_trend']
    academic_trend = context['academic_trend']
    circuit_name = f"Circuit: {request.user.circuit.name}"

    # --- Helper functions for trend tables ---
    def wrap_labels_and_values(data_dict):
        keys = list(data_dict.keys())
        values = [str(v) for v in data_dict.values()]
        return [keys, values]

    def get_fixed_col_widths(data_dict):
        keys = list(data_dict.keys())
        widths = []
        for key in keys:
            length = len(str(key))
            width = 200 if "Circuit" in str(key) else max(60, length * 6)  # Increased width for Circuit name
            widths.append(width)
        return widths

    # --- School-wise Tables + Charts ---
    for school_name, dept_data in school_departments.items():
        elements.append(Paragraph(f"School: {school_name}", subtitle_style))
        for dept, dept_info in dept_data.items():
            elements.append(Paragraph(f"{dept} Department", subtitle_style))
            table_data = [["Subject"] + dept_info["all_classes"]]

            for subject, class_scores in dept_info["subjects"].items():
                row = [subject] + [class_scores.get(cls, "-") for cls in dept_info["all_classes"]]
                table_data.append(row)

            max_cols = len(dept_info["all_classes"]) + 1
            col_widths = [100] + [(A4[0] - 120) / (max_cols - 1)] * (max_cols - 1)

            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ]))
            elements.extend([table, Spacer(1, 10)])

            # Generating chart for the department
            class_names = dept_info["all_classes"]
            subjects = list(dept_info["subjects"].keys())
            data = []
            for cls in class_names:
                row = [dept_info["subjects"][subj].get(cls, 0) or 0 for subj in subjects]
                data.append(row)

            try:
                if data and any(any(v > 0 for v in row) for row in data):
                    fig, ax = plt.subplots(figsize=(8, 4))
                    x = range(len(subjects))
                    width = 0.8 / len(data)

                    for i, row in enumerate(data):
                        offset = i * width
                        ax.bar([pos + offset for pos in x], row, width, label=class_names[i])

                    ax.set_xticks([pos + width * (len(data) / 2) for pos in x])
                    ax.set_xticklabels(subjects, rotation=45, ha='right')
                    ax.set_ylabel('Average Score')
                    ax.set_title(f"{dept} Department Class-wise Subject Performance")
                    ax.legend()

                    img_buffer = BytesIO()
                    plt.tight_layout()
                    canvas = FigureCanvas(fig)
                    canvas.print_png(img_buffer)
                    plt.close(fig)

                    img_buffer.seek(0)
                    img = Image(img_buffer, width=480, height=240)
                    elements.extend([img, Spacer(1, 20)])

            except Exception as e:
                print(f"Error generating chart for {school_name} - {dept}: {e}")
                elements.append(Paragraph(f"Error generating chart for {dept} department.", styles['Normal']))

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
    def draw_custom_header(c, circuit_name, academic_year, term):
        page_width, page_height = A4
        banner_color = colors.HexColor("#f2f2f2")
        text_color = colors.black

        c.setFillColor(banner_color)
        c.rect(0, page_height - 60, page_width, 60, fill=1, stroke=0)
        c.setFillColor(text_color)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(page_width / 2, page_height - 35, "Circuit Performance Report")

        c.setFont("Helvetica", 12)
        c.drawCentredString(page_width / 2, page_height - 52, f"Circuit: {circuit_name}")

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
        onFirstPage=lambda c, d: [draw_custom_header(c, request.user.circuit.name, academic_year, term), draw_footer(c, d)],
        onLaterPages=draw_footer
    )

    buffer.seek(0)
    safe_year = str(academic_year).replace("/", "_")
    filename = f"{request.user.circuit.name}_Circuit_Performance_{safe_year}_{term}.pdf"

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename={filename}"
    return response
