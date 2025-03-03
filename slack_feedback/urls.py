from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from rest_framework.routers import DefaultRouter
from feedback.views import FeedbackViewSet, slack_event_listener, get_mentions, auth_callback, get_user_info, oauth_success, check_auth, debug_session, summarize_feedback

router = DefaultRouter()
router.register(r'feedbacks', FeedbackViewSet)


def google_auto_login(request):
    return redirect('http://127.0.0.1:8000/accounts/google/login/')


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", google_auto_login),
    path("accounts/", include("allauth.urls")),
    path('api/', include(router.urls)),
    path('slack/events/', slack_event_listener, name='slack_event_listener'),
    path('api/get-mentions/', get_mentions, name='get_mentions'),
    path('api/auth/callback/', auth_callback, name='auth_callback'),
    path('api/user/info/', get_user_info, name='get_user_info'),
    path('oauth/success/', oauth_success, name='oauth_success'),
    path('api/auth/check/', check_auth, name='check_auth'),
    path('api/debug/session/', debug_session, name='debug_session'),
    path('api/feedback/summarize/', summarize_feedback, name='summarize_feedback'),
]
