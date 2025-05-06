# --- Standard Library ---
import csv
import json
import os
from io import BytesIO
from collections import defaultdict
import logging

# --- Django Core ---
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.validators import validate_email
from django.http import (
    HttpResponse, JsonResponse
)
from django.shortcuts import (
    render, redirect, get_object_or_404
)
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Q

# --- Third-party Libraries ---
import pandas as pd
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
)

# --- Internal Imports ---
from core.models import (
    District, Notification,School, ResultUploadDeadline, 
    Circuit, StudentMark, Department
)
from core.forms import (
    AddSchoolForm,
)

logger = logging.getLogger(__name__)


User = get_user_model()


#------------------------------- SISO MANAGEMENT -------------------------

@login_required
def create_circuit(request):
    if request.user.role != 'cis':
        return JsonResponse({"success": False, "message": "You do not have the required permission."}, status=403)

    if request.method == 'POST':
        # Get circuit name and SISO ID from the request
        circuit_name = request.POST.get('name')
        siso_id = request.POST.get('siso_id', None)

        if not circuit_name:
            return JsonResponse({"success": False, "message": "Circuit name is required."}, status=400)

        district = request.user.district

        # Check if a SISO was provided and fetch the user
        siso = None
        if siso_id:
            siso = get_object_or_404(User, id=siso_id, role='siso', district=district)

        # Create the new Circuit
        new_circuit = Circuit(name=circuit_name, district=district, siso=siso)

        try:
            new_circuit.save()  # This will call clean() and validate
            return JsonResponse({"success": True, "message": "Circuit created successfully!", "circuit_id": new_circuit.id})
        except ValidationError as e:
            return JsonResponse({"success": False, "message": str(e)}, status=400)

    return JsonResponse({"success": False, "message": "Invalid request method."}, status=400)


@login_required
def assign_siso(request):
    if request.user.role != 'cis':
        return JsonResponse({"success": False, "message": "You do not have the required permission."}, status=403)

    if request.method == 'POST':
        circuit_id = request.POST.get('circuit')
        siso_id = request.POST.get('siso')

        try:
            # Get the circuit and siso objects
            circuit = Circuit.objects.get(id=circuit_id, district=request.user.district)
            siso = request.user.__class__.objects.get(id=siso_id, role='siso', district=request.user.district)

            # Check if the SISO is already assigned to another circuit
            if circuit.siso:
                return JsonResponse({"success": False, "message": f"The SISO {siso.first_name} {siso.last_name} is already assigned to another circuit."}, status=400)

            # Assign the SISO to the circuit
            circuit.siso = siso
            circuit.save()

            return JsonResponse({"success": True, "message": f"SISO {siso.first_name} {siso.last_name} has been successfully assigned to {circuit.name} Circuit."})

        except Circuit.DoesNotExist:
            return JsonResponse({"success": False, "message": "Circuit not found or doesn't belong to your district."}, status=404)

        except request.user.__class__.DoesNotExist:
            return JsonResponse({"success": False, "message": "SISO not found or doesn't belong to your district."}, status=404)

    return JsonResponse({"success": False, "message": "Invalid request method."}, status=400)


@login_required
def reassign_siso(request):
    if request.method == 'POST':
        # Retrieve the SISO and circuit info from POST
        siso_id = request.POST.get('siso')
        new_circuit_id = request.POST.get('new_circuit')

        # Fetch the SISO and new circuit objects
        siso = get_object_or_404(User, id=siso_id, role='siso', district=request.user.district)
        new_circuit = get_object_or_404(Circuit, id=new_circuit_id, district=request.user.district)

        # Check if the SISO is already assigned to a different circuit
        old_circuit = siso.assigned_circuit

        try:
            if old_circuit:
                # Seize SISO from old circuit by setting it to None
                old_circuit.siso = None
                old_circuit.save()

            # Reassign the SISO to the new circuit
            new_circuit.siso = siso
            new_circuit.save()

            return JsonResponse({"success": True, "message": f"SISO {siso.first_name} {siso.last_name} has been successfully reassigned to {new_circuit.name} Circuit."})
        
        except Exception as e:
            return JsonResponse({"success": False, "message": f"An error occurred while reassigning the SISO: {str(e)}"})

    return JsonResponse({"success": False, "message": "Invalid request method."})



def siso_management(request):
    return render(request, 'cis/siso_management.html')

