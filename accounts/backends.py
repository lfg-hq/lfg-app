from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class EmailBackend(ModelBackend):
    """
    Authenticate using email.
    
    This backend will try to authenticate a user with the provided email
    or username, treating them as the same field.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Check if the username parameter contains an email
            user = User.objects.get(
                Q(username=username) | Q(email=username)
            )
            
            # Check password
            if user.check_password(password):
                return user
                
        except User.DoesNotExist:
            return None
            
        return None 