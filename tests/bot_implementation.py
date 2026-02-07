import os
import sys
import logging
from pathlib import Path
import base64

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from WebexWSClient import WebexWSClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BotImplementation")

def activity_id_to_message_id(activity_id: str) -> str:
    base_string = f"ciscospark://us/MESSAGE/{activity_id}"
    return base64.b64encode(base_string.encode("utf-8")).decode("utf-8").rstrip("=")

def main():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        print("Error: BOT_TOKEN environment variable not set.")
        sys.exit(1)

    client = WebexWSClient(access_token=bot_token, device_name="bot-runner")

    if not client.my_id:
        print("Error: Failed to initialize client (invalid token?).")
        sys.exit(1)

    async def on_message(event):
        data = event.get("data", {})
        activity = data.get("activity", {})

        if data.get("eventType") == "conversation.activity" and activity.get("verb") == "post":
            actor_id = activity.get("actor", {}).get("id")

            # Decode my_id to UUID to compare with actor_id (which is usually UUID in events)
            my_uuid = None
            try:
                decoded = base64.b64decode(client.my_id + "==").decode("utf-8")
                my_uuid = decoded.split("/")[-1]
            except:
                pass

            if actor_id == my_uuid:
                # Ignoring own message
                return

            activity_id = activity.get("id")
            if not activity_id:
                return

            try:
                message_id = activity_id_to_message_id(activity_id)
                message = client.api.messages.get(message_id)
            except Exception as e:
                logger.error(f"Failed to get message: {e}")
                return

            if message.personId == client.my_id:
                return

            is_mentioned = client.my_id in (message.mentionedPeople or [])
            is_direct = message.roomType == 'direct'

            if is_mentioned or is_direct:
                logger.info(f"Received message from {message.personEmail}: {message.text}")
                # Reply
                reply_text = f"hi <@{message.personId}>"
                client.send_message(roomId=message.roomId, markdown=reply_text)
                logger.info(f"Replied to {message.personEmail}")

    client.add_event_listener(on_message)

    print(f"Bot started as {client.my_email}. Press Ctrl+C to stop.")
    client.run()

if __name__ == "__main__":
    main()
