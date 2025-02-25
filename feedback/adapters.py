from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from django.contrib.auth import get_user_model

User = get_user_model()

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """ Automatically link social accounts if an email already exists """
        user_email = sociallogin.account.extra_data.get("email")
        if user_email:
            try:
                user = User.objects.get(email=user_email)
                sociallogin.connect(request, user)
            except User.DoesNotExist:
                pass  # No existing user, proceed with signup
