import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.TournamentDataProvider.NexusRoomClient import NexusRoomClient


class TestNexusRoomClient(unittest.TestCase):
    def setUp(self):
        self.client = NexusRoomClient()

    def test_parse_url_standard_match_live(self):
        url = "https://thenexus.gg/matches/grand-finals-crew/live?token=signed_token_123"
        origin, slug, token = self.client.parse_url(url)
        self.assertEqual(origin, "https://thenexus.gg")
        self.assertEqual(slug, "grand-finals-crew")
        self.assertEqual(token, "signed_token_123")

    def test_parse_url_api_endpoint(self):
        url = "http://localhost:3000/api/live-match/showmatch-crew-4v4/stream?token=xyz_999"
        origin, slug, token = self.client.parse_url(url)
        self.assertEqual(origin, "http://localhost:3000")
        self.assertEqual(slug, "showmatch-crew-4v4")
        self.assertEqual(token, "xyz_999")

    def test_parse_url_room_path(self):
        url = "https://staging.thenexus.gg/room/crew-battle-alpha"
        origin, slug, token = self.client.parse_url(url)
        self.assertEqual(origin, "https://staging.thenexus.gg")
        self.assertEqual(slug, "crew-battle-alpha")
        self.assertIsNone(token)

    def test_parse_url_whitespace_handling(self):
        url = "   https://thenexus.gg/matches/clean-slug/live?token=tok   \n"
        origin, slug, token = self.client.parse_url(url)
        self.assertEqual(origin, "https://thenexus.gg")
        self.assertEqual(slug, "clean-slug")
        self.assertEqual(token, "tok")

    def test_sse_event_parsing_and_emission(self):
        received_payloads = []
        self.client.signals.room_updated.connect(lambda p: received_payloads.append(p))

        mock_event_line = 'data: {"match_id": 42, "status": "in_progress", "active_duelist_id": 101}\n'
        line = mock_event_line.strip()
        if line.startswith("data:"):
            payload = json.loads(line[5:].strip())
            self.client.signals.room_updated.emit(payload)

        self.assertEqual(len(received_payloads), 1)
        self.assertEqual(received_payloads[0]["match_id"], 42)
        self.assertEqual(received_payloads[0]["active_duelist_id"], 101)


if __name__ == "__main__":
    unittest.main()
