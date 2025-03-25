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
    Profile, School, SchoolSubmission, Circuit
)

from core.forms import (
    AddSchoolForm, BulkUploadForm, 
    AssignSISOForm, CreateCircuitForm,
    ReassignSISOForm, DeleteSISOForm,
)
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.hashers import make_password
import csv
import io
from django.http import HttpResponse
from django.shortcuts import render
from core.models import School
from openpyxl import Workbook
from django.db import transaction


User = get_user_model()


def download_district_report(request):
    # Your logic to generate and return the report, e.g., a file download
    response = HttpResponse("Here is the district report", content_type="application/pdf")
    response['Content-Disposition'] = 'attachment; filename="district_report.pdf"'
    return response


def get_user_circuits(user):
    return Circuit.objects.filter(district=user.assigned_district)


def create_circuit(request):
    if request.method == 'POST':
        print("Received POST request")  # Debugging
        
        create_circuit_form = CreateCircuitForm(request.POST, district=request.user.district)

        if create_circuit_form.is_valid():
            print("Form is valid")  # Debugging

            # Save the circuit
            circuit = create_circuit_form.save(commit=False)
            circuit.district = request.user.district  # Ensure district is set
            print(f"Assigned District: {circuit.district}")  # Debugging
            circuit.save()
            print(f"Circuit saved with ID: {circuit.id}")  # Debugging

            # Assign SISO if provided in the form
            siso_id = request.POST.get('siso')  # Fetch SISO from form data
            print(f"Received SISO ID: {siso_id}")  # Debugging
            
            if siso_id:
                try:
                    siso = User.objects.get(id=int(siso_id), district=request.user.district, role='siso')
                    circuit.siso = siso  # Assign SISO to Circuit
                    circuit.save()
                    print(f"SISO {siso.id} assigned to Circuit {circuit.id}")  # Debugging
                except (User.DoesNotExist, ValueError):
                    print("Invalid SISO selected")  # Debugging
                    messages.error(request, "Invalid SISO selected.")

            messages.success(request, 'Circuit created successfully!')

        else:
            print("Form errors:", create_circuit_form.errors)  # Debugging

    else:
        print("Received GET request")  # Debugging
        create_circuit_form = CreateCircuitForm(district=request.user.district)

    # Fetch all SISOs for the user's district
    all_sisos = User.objects.filter(district=request.user.district, role='siso')
    print(f"Fetched {all_sisos.count()} SISOs for district {request.user.district}")  # Debugging

    return render(request, 'cis/create_circuit.html', {
        'create_circuit_form': create_circuit_form,
        'all_sisos': all_sisos
    })




def assign_siso(request):
    if request.method == 'POST':
        assign_siso_form = AssignSISOForm(request.POST, user=request.user)  # Pass user

        print("Submitted data:", request.POST)  # Debugging print

        if assign_siso_form.is_valid():
            siso_user = assign_siso_form.save(user=request.user)  # Save SISO user
            messages.success(request, f'SISO {siso_user.first_name} assigned successfully!')
            return redirect('cis:assign_siso')
        else:
            print("Form is invalid:", assign_siso_form.errors)  # Debugging print

    else:
        assign_siso_form = AssignSISOForm(user=request.user)  # Pass user to filter circuits

    return render(request, 'cis/assign_siso.html', {'assign_siso_form': assign_siso_form})





def reassign_siso(request):
    print("Received request:", request.method)  # Log request type

    # Initialize form for GET requests
    reassign_siso_form = ReassignSISOForm(district=request.user.district)

    if request.method == 'POST':
        print("Processing POST request...")
        reassign_siso_form = ReassignSISOForm(request.POST, district=request.user.district)

        if reassign_siso_form.is_valid():
            print("Form is valid")

            # Get cleaned data
            siso = reassign_siso_form.cleaned_data['siso']
            new_circuit = reassign_siso_form.cleaned_data['circuit']
            print("Selected SISO:", siso)
            print("New circuit:", new_circuit)

            # Update and save
            siso.circuit = new_circuit
            siso.save()
            print("SISO reassigned and saved successfully")

            messages.success(request, 'SISO reassigned successfully!')
            return redirect('cis:reassign_siso')  # Redirect to avoid form re-submission
        else:
            print("Form is invalid:", reassign_siso_form.errors)  # Print form errors for debugging

    else:
        print("GET request received, rendering form")  

    # Fetch all SISOs and circuits for the user’s district for the dropdowns
    all_sisos = User.objects.filter(district=request.user.district, role='siso')
    circuits = Circuit.objects.filter(district=request.user.district)
    print("Fetched SISOs:", list(all_sisos))
    print("Fetched circuits:", list(circuits))

    return render(request, 'cis/reassign_siso.html', {
        'reassign_siso_form': reassign_siso_form,
        'all_sisos': all_sisos,
        'circuits': circuits
    })

