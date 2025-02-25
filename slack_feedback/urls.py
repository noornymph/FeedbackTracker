from django.urls import path, include
from rest_framework.routers import DefaultRouter
from feedback.views import FeedbackViewSet, slack_event_listener, get_mentions

router = DefaultRouter()
router.register(r'feedbacks', FeedbackViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('slack/events/', slack_event_listener, name='slack_event_listener'),
    path('api/get-mentions/', get_mentions, name='get_mentions'),
]
