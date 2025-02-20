def fetch_historical_data():
    messages = fetch_feedback_messages()
    
    if messages:
        for message in messages:
            slack_message_id = message.get('ts')
            message_text = message.get('text')
            slack_user_id = message.get('user')
            timestamp = timezone.make_aware(timezone.datetime.fromtimestamp(float(slack_message_id)))
            
            # Get or create SlackUser object
            slack_user, created = SlackUser.objects.get_or_create(
                slack_id=slack_user_id,
                defaults={'username': message.get('user_name', '')}
            )

            # Check if the message already exists in the database
            feedback_message, created = Feedback.objects.get_or_create(
                slack_message_id=slack_message_id,
                defaults={
                    'message': message_text,
                    'timestamp': timestamp,
                    'user': slack_user,
                    'sender': slack_user,  # Assuming sender is the same as user
                }
            )

            # Fetch reactions for the message
            reactions = fetch_reactions_for_message(slack_message_id)
            for reaction in reactions:
                reaction_name = reaction['name']
                
                # Ensure we have a Slack user for the reaction
                reaction_user_id = reaction.get('user')
                reaction_user = SlackUser.objects.get(slack_id=reaction_user_id)  # Assuming user exists
                
                try:
                    # Create Reaction entry
                    Reaction.objects.get_or_create(
                        feedback=feedback_message,
                        user=reaction_user,
                        reaction=reaction_name
                    )
                except IntegrityError:
                    print(f"Error saving reaction for message {slack_message_id}.")