def delete_siso(request):
    if request.method == 'POST':
        delete_siso_form = DeleteSISOForm(request.POST, district=request.user.district)
        if delete_siso_form.is_valid():
            siso = delete_siso_form.cleaned_data['siso']
            siso.delete()
            messages.success(request, 'SISO deleted successfully!')
            return redirect('cis:delete_siso')
    else:
        delete_siso_form = DeleteSISOForm(district=request.user.district)

    # Fetch all SISOs for the user’s district for the SISO dropdown
    sisos = User.objects.filter(district=request.user.district, role='siso')
    return render(request, 'cis/delete_siso.html', {
        'delete_siso_form': delete_siso_form,
        'sisos': sisos
    })

def siso_management(request):
    return render(request, 'cis/siso_management.html')



def add_school(request):
    # Fetch circuits for the logged-in user's assigned district
    circuits = Circuit.objects.filter(district=request.user.assigned_district)
    add_school_form = AddSchoolForm(request=request)  # Pass request to form initialization

    if request.method == "POST":
        add_school_form = AddSchoolForm(request.POST, request=request)  # Pass request again for validation

        if not add_school_form.is_valid():
            messages.error(request, "Form submission failed. Please correct the errors.")
            return render(request, 'cis/add_school.html', {'add_school_form': add_school_form, 'circuits': circuits})

        # Get the circuit ID from the POST data
        circuit_id = request.POST.get("circuit")
        try:
            circuit = Circuit.objects.get(id=circuit_id)  # Get circuit by ID
        except Circuit.DoesNotExist:
            messages.error(request, "Selected circuit does not exist.")
            return render(request, 'cis/add_school.html', {'add_school_form': add_school_form, 'circuits': circuits})

        # Create the School instance without saving to the database yet
        school = add_school_form.save(commit=False)
        school.district = request.user.assigned_district  # Set the district
        school.circuit = circuit  # Set the circuit from the selection
        
        # Now save the school instance
        school.save()

        # Now save the headteacher information
        headteacher = User.objects.create(
            staff_id=add_school_form.cleaned_data['headteacher_staff_id'],
            first_name=add_school_form.cleaned_data['headteacher_first_name'],
            last_name=add_school_form.cleaned_data['headteacher_last_name'],
            license_number=add_school_form.cleaned_data['headteacher_license_number'],
            email=add_school_form.cleaned_data['headteacher_email'],
            phone_number=add_school_form.cleaned_data['headteacher_phone_number'],
            role='headteacher',  # Assuming 'headteacher' is a valid role in your User model
            district=school.district,  # Assign the district from the school
            password=make_password(add_school_form.cleaned_data['headteacher_password'])  # Hash the password
        )

        # Associate the headteacher with the school
        school.headteacher = headteacher  # Set the headteacher for the school
        school.save()  # Save the school again to update the headteacher reference

        messages.success(request, "School and Headteacher added successfully!")
        return redirect("cis:school_list")

    return render(request, 'cis/add_school.html', {'add_school_form': add_school_form, 'circuits': circuits})


def school_list(request):

    # Fetch schools based on the logged-in user's assigned district
    schools = School.objects.filter(district=request.user.assigned_district) 

    return render(request, 'cis/school_list.html', {'schools': schools})


