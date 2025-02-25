from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from rest_framework.routers import DefaultRouter
from feedback.views import FeedbackViewSet, slack_event_listener, get_mentions

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
]
