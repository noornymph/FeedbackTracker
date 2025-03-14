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
from django.urls import reverse
from django.shortcuts import redirect
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import openai
from slack_sdk.signature import SignatureVerifier
import logging

SLACK_VERIFICATION_TOKEN = settings.SLACK_BOT_TOKEN  # From Slack settings
logger = logging.getLogger(__name__)

@csrf_exempt
def slack_event_listener(request):
    """
    Listens to Slack events and stores them in the database.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            logger.info("Received data: %s", data)

            # Handle URL verification challenge
            if data.get('type') == 'url_verification':
                return JsonResponse({'challenge': data.get('challenge')})

            # Handle actual events
            if data.get('type') == 'event_callback':
                event = data.get('event', {})
                event_type = event.get('type')
                
                if event_type == 'message' and 'subtype' not in event:
                    # Handle new message
                    slack_message_id = event.get('ts')
                    message_text = event.get('text')
                    slack_user_id = event.get('user')
                    timestamp = timezone.make_aware(timezone.datetime.fromtimestamp(float(slack_message_id)))

                    # Get or create the SlackUser
                    slack_user, _ = SlackUser.objects.get_or_create(
                        slack_id=slack_user_id,
                        defaults={'username': ''}  # You might want to fetch the username from Slack API
                    )

                    # Create or update the feedback message
                    feedback_message, created = Feedback.objects.update_or_create(
                        slack_message_id=slack_message_id,
                        defaults={
                            'message': message_text,
                            'timestamp': timestamp,
                            'user': slack_user,
                            'sender': slack_user,
                            'source': 'slack',
                        }
                    )
                    logger.info(f"{'Created' if created else 'Updated'} message: {feedback_message.id}")

                elif event_type == 'reaction_added':
                    # Handle new reaction
                    slack_message_id = event.get('item', {}).get('ts')
                    reaction_name = event.get('reaction')

                    try:
                        # Get the related message
                        feedback_message = Feedback.objects.get(slack_message_id=slack_message_id)
                        
                        # Always create a new reaction entry
                        reaction = Reaction.objects.create(
                            feedback=feedback_message,
                            reaction=reaction_name
                        )
                        logger.info(f"Created reaction: {reaction.reaction}")

                    except Feedback.DoesNotExist:
                        logger.error(f"Message not found for reaction: {slack_message_id}")

                elif event_type == 'reaction_removed':
                    # Handle reaction removal
                    slack_message_id = event.get('item', {}).get('ts')
                    reaction_name = event.get('reaction')

                    try:
                        feedback_message = Feedback.objects.get(slack_message_id=slack_message_id)
                        
                        # Delete one instance of the reaction
                        reaction = Reaction.objects.filter(
                            feedback=feedback_message,
                            reaction=reaction_name
                        ).first()
                        if reaction:
                            reaction.delete()
                            logger.info(f"Deleted reaction {reaction_name} from message {slack_message_id}")

                    except Feedback.DoesNotExist:
                        logger.error(f"Message not found for reaction: {slack_message_id}")

                elif event_type == 'message' and event.get('subtype') == 'message_deleted':
                    # Handle message deletion
                    deleted_ts = event.get('deleted_ts')
                    try:
                        Feedback.objects.filter(slack_message_id=deleted_ts).delete()
                        logger.info(f"Deleted message {deleted_ts}")
                    except Exception as e:
                        logger.error(f"Error deleting message: {str(e)}")

            return JsonResponse({'status': 'ok'})

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON: %s", str(e))
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error("Unexpected error: %s", str(e))
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def get_mentions(request):
    """
    Returns paginated mentions where a user is tagged, including reactions and sender details.
    """
    if request.method == 'GET':
        user_id = request.GET.get('user_id')
        page = int(request.GET.get('page', 1))

        if not user_id:
            return JsonResponse({"error": "User ID is required"}, status=400)

        try:
            # Get Slack user
            slack_user = SlackUser.objects.get(slack_id=user_id)

            # Optimize query using prefetch_related for efficiency
            mentioned_messages = TaggedUser.objects.filter(user=slack_user).select_related('feedback')
            feedback_qs = Feedback.objects.filter(id__in=mentioned_messages.values('feedback_id'))\
                .order_by("timestamp")\
                .prefetch_related(
                    'reactions',  # Simplified - no need to select_related('user') for reactions
                    Prefetch('tagged_users', queryset=TaggedUser.objects.select_related('user'))
                ).select_related('sender', 'user')

            # Paginate results (limit 20 mentions per page)
            paginator = Paginator(feedback_qs, 20)
            mentions_page = paginator.get_page(page)

            # Prepare response
            data = []
            for feedback in mentions_page:
                # Process the message to replace user IDs with usernames
                processed_message = feedback.message
                
                # Find all user mentions in the format <@U12345678>
                user_mentions = re.findall(r'<@([A-Z0-9]+)>', processed_message)
                
                # Replace each mention with the username
                for mentioned_id in user_mentions:
                    try:
                        # Try to find the user in our database
                        mentioned_user = SlackUser.objects.filter(slack_id=mentioned_id).first()
                        if mentioned_user and mentioned_user.username:
                            # Replace the ID with the username
                            processed_message = processed_message.replace(
                                f'<@{mentioned_id}>', 
                                f'@{mentioned_user.username}'
                            )
                    except Exception as e:
                        print(f"Error processing mention for {mentioned_id}: {e}")
                
                # Simplified reaction data - just return the reaction names
                reactions = [{"reaction": r.reaction} for r in feedback.reactions.all()]
                sender = {
                    "sender_id": feedback.sender.slack_id if feedback.sender else None,
                    "sender_username": feedback.sender.username if feedback.sender else "Unknown"
                }
                
                # Get tagged users information
                tagged_users = [
                    {
                        "user_id": tu.user.slack_id,
                        "username": tu.user.username,
                        "username_mentioned": tu.username_mentioned
                    } for tu in feedback.tagged_users.all()
                ]
                
                data.append({
                    "message": processed_message,
                    "original_message": feedback.message,
                    "timestamp": feedback.timestamp,
                    "mentioned_in": feedback.slack_message_id,
                    "reactions": reactions,  # Now just contains reaction names
                    "sender": sender,
                    "source": feedback.source,
                    "tagged_users": tagged_users,
                    "recipient": {
                        "user_id": feedback.user.slack_id,
                        "username": feedback.user.username
                    }
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

@csrf_exempt
def auth_callback(request):
    """Handle OAuth callback and return user ID"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = data.get('code')
            
            # Process the OAuth code and get user info
            # This is a simplified example - you'd need to implement the actual OAuth flow
            
            # Return the user's Slack ID that can be used for API calls
            user = request.user
            slack_user = SlackUser.objects.filter(username=user.email.split('@')[0]).first()
            
            if slack_user:
                return JsonResponse({
                    "user_id": slack_user.slack_id,
                    "username": slack_user.username
                })
            else:
                # Create a new SlackUser if one doesn't exist
                email_username = user.email.split('@')[0]
                slack_user = SlackUser.objects.create(
                    slack_id=f"temp_{user.id}",  # Temporary ID until real Slack ID is available
                    username=email_username
                )
                return JsonResponse({
                    "user_id": slack_user.slack_id,
                    "username": slack_user.username
                })
                
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
            
    return JsonResponse({"error": "Invalid request"}, status=400)