#------------------------ API ENDPOINTS -------------------------------
# views.py
@login_required
def get_user_circuits(request):
    if hasattr(request.user, 'district'):
        circuits = Circuit.objects.filter(district=request.user.district)
        data = [{"id": c.id, "name": c.name} for c in circuits]  # No 'code' key here
        return JsonResponse(data, safe=False)
    return JsonResponse([], safe=False)


@login_required
def get_siso_current_circuit(request, siso_id):
    siso = get_object_or_404(User, id=siso_id, role='siso', district=request.user.district)
    current_circuit = siso.assigned_circuit

    if current_circuit:
        return JsonResponse({"id": current_circuit.id, "name": current_circuit.name})
    else:
        return JsonResponse({"id": None, "name": "No circuit assigned"})

@login_required
def get_user_sisos(request):
    if hasattr(request.user, 'district'):
        sisos = User.objects.filter(role='siso', district=request.user.district)
        data = [{"id": siso.id, "first_name": siso.first_name, "last_name": siso.last_name} for siso in sisos]
        return JsonResponse({"sisos": data}, safe=False)
    return JsonResponse({"sisos": []}, safe=False)



def fetch_circuits_and_schools(request, district_id):
    try:
        district = District.objects.get(id=district_id)
        data = [
            {
                "id": circuit.id,
                "name": circuit.name,
                "schools": [{"id": school.id, "name": school.name} for school in circuit.schools.all()]
            }
            for circuit in district.circuits.all()
        ]
        return JsonResponse({"district": district.name, "circuits": data}, safe=False)
    except District.DoesNotExist:
        return JsonResponse({"error": "District not found"}, status=404)


#-------------- SCHOOL MANAGEMENT ----------------------

def school_management(request):
    return render(request, 'cis/school_management.html')

@login_required
@require_POST
def manual_school_upload(request):
    form = AddSchoolForm(request.POST, request=request)

    if form.is_valid():
        # Save the school instance (but hold off on M2M until later)
        school = form.save(commit=False)
        school.district = request.user.district
        school.circuit = form.cleaned_data["circuit"]
        school.save()

        # Save the many-to-many relationship (e.g., departments)
        form.save_m2m()

        return JsonResponse({"success": True, "message": "School created successfully!"})
    
    return JsonResponse({"success": False, "errors": form.errors}, status=400)


@login_required
def bulk_upload_schools(request):
    """Handles bulk school + headteacher upload via CSV or Excel."""
    if request.method == "POST" and request.FILES.get("file"):
        file = request.FILES["file"]
        file_extension = os.path.splitext(file.name)[1].lower()

        if file_extension not in [".csv", ".xls", ".xlsx"]:
            return JsonResponse({
                "success": False,
                "error": "Invalid file type! Only .csv, .xls, and .xlsx are allowed."
            }, status=400)

        file_path = default_storage.save(f"uploads/{file.name}", file)
        df = load_file(file_extension, default_storage.path(file_path))

        if df is None:
            return JsonResponse({
                "success": False,
                "error": "Error reading the file. Ensure it's a valid CSV or Excel."
            }, status=400)

        try:
            schools_created, skipped_entries = process_bulk_schools(df, request.user)
        except ValueError as ve:
            return JsonResponse({
                "success": False,
                "error": str(ve)
            }, status=400)

        if skipped_entries:
            return JsonResponse({
                "success": False,
                "error": f"Some rows were skipped: {', '.join(skipped_entries)}"
            }, status=400)

        return JsonResponse({
            "success": True,
            "message": f"{schools_created} schools uploaded successfully!",
            "skipped_entries": skipped_entries
        })

    return JsonResponse({"success": False, "error": "Invalid request"}, status=400)


def load_file(file_extension, file_path):
    """Load file (CSV or Excel) into a pandas DataFrame."""
    try:
        if file_extension == ".csv":
            df = pd.read_csv(file_path, dtype=str)
        elif file_extension in [".xls", ".xlsx"]:
            df = pd.read_excel(file_path, dtype=str)

        df.columns = [col.strip().lower() for col in df.columns]
        return df
    except Exception as e:
        print(f"Error loading file: {str(e)}")
        return None


