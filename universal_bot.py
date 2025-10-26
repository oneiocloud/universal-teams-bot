from botbuilder.core import ActivityHandler, TurnContext

class UniversalBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        text = turn_context.activity.text.strip().lower()
        if text == "create ticket":
            await turn_context.send_activity("gimme a minute")
        else:
            await turn_context.send_activity("say 'create ticket' to start something")