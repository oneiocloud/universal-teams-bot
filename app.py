# app.py
from aiohttp import web
import logging
import os
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    BotFrameworkAdapter,
    TurnContext,
)
from botbuilder.schema import Activity, ConversationReference, InvokeResponse
from universal_bot import UniversalBot
from storage_utils import get_ticket_context
from card_validator import validate_card  

# Adapter config
SETTINGS = BotFrameworkAdapterSettings(
    os.environ.get("MicrosoftAppId", ""),
    os.environ.get("MicrosoftAppPassword", "")
)
ADAPTER = BotFrameworkAdapter(SETTINGS)
BOT = UniversalBot()

logger = logging.getLogger("teamsbot")
logging.basicConfig(level=logging.INFO)


# Main bot endpoint (for Teams)
async def messages(req: web.Request) -> web.Response:
    try:
        activity = await ADAPTER.parse_request(req)
        logger.info(f"Incoming activity: type={getattr(activity, 'type', None)} id={getattr(activity, 'id', None)} from={getattr(activity, 'from_property', None)}")
        auth_header = req.headers.get("Authorization", "")
        logger.info("Processing activity through adapter...")
        response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        if isinstance(response, InvokeResponse):
            logger.info(f"Adapter returned response with status: {response.status}")
            return web.json_response(response.body, status=response.status)
        else:
            logger.info("Adapter returned no response object or non-invoke response; returning HTTP 200")
            return web.Response(status=200)
    except Exception as e:
        logger.exception("Error handling activity")
        return web.Response(status=500, text="Error handling activity")

# New ONEiO entry point
async def send_card(req: web.Request) -> web.Response:
    try:
        payload = await req.json()
        logger.info("/api/send_card endpoint triggered")
        logger.info(f"Received /api/send_card payload: {payload}")
        ticket_id = payload.get("ticket_id")
        card = payload.get("card")
        logger.info(f"ticket_id={ticket_id}, card_present={bool(card)}")

        # Validate ticket_id and card existence
        if not ticket_id or not card:
            return web.json_response({"error": "Missing ticket_id or card"}, status=400)

        try:
            validate_card(card)
            logger.info("Adaptive Card validated successfully")
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)

        # Load conversation reference and activity ID from storage
        ticket_context = get_ticket_context(ticket_id)
        logger.info(f"Loaded ticket_context for {ticket_id}: {ticket_context}")
        if not ticket_context:
            return web.json_response({"error": f"Ticket context for ticket {ticket_id} not found"}, status=404)

        from botbuilder.schema import ConversationReference
        conversation_reference = ConversationReference().deserialize(ticket_context.get("conversation_reference"))
        activity_id = ticket_context.get("activity_id")
        if not conversation_reference or not activity_id:
            return web.json_response({"error": f"Conversation reference or activity ID for ticket {ticket_id} missing"}, status=404)

        # Define the callback to update the activity
        async def continue_callback(turn_context: TurnContext):
            from botbuilder.schema import Attachment

            updated_activity = Activity(
                type="message",
                id=activity_id,
                attachments=[
                    Attachment(
                        content_type="application/vnd.microsoft.card.adaptive",
                        content=card
                    )
                ]
            )
            logger.info(f"Updating activity id={updated_activity.id} with new card attachment")
            await turn_context.update_activity(updated_activity)
            logger.info("update_activity completed")

        logger.info(f"About to continue conversation for ticket {ticket_id} using activity_id={activity_id}")
        # Continue the conversation and update the card
        await ADAPTER.continue_conversation(conversation_reference, continue_callback, os.environ.get("MicrosoftAppId", ""))

        return web.json_response({"message": "Card updated"}, status=200)
    except Exception as e:
        logger.exception("Error processing send_card")
        return web.json_response({"error": "Error processing send_card"}, status=500)

# Set up app + routes
app = web.Application()
app.router.add_post("/api/messages", messages)
app.router.add_post("/api/send_card", send_card)

# Azure entry point
def main(req): return app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    logger.info("🚀 Bot running with manual startup")
    web.run_app(app, host="0.0.0.0", port=port)