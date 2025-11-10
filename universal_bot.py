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
    async def on_message_activity(self, turn_context: TurnContext):
        if turn_context.activity.value:
            return await self._handle_card_action(turn_context)

        text = turn_context.activity.text.strip().lower()
        if text == "create ticket":
            return await self._handle_create_ticket(turn_context)
        else:
            return await self._handle_invalid_message(turn_context)

    async def on_invoke_activity(self, turn_context: TurnContext) -> InvokeResponse:
        if turn_context.activity.name == "adaptiveCard/action":
            return await self._handle_card_action(turn_context)
        else:
            logger.warning(f"Unknown invoke activity: {turn_context.activity.name}")
            return InvokeResponse(status=501)


    async def _handle_create_ticket(self, turn_context: TurnContext):
        logger.info("Handling 'create ticket' message")
        ticket_id = generate_ticket_id()
        activity_id = await self._send_loading_card(turn_context, ticket_id, "Please wait while we prepare your form.")
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
        logger.info(f"Raw incoming activity value: {turn_context.activity.value}")
        logger.info(f"Full incoming activity object: {turn_context.activity}")
        logger.info("Handling card action (submit or execute)")
        activity = turn_context.activity

        if activity.type == "invoke":                                                       # Handle Action.Execute
            action_value = activity.value.get("action", {}) or {}
            verb = action_value.get("verb") or action_value.get("action")
            static_data = activity.value.get("data", {}) or {}
            inputs = activity.value.get("inputs", {}) or {}
            datafields = {**static_data, **inputs}
        else:                                                                               # Handle Action.Submit
            verb = activity.value.get("verb")
            datafields = activity.value or {}

        ticket_id = get_ticket_id_by_activity(activity.reply_to_id or activity.id)
        if not ticket_id:
            logger.error("No ticket_id could be found for this activity.")
            await turn_context.send_activity("Could not determine the ticket ID.")
            return InvokeResponse(status=400)

        try:
            await self._send_loading_card(turn_context, ticket_id, "Updating ticket...")
        except Exception as e:
            logger.warning(f"Failed to update with loading card: {e}")

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

        logger.info("Returning InvokeResponse with status 200 for Teams")
        return InvokeResponse(status=200, body={"message": "Successful"})

    
    async def _send_loading_card(self, turn_context: TurnContext, ticket_id: str, description_text: str):
        card_content = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.6",
            "body": [
                {
                    "type": "ColumnSet",
                    "columns": [
                        {
                            "type": "Column",
                            "width": "auto",
                            "items": [
                                {
                                    "type": "Image",
                                    "url": "https://cdn.prod.website-files.com/615862cf7e67455a772dfa12/674f00941f14b7062960bb98_ONEiO_Wordmark-comp_Accent_black-bluedot-small.png",
                                    "width": "50px",
                                    "height": "50px"
                                }
                            ]
                        },
                        {
                            "type": "Column",
                            "width": "stretch",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": "ONEiO Teams Bot",
                                    "weight": "Bolder",
                                    "size": "Medium",
                                    "horizontalAlignment": "Center",
                                    "wrap": True
                                },
                                {
                                    "type": "TextBlock",
                                    "text": "Creating your ticket...",
                                    "horizontalAlignment": "Center",
                                    "spacing": "None",
                                    "isSubtle": True,
                                    "wrap": True
                                }
                            ],
                            "verticalContentAlignment": "Center"
                        }
                    ]
                },
                {
                    "type": "TextBlock",
                    "text": description_text,
                    "horizontalAlignment": "Center",
                    "wrap": True,
                    "spacing": "Medium"
                },
                {
                    "type": "TextBlock",
                    "text": "Loading...",
                    "weight": "Bolder",
                    "size": "Large",
                    "horizontalAlignment": "Center",
                    "spacing": "Medium"
                },
                {
                    "type": "Image",
                    "url": "https://usagif.com/wp-content/uploads/loading-96.gif",
                    "horizontalAlignment": "Center",
                    "size": "Small",
                    "spacing": "Small"
                },
                {
                    "type": "TextBlock",
                    "text": f"Ticket ID: {ticket_id}",
                    "isSubtle": True,
                    "spacing": "Small",
                    "horizontalAlignment": "Center",
                    "wrap": True
                }
            ]
        }
        card_attachment = Attachment(
            content_type="application/vnd.microsoft.card.adaptive",
            content=card_content
        )
        if turn_context.activity.reply_to_id:
            sent_activity = await turn_context.update_activity(
                Activity(
                    id=turn_context.activity.reply_to_id,
                    type="message",
                    attachments=[card_attachment],
                    conversation=turn_context.activity.conversation
                )
            )
        else:
            sent_activity = await turn_context.send_activity(
                Activity(
                    type="message",
                    attachments=[card_attachment]
                )
            )
        logger.info("Displayed loading card in chat")
        return sent_activity.id


def send_to_oneio(payload):
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