def validate_school_row(row, circuit_lookup, password1, password2, row_num):
    required_fields = [
        "school_name", "school_code", "circuit_name", "departments",
        "headteacher_staff_id", "headteacher_first_name", "headteacher_last_name",
        "headteacher_license_number", "headteacher_email", "headteacher_phone_number"
    ]
    for field in required_fields:
        if not str(row[field]).strip():
            return f"Row {row_num}: Missing required field ({field})."

    try:
        validate_email(row["headteacher_email"])
    except ValidationError:
        return f"Row {row_num}: Invalid email format ({row['headteacher_email']})."

    circuit_name = str(row["circuit_name"]).strip().lower()
    if circuit_name not in circuit_lookup:
        return f"Row {row_num}: Invalid or unrecognized circuit name ({circuit_name})."

    phone = str(row["headteacher_phone_number"]).strip()
    if not phone.isdigit() or len(phone) < 10:
        return f"Row {row_num}: Invalid phone number ({phone})."

    if password1 != password2:
        return f"Row {row_num}: Passwords do not match."
    if len(password1) < 8:
        return f"Row {row_num}: Password too short."

    return None


def process_bulk_schools(df, user):
    required_columns = [
        "school_name", "school_code", "circuit_name", "departments",
        "headteacher_staff_id", "headteacher_first_name", "headteacher_last_name",
        "headteacher_license_number", "headteacher_email", "headteacher_phone_number",
        "password1", "password2"
    ]

    if not all(col in df.columns for col in required_columns):
        raise ValueError("Invalid file format. Please use the provided template.")

    df = df.fillna("")

    schools_created = 0
    skipped_entries = []

    
    existing_school_codes = set(School.objects.values_list("school_code", flat=True))
    existing_headteacher_emails = set(User.objects.values_list("email", flat=True))

    
    circuits = Circuit.objects.filter(district=user.district)
    circuit_lookup = {c.name.strip().lower(): c for c in circuits}
    all_departments = {d.name.strip().lower(): d for d in Department.objects.all()}

    for index, row in df.iterrows():
        row_num = index + 2
        

        try:
            school_code = str(row["school_code"]).strip()
            email = str(row["headteacher_email"]).strip().lower()
            password1 = str(row["password1"]).strip()
            password2 = str(row["password2"]).strip()
            circuit_name = str(row["circuit_name"]).strip().lower()
            department_names = str(row.get("departments", "")).strip()

            if school_code in existing_school_codes or email in existing_headteacher_emails:
                msg = f"Row {row_num}: Duplicate school code ({school_code}) or email ({email})."
                
                skipped_entries.append(msg)
                continue

            

            error = validate_school_row(row, circuit_lookup, password1, password2, row_num)
            if error:
                
                skipped_entries.append(error)
                continue

            school = School.objects.create(
                name=row["school_name"].strip(),
                school_code=school_code,
                circuit=circuit_lookup[circuit_name],
                district=user.district
            )

            if department_names:
                try:
                    dept_list = [name.strip().lower() for name in department_names.split(",")]
                    matched_departments = [all_departments[name] for name in dept_list if name in all_departments]
                    if matched_departments:
                        
                        school.department.set(matched_departments)
                    else:
                        msg = f"Row {row_num}: No valid departments found in '{department_names}'."

                        school.delete()
                        skipped_entries.append(msg)
                        continue
                except Exception as e:
                    msg = f"Row {row_num}: Error processing departments - {str(e)}"
                    school.delete()
                    skipped_entries.append(msg)
                    continue
            else:
                msg = f"Row {row_num}: Departments column is empty."
                school.delete()
                skipped_entries.append(msg)
                continue

            headteacher = User.objects.create(
                staff_id=row["headteacher_staff_id"].strip(),
                first_name=row["headteacher_first_name"].strip(),
                last_name=row["headteacher_last_name"].strip(),
                license_number=row["headteacher_license_number"].strip(),
                email=email,
                phone_number=row["headteacher_phone_number"].strip(),
                role="headteacher",
                district=school.district,
                circuit=school.circuit,
                school=school,
                password=make_password(password1)
            )

            school.headteacher = headteacher
            school.save()

            schools_created += 1

        except Exception as e:
            msg = f"Row {row_num}: Unexpected error - {str(e)}"
            try:
                school.delete()
            except:
                pass
            skipped_entries.append(msg)

    return schools_created, skipped_entries



