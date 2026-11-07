import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.TournamentDataProvider.NexusRoomClient import NexusRoomClient
from src.Helpers.TSHCharacterHelper import normalize_character_name, parse_mii_moveset


class TestNexusRoomClient(unittest.TestCase):
    def setUp(self):
        self.client = NexusRoomClient()

    def test_parse_url_standard_match_live(self):
        url = "https://thenexus.gg/matches/grand-finals-crew/live?token=signed_token_123"
        origin, slug, token = self.client.parse_url(url)
        self.assertEqual(origin, "https://thenexus.gg")
        self.assertEqual(slug, "grand-finals-crew")
        self.assertEqual(token, "signed_token_123")

    def test_parse_url_qa_subdomain(self):
        url = "https://qa.thenexus.gg/matches/qa-crew-battle/live?token=qa_token"
        origin, slug, token = self.client.parse_url(url)
        self.assertEqual(origin, "https://qa.thenexus.gg")
        self.assertEqual(slug, "qa-crew-battle")
        self.assertEqual(token, "qa_token")

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

    def test_parse_url_no_scheme(self):
        url = "qa.thenexus.gg/matches/no-scheme-match"
        origin, slug, token = self.client.parse_url(url)
        self.assertEqual(origin, "https://qa.thenexus.gg")
        self.assertEqual(slug, "no-scheme-match")

        url_local = "localhost:3000/matches/local-match"
        origin_l, slug_l, token_l = self.client.parse_url(url_local)
        self.assertEqual(origin_l, "http://localhost:3000")
        self.assertEqual(slug_l, "local-match")

    def test_parse_url_whitespace_handling(self):
        url = "   https://thenexus.gg/matches/clean-slug/live?token=tok   \n"
        origin, slug, token = self.client.parse_url(url)
        self.assertEqual(origin, "https://thenexus.gg")
        self.assertEqual(slug, "clean-slug")
        self.assertEqual(token, "tok")

    def test_parse_url_rejects_x_com(self):
        url = "https://x.com/2113696815728251063"
        with self.assertRaises(ValueError) as ctx:
            self.client.parse_url(url)
        self.assertIn("Invalid host", str(ctx.exception))
        self.assertIn("thenexus.gg", str(ctx.exception))

    def test_parse_url_rejects_arbitrary_domains(self):
        for bad_url in [
            "https://google.com/matches/test",
            "https://not-thenexus.gg/matches/test",
            "https://fake-thenexus.gg/matches/test",
        ]:
            with self.subTest(bad_url=bad_url):
                with self.assertRaises(ValueError):
                    self.client.parse_url(bad_url)

    def test_parse_url_rejects_missing_slug(self):
        with self.assertRaises(ValueError):
            self.client.parse_url("https://thenexus.gg/")
        with self.assertRaises(ValueError):
            self.client.parse_url("https://thenexus.gg/about")

    def test_connect_url_validation_failure(self):
        success, err = self.client.connect_url("https://x.com/something")
        self.assertFalse(success)
        self.assertTrue(len(err) > 0)
        self.assertFalse(self.client.is_running)

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

    def test_parse_url_cloud_run_host(self):
        url = "https://the-nexus-qa-ia6suqvgqq-ue.a.run.app/matches/cloudrun-match/live?token=cr_tok"
        origin, slug, token = self.client.parse_url(url)
        self.assertEqual(origin, "https://the-nexus-qa-ia6suqvgqq-ue.a.run.app")
        self.assertEqual(slug, "cloudrun-match")
        self.assertEqual(token, "cr_tok")

    def test_connect_url_constructs_stream_urls(self):
        # qa.thenexus.gg -> uses official domain; server returns 307 redirect to streaming host
        self.client.connect_url("https://qa.thenexus.gg/matches/qa-crew/live?token=test_tok")
        self.assertEqual(
            self.client.stream_url,
            "https://qa.thenexus.gg/api/live-match/qa-crew/stream?token=test_tok"
        )
        self.client.disconnect()

        # thenexus.gg -> uses official domain
        self.client.connect_url("https://thenexus.gg/matches/prod-crew/live?token=test_tok")
        self.assertEqual(
            self.client.stream_url,
            "https://thenexus.gg/api/live-match/prod-crew/stream?token=test_tok"
        )
        self.client.disconnect()

        # localhost -> preserves localhost for dev
        self.client.connect_url("http://localhost:3000/matches/local-crew/live?token=test_tok")
        self.assertEqual(
            self.client.stream_url,
            "http://localhost:3000/api/live-match/local-crew/stream?token=test_tok"
        )
        self.client.disconnect()

    def test_disconnect_cleans_up_resources(self):
        class MockRaw:
            def __init__(self):
                self.closed = False
            def close(self):
                self.closed = True

        class MockResponse:
            def __init__(self):
                self.closed = False
                self.raw = MockRaw()
            def close(self):
                self.closed = True

        mock_resp = MockResponse()
        self.client.current_response = mock_resp
        self.client.is_running = True
        self.client.slug = "test-slug"
        self.client.token = "test-token"

        self.client.disconnect()

        self.assertFalse(self.client.is_running)
        self.assertTrue(mock_resp.closed)
        self.assertTrue(mock_resp.raw.closed)
        self.assertIsNone(self.client.current_response)
        self.assertIsNone(self.client.slug)
        self.assertIsNone(self.client.token)

    def test_mii_character_normalization(self):
        cases = [
            ("Mii Brawler (1332)", ("Mii Brawler", "1332")),
            ("Mii Gunner (3122)", ("Mii Gunner", "3122")),
            ("Mii Swordfighter (2132)", ("Mii Swordfighter", "2132")),
            ("Mii Sword Fighter (2132)", ("Mii Swordfighter", "2132")),
            ("Mii Brawler 1332", ("Mii Brawler", "1332")),
            ("mii brawler (1231)", ("Mii Brawler", "1231")),
            ("Mii Brawler", ("Mii Brawler", None)),
            ("Mii Gunner", ("Mii Gunner", None)),
            ("Mii Swordfighter", ("Mii Swordfighter", None)),
            ("Mario", ("Mario", None)),
            ("Fox", ("Fox", None)),
            ("", (None, None)),
            (None, (None, None)),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_character_name(raw), expected)

    def test_parse_mii_moveset(self):
        self.assertEqual(parse_mii_moveset("Mii Brawler (1332)"), "1332")
        self.assertEqual(parse_mii_moveset("Mii Gunner (3122)"), "3122")
        self.assertEqual(parse_mii_moveset("1332"), "1332")
        self.assertEqual(parse_mii_moveset("(2132)"), "2132")
        self.assertIsNone(parse_mii_moveset("Mii Brawler"))
        self.assertIsNone(parse_mii_moveset("Mario"))
        self.assertIsNone(parse_mii_moveset(""))
        self.assertIsNone(parse_mii_moveset(None))


if __name__ == "__main__":
    unittest.main()
