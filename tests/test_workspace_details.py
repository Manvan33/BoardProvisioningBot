import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock dependencies
sys.modules['helper'] = MagicMock()
sys.modules['oauth_manager'] = MagicMock()
sys.modules['storage_manager'] = MagicMock()
# We need to mock webex_utils but allow setting return values
mock_webex_utils = MagicMock()
sys.modules['webex_utils'] = mock_webex_utils
sys.modules['webex_admin'] = MagicMock()

from bot_ws import BotWS

class TestWorkspaceDetails(unittest.TestCase):
    def setUp(self):
        self.mock_storage = MagicMock()
        self.mock_api = MagicMock()

        # Configure webex_utils mock
        mock_webex_utils.base64_to_uuid.return_value = "uuid-123"

        with patch('bot_ws.WebexTeamsAPI', return_value=self.mock_api):
            with patch.dict(os.environ, {
                "BOT_TOKEN": "fake_token",
                "OAUTH_CLIENT_ID": "fake_id",
                "OAUTH_CLIENT_SECRET": "fake_secret"
            }):
                self.mock_api.people.me.return_value.displayName = "Test Bot"
                self.mock_api.people.me.return_value.emails = ["bot@example.com"]
                self.mock_api.memberships.list.return_value = []

                self.bot = BotWS(bot_token="fake_token", storage=self.mock_storage)

    def test_format_uptime(self):
        # Test seconds to readable string
        self.assertEqual(self.bot._format_uptime("60"), "1m")
        self.assertEqual(self.bot._format_uptime("3600"), "1h")
        self.assertEqual(self.bot._format_uptime("86400"), "1d")
        self.assertEqual(self.bot._format_uptime("90060"), "1d 1h 1m")
        self.assertEqual(self.bot._format_uptime("30"), "< 1m")
        self.assertEqual(self.bot._format_uptime("invalid"), "")
        self.assertEqual(self.bot._format_uptime("-10"), "")

    def test_workspace_details_string_with_uptime(self):
        workspace_id = "ws1"
        workspace_name = "Test Workspace"

        # Mock WebexAdmin
        mock_admin = MagicMock()

        # Mock device data
        device_id = "device_id_1"
        device = {
            "id": device_id,
            "product": "Webex Board",
            "callingDeviceId": "call_id",
            "mac": "AA:BB:CC",
            "connectionStatus": "connected",
            "primarySipUrl": "sip:device@example.com",
            "ip": "1.2.3.4"
        }
        mock_admin.get_devices.return_value = [device]

        # Mock uptime
        mock_admin.get_device_uptime.return_value = "90060" # 1d 1h 1m

        result = self.bot.workspace_details_string(workspace_id, workspace_name, mock_admin)

        self.assertIn("uptime: 1d 1h 1m", result)
        self.assertIn("🟢", result) # Connected status
        mock_admin.get_device_uptime.assert_called_with(device_id)

    def test_workspace_details_string_no_uptime_when_disconnected(self):
        workspace_id = "ws1"
        workspace_name = "Test Workspace"
        mock_admin = MagicMock()

        device = {
            "id": "device_id_1",
            "product": "Webex Board",
            "connectionStatus": "disconnected",
            "lastSeen": "2023-01-01T12:00:00.000Z"
        }
        mock_admin.get_devices.return_value = [device]

        result = self.bot.workspace_details_string(workspace_id, workspace_name, mock_admin)

        self.assertNotIn("uptime:", result)
        self.assertIn("🔴", result)
        mock_admin.get_device_uptime.assert_not_called()

if __name__ == '__main__':
    unittest.main()
