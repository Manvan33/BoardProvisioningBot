import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Mocking modules before imports
sys.modules['dotenv'] = MagicMock()
sys.modules['websockets'] = MagicMock()
sys.modules['websockets.exceptions'] = MagicMock()
sys.modules['webexteamssdk'] = MagicMock()
sys.modules['helper'] = MagicMock()
sys.modules['oauth_manager'] = MagicMock()
sys.modules['storage_manager'] = MagicMock()
sys.modules['webex_utils'] = MagicMock()
sys.modules['webex_admin'] = MagicMock()

# Add parent directory to path so we can import bot_ws
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot_ws import BotWS

class TestBotLogic(unittest.TestCase):
    def setUp(self):
        # Mock dependencies
        self.mock_storage = MagicMock()
        self.mock_api = MagicMock()

        # Patch WebexTeamsAPI to return our mock
        with patch('bot_ws.WebexTeamsAPI', return_value=self.mock_api):
            # Patch os.getenv to provide required env vars
            with patch.dict(os.environ, {
                "BOT_TOKEN": "fake_token",
                "OAUTH_CLIENT_ID": "fake_id",
                "OAUTH_CLIENT_SECRET": "fake_secret"
            }):
                # Need to mock me() call in __init__
                self.mock_api.people.me.return_value.displayName = "Test Bot"
                self.mock_api.people.me.return_value.emails = ["bot@example.com"]
                self.mock_api.people.me.return_value.id = "bot_id"
                self.mock_api.memberships.list.return_value = []

                # Mock storage.get_room to return a valid room dict
                self.mock_room = {
                    'room_authorized_users': [],
                    'managed_org': {},
                    'room_admin': {'id': 'admin_id', 'email': 'admin@example.com'}
                }
                self.mock_storage.get_room.return_value = self.mock_room

                self.bot = BotWS(bot_token="fake_token", storage=self.mock_storage)

    def test_add_user_by_email_text(self):
        # Test functionality: adding user by email string
        room_id = "room123"
        actor_id = "actor123"
        email = "user@example.com"

        # Mock memberships.list to return the user
        m = MagicMock()
        m.personId = "user_id_123"
        m.personEmail = email
        self.mock_api.memberships.list.return_value = [m]

        # Mock message object
        message_obj = MagicMock()
        message_obj.text = f"add {email}"
        message_obj.mentionedPeople = []

        self.bot.handle_command(message_obj, room_id, actor_id)

        # Verify API called for all memberships
        self.mock_api.memberships.list.assert_called_with(roomId=room_id)
        # Verify user added to storage
        self.assertIn("user_id_123", self.mock_room['room_authorized_users'])

    def test_add_multiple_users_text(self):
        room_id = "room123"
        actor_id = "actor123"
        email1 = "user1@example.com"
        email2 = "user2@example.com"

        m1 = MagicMock()
        m1.personId = "id1"
        m1.personEmail = email1
        m2 = MagicMock()
        m2.personId = "id2"
        m2.personEmail = email2
        self.mock_api.memberships.list.return_value = [m1, m2]

        message_obj = MagicMock()
        message_obj.text = f"add {email1} {email2}"
        message_obj.mentionedPeople = []

        self.bot.handle_command(message_obj, room_id, actor_id)

        self.assertIn("id1", self.mock_room['room_authorized_users'])
        self.assertIn("id2", self.mock_room['room_authorized_users'])

    def test_add_user_by_mention(self):
        room_id = "room123"
        actor_id = "actor123"
        user_id = "user_id_123"
        email = "user@example.com"

        m = MagicMock()
        m.personId = user_id
        m.personEmail = email
        self.mock_api.memberships.list.return_value = [m]

        message_obj = MagicMock()
        message_obj.text = "add John Doe"
        message_obj.mentionedPeople = [user_id]

        self.bot.handle_command(message_obj, room_id, actor_id)

        self.assertIn(user_id, self.mock_room['room_authorized_users'])

    def test_add_mixed_mentions_and_text(self):
        room_id = "room123"
        actor_id = "actor123"

        user_id_1 = "user_id_1"
        email_1 = "user1@example.com" # From mention
        email_2 = "user2@example.com" # From text
        id_2 = "user_id_2"

        m1 = MagicMock()
        m1.personId = user_id_1
        m1.personEmail = email_1
        m2 = MagicMock()
        m2.personId = id_2
        m2.personEmail = email_2
        self.mock_api.memberships.list.return_value = [m1, m2]

        message_obj = MagicMock()
        message_obj.text = f"add John {email_2}"
        message_obj.mentionedPeople = [user_id_1]

        self.bot.handle_command(message_obj, room_id, actor_id)

        self.assertIn(user_id_1, self.mock_room['room_authorized_users'])
        self.assertIn(id_2, self.mock_room['room_authorized_users'])

    def test_ignore_bot_mention(self):
        room_id = "room123"
        actor_id = "actor123"

        # Bot's ID is "bot_id" (set in setUp)
        user_id = "user_id_123"
        email = "user@example.com"

        m = MagicMock()
        m.personId = user_id
        m.personEmail = email
        self.mock_api.memberships.list.return_value = [m]

        message_obj = MagicMock()
        message_obj.text = "add @Bot @User"
        message_obj.mentionedPeople = ["bot_id", user_id]

        self.bot.handle_command(message_obj, room_id, actor_id)

        self.assertIn(user_id, self.mock_room['room_authorized_users'])

    def test_remove_user_by_mention(self):
        room_id = "room123"
        actor_id = "actor123"
        user_id = "user_id_123"
        email = "user@example.com"

        self.mock_room['room_authorized_users'] = [user_id]

        m = MagicMock()
        m.personId = user_id
        m.personEmail = email
        self.mock_api.memberships.list.return_value = [m]

        message_obj = MagicMock()
        message_obj.text = "remove @User"
        message_obj.mentionedPeople = [user_id]

        self.bot.handle_command(message_obj, room_id, actor_id)

        self.assertNotIn(user_id, self.mock_room['room_authorized_users'])

    def test_remove_user_by_email(self):
        room_id = "room123"
        actor_id = "actor123"
        user_id = "user_id_123"
        email = "user@example.com"

        self.mock_room['room_authorized_users'] = [user_id]

        m = MagicMock()
        m.personId = user_id
        m.personEmail = email
        self.mock_api.memberships.list.return_value = [m]

        message_obj = MagicMock()
        message_obj.text = f"remove {email}"
        message_obj.mentionedPeople = []

        self.bot.handle_command(message_obj, room_id, actor_id)

        self.assertNotIn(user_id, self.mock_room['room_authorized_users'])


if __name__ == '__main__':
    unittest.main()