@login_required
def download_school_template(request, file_format):
    headers = [
        "school_name",
        "school_code",
        "circuit_name",
        "departments",  # New column added
        "headteacher_staff_id",
        "headteacher_first_name",
        "headteacher_last_name",
        "headteacher_license_number",
        "headteacher_email",
        "headteacher_phone_number",
        "password1",
        "password2"
    ]

    if file_format == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="bulk_school_upload_template.csv"'

        writer = csv.writer(response)
        writer.writerow(headers)
        return response

    elif file_format == "excel":
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="bulk_school_upload_template.xlsx"'

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "School Upload Template"
        sheet.append(headers)

        workbook.save(response)
        return response

    return HttpResponse("Invalid file format requested", status=400)


# -------------- API ENDPOINTS ------------------------

@login_required
def get_departments(request):
    departments = Department.objects.all().values("id", "name")
    return JsonResponse(list(departments), safe=False)


@login_required
def get_schools(request):
    user = request.user

    # Ensure only CIS users can access this
    if not hasattr(user, 'district') or not user.role.lower() == 'cis':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    # Filter schools by user's district
    schools = School.objects.filter(circuit__district=user.district).values('id', 'name')

    return JsonResponse(list(schools), safe=False)

@login_required
def get_roles(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    roles = [
        {'id': role[0], 'name': role[1]} for role in User.ROLE_CHOICES
    ]
    return JsonResponse({'roles': roles})

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


#------------------- PERFORMANCE ANALYSIS -----------------------------------

def district_performance_analysis(request):
    context = get_district_performance_context(request)
    return render(request, 'cis/district_performance_analysis.html', context)

def get_district_performance_context(request):
    """Generates district-wide performance analysis for CIS by aggregating circuit-level reports."""

    print("🔍 Starting district performance context generation...")

    # Load filters
    filter_options = json.loads(get_available_terms(request).content)
    academic_year = request.GET.get("academic_year", "").strip()
    selected_term = request.GET.get("term", "all")
    circuit_id = request.GET.get("circuit_id", "all")

    valid_years = [year["name"] for year in filter_options["academic_years"]]
    academic_year = academic_year if academic_year in valid_years else filter_options["selected_academic_year"]

    all_terms = [t["name"] for t in filter_options["terms"]]
    selected_term = selected_term if selected_term in all_terms else "Term 1"

    user = request.user
    if not hasattr(user, 'district') or user.role != 'cis':
        return redirect("homepage")

    circuits_in_district = Circuit.objects.filter(district=user.district)
    available_circuits = [{"id": c.id, "name": c.name} for c in circuits_in_district]

    if circuit_id == "all":
        circuits_to_analyze = circuits_in_district
    else:
        circuits_to_analyze = circuits_in_district.filter(id=circuit_id)

    print(f"🧭 Circuits selected for analysis: {circuits_to_analyze.count()}")

    circuit_analyses = []

    for circuit in circuits_to_analyze:
        print(f"\n📍 Analyzing Circuit: {circuit.name}")
        schools_in_circuit = School.objects.filter(circuit=circuit)

        selected_marks = StudentMark.objects.filter(
            student__school__in=schools_in_circuit,
            academic_year=academic_year,
            term=selected_term,
            subject__results__status="Submitted"
        ).select_related("student__school", "student__class_group", "subject")

        selected_marks = deduplicate_marks(selected_marks)

        school_departments = {}
        school_subject_averages = {}
        school_subjects = {}
        school_score_buckets = {}
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

            all_scores = [score for score in subjects.values() if isinstance(score, (int, float))]
            score_buckets = {
                "80-100": sum(1 for s in all_scores if s >= 80),
                "55-79": sum(1 for s in all_scores if 55 <= s < 80),
                "50-54": sum(1 for s in all_scores if 50 <= s < 55),
                "40-49": sum(1 for s in all_scores if 40 <= s < 50),
                "0-39":  sum(1 for s in all_scores if s < 40),
            }

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
            school_score_buckets[school.name] = score_buckets
            school_chart_data[school.name] = chart_data_per_school

        # === Trend Data ===
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
            "Circuit": circuit.name,
            **{key: round(sum(v) / len(v), 2) if v else "-" for key, v in term_aggregates.items()}
        }
        academic_trend = {
            "Circuit": circuit.name,
            **{year: round(sum(v) / len(v), 2) if v else "-" for year, v in year_aggregates.items()}
        }

        term_labels = list(term_trend.keys())[1:]
        term_values = [float(val) if isinstance(val, (int, float)) else None for val in list(term_trend.values())[1:]]
        year_labels = list(academic_trend.keys())[1:]
        year_values = [float(val) if isinstance(val, (int, float)) else None for val in list(academic_trend.values())[1:]]

        circuit_analyses.append({
            "name": circuit.name,
            "school_departments": school_departments,
            "school_subject_averages": school_subject_averages,
            "school_subjects": school_subjects,
            "school_score_buckets": school_score_buckets,
            "school_chart_data": school_chart_data,
            "term_trend": term_trend,
            "academic_trend": academic_trend,
            "term_chart": {"labels": term_labels, "data": term_values},
            "year_chart": {"labels": year_labels, "data": year_values},
        })

    print("✅ District-level analysis complete.")

    return {
        "circuits": circuit_analyses,
        "filters": {
            "terms": all_terms,
            "academic_years": valid_years,
            "selected_year": academic_year,
            "selected_term": selected_term,
            "selected_circuit": circuit_id,
            "available_circuits": available_circuits
        },
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
def download_district_performance_pdf(request):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=120, bottomMargin=50)
    elements = []
    styles = getSampleStyleSheet()
    subtitle_style = styles['Heading4']

    # Get district-wide performance context
    context = get_district_performance_context(request)
    academic_year = context['filters']['selected_year']
    term = context['filters']['selected_term']
    circuits = context['circuits']
    district_name = f"District: {request.user.district.name}"

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
            width = 200 if "District" in str(key) else max(60, length * 6)  # Increased width for District name
            widths.append(width)
        return widths

    # --- Circuit and School Name Styles ---
    circuit_style = ParagraphStyle(
        "CircuitName",
        parent=styles['Normal'],
        fontName='Helvetica-Bold',  # Bold font
        fontSize=14,
        textColor=colors.black,
        alignment=1,  # Centered
        spaceAfter=6
    )

    school_style = ParagraphStyle(
        "SchoolName",
        parent=styles['Normal'],
        fontName='Helvetica-Bold',  # Bold font
        fontSize=12,
        textColor=colors.black,
        alignment=0,  # Align left
        spaceAfter=6,
        underline=True  # Underlined
    )

    # --- Circuit-wise Tables ---
    for circuit_analysis in circuits:
        circuit_name = circuit_analysis['name']
        school_departments = circuit_analysis['school_departments']
        term_trend = circuit_analysis['term_trend']
        academic_trend = circuit_analysis['academic_trend']

        # Add Circuit Name centered and bolded
        elements.append(Paragraph(f"<b>{circuit_name}</b>", circuit_style))

        # School-wise tables for each circuit
        for school_name, dept_data in school_departments.items():
            # Add School Name underlined and bolded
            elements.append(Paragraph(f"<u>{school_name}</u>", school_style))
            for dept, dept_info in dept_data.items():
                elements.append(Paragraph(f"{dept}", subtitle_style))
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
    def draw_custom_header(c, district_name, academic_year, term):
        page_width, page_height = A4
        banner_color = colors.HexColor("#f2f2f2")
        text_color = colors.black

        c.setFillColor(banner_color)
        c.rect(0, page_height - 60, page_width, 60, fill=1, stroke=0)
        c.setFillColor(text_color)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(page_width / 2, page_height - 35, "District Performance Report")

        c.setFont("Helvetica", 12)
        c.drawCentredString(page_width / 2, page_height - 52, f"District: {district_name}")

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
        onFirstPage=lambda c, d: [draw_custom_header(c, request.user.district.name, academic_year, term), draw_footer(c, d)],
        onLaterPages=draw_footer
    )

    buffer.seek(0)
    safe_year = str(academic_year).replace("/", "_")
    filename = f"{request.user.district.name}_District_Performance_{safe_year}_{term}.pdf"

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename={filename}"
    return response


