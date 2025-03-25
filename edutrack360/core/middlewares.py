from django.shortcuts import redirect

# class ForcePasswordChangeMiddleware:
#     def __init__(self, get_response):
#         self.get_response = get_response

#     def __call__(self, request):
#         # Redirect authenticated users who haven't changed their password
#         if request.user.is_authenticated and not request.user.password_changed:
#             if request.path not in ['/change-password/', '/logout/']:  # Allow password change and logout
#                 return redirect('/change-password/')
#         return self.get_response(request)
