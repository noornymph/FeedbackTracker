import requests
from django.conf import settings
from django.utils import timezone
from .models import SlackUser, Feedback, Reaction

SLACK_TOKEN = settings.SLACK_BOT_TOKEN  # OAuth Token from Slack
CHANNEL_ID = settings.SLACK_CHANNEL_ID  # Slack channel ID for your feedback channel

SLACK_API_URL = "https://slack.com/api/conversations.history"
REACT_API_URL = "https://slack.com/api/reactions.get"

def fetch_feedback_messages():
    """Fetch latest feedback messages from the Slack channel."""
    headers = {'Authorization': f'Bearer {SLACK_TOKEN}'}
    params = {'channel': CHANNEL_ID, 'limit': 100}

    response = requests.get(SLACK_API_URL, headers=headers, params=params)
    
    if response.status_code == 200:
        return response.json().get('messages', [])
    return []

def fetch_reactions_for_message(slack_message_id):
    """Fetch reactions for a specific message from Slack."""
    headers = {'Authorization': f'Bearer {SLACK_TOKEN}'}
    params = {'channel': CHANNEL_ID, 'timestamp': slack_message_id}

    response = requests.get(REACT_API_URL, headers=headers, params=params)
    
    if response.status_code == 200:
        return response.json().get('message', {}).get('reactions', [])
    return []

def get_or_create_slack_user(slack_id, username=None):
    """Retrieve or create a SlackUser based on the Slack ID."""
    user, created = SlackUser.objects.get_or_create(slack_id=slack_id, defaults={'username': username or f"User-{slack_id}"})
    return user

def save_messages_and_reactions():
    """Fetch and store messages along with reactions from Slack."""
    messages = fetch_feedback_messages()

    if not messages:
        return

    for message in messages:
        slack_message_id = message.get('ts')
        message_text = message.get('text')
        slack_sender_id = message.get('user')
        timestamp = timezone.make_aware(timezone.datetime.fromtimestamp(float(slack_message_id)))

        # Ensure sender exists in SlackUser model
        sender = get_or_create_slack_user(slack_sender_id)

        # Assuming self-feedback (sender == receiver)
        feedback, created = Feedback.objects.get_or_create(
            sender=sender,
            user=sender,  # Can be changed if there is a separate receiver
            message=message_text,
            timestamp=timestamp
        )

        # Fetch and save reactions
        reactions = fetch_reactions_for_message(slack_message_id)
        for reaction in reactions:
            reaction_name = reaction['name']
            reaction_users = reaction.get('users', [])

            for slack_reactor_id in reaction_users:
                reactor = get_or_create_slack_user(slack_reactor_id)
                Reaction.objects.get_or_create(feedback=feedback, user=reactor, reaction=reaction_name)
