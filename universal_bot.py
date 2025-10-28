import os
import requests
from requests.auth import HTTPBasicAuth
from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import Activity, Attachment
from botbuilder.core import TurnContext
from storage_utils import save_ticket_context, get_ticket_context, get_ticket_id_by_activity
from botbuilder.schema import InvokeResponse
import datetime
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("universal_bot")

class UniversalBot(ActivityHandler):
    async def on_turn(self, turn_context: TurnContext):
        activity_type = turn_context.activity.type
        logger.info(f"Entered on_turn with activity type: {activity_type}")

        if activity_type == "message":
            await self.on_message_activity(turn_context)

        elif activity_type == "invoke":
            logger.info("Received invoke activity; routing to on_teams_card_action_invoke")
            return await self.on_teams_card_action_invoke(turn_context)

        else:
            logger.warning(f"Unsupported activity type: {activity_type}")

    async def on_message_activity(self, turn_context: TurnContext):
        logger.info("Entered on_message_activity")
        text = turn_context.activity.text.strip().lower()
        logger.info(f"Received message: {text}")
        if text == "create ticket":
            # Generate unique ticket ID using current UTC timestamp in milliseconds
            ticket_id = generate_ticket_id()
            
            # Construct a basic "loading" adaptive card with the ticket ID visible
            card_content = {
                "type": "AdaptiveCard",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": "Loading...",
                        "weight": "Bolder",
                        "size": "Medium"
                    },
                    {
                        "type": "TextBlock",
                        "text": f"Ticket ID: {ticket_id}",
                        "wrap": True
                    }
                ],
                "version": "1.0"
            }
            card_attachment = Attachment(
                content_type="application/vnd.microsoft.card.adaptive",
                content=card_content
            )
            
            # Send the card to the user and retrieve the sent activity
            sent_activity = await turn_context.send_activity(Activity(attachments=[card_attachment]))
            activity_id = sent_activity.id
            logger.info(f"Sent loading card with ticket ID: {ticket_id}")
            
            # Generate and serialize the conversation reference
            conversation_reference = TurnContext.get_conversation_reference(turn_context.activity)
            
            # Save the ticket context
            save_ticket_context(ticket_id, conversation_reference, activity_id)
            
            # Compose payload and send to placeholder function
            payload = {
                "verb": "ticket_created",
                "ticket_id": ticket_id
            }
            logger.info(f"Sending payload to ONEiO: {payload}")
            try:
                self.send_to_oneio(payload)
            except Exception as e:
                logger.error(f"Failed to send to ONEiO: {e}")
        else:
            await turn_context.send_activity("say 'create ticket' to start something")

    async def on_teams_card_action_invoke(self, turn_context: TurnContext):
        logger.info("Entered on_teams_card_action_invoke")
        activity = turn_context.activity
        action_value = activity.value.get("action")
        if isinstance(action_value, dict):
            verb = action_value.get("verb") or action_value.get("action")
        else:
            verb = action_value
        datafields = activity.value.get("data") or activity.value.get("inputs") or {}
        ticket_id = get_ticket_id_by_activity(activity.reply_to_id or activity.id)
        if not ticket_id:
            logger.error("No ticket_id could be found for this activity.")
            await turn_context.send_activity("Could not determine the ticket ID.")
            return InvokeResponse(status=400)
        logger.info(f"Extracted verb: {verb}")
        logger.info(f"Extracted ticket_id: {ticket_id}")
        logger.info(f"Extracted datafields: {datafields}")
        payload = {
            "ticket_id": ticket_id,
            "verb": verb,
            "data": datafields,
            "user": activity.from_property.as_dict() if hasattr(activity.from_property, "as_dict") else vars(activity.from_property),
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }
        logger.info(f"Sending payload to ONEiO: {payload}")
        try:
            # send payload to ONEiO (synchronous)
            self.send_to_oneio(payload)
        except Exception as e:
            logger.error(f"Failed to send to ONEiO: {e}")
            # Inform the user in Teams and return a 500 InvokeResponse with an error body
            try:
                await turn_context.send_activity("An error occurred while processing your request.")
            except Exception as send_err:
                logger.warning(f"Failed to send error message to user: {send_err}")
            return InvokeResponse(status=500, body={"error": str(e)})

        # Send a short confirmation message to the user so Teams UI shows immediate feedback
        try:
            await turn_context.send_activity("✅ Your action was received and forwarded to ONEiO.")
        except Exception as send_err:
            logger.warning(f"Failed to send confirmation message to user: {send_err}")

        # Return a proper InvokeResponse with a small body so Teams doesn't report "Unable to reach app"
        return InvokeResponse(status=200, body={"status": "accepted"})

    def send_to_oneio(self, payload):
        # Read credentials and endpoint from environment variables
        username = os.environ.get("ONEIO_USERNAME")
        password = os.environ.get("ONEIO_PASSWORD")
        url = os.environ.get("ONEIO_URL")
        if not (username and password and url):
            raise ValueError("ONEIO credentials or URL not set in environment variables")
        logger.info(f"Sending POST request to ONEiO URL: {url}")
        # Send the payload to the ONEiO endpoint with basic authentication
        response = requests.post(
            url,
            json=payload,
            auth=HTTPBasicAuth(username, password)
        )
        logger.info(f"Received response status code: {response.status_code}")
        response.raise_for_status()



def generate_ticket_id():
    return str(int(datetime.datetime.utcnow().timestamp() * 1000))