#--------------------- USER MANAGEMENT ----------------------

def user_management(request):
    return render(request, 'cis/user_management.html')

logger = logging.getLogger(__name__)


@login_required
def user_search(request):
    user = request.user
    print(f"Authenticated user: {user}, Role: {user.role}")

    if user.role != 'cis':
        print("Permission denied: user is not a CIS.")
        return JsonResponse({"success": False, "message": "Permission Denied"}, status=403)

    if request.method == 'POST':
        print("POST request received.")

        # Case 1: Searching for a user by staff_id
        if 'staff_id' in request.POST and 'role_change' not in request.POST:
            print("User search request detected.")
            try:
                staff_id = int(request.POST.get('staff_id'))
                print(f"Searching for user with staff ID: {staff_id}")
            except (TypeError, ValueError):
                print("Invalid staff ID received.")
                return JsonResponse({"success": False, "message": "Invalid staff ID."}, status=400)

            try:
                searched_user = User.objects.get(staff_id=staff_id, district=user.district)
                print(f"User found: {searched_user}")
                circuits = Circuit.objects.filter(district=user.district)
                schools = School.objects.filter(district=user.district)

                return JsonResponse({
                    'success': True,
                    'searched_user': {
                        'staff_id': searched_user.staff_id,
                        'license_number': searched_user.license_number,
                        'first_name': searched_user.first_name,
                        'last_name': searched_user.last_name,
                        'email': searched_user.email,
                        'phone_number': searched_user.phone_number,
                        'role': searched_user.role,
                    },
                    'available_options': {
                        'circuits': list(circuits.values('id', 'name')),
                        'schools': list(schools.values('id', 'name')),
                    },
                })

            except User.DoesNotExist:
                print(f"No user found with staff ID {staff_id} in district {user.district}")
                return JsonResponse({"success": False, "message": "User not found in your district."}, status=404)

        # Case 2: Updating user role and assignments
        elif 'role_change' in request.POST:
            print("Role change request detected.")

            staff_id = request.POST.get('staff_id')
            new_role = request.POST.get('role')
            new_circuit_id = request.POST.get('circuit')
            new_school_id = request.POST.get('school')

            print(f"Received role change for staff ID {staff_id} to role {new_role}")
            print(f"Circuit ID: {new_circuit_id}, School ID: {new_school_id}")

            if not staff_id or not new_role:
                print("Missing required fields for role change.")
                return JsonResponse({"success": False, "message": "Missing required fields."}, status=400)

            try:
                target_user = User.objects.get(staff_id=staff_id, district=user.district)
                print(f"Target user for update found: {target_user}")
            except User.DoesNotExist:
                print("User not found for role update.")
                return JsonResponse({"success": False, "message": "User not found in your district."}, status=404)

            # 🔁 Clean up old role associations before assigning new role
            if target_user.role == 'siso' and target_user.circuit:
                old_circuit = target_user.circuit
                if old_circuit.siso == target_user:
                    old_circuit.siso = None
                    old_circuit.save()
                    print(f"Removed user from old circuit's siso: {old_circuit}")

            if target_user.role == 'headteacher' and target_user.school:
                old_school = target_user.school
                if old_school.headteacher == target_user:
                    old_school.headteacher = None
                    old_school.save()
                    print(f"Removed user from old school's headteacher: {old_school}")

            # Role-specific logic
            if new_role == 'siso':
                if not new_circuit_id:
                    print("Missing circuit ID for SISO assignment.")
                    return JsonResponse({"success": False, "message": "SISO must be assigned to a circuit."}, status=400)
                try:
                    circuit = Circuit.objects.get(id=new_circuit_id, district=user.district)
                    target_user.circuit = circuit
                    target_user.school = None

                    # Assign user as the new SISO
                    circuit.siso = target_user
                    circuit.save()

                except Circuit.DoesNotExist:
                    print("Invalid circuit ID.")
                    return JsonResponse({"success": False, "message": "Invalid circuit for your district."}, status=400)

            elif new_role == 'headteacher':
                if not new_school_id:
                    print("Missing school ID for Headteacher assignment.")
                    return JsonResponse({"success": False, "message": "Headteacher must be assigned to a school."}, status=400)
                try:
                    school = School.objects.get(id=new_school_id, district=user.district)
                    target_user.school = school
                    target_user.circuit = None

                    # Assign user as the new headteacher
                    school.headteacher = target_user
                    school.save()

                except School.DoesNotExist:
                    print("Invalid school ID.")
                    return JsonResponse({"success": False, "message": "Invalid school for your district."}, status=400)

            else:
                print(f"Role {new_role} does not require a school or circuit.")
                target_user.circuit = None
                target_user.school = None

            target_user.role = new_role
            target_user.save()
            print(f"User role updated successfully: {target_user}")

            return JsonResponse({
                "success": True,
                "message": "User role and assignments updated successfully.",
                "updated_user": {
                    "staff_id": target_user.staff_id,
                    "role": target_user.role,
                    "circuit": target_user.circuit.name if target_user.circuit else None,
                    "school": target_user.school.name if target_user.school else None,
                }
            })

        print("POST request did not match any handled operation.")
        return JsonResponse({"success": False, "message": "Invalid POST data."}, status=400)

    print("Request method was not POST.")
    return JsonResponse({"success": False, "message": "Invalid request method."}, status=400)


