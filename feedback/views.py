import json
import re
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import Feedback, Reaction, SlackUser, TaggedUser
from django.conf import settings
from rest_framework import viewsets
from .serializers import FeedbackSerializer
from django.db.models import Prefetch

SLACK_VERIFICATION_TOKEN = settings.SLACK_BOT_TOKEN  # From Slack settings

@csrf_exempt
def slack_event_listener(request):
    """
    Listens to Slack events like messages, message edits, and reactions.
    """
    if request.method == 'POST':
        data = json.loads(request.body)

        # Verify the request is coming from Slack
        if data.get('token') != SLACK_VERIFICATION_TOKEN:
            return JsonResponse({"error": "Invalid token"}, status=403)

        event = data.get('event', {})

        # Handle new messages
        if event.get('type') == 'message' and 'subtype' not in event:
            slack_message_id = event.get('ts')
            message_text = event.get('text')
            slack_user_id = event.get('user')
            timestamp = timezone.make_aware(timezone.datetime.fromtimestamp(float(slack_message_id)))

            if not slack_user_id:
                return JsonResponse({"error": "User ID missing"}, status=400)

            # Get or create the SlackUser
            slack_user, _ = SlackUser.objects.get_or_create(
                slack_id=slack_user_id,
                defaults={'username': ''}
            )

            # Use update_or_create to store or update the message
            feedback_message, created = Feedback.objects.update_or_create(
                slack_message_id=slack_message_id,
                defaults={
                    'message': message_text,
                    'timestamp': timestamp,
                    'user': slack_user,
                    'sender': slack_user,
                }
            )

            # Extract and store mentioned users
            user_mentions = re.findall(r'@(\w+)', message_text)
            for mentioned_username in user_mentions:
                mentioned_user, _ = SlackUser.objects.get_or_create(username=mentioned_username)
                TaggedUser.objects.get_or_create(
                    feedback=feedback_message,
                    user=mentioned_user,
                    username_mentioned=mentioned_username
                )

        # Handle message updates
        elif event.get('type') == 'message' and event.get('subtype') == 'message_changed':
            slack_message_id = event.get('message', {}).get('ts')
            new_text = event.get('message', {}).get('text')

            # Update the existing message
            Feedback.objects.filter(slack_message_id=slack_message_id).update(message=new_text)

        # Handle reactions
        elif event.get('type') == 'reaction_added':
            slack_message_id = event.get('item', {}).get('ts')
            reaction_name = event.get('reaction')
            reaction_user_id = event.get('user')

            if not slack_message_id or not reaction_name or not reaction_user_id:
                return JsonResponse({"error": "Missing reaction data"}, status=400)

            # Get or create SlackUser
            reaction_user, _ = SlackUser.objects.get_or_create(slack_id=reaction_user_id)

            # Fetch the related message
            feedback_message = Feedback.objects.filter(slack_message_id=slack_message_id).first()
            if feedback_message:
                Reaction.objects.get_or_create(
                    feedback=feedback_message,
                    user=reaction_user,
                    reaction=reaction_name
                )

        return JsonResponse({"status": "ok"})

    return JsonResponse({"error": "Invalid request"}, status=400)

@csrf_exempt
def get_mentions(request):
    """
    Returns paginated mentions where a user is tagged, including reactions and sender details.
    """
    if request.method == 'GET':
        user_id = request.GET.get('user_id')
        page = int(request.GET.get('page', 1))  # Default to page 1

        if not user_id:
            return JsonResponse({"error": "User ID is required"}, status=400)

        try:
            # Get Slack user
            slack_user = SlackUser.objects.get(slack_id=user_id)

            # Optimize query using prefetch_related for efficiency
            mentioned_messages = TaggedUser.objects.filter(user=slack_user).select_related('feedback')
            feedback_qs = Feedback.objects.filter(id__in=mentioned_messages.values('feedback_id')) \
                                           .prefetch_related(
                                               Prefetch('reactions', queryset=Reaction.objects.all())
                                           )
            feedback_qs = Feedback.objects.filter(id__in=mentioned_messages.values('feedback_id'))\
                .order_by("timestamp")\
                .prefetch_related(
                    Prefetch('reactions', queryset=Reaction.objects.all())
                )

            # Paginate results (limit 20 mentions per page)
            paginator = Paginator(feedback_qs, 20)
            mentions_page = paginator.get_page(page)

            # Prepare response
            data = []
            for feedback in mentions_page:
                reactions = [{"reaction": r.reaction, "user_id": r.user.slack_id} for r in feedback.reactions.all()]
                sender = {
                    "sender_id": feedback.sender.slack_id if feedback.sender else None,
                    "sender_username": feedback.sender.username if feedback.sender else "Unknown"
                }
                data.append({
                    "message": feedback.message,
                    "timestamp": feedback.timestamp,
                    "mentioned_in": feedback.slack_message_id,
                    "reactions": reactions,
                    "sender": sender
                })

            return JsonResponse({
                "mentions": data,
                "total_pages": paginator.num_pages,
                "current_page": mentions_page.number
            }, status=200)

        except SlackUser.DoesNotExist:
            return JsonResponse({"error": "User not found"}, status=404)

    return JsonResponse({"error": "Invalid request"}, status=400)


class FeedbackViewSet(viewsets.ModelViewSet):
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer
