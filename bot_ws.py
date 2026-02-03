#!/usr/bin/env python3
from __future__ import print_function

import asyncio
from base64 import b64encode
import datetime
import json
import os
import secrets
import signal
import sys
from time import time
import uuid
from dotenv import load_dotenv
from pathlib import Path
import websockets

from webex_admin import WebexAdmin

load_dotenv()
from websockets.exceptions import ConnectionClosed, ConnectionClosedError

from webexteamssdk import WebexTeamsAPI, ApiError
import helper
from oauth_manager import OAuthManager
from storage_manager import StorageManager
import webex_utils

class BotWS:

    def __init__(self, bot_token, storage: StorageManager):
        self.bot_token = bot_token
        self.api = WebexTeamsAPI(access_token=self.bot_token)
        self.storage = storage
        
        me = self.api.people.me()
        self.bot_name = me.displayName
        self.bot_email = me.emails[0] if me.emails else ""
        self.bot_id = me.id
        my_memberships = self.api.memberships.list(personId=self.bot_id)
        self.my_memberships = list(my_memberships)
        for membership in self.my_memberships:
            self.get_or_create_room(membership.roomId)
        self.active_auth_requests = {}

        @staticmethod
        def unauthorized_message(room_admin_email):
            return f"You don't have rights in this room, please ask {room_admin_email} to grant you permissions."

        self.device_info = None
        self.websocket = None
        self.running = False
        self._pending_reinits = set()
        self.loop = None
        
        OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
        OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
        OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://127.0.0.1:9999/auth")
        if not OAUTH_CLIENT_ID or not OAUTH_CLIENT_SECRET:
            print("ERROR: OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET are required")
            sys.exit(1)

                
        self.oauth = OAuthManager(
            client_id=OAUTH_CLIENT_ID,
            client_secret=OAUTH_CLIENT_SECRET,
            redirect_uri=OAUTH_REDIRECT_URI,
            tokens_store_function = self.store_tokens
        )
        print(f"OAuth enabled: {OAUTH_REDIRECT_URI}")
        
    def code_card(self, room) -> helper.AdaptiveCard:
        webex_admin = WebexAdmin(
            my_token=self.get_valid_token_for_room(room)
        )
        workspaces = webex_admin.list_workspaces()
        return helper.make_code_card(workspaces)
    
    def store_tokens(self, room_id: str, state: str, access_token: str, refresh_token: str, expires_at: datetime.datetime) -> None:
        room = self.storage.get_room(room_id)
        if not room:
            print("Error: Room not found in storage.")
            return
        auth_message_id = self.active_auth_requests.get(state, "")
        if auth_message_id:
            self.api.messages.delete(messageId=auth_message_id)
            self.active_auth_requests.pop(state, None)
        webex_admin = WebexAdmin(
            my_token=access_token
        )
        if not webex_admin.token_is_valid():
            print("Error: Provided access token is not valid.")
            self.api.messages.create(
                roomId=room_id,
                markdown=f"{webex_admin.name}({webex_admin.my_email}) doesn't have admin rights on organization **{webex_admin.org_name}** or the token is invalid.\nPlease try authorizing again."
            )
            self.does_room_manage_org(room_id)
            return
        room['managed_org']['oauth_tokens'] = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_at': expires_at.isoformat()
        }
        room['managed_org']['org_id'] = webex_admin.org_id
        room['managed_org']['org_name'] = webex_admin.org_name
        self.api.messages.create(
            roomId=room_id,
            markdown=f"Successfully authorized organization **{webex_admin.org_name}** with admin {webex_admin.name}({webex_admin.my_email}).  You can now request activation codes by saying *@{self.bot_name} hello*."
        )
        self.storage.save()
        print(f"Stored tokens for room {room_id}")

    def get_or_create_room(self, room_id: str) -> dict:
        room = self.storage.get_room(room_id)
        if not room:
            room_details = self.api.rooms.get(room_id)
            if not room_details:
                raise Exception(f"Failed to get room details for room {room_id}")
            room = self.storage.add_room(room_id, room_details.title)
            if room_details.type == "direct":
                creator = self.api.people.get(room_details.creatorId)
                room_admin_email = creator.emails[0] if creator.emails else ""
                self.set_room_admin(room_id, room_admin_email, quiet=True)
        return room
    
    def save(self) -> None:
        self.storage.save()
        print("Bot state saved to bot_data.json")

    async def _connect_websocket(self) -> None:
        if not self.device_info:
            self.device_info = webex_utils.get_device_info(self.bot_token)
        
        ws_url = self.device_info.get("webSocketUrl")
        if not ws_url:
            raise Exception("No webSocketUrl in device info")
        
        print(f"Connecting to WebSocket: {ws_url[:50]}...")
        
        self.websocket = await websockets.connect(
            ws_url,
            ping_interval=30,
            ping_timeout=10,
        )
        auth_message = {
            "id": str(uuid.uuid4()),
            "type": "authorization",
            "data": {
                "token": f"Bearer {self.bot_token}"
            }
        }
        await self.websocket.send(json.dumps(auth_message))

    async def _process_websocket_message(self, message: str) -> None:
        try:
            msg = json.loads(message)
            
            if msg.get("data", {}).get("eventType") == "conversation.activity":
                activity = msg["data"].get("activity", {})
                verb = activity.get("verb", "")
                
                if verb == "post":
                    await self._handle_message_event(activity)
                elif verb == "cardAction":
                    await self._handle_card_event(activity)
                elif verb == "add":
                    await self._handle_membership_add_event(activity)
                elif verb == "leave":
                    await self._handle_membership_leave_event(activity)
                    
        except json.JSONDecodeError as e:
            print(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            print(f"Error processing message: {e}")
            import traceback
            traceback.print_exc()

    async def _handle_message_event(self, activity: dict) -> None:
        activity_id = activity.get("id", "") 
        if not activity_id:
            return
        try:
            message = self.api.messages.get(webex_utils.activity_id_to_message_id(activity_id))
        except ApiError as e:
            print(f"Failed to get message for activity id {activity_id}: {e}")
            return
        # Ignore messages from the bot itself
        if message.personId == self.bot_id:
            return
        
        room_id = message.roomId
        person_id = message.personId
        if not self.is_user_authorized(room_id, person_id):
            return
        
        if message.text:
            self.handle_command(message.text, room_id, person_id)

    async def _handle_card_event(self, activity: dict) -> None:
        activity_id = activity.get("id", "")
        if not activity_id:
            return
        
        attachment_id = webex_utils.activity_id_to_attachment_action_id(activity_id)
        
        target = activity.get("target", {})
        room_id = self._extract_room_id_from_target(target)
        
        person_id = self.get_id_from_email(activity.get("actor", {}).get("id", ""), room_id)
        if not self.is_user_authorized(room_id, person_id):
            return
        if room_id and person_id:
            self.handle_card(attachment_id, room_id, person_id)

    async def _handle_membership_add_event(self, activity: dict) -> None:
        obj = activity.get("object", {})
        person_id = obj.get("id", "")
        
        target = activity.get("target", {})
        room_id = webex_utils.extract_room_id_from_target(target)
        admin_id = self.get_id_from_email(activity.get("actor", {}).get("id", ""), room_id)
        
        if not room_id:
            return
        
        if person_id and webex_utils.is_bot_id(self.bot_id, person_id):
            print(f"Bot was added to room {room_id}")
            self.handle_added(room_id, admin_id)

    async def _handle_membership_leave_event(self, activity: dict) -> None:
        obj = activity.get("object", {})
        person_id = obj.get("id", "")
        
        target = activity.get("target", {})
        room_id = webex_utils.extract_room_id_from_target(target)
        
        if not room_id:
            return
        
        if person_id and webex_utils.is_bot_id(self.bot_id, person_id):
            print(f"Bot was removed from room {room_id}")
            self.handle_removed(room_id)

    def _activity_id_to_attachment_action_id(self, activity_id: str) -> str:
        base_string = f"ciscospark://us/ATTACHMENT_ACTION/{activity_id}"
        return b64encode(base_string.encode("utf-8")).decode("utf-8").rstrip("=")

    def _extract_room_id_from_target(self, target: dict) -> str:
        target_id = target.get("id", "")
        if not target_id:
            return ""
        
        base_string = f"ciscospark://us/ROOM/{target_id}"
        return b64encode(base_string.encode("utf-8")).decode("utf-8").rstrip("=")

    def _extract_person_id_from_actor(self, actor: dict) -> str:
        actor_id = actor.get("id", "")
        if not actor_id:
            return ""
        base_string = f"ciscospark://us/PEOPLE/{actor_id}"
        return b64encode(base_string.encode("utf-8")).decode("utf-8").rstrip("=")

    def _is_bot_id(self, person_id: str) -> bool:
        try:
            import base64
            decoded = base64.b64decode(self.bot_id + "==").decode("utf-8")
            if "/PEOPLE/" in decoded:
                bot_uuid = decoded.split("/PEOPLE/")[-1]
                return person_id == bot_uuid
        except:
            pass
        
        return person_id == self.bot_id

    def does_room_manage_org(self, room_id: str) -> bool:
        room = self.storage.get_room(room_id)
        if not room:
            print("Error: Room not found in storage.")
            raise Exception("Room not found in storage.")
        if room['managed_org'].get('org_id', ''):
            print("Room has an authorized org.")
            return True
        else:
            request_id = secrets.token_urlsafe(32)
            auth_url = self.oauth.create_auth_url(room_id, request_id)
            message = self.api.messages.create(
                roomId=room_id, 
                markdown=f"To get started, please authorize with your admin account:\n\n[Click here to authorize]({auth_url})"
            )
            self.active_auth_requests[request_id] = message.id
            return False
    
    def remove_managed_org(self, room_id: str) -> None:
        room = self.storage.get_room(room_id)
        if not room:
            print("Error: Room not found in storage.")
            return
        room['managed_org'] = {
            'org_id': '',
            'org_name': '',
            'oauth_tokens': {}
        }
        print(f"Removed managed organization from room {room_id}")

    def get_email_from_id(self, person_id: str, room_id: str) -> str:
        try:
            memberships = self.api.memberships.list(roomId=room_id, personId=person_id)
            for membership in memberships:
                return membership.personEmail
            return ""
        except ApiError:
            return ""

    def get_id_from_email(self, email: str, room_id: str) -> str:
        try:
            memberships = self.api.memberships.list(roomId=room_id, personEmail=email)
            for membership in memberships:
                return membership.personId
            return ""
        except ApiError:
            return ""

    def set_room_admin(self, room_id: str, user_email: str, quiet=False) -> bool:
        room = self.storage.get_room(room_id)
        if not room:
            print("Error: Room not found in storage.")
            return False
        admin_id = self.get_id_from_email(user_email, room_id)
        if not admin_id:
            print(f"Error: User {user_email} not found in room {room_id}.")
            return False
        room['room_admin']['email'] = user_email
        room['room_admin']['id'] = admin_id
        if not quiet:
            self.api.messages.create(
                roomId=room_id,
                text=f"User {user_email} is now the room admin."
            )
        return True

    def add_allowed_user(self, room_id: str, user_email: str) -> bool:
        room = self.storage.get_room(room_id)
        if not room:
            print("Error: Room not found in storage.")
            return False
        try:
            memberships = list(self.api.memberships.list(roomId=room_id, personEmail=user_email))
            if not memberships:
                print(f"Error: User {user_email} not found in room {room_id}.")
                return False
            room['room_authorized_users'].append(memberships[0].personId)
        except ApiError:
            print(f"Error: Could not retrieve memberships for user {user_email} in room {room_id}.")
            return False
        return True
    
    def remove_allowed_user(self, room_id: str, user_email: str) -> bool:
        room = self.storage.get_room(room_id)
        if not room:
            print("Error: Room not found in storage.")
            return False
        admin_id = self.get_id_from_email(user_email, room_id)
        if not admin_id:
            print(f"Error: User {user_email} not found in room {room_id}.")
            return False
        person_id = admin_id
        if person_id in room['room_authorized_users']:
            room['room_authorized_users'].remove(person_id)
            return True
        else:
            print(f"Error: User {user_email} is not in the authorized users list for room {room_id}.")
            return False

    def handle_added(self, room_id: str, admin_id: str) -> None:
        room_details = self.api.rooms.get(room_id)
        admin_email = self.get_email_from_id(admin_id, room_id)
        if not admin_email or not room_details:
            print("Error: Could not get admin email or room details.")
            return
        self.storage.add_room(
            room_id,
            room_details.title
        )
        self.api.messages.create(
            roomId=room_id,
            text="Hello! I'm here to help you provision Webex Boards for your organization."
        )
        self.set_room_admin(room_id, admin_email)
        self.does_room_manage_org(room_id)

    def handle_removed(self, room_id: str) -> None:
        self.storage.remove_room(room_id)
        print(f"Cleaned up state for room {room_id}")

    def is_user_authorized(self, room_id: str, actor_id: str) -> bool:
        room = self.storage.get_room(room_id)
        if not room:
            print("Error: Room not found in storage.")
            return False
        room_admin = room['room_admin']
        # if room_admin email and id are empty, authorize the first user to send a message
        if not room_admin.get('email') and not room_admin.get('id'):
            print("No room admin set, authorizing first user to send a message.")
            return self.set_room_admin(room_id, self.get_email_from_id(actor_id, room_id))
        authorized = actor_id in room['room_authorized_users'] or actor_id == room_admin['id']
        if not authorized:
            room_admin_email = room['room_admin'].get('email', 'the room admin')
            self.api.messages.create(
                roomId=room_id,
                text=f"You don't have rights in this room, please ask {room_admin_email} to grant you permissions."
            )
        return authorized
    
    def get_valid_token_for_room(self, room) -> str:
        tokens = room.get('managed_org', {}).get('oauth_tokens', {})
        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token')
        expires_at = datetime.datetime.fromisoformat(tokens.get('expires_at', '1970-01-01T00:00:00'))
        if not access_token or time() >= expires_at.timestamp():
            print("Access token missing or expired.")
            tokens = self.oauth.refresh_tokens(refresh_token=refresh_token)
            room['managed_org']['oauth_tokens'] = tokens
            access_token = room['managed_org']['oauth_tokens']['access_token']
        return access_token
    
    def handle_card(self, attachment_id: str, room_id: str, actor_id: str) -> None:
        try:
            if not self.does_room_manage_org(room_id):
                return
            card_input = self.api.attachment_actions.get(id=attachment_id)
        except ApiError as e:
            print(f"Failed to get attachment action: {e}")
            return
        
        room = self.storage.get_room(room_id)
        if not room:
            print("Error: Room not found in storage.")
            return
        
        webex_admin = WebexAdmin(
            my_token=self.get_valid_token_for_room(room)
        )
        new_workspace_name = card_input.inputs["workspace"].strip()
        existing_workspace_id = card_input.inputs.get("existing-workspace", "").strip()
        if not new_workspace_name and not existing_workspace_id:
            self.api.messages.create(
                roomId=room_id,
                text="Please provide a workspace name or select an existing workspace."
            )
            return
        
        existing_workspace_name = webex_admin.list_workspaces().get(existing_workspace_id, "")
        workspace_name = new_workspace_name if new_workspace_name else existing_workspace_name
        activation_code = webex_admin.get_activation_code(new_workspace_name, existing_workspace_id)
        if activation_code == "":
            self.api.messages.create(
                roomId=room_id,
                text="Something went wrong. Please check if you need to update the access "
                        "token or if you've been sending too many requests."
            )
            return
        
        activation_code = helper.split_code(activation_code)
        print("Sending activation code.")
        self.api.messages.create(
            roomId=room_id,
            markdown=f"Here's your activation code: {activation_code} for workspace *{workspace_name}*"
        )
    

    def handle_command(self, message: str, room_id: str, actor_id: str) -> None:
        words = message.split()
        if not words:
            return
        
        # Messages sent to everyone are not addressed to the bot
        if words[0] == "All":
            return
        # Strip bot name if it's the first word
        if self.bot_name.split()[0].lower() == words[0].lower():
            words = words[1:]
        command = words
        
        print(f"Command: {' '.join(command)}")
        
        match command[0]:
            case "reinit" | "reinitialize":
                self.remove_managed_org(room_id)
                self.does_room_manage_org(room_id)
                return
            case "add":
                for email in command[1:]:
                    success = self.add_allowed_user(room_id, email)
                    if success:
                        self.api.messages.create(
                            roomId=room_id,
                            text=f"User {email} added successfully."
                        )
                    else:
                        self.api.messages.create(
                            roomId=room_id,
                            text=f"Failed to add user {email}. Make sure they are in this room."
                        )
                return
            case "help":
                self.api.messages.create(
                    roomId=room_id,
                    text=(
                        "To initialize the bot, please authorize using the link provided. "
                        "If the bot is already initialized, mention the bot to receive a card "
                        "to fill out to get an activation code.\n\nOther commands include:\n- "
                        "`add` [email]: add an authorized user to your organization; add "
                        "`info`: get info about the organization linked to this room\n- "
                        "several at once separated with a space\n- "
                        "`remove` [email]: remove an authorized user from your organization; "
                        "remove several at once separated with a space\n- "
                        "`reinit`: change organization and/or re-authorize for this room\n "
                        "If you require further assistance, please contact me "
                        "at ivanivan@cisco.com."
                    )
                )
            case "remove":
                for email in command[1:]:
                    success = self.remove_allowed_user(room_id, email)
                    if success:
                        self.api.messages.create(
                            roomId=room_id,
                            text=f"User {email} removed successfully.")
                    else:
                        self.api.messages.create(
                            roomId=room_id,
                            text=f"Failed to remove user {email}. Make sure they are in the allowed users list.")
            case "info":
                room = self.storage.get_room(room_id)
                if not room:
                    print("Error: Room not found in storage.")
                    return
                org_name = room['managed_org'].get('org_name', 'N/A')
                org_id = room['managed_org'].get('org_id', 'N/A')
                room_admin_email = room['room_admin'].get('email', 'N/A')
                authorized_users = [
                    self.get_email_from_id(user_id, room_id)
                    for user_id in room['room_authorized_users']
                ]
                authorized_users_str = ", ".join(authorized_users) if authorized_users else "N/A"
                self.api.messages.create(
                    roomId=room_id,
                    markdown=(
                        f"**This room is linked to the following organization:**\n"
                        f"- Organization Name: {org_name}\n"
                        f"- Organization ID: {org_id}\n\n"
                        f"{self.bot_name} will only respond to authorized users in this room:\n"
                        f"- Owner: {room_admin_email}\n"
                        f"- Authorized Users: {authorized_users_str}"
                    )
                )
            case _:
                room = self.storage.get_room(room_id)
                if not self.does_room_manage_org(room_id):
                    return
                self.api.messages.create(
                    roomId=room_id,
                    text="Here's your card",
                    attachments=[self.code_card(room)]
                )

    async def _run_loop(self) -> None:
        reconnect_delay = 5
        max_reconnect_delay = 300
        
        await self.oauth._start_http_server()
        while self.running:
            try:
                await self._connect_websocket()
                reconnect_delay = 5
                
                print("Listening for Webex events...")
                
                async for message in self.websocket: # type: ignore
                    if not self.running:
                        break
                    await self._process_websocket_message(message) # type: ignore
                    
            except ConnectionClosedError as e:
                # that means authentication error
                print(f"WebSocket connection closed error: {e}")
                self.running = False

            except ConnectionClosed as e:
                print(f"WebSocket connection closed: {e}")
            except Exception as e:
                print(f"WebSocket error: {e}")
                import traceback
                traceback.print_exc()
            
            if self.running:
                print(f"Reconnecting in {reconnect_delay} seconds...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)


    def run(self) -> None:
        self.running = True
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        def signal_handler(sig, frame):
            print(f"\nReceived signal {sig}, shutting down...")
            self.running = False
            if self.websocket:
                asyncio.run_coroutine_threadsafe(self.websocket.close(), self.loop) # type: ignore
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            self.loop.run_until_complete(self._run_loop())
        finally:
            self.loop.close()
            print("Bot stopped")

    def stop(self) -> None:
        self.running = False
        if self.websocket:
            asyncio.run_coroutine_threadsafe(self.websocket.close(), self.loop) # type: ignore


if __name__ == "__main__":
    bot_data_location = Path("bot_data.json")
    # create file if it doesn't exist
    if not bot_data_location.exists():
        bot_data_location.touch()
        
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN is required")
        sys.exit(1)
    bot = BotWS(bot_token=BOT_TOKEN, storage=StorageManager(fileLocation=bot_data_location))
    
    print(f"Starting WebSocket bot: {bot.bot_name} ({bot.bot_email})")
    print("Press Ctrl+C to stop")
    
    try:
        bot.run()
    finally:
        bot.save()