@login_required
def create_user(request):
    print("[DEBUG] Request method:", request.method)
    print("[DEBUG] Logged-in user:", request.user)
    print("[DEBUG] User ID:", request.user.id)
    print("[DEBUG] User role:", request.user.role if hasattr(request.user, 'role') else "No role")
    print("[DEBUG] User district:", getattr(request.user, 'district', None))
    print("[DEBUG] User school:", getattr(request.user, 'school', None))
    print("[DEBUG] User circuit:", getattr(request.user, 'circuit', None))

    # Ensure the logged-in user has necessary attributes
    if not hasattr(request.user, 'district') or not hasattr(request.user, 'school') or not hasattr(request.user, 'circuit'):
        print("[ERROR] User is missing required attributes (district, school, circuit)")
        return JsonResponse({"success": False, "message": "User does not have required attributes."}, status=400)

    if request.method == "POST":
        print("[DEBUG] Request.POST data:", request.POST)

        # Get the POST data
        district_id = request.POST.get('district')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')
        staff_id = request.POST.get('staff_id')
        license_number = request.POST.get('license_number')
        role = request.POST.get('role')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        

        # Validate password match
        if password1 != password2:
            return JsonResponse({"success": False, "message": "Passwords do not match."}, status=400)

        # Retrieve district by ID
        try:
            district = District.objects.get(id=district_id)
        except ValueError:
            # Try to fallback to name if ID fails
            try:
                district = District.objects.get(name=district_id)
            except District.DoesNotExist:
                return JsonResponse({"success": False, "message": "Invalid district."}, status=400)

        # Validate role and handle required fields
        if role not in ['headteacher', 'siso', 'teacher']:
            return JsonResponse({"success": False, "message": "Invalid role selected."}, status=400)

        if role == 'headteacher' and not request.POST.get('school'):
            return JsonResponse({"success": False, "message": "School is required for Headteacher role."}, status=400)

        if role == 'siso' and not request.POST.get('circuit'):
            return JsonResponse({"success": False, "message": "Circuit is required for SISO role."}, status=400)

        # Create user
        user = User(
            staff_id=staff_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            license_number=license_number,
            district=district,  # Assign district
            role=role,  # Assign role
        )
        user.set_password(password1)

        # Handle user roles and assignments
        if role == 'headteacher':
            school_id = request.POST.get('school')
            try:
                school = School.objects.get(id=school_id)
                user.school = school
                user.circuit = school.circuit
            except School.DoesNotExist:
                return JsonResponse({"success": False, "message": "Invalid school."}, status=400)

        elif role == 'siso':
            circuit_id = request.POST.get('circuit')
            try:
                circuit = Circuit.objects.get(id=circuit_id, district=district)
                user.circuit = circuit
            except Circuit.DoesNotExist:
                return JsonResponse({"success": False, "message": "Invalid circuit."}, status=400)

        elif role == 'teacher':
            user.school = request.user.school
            user.circuit = request.user.circuit

        try:
            # Save the user to the database
            user.save()

            # Assign reverse role references if necessary
            if role == 'headteacher' and user.school:
                user.school.headteacher = user
                user.school.save()
            elif role == 'siso' and user.circuit:
                user.circuit.siso = user
                user.circuit.save()

            return JsonResponse({"success": True, "message": "User registered successfully!"})

        except ValidationError as e:
            return JsonResponse({"success": False, "message": f"Validation error: {str(e)}"}, status=400)

    print("[WARNING] Invalid request method.")
    return JsonResponse({"success": False, "message": "Invalid request method."}, status=400)


