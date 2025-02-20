import json
import re
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import Feedback, Reaction, SlackUser, TaggedUser
from django.conf import settings
from rest_framework import viewsets
from .serializers import FeedbackSerializer

SLACK_VERIFICATION_TOKEN = settings.SLACK_BOT_TOKEN  # From Slack settings

@csrf_exempt
def slack_event_listener(request):
    """
    Listens to events from Slack like messages and reactions.
    """
    if request.method == 'POST':
        data = json.loads(request.body)

        # Verify the request is coming from Slack (token validation)
        if data.get('token') != SLACK_VERIFICATION_TOKEN:
            return JsonResponse({"error": "invalid token"}, status=403)

        event = data.get('event', {})

        if event.get('type') == 'message' and 'subtype' not in event:
            # Handle new message (if it is not a bot message)
            slack_message_id = event.get('ts')
            message_text = event.get('text')
            slack_user_id = event.get('user')
            timestamp = timezone.make_aware(timezone.datetime.fromtimestamp(float(slack_message_id)))

            # Get or create the SlackUser for the sender
            slack_user, _ = SlackUser.objects.get_or_create(
                slack_id=slack_user_id,
                defaults={'username': event.get('user_name', '')}
            )

            # Store the message in the database
            feedback_message, _ = Feedback.objects.get_or_create(
                slack_message_id=slack_message_id,
                defaults={
                    'message': message_text,
                    'timestamp': timestamp,
                    'user': slack_user,
                    'sender': slack_user,
                }
            )

            # Extract mentions (user tags) from the message
            user_mentions = re.findall(r'@(\w+)', message_text)

            for mentioned_username in user_mentions:
                # Get or create the mentioned user
                mentioned_user, _ = SlackUser.objects.get_or_create(username=mentioned_username)

                # Save the tagged user in the database
                TaggedUser.objects.get_or_create(
                    feedback=feedback_message,
                    user=mentioned_user,
                    username_mentioned=mentioned_username
                )

        elif event.get('type') == 'reaction_added':
            # Handle new reaction added to a message
            slack_message_id = event.get('item', {}).get('ts')
            reaction_name = event.get('reaction')
            reaction_user_id = event.get('user')

            # Get or create SlackUser for the reaction
            reaction_user, _ = SlackUser.objects.get_or_create(slack_id=reaction_user_id)

            # Fetch the feedback message related to this reaction
            feedback_message = Feedback.objects.filter(slack_message_id=slack_message_id).first()

            if feedback_message:
                # Store the reaction in the database
                Reaction.objects.get_or_create(
                    feedback=feedback_message,
                    user=reaction_user,
                    reaction=reaction_name
                )

        return JsonResponse({"status": "ok"})
    return JsonResponse({"error": "Invalid request"}, status=400)

class FeedbackViewSet(viewsets.ModelViewSet):
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer