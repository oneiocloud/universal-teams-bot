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

        if (activity_type == "message" and turn_context.activity.value) or (                        # Handle Action.Submit
            activity_type == "invoke" and turn_context.activity.name == "adaptiveCard/action"):     # Handle Action.Execute
            return await self._handle_card_action(turn_context)

        elif activity_type == "message":
            text = turn_context.activity.text.strip().lower()
            if text == "create ticket":
                return await self._handle_create_ticket(turn_context)
            else:
                return await self._handle_invalid_message(turn_context)

        elif activity_type == "invoke":
            logger.warning(f"Invoke activity not handled: {turn_context.activity.name}")
            return InvokeResponse(status=501)

        else:
            logger.warning(f"Unsupported activity type: {activity_type}")


    async def _handle_create_ticket(self, turn_context: TurnContext):
        logger.info("Handling 'create ticket' message")
        ticket_id = generate_ticket_id()
        card_content = {
            "type": "AdaptiveCard",
            "body": [
                {"type": "TextBlock", "text": "Loading...", "weight": "Bolder", "size": "Medium"},
                {"type": "TextBlock", "text": f"Ticket ID: {ticket_id}", "wrap": True}
            ],
            "version": "1.0"
        }
        card_attachment = Attachment(
            content_type="application/vnd.microsoft.card.adaptive",
            content=card_content
        )
        sent_activity = await turn_context.send_activity(Activity(attachments=[card_attachment]))
        activity_id = sent_activity.id
        logger.info(f"Sent loading card with ticket ID: {ticket_id}")
        conversation_reference = TurnContext.get_conversation_reference(turn_context.activity)
        save_ticket_context(ticket_id, conversation_reference, activity_id)
        payload = {"verb": "ticket_created", "ticket_id": ticket_id}
        logger.info(f"Sending payload to ONEiO: {payload}")
        try:
            send_to_oneio(payload)
        except Exception as e:
            logger.error(f"Failed to send to ONEiO: {e}")


    async def _handle_invalid_message(self, turn_context: TurnContext):
        logger.info("Handling unrecognized message")
        await turn_context.send_activity("Say 'create ticket' to open a new ticket.")


    async def _handle_card_action(self, turn_context: TurnContext):
        logger.info("Handling card action (submit or execute)")
        activity = turn_context.activity

        if activity.type == "invoke":                                                       # Handle Action.Execute
            action_value = activity.value.get("action", {})
            verb = action_value.get("verb") or action_value.get("action")
            datafields = activity.value.get("data") or activity.value.get("inputs") or {}
        else:                                                                               # Handle Action.Submit
            verb = activity.value.get("verb")
            datafields = activity.value

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

        try:
            send_to_oneio(payload)
        except Exception as e:
            logger.error(f"Failed to send to ONEiO: {e}")
            try:
                await turn_context.send_activity("An error occurred while processing your request.")
            except Exception as send_err:
                logger.warning(f"Failed to send error message to user: {send_err}")
            return InvokeResponse(status=500, body={"error": str(e)})

        if activity.type == "invoke":
            return InvokeResponse(status=200, body={"type": "application/vnd.microsoft.activity.message", "text": ""})



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