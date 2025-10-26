import os
from aiohttp import web
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    BotFrameworkAdapter,
    ConversationState,
    MemoryStorage,
)
from universal_bot import UniversalBot

# Adapter setup
SETTINGS = BotFrameworkAdapterSettings(
    os.environ.get("MicrosoftAppId", ""),
    os.environ.get("MicrosoftAppPassword", "")
)
ADAPTER = BotFrameworkAdapter(SETTINGS)

MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)
BOT = UniversalBot(CONVERSATION_STATE)

# Route handler
async def messages(req: web.Request) -> web.Response:
    body = await req.json()
    activity = await ADAPTER.parse_request(req)
    auth_header = req.headers.get("Authorization", "")
    response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
    return web.Response(status=response.status)

# App
app = web.Application()
app.router.add_post("/api/messages", messages)

# Azure needs this entry point
def main(req): return app