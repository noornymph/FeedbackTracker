from django.core.management.base import BaseCommand
from feedback.models import SlackUser, Feedback, Reaction
from django.utils import timezone
from django.conf import settings
import requests
from django.db import IntegrityError  # Add the missing import

# Slack API URL
SLACK_API_URL = 'https://slack.com/api/conversations.history'

# Replace with your actual Slack token
SLACK_TOKEN = settings.SLACK_BOT_TOKEN
CHANNEL_ID = 'C011BRATXHA'

def fetch_historical_data():
    headers = {
        'Authorization': f'Bearer {SLACK_TOKEN}'
    }

    params = {
        'channel': CHANNEL_ID,
        'limit': 100,
    }
    
    while True:
        response = requests.get(SLACK_API_URL, headers=headers, params=params)
        data = response.json()
        print("Slack API Response:", data)

        messages = data.get('messages', [])
        if not messages:
            print("No more messages to fetch.")
            break

        for message in messages:
            slack_message_id = message.get('ts')
            message_text = message.get('text')
            slack_user_id = message.get('user')
            
            # Skip messages that don't have a sender (e.g., bot messages, system messages)
            if not slack_user_id:
                print(f"Skipping message {slack_message_id} due to missing user ID.")
                continue  # Move to the next message in the loop

            timestamp = timezone.make_aware(timezone.datetime.fromtimestamp(float(slack_message_id)))

            # Check if message ID already exists in the database
            if Feedback.objects.filter(slack_message_id=slack_message_id).exists():
                print(f"Message with ID {slack_message_id} already exists in the database. Skipping.")
                continue  # Skip if message already exists

            # Get or create SlackUser
            slack_user, created = SlackUser.objects.get_or_create(
                slack_id=slack_user_id,
                defaults={'username': message.get('user_name', '')}
            )
            
            if created:
                print(f"Created new SlackUser: {slack_user.username} (ID: {slack_user.slack_id})")
            else:
                print(f"SlackUser {slack_user.username} already exists (ID: {slack_user.slack_id})")

            # Create Feedback entry
            feedback_message = Feedback.objects.create(
                slack_message_id=slack_message_id,
                message=message_text,
                timestamp=timestamp,
                user=slack_user,
                sender=slack_user,
            )

            print(f"Created new Feedback: {feedback_message.message} (ID: {feedback_message.id})")

            # Fetch and store reactions only if message was stored successfully
            reactions = fetch_reactions_for_message(slack_message_id)
            for reaction in reactions:
                reaction_name = reaction['name']
                for reaction_user_id in reaction.get('users', []):  # Iterate through all users who reacted

                    # Skip reactions from users who are not in the database
                    try:
                        reaction_user = SlackUser.objects.get(slack_id=reaction_user_id)
                        reaction_obj, created = Reaction.objects.get_or_create(
                            feedback=feedback_message,
                            user=reaction_user,
                            reaction=reaction_name
                        )
                        if created:
                            print(f"Created new Reaction: {reaction_obj.reaction} (ID: {reaction_obj.id})")
                        else:
                            print(f"Reaction {reaction_obj.reaction} already exists for Feedback ID {feedback_message.id}")
                    except SlackUser.DoesNotExist:
                        print(f"Skipping reaction {reaction_name} from user {reaction_user_id} as user does not exist.")
        # Handle pagination
        next_cursor = data.get('response_metadata', {}).get('next_cursor', '')
        if not next_cursor:
            break
        params['cursor'] = next_cursor

def fetch_reactions_for_message(slack_message_id):
    reaction_url = 'https://slack.com/api/reactions.get'
    headers = {
        'Authorization': f'Bearer {SLACK_TOKEN}'
    }
    params = {
        'channel': CHANNEL_ID,
        'timestamp': slack_message_id
    }

    response = requests.get(reaction_url, headers=headers, params=params)
    return response.json().get('message', {}).get('reactions', [])

class Command(BaseCommand):
    help = "Fetch and store Slack messages and reactions"

    def handle(self, *args, **kwargs):
        self.stdout.write("Fetching messages from Slack...")
        try:
            fetch_historical_data()  # Call the service
            self.stdout.write(self.style.SUCCESS("Messages and reactions fetched successfully"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
