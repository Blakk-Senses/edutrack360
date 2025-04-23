from django.contrib.auth.models import BaseUserManager
import uuid

class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, staff_id=None, password=None, **extra_fields):
        """
        Create and return a regular user with the given staff_id and password.
        """
        if not password:
            raise ValueError("A password must be provided for the user.")

        # If the user is not an admin, we fetch the district from the logged-in CIS user
        district = extra_fields.get('district')  # If district is passed, use it; otherwise, use logged-in user's district

        if not district:
            # If district is not passed, get it from the current logged-in CIS user
            user = extra_fields.get('logged_in_user')
            if user and user.role == 'cis' and user.district:
                district = user.district  # Inherit district from the logged-in CIS user

        # Set the district field in extra_fields
        extra_fields['district'] = district

        # Handle admin users separately
        is_superuser = extra_fields.get('is_superuser', False)
        role = extra_fields.get('role')

        if is_superuser or role == 'admin':
            # Admin users must have the role set to 'admin' explicitly
            staff_id = staff_id or '00000000'
            extra_fields.setdefault('role', 'admin')  # Ensure admin role is set
        else:
            if not staff_id:
                raise ValueError("The staff_id field must be set for non-admin users.")
            if not role:
                raise ValueError("The role field is required for regular users.")
            if role != 'admin':  # Admin does not require other fields
                if not extra_fields.get('license_number'):
                    raise ValueError("The license_number field is required for regular users.")
                if not extra_fields.get('district'):
                    raise ValueError("The district field is required for regular users.")
                if role in ['siso', 'headteacher', 'teacher'] and not extra_fields.get('circuit'):
                    raise ValueError("The circuit field is required for SISO, Headteacher, and Teacher users.")
                if role == 'headteacher' and not extra_fields.get('school'):
                    raise ValueError("The school field is required for Headteacher users.")
        
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        user = self.model(staff_id=staff_id, **extra_fields)
        user.set_password(password)  # Hashes the password before saving
        user.save(using=self._db)
        return user

    def create_superuser(self, staff_id=None, password=None, **extra_fields):
        """
        Create and return a superuser with the given staff_id and password.
        """
        if not password:
            raise ValueError("A password must be provided for the superuser.")

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        # Remove role and license_number validation for superusers
        extra_fields.pop('role', None)
        extra_fields.pop('license_number', None)

        return self.create_user(staff_id or '00000000', password, **extra_fields)

    def generate_unique_license_number(self):
        """
        Generate a unique license number in the format LICENSE-XXXXXXXX.
        """
        return f"LICENSE-{uuid.uuid4().hex[:8]}"
