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

class UniversalBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        print("Entered on_message_activity")
        text = turn_context.activity.text.strip().lower()
        print(f"Received message: {text}")
        if text == "create ticket":
            # Generate unique ticket ID using current UTC timestamp in milliseconds
            ticket_id = str(int(datetime.datetime.utcnow().timestamp() * 1000))
            
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
            print(f"Sent loading card with ticket ID: {ticket_id}")
            
            # Generate and serialize the conversation reference
            conversation_reference = TurnContext.get_conversation_reference(turn_context.activity)
            
            # Save the ticket context
            save_ticket_context(ticket_id, conversation_reference, activity_id)
            
            # Compose payload and send to placeholder function
            payload = {
                "verb": "ticket_created",
                "ticket_id": ticket_id
            }
            print(f"Sending payload to ONEiO: {payload}")
            self.send_to_oneio(payload)
        else:
            await turn_context.send_activity("say 'create ticket' to start something")

    async def on_teams_card_action_invoke(self, turn_context: TurnContext):
        print("Entered on_teams_card_action_invoke")
        activity = turn_context.activity
        action_value = activity.value.get("action")
        if isinstance(action_value, dict):
            verb = action_value.get("verb") or action_value.get("action")
        else:
            verb = action_value
        datafields = activity.value.get("data") or activity.value.get("inputs") or {}
        ticket_id = get_ticket_id_by_activity(activity.reply_to_id or activity.id)
        print(f"Extracted verb: {verb}")
        print(f"Extracted ticket_id: {ticket_id}")
        print(f"Extracted datafields: {datafields}")
        payload = {
            "ticket_id": ticket_id,
            "verb": verb,
            "data": datafields,
            "user": activity.from_property.as_dict() if hasattr(activity.from_property, "as_dict") else vars(activity.from_property),
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }
        print(f"Sending payload to ONEiO: {payload}")
        self.send_to_oneio(payload)
        return InvokeResponse(status=200)

    def send_to_oneio(self, payload):
        # Read credentials and endpoint from environment variables
        username = os.environ.get("ONEIO_USERNAME")
        password = os.environ.get("ONEIO_PASSWORD")
        url = os.environ.get("ONEIO_URL")
        if not (username and password and url):
            raise ValueError("ONEIO credentials or URL not set in environment variables")
        print(f"Sending POST request to ONEiO URL: {url}")
        # Send the payload to the ONEiO endpoint with basic authentication
        response = requests.post(
            url,
            json=payload,
            auth=HTTPBasicAuth(username, password)
        )
        print(f"Received response status code: {response.status_code}")
        response.raise_for_status()