@csrf_exempt
def get_user_info(request):
    """Get user info from session and link with Slack ID"""
    if request.user.is_authenticated:
        try:
            # Get email username
            email = request.user.email
            email_username = email.split('@')[0]
            
            # First, try to find a SlackUser by username
            slack_user = SlackUser.objects.filter(username=email_username).first()
            
            if slack_user and not slack_user.slack_id.startswith('temp_'):
                # User already exists with a real Slack ID
                return JsonResponse({
                    "user_id": slack_user.slack_id,
                    "username": slack_user.username,
                    "email": email
                })
            
            # Need to fetch from Slack API
            try:
                # Disable SSL verification to work around certificate issues
                import ssl
                ssl._create_default_https_context = ssl._create_unverified_context
                
                # Initialize Slack client
                slack_client = WebClient(token=settings.SLACK_BOT_TOKEN)
                
                # Look up user by email
                slack_response = slack_client.users_lookupByEmail(email=email)
                slack_id = slack_response['user']['id']
                slack_username = slack_response['user']['name']
                
                # Update or create the SlackUser
                if slack_user:
                    # Update existing user
                    slack_user.slack_id = slack_id
                    slack_user.save()
                else:
                    # Create new user
                    slack_user = SlackUser.objects.create(
                        slack_id=slack_id,
                        username=email_username
                    )
                
                return JsonResponse({
                    "user_id": slack_id,
                    "username": slack_username,
                    "email": email
                })
                
            except Exception as slack_error:
                print(f"Error fetching from Slack API: {slack_error}")
                
                # If we couldn't fetch from Slack, use a temporary ID
                if not slack_user:
                    # Create a new user with a unique temporary ID
                    temp_id = f"temp_{request.user.id}"
                    
                    # Check if this temp_id already exists
                    while SlackUser.objects.filter(slack_id=temp_id).exists():
                        # If it exists, add a random suffix
                        import random
                        temp_id = f"temp_{request.user.id}_{random.randint(1000, 9999)}"
                    
                    slack_user = SlackUser.objects.create(
                        slack_id=temp_id,
                        username=email_username
                    )
                
                return JsonResponse({
                    "user_id": slack_user.slack_id,
                    "username": email_username,
                    "email": email,
                    "note": "Could not fetch real Slack ID"
                })
                
        except Exception as e:
            import traceback
            print(f"Error in get_user_info: {str(e)}")
            print(traceback.format_exc())
            return JsonResponse({"error": str(e)}, status=400)
    
    return JsonResponse({"error": "Not authenticated"}, status=401)

