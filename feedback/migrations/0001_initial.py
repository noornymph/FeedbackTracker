# Generated by Django 5.1.6 on 2025-02-17 07:43

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SlackUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slack_id', models.CharField(max_length=50, unique=True)),
                ('username', models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name='Feedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('timestamp', models.DateTimeField()),
                ('reactions', models.JSONField(default=dict)),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feedback_given', to='feedback.slackuser')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feedback_received', to='feedback.slackuser')),
            ],
        ),
    ]
