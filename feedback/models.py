from django.db import models

class SlackUser(models.Model):
    slack_id = models.CharField(max_length=50, unique=True)
    username = models.CharField(max_length=100)

    def __str__(self):
        return self.username


class Feedback(models.Model):
    user = models.ForeignKey(SlackUser, on_delete=models.CASCADE, related_name="feedback_received")
    sender = models.ForeignKey(SlackUser, on_delete=models.CASCADE, related_name="feedback_given")
    message = models.TextField()
    timestamp = models.DateTimeField()
    reactions = models.JSONField(default=dict)  # Store reactions as JSON

    def __str__(self):
        return f"{self.sender} → {self.user}: {self.message[:20]}"
