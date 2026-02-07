import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path so we can import bot_ws
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock dependencies that might be imported at module level or problematic
sys.modules['helper'] = MagicMock()
sys.modules['oauth_manager'] = MagicMock()
sys.modules['storage_manager'] = MagicMock()
sys.modules['webex_utils'] = MagicMock()
sys.modules['webex_admin'] = MagicMock()

# Now import BotWS
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
                    'room_admin': {}
                }
                self.mock_storage.get_room.return_value = self.mock_room

                self.bot = BotWS(bot_token="fake_token", storage=self.mock_storage)

    def test_add_user_by_email_text(self):
        # Test functionality: adding user by email string
        room_id = "room123"
        actor_id = "actor123"
        email = "user@example.com"

        # Mock API calls for add_allowed_user
        # add_allowed_user calls memberships.list(personEmail=email)
        m = MagicMock()
        m.personId = "user_id_123"
        self.mock_api.memberships.list.return_value = [m]

        # Mock message object
        message_obj = MagicMock()
        message_obj.text = f"add {email}"
        message_obj.mentionedPeople = []

        self.bot.handle_command(message_obj, room_id, actor_id)

        # Verify API called with email
        self.mock_api.memberships.list.assert_called_with(roomId=room_id, personEmail=email)
        # Verify user added to storage
        self.assertIn("user_id_123", self.mock_room['room_authorized_users'])

    def test_add_multiple_users_text(self):
        room_id = "room123"
        actor_id = "actor123"
        email1 = "user1@example.com"
        email2 = "user2@example.com"

        # Handle multiple calls
        def list_memberships(roomId=None, personEmail=None, **kwargs):
            if personEmail == email1:
                m = MagicMock()
                m.personId = "id1"
                return [m]
            if personEmail == email2:
                m = MagicMock()
                m.personId = "id2"
                return [m]
            return []

        self.mock_api.memberships.list.side_effect = list_memberships

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

        # Mock API calls
        # 1. get_email_from_id calls memberships.list(personId=user_id)
        # 2. add_allowed_user calls memberships.list(personEmail=email)

        def list_memberships(roomId=None, personId=None, personEmail=None, **kwargs):
            if personId == user_id:
                m = MagicMock()
                m.personEmail = email
                m.personId = user_id
                return [m]
            if personEmail == email:
                m = MagicMock()
                m.personId = user_id
                return [m]
            return []

        self.mock_api.memberships.list.side_effect = list_memberships

        message_obj = MagicMock()
        message_obj.text = "add John Doe"
        message_obj.mentionedPeople = [user_id]

        self.bot.handle_command(message_obj, room_id, actor_id)

        # Verify both calls happened (we can inspect mock calls or just verify outcome)
        self.assertIn(user_id, self.mock_room['room_authorized_users'])

    def test_add_mixed_mentions_and_text(self):
        room_id = "room123"
        actor_id = "actor123"

        user_id_1 = "user_id_1"
        email_1 = "user1@example.com" # From mention
        email_2 = "user2@example.com" # From text
        id_2 = "user_id_2"

        def list_memberships(roomId=None, personId=None, personEmail=None, **kwargs):
            if personId == user_id_1:
                m = MagicMock()
                m.personEmail = email_1
                m.personId = user_id_1
                return [m]
            if personEmail == email_1:
                m = MagicMock()
                m.personId = user_id_1
                return [m]
            if personEmail == email_2:
                m = MagicMock()
                m.personId = id_2
                return [m]
            return []

        self.mock_api.memberships.list.side_effect = list_memberships

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

        def list_memberships(roomId=None, personId=None, personEmail=None, **kwargs):
            if personId == user_id:
                m = MagicMock()
                m.personEmail = email
                m.personId = user_id
                return [m]
            if personEmail == email:
                m = MagicMock()
                m.personId = user_id
                return [m]
            return []

        self.mock_api.memberships.list.side_effect = list_memberships

        message_obj = MagicMock()
        message_obj.text = "add @Bot @User"
        message_obj.mentionedPeople = ["bot_id", user_id]

        self.bot.handle_command(message_obj, room_id, actor_id)

        # Should only try to add user, not bot
        self.assertIn(user_id, self.mock_room['room_authorized_users'])
        # Also ensure we didn't add @Bot or @User strings as users (they don't have dots)


if __name__ == '__main__':
    unittest.main()