@login_required
def bulk_upload_schools(request):
    bulk_upload_form = BulkUploadForm()

    if request.method == 'POST':
        bulk_upload_form = BulkUploadForm(request.POST, request.FILES)
        if bulk_upload_form.is_valid():
            csv_file = request.FILES.get('csv_file')

            # Validate CSV file format
            if not csv_file or not csv_file.name.endswith('.csv'):
                messages.error(request, "Invalid file format. Please upload a CSV file.")
                return redirect('cis:bulk_upload_schools')

            try:
                decoded_file = csv_file.read().decode('utf-8')
                io_string = io.StringIO(decoded_file)
                csv_reader = csv.DictReader(io_string)

                # Debugging the CSV headers
                print("CSV Headers:", csv_reader.fieldnames)

                # Validate CSV headers
                required_headers = {'School Name', 'School Code', 'Circuit', 'Staff ID', 
                                    'First Name', 'Last Name', 'License Number', 
                                    'Email', 'Phone Number', 'Password'}

                if not required_headers.issubset(csv_reader.fieldnames):
                    messages.error(request, "Invalid CSV format. Ensure correct column headers.")
                    return redirect('cis:bulk_upload_schools')

                district = request.user.assigned_district
                users_to_create = []
                schools_to_create = []
                headteachers_map = {}

                with transaction.atomic():
                    for row in csv_reader:
                        # Debugging the current row of CSV
                        print(f"Processing row: {row}")

                        circuit, _ = Circuit.objects.get_or_create(name=row['Circuit'])

                        # Check for duplicate email
                        if User.objects.filter(email=row['Email']).exists():
                            messages.warning(request, f"Skipping duplicate email: {row['Email']}")
                            continue

                        # Create headteacher user
                        headteacher = User(
                            staff_id=row['Staff ID'],
                            license_number=row['License Number'],
                            first_name=row['First Name'],
                            last_name=row['Last Name'],
                            email=row['Email'],
                            phone_number=row['Phone Number'],
                            password=make_password(row['Password']),
                            role='headteacher',
                            district=district,
                        )
                        users_to_create.append(headteacher)
                        headteachers_map[row['Email']] = headteacher

                    # Bulk create users
                    if users_to_create:
                        User.objects.bulk_create(users_to_create)
                        print(f"Created {len(users_to_create)} users.")

                    for row in csv_reader:
                        circuit = Circuit.objects.get(name=row['Circuit'])
                        headteacher = headteachers_map.get(row['Email'])

                        # Check for duplicate school code
                        if School.objects.filter(school_code=row['School Code']).exists():
                            messages.warning(request, f"Skipping duplicate school code: {row['School Code']}")
                            continue

                        school = School(
                            name=row['School Name'],
                            school_code=row['School Code'],
                            circuit=circuit,
                            district=district,
                            headteacher=headteacher
                        )
                        schools_to_create.append(school)

                    # Bulk create schools
                    if schools_to_create:
                        School.objects.bulk_create(schools_to_create)
                        print(f"Created {len(schools_to_create)} schools.")

                messages.success(request, "Bulk upload successful!")
                return redirect('cis:bulk_upload_schools')  # Redirect to a confirmation page

            except Exception as e:
                messages.error(request, f"Error processing CSV: {str(e)}")
                print(f"Error while processing CSV: {e}")

        else:
            messages.error(request, "Form is invalid. Please check the uploaded file.")

    return render(request, 'cis/bulk_onboarding.html', {'bulk_upload_form': bulk_upload_form})




def download_bulk_upload_template(request, file_format="csv"):
    # Fetch the user-specific district (this assumes the user is logged in)
    user = request.user
    district = user.assigned_district  # Assuming user has 'assigned_district' field

    # Data for CSV/Excel headers (excluding district)
    headers = [
        'School Name',
        'School Code',
        'Circuit',
        'Staff ID',
        'First Name',
        'Last Name',
        'License Number',
        'Email',
        'Phone Number',
        'Password',
    ]

    if file_format == "csv":
        # Generate CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="bulk_upload_template.csv"'

        writer = csv.writer(response)
        writer.writerow(headers)

        # Provide a blank row for data entry (optional)
        writer.writerow([
            '', '', '', '', '', '', '', '', '', '',
        ])

        return response

    elif file_format == "excel":
        # Generate Excel response
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="bulk_upload_template.xlsx"'

        wb = Workbook()
        ws = wb.active
        ws.append(headers)  # Write headers

        # Add a blank row for data entry (optional)
        ws.append([
            '', '', '', '', '', '', '', '', '', '',
        ])

        wb.save(response)
        return response

    return HttpResponse("Invalid file format requested", status=400)

def school_management(request):
    return render(request, 'cis/school_management.html')


@login_required
def get_circuits(request):
    """
    Fetch all circuits associated with the logged-in user's district.
    """
    district = request.user.district  # Assuming that district is a field on the User model
    circuits = Circuit.objects.filter(district=district).values('id', 'name')
    return JsonResponse({'circuits': list(circuits)})

@login_required
def get_siso(request):
    """
    Fetch all SISOs associated with the logged-in user's district.
    """
    district = request.user.district  # Assuming that district is a field on the User model
    sisos = User.objects.filter(district=district, role='siso').values('id', 'first_name', 'last_name')
    return JsonResponse({'sisos': list(sisos)})

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

def user_management(request):
    return render(request, 'cis/user_management.html')


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
