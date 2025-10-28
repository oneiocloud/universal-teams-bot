# app.py
from aiohttp import web
import logging
import os
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    BotFrameworkAdapter,
    TurnContext,
)
from botbuilder.schema import Activity
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
        auth_header = req.headers.get("Authorization", "")
        response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        if response:
            return web.Response(status=response.status)
        else:
            return web.Response(status=200)
    except Exception as e:
        logger.exception("Error handling activity")
        return web.Response(status=500, text="Error handling activity")

# New ONEiO entry point
async def send_card(req: web.Request) -> web.Response:
    try:
        payload = await req.json()
        logger.info("/api/send_card endpoint triggered")
        ticket_id = payload.get("ticket_id")
        card = payload.get("card")

        # Validate ticket_id and card existence
        if not ticket_id or not card:
            return web.Response(status=400, text="Missing ticket_id or card")

        try:
            validate_card(card)
        except ValueError as e:
            return web.Response(status=400, text=str(e))

        # Load conversation reference and activity ID from storage
        ticket_context = get_ticket_context(ticket_id)
        if not ticket_context:
            return web.Response(status=404, text=f"Ticket context for ticket {ticket_id} not found")

        conversation_reference = ticket_context.get("conversation_reference")
        activity_id = ticket_context.get("activity_id")
        if not conversation_reference or not activity_id:
            return web.Response(status=404, text=f"Conversation reference or activity ID for ticket {ticket_id} missing")

        # Define the callback to update the activity
        async def continue_callback(turn_context: TurnContext):
            updated_activity = Activity(
                type="message",
                id=activity_id,
                attachments=[card]
            )
            await turn_context.update_activity(updated_activity)

        # Continue the conversation and update the card
        await ADAPTER.continue_conversation(conversation_reference, continue_callback, os.environ.get("MicrosoftAppId", ""))

        return web.Response(status=200, text="Card updated")
    except Exception as e:
        logger.exception("Error processing send_card")
        return web.Response(status=500, text="Error processing send_card")

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