#------------------------ NOTIFICATIONS -------------------------------

@login_required
def send_notification(request):
    return render(request, 'cis/send_notifications.html')
    

@login_required
@require_http_methods(["GET", "POST"])
def set_result_upload_deadline(request):
    user = request.user

    # Ensure the user has the correct role
    if user.role != 'cis':
        if request.method == "POST":
            print(f"[DEBUG] Permission Denied: User role is not 'cis'.")
            return JsonResponse({"success": False, "message": "Permission Denied"}, status=403)
        print(f"[DEBUG] User role is not 'cis'. Redirecting to permission denied page.")
        return render(request, "cis/permission_denied.html")

    # 🎯 Use shared helper for filter options
    print("[DEBUG] Fetching filter options...")
    filter_options = json.loads(get_available_terms(request).content.decode("utf-8"))
    available_years = [year["name"] for year in filter_options.get("academic_years", [])]
    available_terms = [term["name"] for term in filter_options.get("terms", [])]

    print(f"[DEBUG] Available Years: {available_years}")
    print(f"[DEBUG] Available Terms: {available_terms}")

    # 🎯 Extract selected year/term with fallback
    academic_year = request.GET.get("academic_year")
    selected_year = academic_year if academic_year in available_years else filter_options.get("selected_academic_year", available_years[0] if available_years else None)

    term = request.GET.get("term")
    selected_term = term if term in available_terms else filter_options.get("selected_term", available_terms[0] if available_terms else None)

    print(f"[DEBUG] Selected Year from GET: {selected_year}")
    print(f"[DEBUG] Selected Term from GET: {selected_term}")

    # 🎯 Handle GET request for rendering the form
    if request.method == "GET":
        print("[DEBUG] Rendering GET response (form).")
        return render(request, "cis/send_notifications.html", {
            "available_years": available_years,
            "available_terms": available_terms,
            "selected_year": selected_year,
            "selected_term": selected_term
        })

    # 🎯 Handle POST request for form submission
    data = request.POST
    print(f"[DEBUG] POST Data: {data}")

    term = data.get("term")
    academic_year = data.get("academic_year")
    deadline_str = data.get("deadline_date")

    # 🎯 Debug POST data validation
    if not (term and academic_year and deadline_str):
        print("[DEBUG] Missing required fields in POST data.")
        return JsonResponse({"success": False, "message": "All fields are required."}, status=400)

    # 🎯 Parse deadline date
    deadline_date = parse_date(deadline_str)
    print(f"[DEBUG] Parsed Deadline Date: {deadline_date}")
    if not deadline_date:
        print("[DEBUG] Invalid deadline date format.")
        return JsonResponse({"success": False, "message": "Invalid date format."}, status=400)

    # 🎯 Use available terms and academic years for validation
    valid_term_names = available_terms
    valid_year_names = available_years

    print(f"[DEBUG] Valid Term Names: {valid_term_names}")
    print(f"[DEBUG] Valid Academic Year Names: {valid_year_names}")

    # 🎯 Ensure the selected term and academic year are valid
    if term not in valid_term_names:
        print(f"[DEBUG] Invalid term selected: {term}")
        return JsonResponse({"success": False, "message": f"Invalid term: {term}"}, status=400)

    if academic_year not in valid_year_names:
        print(f"[DEBUG] Invalid academic year selected: {academic_year}")
        return JsonResponse({"success": False, "message": f"Invalid academic year: {academic_year}"}, status=400)

    # 🎯 Handle district and deadline save
    try:
        district = user.district
        print(f"[DEBUG] User District: {district}")
    except AttributeError:
        print("[DEBUG] User does not have a district assigned.")
        return JsonResponse({"success": False, "message": "User does not have a district assigned."}, status=403)

    try:
        obj, created = ResultUploadDeadline.objects.update_or_create(
            district=district,
            term=term,
            academic_year=academic_year,
            defaults={"deadline_date": deadline_date, "created_by": user}
        )
        print(f"[DEBUG] ResultUploadDeadline {'created' if created else 'updated'}: {obj}")
    except Exception as e:
        print(f"[ERROR] Error saving ResultUploadDeadline: {e}")
        return JsonResponse({"success": False, "message": "An error occurred while saving the deadline."}, status=500)

    return JsonResponse({
        "success": True,
        "message": f"Deadline {'created' if created else 'updated'} successfully."
    })


@login_required
@user_passes_test(lambda u: u.role == "cis")
def get_notifications(request):
    cis = request.user 
    notifications = Notification.objects.filter(recipient=cis, is_read=False).order_by("-created_at")

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
@user_passes_test(lambda u: u.role == "cis")
def mark_notification_as_read(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, recipient=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({"success": "Notification marked as read"}, status=200)
    except Notification.DoesNotExist:
        return JsonResponse({"error": "Notification not found"}, status=404)
