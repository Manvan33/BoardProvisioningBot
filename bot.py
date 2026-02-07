from __future__ import print_function  # Needed if you want to have console output using Flask
from webexteamssdk import WebexTeamsAPI, ApiError
import json
import helper


# The entity communicating with the user
class Bot:

    def __init__(self, data):
        # read from file
        self.name = data["bot_name"]
        self.email = data["bot_email"]
        self.bot_token = data["bot_token"]

        # handles any API calls using the SDK
        self.api = WebexTeamsAPI(access_token=self.bot_token)
        self.id = self.api.people.me().id

        # adaptive cards
        self.code_card = helper.make_code_card()
        self.init_card = helper.make_init_card()

        # will be populated on startup
        self.webhooks = []

        # user populated data, is read from file in app.py and passed on creation
        # empty data passed if not found in file
        self.orgs = data["orgs"]  # list of organizations
        self.org_allowed_users = data["org_allowed_users"]  # list of allowed users for each organization
        self.org_id_to_email = data["org_id_to_email"]  # list of mappings of ids to emails for users of each organization
        self.room_to_admin = {}  # maps each room to its admin
        self.room_to_org = data["room_to_org"]  # maps each room to its current org

        #  create an admin for each known room
        for room in data["admin_data"].keys():
            admin = helper.create_admin(data["admin_data"][room]["admin_token"], data["admin_data"][room]["org_id"], self.room_to_org[room])
            if admin.my_id == "": # if admin fails to get id, should be reinitialized
                self.reinit(room)
            else:
                self.room_to_admin[room] = admin

        self.unauthorized_message = ("You're unauthorized. Please contact the person who initialized the bot if you "
                                     "require access.")

    def startup(self) -> None:
        webhooks = self.api.webhooks.list()
        for webhook in webhooks:
            self.webhooks.append(webhook)
        if len(self.webhooks) < 4:
            print("Don't have all webhooks. Please verify")

    def teardown(self) -> None:
        admins_saved = {}
        for room in self.room_to_admin.keys():
            admins_saved[room] = self.room_to_admin[room].save()
        data = {
            "bot_name": self.name,
            "bot_token": self.bot_token,
            "bot_email": self.email,
            "orgs": self.orgs,
            "admin_data": admins_saved,
            "org_allowed_users": self.org_allowed_users,
            "room_to_org": self.room_to_org,
            "org_id_to_email": self.org_id_to_email
        }
        with open("bot_data.json", "w") as file:
            json.dump(data, file)

    def init_org(self, org_id, access_token, room_id, user_id):
        # check if this room is known already
        try:
            admin = self.room_to_admin[room_id]
            print("Bot knows this room.")
            if org_id != admin.org_id:
                print("Room wants to change organization.")
                self.room_to_org[room_id] = org_id
            admin.update_token(access_token)
            print("Token updated.")
            if not admin.token_is_valid():
                self.reinit(room_id)
                return None
        except KeyError:
            print("Bot does not know this room. Creating")
            admin = helper.create_admin(access_token, org_id, room_id)
            if not admin.token_is_valid():
                del admin
                return None
            self.room_to_admin[room_id] = admin
            self.org_id_to_email[org_id] = {}

        self.add_allowed_user(org_id, room_id, user_id=user_id)
        self.room_to_org[room_id] = org_id

        return admin

    def reinit(self, room_id):
        self.api.messages.create(roomId=room_id, text="Access token not valid or expired. Please reinitialize.")
        self.api.messages.create(room_id, text="Please initialize", attachments=[self.init_card])

    def get_email_from_id(self, person_id, room_id) -> str:
        try:
            memberships = self.api.memberships.list(roomId=room_id, personId=person_id)
            email = ""
            for membership in memberships:
                email = membership.personEmail
            return email
        except ApiError:
            return ""

        # Converts email to User ID. Needed for allowed users list. Returns empty string if email not found.
    def get_id_from_email(self, email, room_id) -> str:
        try:
            memberships = self.api.memberships.list(roomId=room_id, personEmail=email)
            user_id = ""
            for membership in memberships:
                user_id = membership.personId
            return user_id
        except ApiError:
            return ""

    def remove_room_from_org(self, room_id):
        del self.room_to_org[room_id]

    def add_allowed_user(self, org_id, room_id, email=None, user_id=None):
        if not user_id:
            user_id = self.get_id_from_email(email, room_id)
        elif not email:
            email = self.get_email_from_id(user_id, room_id)
        else:
            print("Error: Must specify user_id or email.")
            return ""
        if user_id == "":
            return user_id
        if org_id in self.orgs:
            if user_id not in self.org_allowed_users[org_id]:
                self.org_allowed_users[org_id].append(user_id)
                self.org_id_to_email[org_id][user_id] = email
                print(f"Added user {email} to allowed for org {org_id}.")
        else:
            self.org_allowed_users[org_id] = [user_id]
            self.org_id_to_email[org_id][user_id] = email
        return user_id

    def remove_allowed_user(self, org_id, email, room_id):
        user_id = self.get_id_from_email(email, room_id)
        if user_id != "" and user_id in self.org_allowed_users[org_id]:
            self.org_allowed_users[org_id].remove(user_id)
            print(f"Removed user {email} from allowed for org {org_id}.")
            return user_id
        else:
            return ""

    def handle_added(self, room_id):
        self.api.messages.create(room_id, text="Hello! I'm here to help you provision Webex Boards for your "
                                               "organization. Please provide me with your organization ID and an "
                                               "admin's access token.")
        self.api.messages.create(room_id, text="Please initialize", attachments=[self.init_card])

    # currently not in use, if want to use please rework
    def handle_removed(self, room_id):
        org_id = self.room_to_org[room_id]
        self.remove_room_from_org(room_id)
        # if org_id not in self.room_to_org.values():
            # del self.room_to_admin[room_id]

    def handle_unauthorized(self, org_id, actor_id, room_id):
        print(f"User {self.org_id_to_email[org_id][actor_id]} unauthorized.")
        self.api.messages.create(room_id, text=self.unauthorized_message)

    # Is called when card was submitted. Asks Admin to create activation code and sends it in the chat
    def handle_card(self, attachment_id, room_id, actor_id):
        card_input = self.api.attachment_actions.get(id=attachment_id)
        try:
            org_id = self.room_to_org[room_id]
            admin = self.room_to_admin[room_id]
        except KeyError:
            try:
                org_id = card_input.inputs["org_id"]
                access_token = card_input.inputs["access_token"]
                admin = self.init_org(org_id, access_token, room_id, actor_id)
                if admin:
                    self.api.messages.create(room_id, text="Initialization success.")
                else:
                    self.api.messages.create(room_id, text="Initialization unsuccessful. Please check your "
                                                           "organization ID and access token or contact "
                                                           "agrobys@cisco.com for assistance.")
                    return
            except KeyError:
                self.api.messages.create(room_id, text="Please initialize", attachments=[self.init_card])
                return
        if actor_id in self.org_allowed_users[org_id]:
            try:
                print(f"User {self.org_id_to_email[org_id][actor_id]} allowed.")
                workspace_name = card_input.inputs["workspace"].strip()
            except KeyError:
                self.api.messages.create(room_id, text="Bot initialized. If you need to update the access token, "
                                                       "please use the 'reinit' command, or type "
                                                       "'help' to view all available commands.")
                return
            # model = card_input.inputs["model"]
            # if model != "":
            #     activation_code = get_activation_code(workspace_name, model=model)
            activation_code = admin.get_activation_code(workspace_name)
            if activation_code == "":
                self.api.messages.create(room_id,
                                         text="Something went wrong. Please check if you need to update the access "
                                              "token or if you've been sending too many requests.")
                return
            activation_code = helper.split_code(activation_code)
            print(f"Sending activation code.")
            self.api.messages.create(room_id, text=f"Here's your activation code: {activation_code} for workspace {workspace_name}")
        else:
            self.handle_unauthorized(org_id, actor_id, room_id)

    # Is called when bot is mentioned. Checks for commands (if no special command is detected, it will send the
    # adaptive card)
    def handle_command(self, message, room_id, actor_id) -> None:
        # Ignore @All mentions
        if message.split()[0] == "All":
            return
        # Make sure bot is initialized for this room
        try:
            org_id = self.room_to_org[room_id]
            admin = self.room_to_admin[room_id]
        except KeyError:
            self.api.messages.create(room_id, text="Please initialize", attachments=[self.init_card])
            return

        # Strips bot mention from command
        if message.split()[0] == self.name:
            command = message.split()[1:]
        else:
            command = message.split()
        print(f"Command: {' '.join(command)}")

        # Command empty, send card
        if len(command) == 0:
            print("Sending card")
            self.api.messages.create(room_id, text="Here's your card", attachments=[self.code_card])

        elif command[0] == "reinit":
            if actor_id in self.org_allowed_users[org_id]:
                self.remove_room_from_org(room_id)
                self.api.messages.create(room_id, text="Please initialize", attachments=[self.init_card])
            else:
                self.handle_unauthorized(org_id, actor_id, room_id)

        elif command[0] == "help":
            self.api.messages.create(room_id, text=f"To initialize the bot, please fill out the card. If you don't "
                                                   f"see the card, mention the bot to receive it. If the bot is "
                                                   f"already initialized, mention the bot to receive a card to fill "
                                                   f"out to get an activation code.\n\nOther commands include:\n- "
                                                   f"add [email]: add an authorized user to your organization; add "
                                                   f"several at once separated with a space\n- "
                                                   f"remove [email]: remove an authorized user from your organization; "
                                                   f"remove several at once separated with a space\n- "
                                                   f"reinit: change organization and/or token for this room\n "
                                                   f"If you require further assistance, please contact me "
                                                   f"at agrobys@cisco.com.")

        # Adds allowed users on "add" command
        elif len(command) > 1 and command[0] == "add":
            if actor_id in self.org_allowed_users[org_id]:
                print(f"User {self.org_id_to_email[org_id][actor_id]} allowed.")
                for email in command[1:]:
                    user_id = self.add_allowed_user(org_id, room_id, email=email)
                    # Empty user_id means provided email was not found
                    if user_id == "":
                        self.api.messages.create(room_id, text=f"Something went wrong. If {email} was valid, check if you need to update your access token.")
                    else:
                        self.api.messages.create(room_id, text=f"User {email} added successfully.")
            else:
                self.handle_unauthorized(org_id, actor_id, room_id)

        # Removes allowed users on "remove" command
        elif len(command) > 1 and command[0] == "remove":
            if actor_id in self.org_allowed_users[org_id]:
                print(f"User {self.org_id_to_email[org_id][actor_id]} allowed.")
                for email in command[1:]:
                    user_id = self.remove_allowed_user(org_id, email, room_id)
                    # Empty user_id means provided email was not found
                    if user_id == "":
                        self.api.messages.create(room_id,
                                                 text=f"User not found in allowed list. If {email} was valid, check if you need to update your access token.")
                    else:
                        self.api.messages.create(room_id, text=f"User {email} removed successfully.")
            else:
                self.handle_unauthorized(org_id, actor_id, room_id)

        # Sends card if no special command is detected
        else:
            print(f"Sending card (No known command detected).")
            self.api.messages.create(room_id, text="Here's your card", attachments=[self.code_card])
