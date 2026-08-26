import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import time

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

class BenchmarkNPlusOne(unittest.TestCase):
    def setUp(self):
        self.mock_storage = MagicMock()
        self.mock_api = MagicMock()

        with patch('bot_ws.WebexTeamsAPI', return_value=self.mock_api):
            with patch.dict(os.environ, {
                "BOT_TOKEN": "fake_token",
                "OAUTH_CLIENT_ID": "fake_id",
                "OAUTH_CLIENT_SECRET": "fake_secret"
            }):
                self.mock_api.people.me.return_value.displayName = "Test Bot"
                self.mock_api.people.me.return_value.emails = ["bot@example.com"]
                self.mock_api.people.me.return_value.id = "bot_id"
                self.mock_api.memberships.list.return_value = []

                self.mock_room = {
                    'room_authorized_users': [],
                    'managed_org': {},
                    'room_admin': {'id': 'admin_id', 'email': 'admin@example.com'}
                }
                self.mock_storage.get_room.return_value = self.mock_room

                self.bot = BotWS(bot_token="fake_token", storage=self.mock_storage)

    def test_benchmark_add_mentions(self):
        num_mentions = 10
        mentioned_people = [f"user_id_{i}" for i in range(num_mentions)]

        # Mock memberships.list
        def list_memberships(roomId=None, personId=None, personEmail=None, id=None, **kwargs):
            # Simulate network delay
            time.sleep(0.01)

            if roomId and not personId and not personEmail and not id:
                # Return all mentioned people + some others
                results = []
                for i in range(num_mentions):
                    m = MagicMock()
                    m.personId = f"user_id_{i}"
                    m.personEmail = f"user_id_{i}@example.com"
                    results.append(m)
                return results

            if id:
                # Batch call simulation
                ids = id.split(',')
                results = []
                for pid in ids:
                    m = MagicMock()
                    m.personEmail = f"{pid}@example.com"
                    m.personId = pid
                    results.append(m)
                return results

            m = MagicMock()
            if personId:
                m.personEmail = f"{personId}@example.com"
                m.personId = personId
            elif personEmail:
                m.personId = personEmail.split('@')[0]
                m.personEmail = personEmail
            return [m]

        self.mock_api.memberships.list.side_effect = list_memberships

        message_obj = MagicMock()
        message_obj.text = "add " + " ".join([f"User{i}" for i in range(num_mentions)])
        message_obj.mentionedPeople = mentioned_people

        print(f"\nStarting benchmark with {num_mentions} mentions...")
        start_time = time.time()
        self.bot.handle_command(message_obj, "room123", "admin_id")
        end_time = time.time()

        duration = end_time - start_time
        print(f"Duration for {num_mentions} mentions: {duration:.4f} seconds")
        print(f"Total API calls (memberships.list): {self.mock_api.memberships.list.call_count}")

if __name__ == '__main__':
    unittest.main()
