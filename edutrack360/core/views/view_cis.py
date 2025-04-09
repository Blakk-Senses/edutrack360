import csv
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from core.models import ( 
    District, Notification, PerformanceSummary, 
    Profile, School, SchoolSubmission, Circuit, StudentMark,
)
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status
import csv
from collections import defaultdict
from django.db.models import Q
from django.shortcuts import redirect
import json
from django.views.decorators.http import require_POST
from core.forms import (
    AddSchoolForm, UserSearchForm, UserRoleChangeForm,
    UserRegistrationForm,
)
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.hashers import make_password
import csv
import io
import os
import pandas as pd
from django.core.files.storage import default_storage
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import render
from core.models import School
from openpyxl import Workbook
from django.db import transaction
import logging
logger = logging.getLogger(__name__)


User = get_user_model()


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
        # Save school
        school = form.save(commit=False)
        school.district = request.user.district  # assuming 'assigned_district' is the correct field
        school.circuit = form.cleaned_data["circuit"]
        school.save()

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

        response_data = {
            "success": True,
            "message": f"{schools_created} schools uploaded successfully!",
            "skipped_entries": skipped_entries
        }

        if skipped_entries:
            response_data["warning"] = "Some rows were skipped due to errors."

        return JsonResponse(response_data)

    return JsonResponse({"success": False, "error": "Invalid request"}, status=400)


def load_file(file_extension, file_path):
    """Load file (CSV or Excel) into a pandas DataFrame."""
    try:
        if file_extension == ".csv":
            return pd.read_csv(file_path, dtype=str)
        elif file_extension in [".xls", ".xlsx"]:
            return pd.read_excel(file_path, dtype=str)
    except Exception as e:
        logger.error(f"Error loading file: {str(e)}")
        return None


def validate_school_row(row, circuit_lookup, password1, password2, row_num):
    required_fields = [
        "school_name", "school_code", "circuit_name",
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
        "school_name", "school_code", "circuit_name",
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

    for index, row in df.iterrows():
        row_num = index + 2
        school_code = str(row["school_code"]).strip()
        email = str(row["headteacher_email"]).strip().lower()
        password1 = str(row["password1"]).strip()
        password2 = str(row["password2"]).strip()
        circuit_name = str(row["circuit_name"]).strip().lower()

        if school_code in existing_school_codes or email in existing_headteacher_emails:
            skipped_entries.append(f"Row {row_num}: Duplicate school code ({school_code}) or email ({email}).")
            continue

        error = validate_school_row(row, circuit_lookup, password1, password2, row_num)
        if error:
            skipped_entries.append(error)
            continue

        try:
            school = School.objects.create(
                name=row["school_name"].strip(),
                school_code=school_code,
                circuit=circuit_lookup[circuit_name],
                district=user.district
            )

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
            skipped_entries.append(f"Row {row_num}: Unexpected error - {str(e)}")

    return schools_created, skipped_entries


@login_required
def download_school_template(request, file_format):
    headers = [
        "school_name",
        "school_code",
        "circuit_name",
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


    
    
def download_circuit_report(request, circuit_id):
    # Generate and return the circuit report
    return HttpResponse(f"Downloading Circuit Report for ID: {circuit_id}")

def download_school_report(request, school_id):
    # Generate and return the school report
    return HttpResponse(f"Downloading School Report for ID: {school_id}")
# Assuming the model is imported from your app

def cis_send_notifications(request):
    return render(request, 'cis/send_notifications.html')

def generate_reports(request):
    return render(request, 'cis/generate_reports.html')




@login_required
def send_notification(request):
    if request.method == "POST":
        recipient_id = request.POST.get("recipient_id")
        message = request.POST.get("message")
        
        if recipient_id and message:
            recipient = User.objects.get(id=recipient_id)
            Notification.objects.create(sender=request.user, recipient=recipient, message=message)
            return JsonResponse({"status": "success", "message": "Notification sent!"})
    
    return JsonResponse({"status": "error", "message": "Invalid request"})

@login_required
def get_notifications(request):
    """Fetch unread notifications for the logged-in user."""
    notifications = Notification.objects.filter(recipient=request.user, is_read=False).order_by("-created_at")
    data = [{"id": n.id, "sender": n.sender.username, "message": n.message, "created_at": n.created_at} for n in notifications]
    return JsonResponse({"notifications": data})

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
    circuit_id = request.GET.get("circuit_id", "all")  # NEW

    valid_years = [year["name"] for year in filter_options["academic_years"]]
    academic_year = academic_year if academic_year in valid_years else filter_options["selected_academic_year"]

    all_terms = [t["name"] for t in filter_options["terms"]]
    selected_term = selected_term if selected_term in all_terms else "Term 1"

    user = request.user
    if not hasattr(user, 'district') or user.role != 'cis':
        return redirect("homepage")

    # Get circuits in district
    circuits_in_district = Circuit.objects.filter(district=user.district)
    available_circuits = [{"id": c.id, "name": c.name} for c in circuits_in_district]

    if circuit_id == "all":
        circuits_to_analyze = circuits_in_district
    else:
        circuits_to_analyze = circuits_in_district.filter(id=circuit_id)

    print(f"🧭 Circuits selected for analysis: {circuits_to_analyze.count()}")

    # Container for all circuit analyses
    circuit_analyses = []

    for circuit in circuits_to_analyze:
        print(f"\n📍 Analyzing Circuit: {circuit.name}")
        schools_in_circuit = School.objects.filter(circuit=circuit)

        selected_marks = StudentMark.objects.filter(
            student__school__in=schools_in_circuit,
            academic_year=academic_year,
            term=selected_term,
            subject__results__status="Submitted"
        ).distinct()

        school_departments = {}
        school_subject_averages = {}
        school_subjects = {}
        school_score_buckets = {}
        school_chart_data = {}

        for school in schools_in_circuit:
            school_marks = selected_marks.filter(student__school_id=school.id)

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

        # Trend Data
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
        ).filter(q_terms, subject__results__status="Submitted")

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
        # Passing chart data to frontend
        "term_chart_data": json.dumps({
            "labels": term_labels,
            "data": term_values
        }),
        "year_chart_data": json.dumps({
            "labels": year_labels,
            "data": year_values
        })
    }

