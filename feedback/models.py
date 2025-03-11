from django.db import models

class SlackUser(models.Model):
    slack_id = models.CharField(max_length=50, unique=True)
    username = models.CharField(max_length=100)

    def __str__(self):
        return self.username

class Feedback(models.Model):
    slack_message_id = models.CharField(max_length=100, unique=True, null=False, default='')  # Unique message ID from Slack
    user = models.ForeignKey(SlackUser, on_delete=models.CASCADE, related_name="feedback_received")
    sender = models.ForeignKey(SlackUser, on_delete=models.CASCADE, related_name="feedback_given")
    message = models.TextField()
    timestamp = models.DateTimeField()
    source = models.CharField(max_length=50, default='slack')  # New field to track the source

    def __str__(self):
        return f"{self.sender} → {self.user}: {self.message[:20]}"

class Reaction(models.Model):
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE, related_name="reactions")
    reaction = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.reaction} on {self.feedback.message[:20]}"

class TaggedUser(models.Model):
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE, related_name="tagged_users")
    user = models.ForeignKey(SlackUser, on_delete=models.CASCADE)  # The actual user object
    username_mentioned = models.CharField(max_length=100)  # The username in the message
    slack_id_mentioned = models.CharField(max_length=50, null=True, blank=True)  # Allow null initially

    def __str__(self):
        return f"{self.user.username} ({self.slack_id_mentioned}) was tagged in {self.feedback.message[:20]}"
