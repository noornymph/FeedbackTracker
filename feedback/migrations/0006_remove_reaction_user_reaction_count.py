# Generated by Django 5.1.6 on 2025-03-11 09:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feedback', '0005_feedback_source'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='reaction',
            name='user',
        ),
        migrations.AddField(
            model_name='reaction',
            name='count',
            field=models.IntegerField(default=1),
        ),
    ]