def oauth_success(request):
    """Redirect to frontend after successful OAuth login"""
    return redirect("http://localhost:5173/feedbacks")

@csrf_exempt
def check_auth(request):
    """Check if user is authenticated via session"""
    if request.user.is_authenticated:
        return JsonResponse({"authenticated": True})
    return JsonResponse({"authenticated": False})

@csrf_exempt
def debug_session(request):
    """Debug endpoint to check session state"""
    return JsonResponse({
        "authenticated": request.user.is_authenticated,
        "user_id": request.user.id if request.user.is_authenticated else None,
        "email": request.user.email if request.user.is_authenticated else None,
        "session_key": request.session.session_key,
    })

@csrf_exempt
def summarize_feedback(request):
    """
    Accepts feedback data and username from the frontend and returns an AI-generated summary.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)
    
    try:
        data = json.loads(request.body)
        feedback_data = data.get('feedback', [])
        username = data.get('username', 'the user')  # Get username from request
        
        if not feedback_data:
            return JsonResponse({"error": "No feedback data provided"}, status=400)
        
        # Call the AI model to summarize the feedback
        summary = generate_feedback_summary(feedback_data, username)
        
        return JsonResponse({
            "summary": summary,
            "feedback_count": len(feedback_data)
        }, status=200)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        import traceback
        print(f"Error in summarize_feedback: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)

def generate_feedback_summary(feedback_data, username):
    """
    Uses OpenAI API to generate a summary of all feedback for a specific user.
    """
    try:
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Updated prompt to focus on individual user feedback analysis
        prompt = (
            f"Analyze the following feedback messages received by {username} and provide "
            "a summary in markdown format with these sections:\n"
            "# Personal Feedback Analysis\n\n"
            "## Main Themes and Patterns\n"
            f"[Analyze main themes in the feedback received by {username}]\n\n"
            "## Key Strengths\n"
            f"[List {username}'s key strengths based on the feedback]\n\n"
            "## Areas for Improvement\n"
            f"[List suggested areas where {username} could improve, based on the feedback]\n\n"
            "## Personal Growth Trends\n"
            f"[Analyze {username}'s growth and development trends based on the feedback]\n\n"
            f"Note: This analysis is specifically about feedback received by {username}.\n\n"
            "Feedback messages to analyze:\n\n"
        )
        
        # Add all feedback messages to the prompt
        for i, feedback in enumerate(feedback_data):
            message_block = (
                f"Message {i+1} (from {feedback.get('sender', 'Unknown')} "
                f"on {feedback.get('timestamp', 'Unknown date')}):\n"
                f"{feedback.get('message', '')}\n"
            )
            
            reactions = feedback.get('reactions', [])
            if reactions:
                reaction_str = ', '.join(str(r) for r in reactions)
                message_block += f"Reactions: {reaction_str}\n"
            message_block += "\n"
            
            prompt += message_block
        
        # Updated system message to focus on personal feedback analysis
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using the 16k model for larger context
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "You are an expert at analyzing personal professional feedback. "
                        "Provide concise summaries focused on the individual's performance, strengths, "
                        "and growth opportunities. Frame the analysis from the perspective of "
                        "feedback received by the specific person."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Error generating feedback summary: {str(e)}")
        return "Unable to generate summary due to an error. Please try again later."
