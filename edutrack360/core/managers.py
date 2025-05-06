from django.contrib.auth.base_user import BaseUserManager
import uuid

class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, staff_id=None, password=None, **extra_fields):
        """
        Create and return a regular user with the given staff_id and password.
        """
        if not password:
            raise ValueError("A password must be provided for the user.")

        # Handle admin/superuser users
        is_superuser = extra_fields.get('is_superuser', False)
        role = extra_fields.get('role')

        if is_superuser or role == 'admin':
            staff_id = staff_id or '00000000'
            extra_fields.setdefault('role', 'admin')
            extra_fields.setdefault('is_staff', True)
            extra_fields.setdefault('is_superuser', True)

        else:
            if not staff_id:
                raise ValueError("The staff_id field must be set for non-admin users.")
            if not role:
                raise ValueError("The role field is required for regular users.")
            if role != 'admin':
                if not extra_fields.get('license_number'):
                    raise ValueError("The license_number field is required for regular users.")
                # We don't require district in extra_fields directly, will check on instance
                if role in ['siso', 'headteacher', 'teacher'] and not extra_fields.get('circuit'):
                    raise ValueError("The circuit field is required for SISO, Headteacher, and Teacher users.")
                if role == 'headteacher' and not extra_fields.get('school'):
                    raise ValueError("The school field is required for Headteacher users.")
            extra_fields.setdefault('is_staff', False)
            extra_fields.setdefault('is_superuser', False)

        # Instantiate user
        user = self.model(staff_id=staff_id, **extra_fields)

        # Validate that district is set for non-admins (from the form or manager)
        if role != 'admin' and not user.district:
            raise ValueError("District must be set for non-admin users.")

        user.set_password(password)
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
        extra_fields['role'] = 'admin'  # Ensure superuser has admin role

        # Superusers don’t require license_number, district, circuit, etc.
        extra_fields.pop('license_number', None)
        extra_fields.pop('district', None)
        extra_fields.pop('circuit', None)
        extra_fields.pop('school', None)

        return self.create_user(staff_id or '00000000', password, **extra_fields)

    def generate_unique_license_number(self):
        """
        Generate a unique license number in the format LICENSE-XXXXXXXX.
        """
        return f"LICENSE-{uuid.uuid4().hex[:8]}"
