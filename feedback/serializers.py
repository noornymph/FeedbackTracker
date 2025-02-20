from rest_framework import serializers
from .models import Feedback, Reaction, SlackUser, TaggedUser

class SlackUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = SlackUser
        fields = ['slack_id', 'username']

class ReactionSerializer(serializers.ModelSerializer):
    user = SlackUserSerializer()

    class Meta:
        model = Reaction
        fields = ['reaction', 'user']

class TaggedUserSerializer(serializers.ModelSerializer):
    user = SlackUserSerializer()
    
    class Meta:
        model = TaggedUser
        fields = ['user', 'username_mentioned']

class FeedbackSerializer(serializers.ModelSerializer):
    sender = SlackUserSerializer()
    user = SlackUserSerializer()
    reactions = ReactionSerializer(many=True, read_only=True)
    tagged_users = TaggedUserSerializer(many=True, read_only=True)  # Add this line

    class Meta:
        model = Feedback
        fields = ['slack_message_id', 'sender', 'user', 'message', 'timestamp', 'reactions', 'tagged_users']