#--------------------- USER MANAGEMENT ----------------------

def user_management(request):
    return render(request, 'cis/user_management.html')

@login_required
def user_search(request):
    user = request.user
    if user.role != 'cis':
        return JsonResponse({"success": False, "message": "Permission Denied"}, status=403)

    if request.method == 'POST':
        search_form = UserSearchForm(request.POST)

        if 'staff_id' in request.POST:
            if search_form.is_valid():
                staff_id = search_form.cleaned_data['staff_id']
                try:
                    searched_user = User.objects.get(staff_id=staff_id, district=user.district)
                    role_change_form = UserRoleChangeForm(instance=searched_user)

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
                            'role': searched_user.role
                        },
                        'role_change_form': {
                            'role': role_change_form.initial['role'],
                            'circuits': list(circuits.values('id', 'name')),
                            'schools': list(schools.values('id', 'name'))
                        },
                    })
                except User.DoesNotExist:
                    return JsonResponse({"success": False, "message": "User not found in your district."}, status=404)

        elif 'role_change' in request.POST:
            staff_id = request.POST.get('staff_id')
            try:
                target_user = User.objects.get(staff_id=staff_id, district=user.district)
            except User.DoesNotExist:
                return JsonResponse({"success": False, "message": "User not found in your district."}, status=404)

            role_change_form = UserRoleChangeForm(request.POST, instance=target_user)
            new_role = request.POST.get('role')
            new_circuit = request.POST.get('circuit')
            new_school = request.POST.get('school')

            if role_change_form.is_valid():
                # Clear previous assignments
                target_user.school = None
                target_user.circuit = None
                target_user.role = new_role

                # Assign new based on selected role
                if new_role == 'siso':
                    if not new_circuit:
                        return JsonResponse({"success": False, "message": "Please assign a circuit for SISO."}, status=400)
                    target_user.circuit = Circuit.objects.get(id=new_circuit)

                elif new_role == 'headteacher':
                    if not new_school:
                        return JsonResponse({"success": False, "message": "Please assign a school for Headteacher."}, status=400)
                    target_user.school = School.objects.get(id=new_school)

                target_user.save()

                return JsonResponse({
                    'success': True,
                    'message': "User role and assignments have been updated successfully.",
                    'updated_user': {
                        'staff_id': target_user.staff_id,
                        'role': target_user.role,
                        'school': target_user.school.name if target_user.school else None,
                        'circuit': target_user.circuit.name if target_user.circuit else None
                    }
                })
            else:
                return JsonResponse({"success": False, "errors": role_change_form.errors}, status=400)

    return JsonResponse({"success": False, "message": "Invalid request method."}, status=400)




@login_required
def create_user(request):
    if request.method == "POST":
        form = UserRegistrationForm(
            request.POST,
            school=request.user.school,
            district=request.user.district,  # Pass district from logged-in user
            circuit=request.user.circuit  # Pass circuit from logged-in user
        )

        if form.is_valid():
            # Save the user with the appropriate role and association
            user = form.save()

            return JsonResponse({"success": True, "message": "User registered successfully!"})
        else:
            return JsonResponse({"success": False, "errors": form.errors}, status=400)

    return JsonResponse({"success": False, "message": "Invalid request method."}, status=400)
