from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
import logging

User = get_user_model()

class StaffIDBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Attempt to find the user by their staff_id
            user = User.objects.get(staff_id=username)
            if user.is_active and user.check_password(password):
                return user
        except User.DoesNotExist:
            return None


class EmailOrStaffIDBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Log the attempt to authenticate
        logging.debug(f"Attempting to authenticate user with username: {username}")
        
        try:
            if "@" in username:
                # Admin login via email, checking the user's role
                logging.debug(f"Admin login attempt with email: {username}")
                user = User.objects.get(email=username)
                
                # Check if the user is an admin (role check) and is active
                if user.is_active and user.role == 'admin':  # Adjusted to use the 'role' field
                    logging.debug(f"Admin user {username} found, checking password...")
                    if user.check_password(password):
                        logging.debug(f"Admin user {username} authenticated successfully.")
                        return user
                    else:
                        logging.debug(f"Password incorrect for admin user {username}.")
            else:
                # Non-admin login via staff_id
                logging.debug(f"Non-admin login attempt with staff_id: {username}")
                user = User.objects.get(staff_id=username)
                
                # Check if the user is active
                if user.is_active:
                    logging.debug(f"User {username} found, checking password...")
                    if user.check_password(password):
                        logging.debug(f"User {username} authenticated successfully.")
                        return user
                    else:
                        logging.debug(f"Password incorrect for user {username}.")
        except User.DoesNotExist:
            logging.debug(f"User with username {username} does not exist.")
            return None
