from django.contrib.auth.models import BaseUserManager
import uuid

class UserManager(BaseUserManager):
    """
    Custom manager for User model where staff_id is the unique identifier for authentication
    instead of usernames.
    """
    use_in_migrations = True

    def create_user(self, staff_id, password=None, **extra_fields):
        """
        Create and return a regular user with the given staff_id and password.
        """
        if not staff_id:
            raise ValueError("The staff_id field must be set.")
        if not password:
            raise ValueError("A password must be provided for the user.")

        # Check if creating a regular user (not a superuser)
        if not extra_fields.get('is_superuser', False):
            if not extra_fields.get('role'):
                raise ValueError("The role field is required for regular users.")
            if not extra_fields.get('license_number'):
                raise ValueError("The license_number field is required for regular users.")

        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        user = self.model(staff_id=staff_id, **extra_fields)
        user.set_password(password)  # Hashes the password before saving
        user.save(using=self._db)
        return user

    def create_superuser(self, staff_id, password=None, **extra_fields):
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

        if not extra_fields.get('first_name'):
            raise ValueError("Superusers must have a first name.")
        if not extra_fields.get('last_name'):
            raise ValueError("Superusers must have a last name.")
        if extra_fields.get('is_staff') is not True:
            raise ValueError("Superusers must have is_staff=True.")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Superusers must have is_superuser=True.")

        return self.create_user(staff_id, password, **extra_fields)

    def generate_unique_license_number(self):
        """
        Generate a unique license number in the format LICENSE-XXXXXXXX.
        """
        return f"LICENSE-{uuid.uuid4().hex[:8]}"
