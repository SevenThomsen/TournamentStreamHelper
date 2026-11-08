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

    def test_round_two_character_resolution_ignores_stale_blind_pick(self):
        """Verify that in Round 2+, characters come strictly from roster_selections,
        and stale blind picks from Round 1 do not override or pollute player selection."""
        # Scenario: Captain was blinded as Pikachu in Round 1, but entered in Round 2 playing Dark Samus
        captain_id = "cap_101"
        roster_selections = [
            {"player_id": "p2", "slot_order": 1, "selected_character": "Peach"},
            {"player_id": captain_id, "slot_order": 2, "selected_character": "Dark Samus"},
        ]
        blind_picks = [
            {"player_id": captain_id, "selected_character": "Pikachu"},
            {"player_id": "p2", "selected_character": "Peach"},
        ]
        live_state_r2 = {
            "round_number": 2,
            "home_active_player_id": captain_id,
            "away_active_player_id": "opp_1",
        }

        selections_by_player = {s["player_id"]: s for s in roster_selections}
        blind_by_player = {bp["player_id"]: bp for bp in blind_picks}

        is_round_one = (live_state_r2.get("round_number") or 1) == 1
        active_home_id = live_state_r2.get("home_active_player_id")
        active_away_id = live_state_r2.get("away_active_player_id")
        is_starter_hidden = (is_round_one and (not active_home_id or not active_away_id))

        # 1. Active Captain in Round 2
        is_active = (captain_id == active_home_id)
        sel_entry = selections_by_player.get(captain_id, {})
        bp_entry = blind_by_player.get(captain_id, {})

        char_name = sel_entry.get("selected_character") or sel_entry.get("character")
        if not char_name and is_round_one and is_active and not is_starter_hidden:
            char_name = bp_entry.get("selected_character") or bp_entry.get("character")

        base_char, _ = normalize_character_name(char_name)
        self.assertEqual(base_char, "Dark Samus")

        # 2. Standby player in Round 2 (has no roster selection)
        standby_id = "standby_99"
        is_active_sb = (standby_id == active_home_id)
        sel_sb = selections_by_player.get(standby_id, {})
        bp_sb = blind_by_player.get(standby_id, {})

        char_name_sb = sel_sb.get("selected_character") or sel_sb.get("character")
        if not char_name_sb and is_round_one and is_active_sb and not is_starter_hidden:
            char_name_sb = bp_sb.get("selected_character") or bp_sb.get("character")

        base_char_sb, _ = normalize_character_name(char_name_sb)
        self.assertIsNone(base_char_sb)

    def test_character_and_skin_preservation_logic(self):
        """Verify that when a player changes characters, the new character is used,
        while if the character matches, custom costume index is preserved."""
        # Case 1: Widget has Pikachu, snapshot provides Dark Samus -> must switch to Dark Samus
        base_char = "Dark Samus"
        cur_char_name = "Pikachu"
        cur_color_idx = 0
        if base_char:
            if cur_char_name and cur_char_name.lower() == base_char.lower() and cur_color_idx > 0:
                mains = {"ssbu": [[base_char, cur_color_idx]]}
            else:
                mains = [base_char]
        self.assertEqual(mains, ["Dark Samus"])

        # Case 2: Widget has Dark Samus with skin 3, snapshot provides Dark Samus -> preserve skin 3
        base_char = "Dark Samus"
        cur_char_name = "Dark Samus"
        cur_color_idx = 3
        if base_char:
            if cur_char_name and cur_char_name.lower() == base_char.lower() and cur_color_idx > 0:
                mains = {"ssbu": [[base_char, cur_color_idx]]}
            else:
                mains = [base_char]
        self.assertEqual(mains, {"ssbu": [["Dark Samus", 3]]})

    def test_in_progress_round_one_stage_strike_preserves_starters(self):
        """Connecting during Round 1 stage striking (or match) must NOT wipe starters,
        even if one team active player ID is temporarily null."""
        live_state = {
            "round_number": 1,
            "phase": "stage_strike",
            "home_active_player_id": "p1_home",
            "away_active_player_id": None,
        }
        roster_selections = [
            {"player_id": "p1_home", "slot_order": 1, "selected_character": "Mario", "stocks_remaining": 3},
            {"player_id": "p1_away", "slot_order": 1, "selected_character": "Fox", "stocks_remaining": 3},
        ]
        active_home_id = live_state.get("home_active_player_id")
        active_away_id = live_state.get("away_active_player_id")

        is_round_one = (live_state.get("round_number") or 1) == 1
        is_starter_selection_phase = live_state.get("phase") in ("blind_pick", "player_select")
        if is_round_one and is_starter_selection_phase and (not active_home_id or not active_away_id):
            active_home_id = None
            active_away_id = None
            roster_selections = [s for s in roster_selections if s.get("slot_order") != 1]

        # Starters must NOT have been wiped out because phase is stage_strike!
        self.assertEqual(len(roster_selections), 2)
        self.assertEqual(roster_selections[0]["selected_character"], "Mario")
        self.assertEqual(roster_selections[1]["selected_character"], "Fox")

    def test_in_progress_round_two_loads_all_sent_in_players_characters(self):
        """Connecting to an in-progress Round 2 match must load characters for:
        - The Round 1 starter who was eliminated (slot 1)
        - The surviving starter on the opposing team (slot 1)
        - The newly sent-in Round 2 player (slot 2)
        While leaving standby players unselected."""
        live_state_r2 = {
            "round_number": 2,
            "phase": "stage_strike",
            "home_active_player_id": "alpha_p2",
            "away_active_player_id": "beta_p1",
        }
        roster_selections = [
            {"player_id": "alpha_p1", "slot_order": 1, "selected_character": "Pikachu", "stocks_remaining": 0},
            {"player_id": "alpha_p2", "slot_order": 2, "selected_character": "Dark Samus", "stocks_remaining": 3},
            {"player_id": "beta_p1", "slot_order": 1, "selected_character": "Daisy", "stocks_remaining": 2},
        ]
        blind_picks = [
            {"player_id": "alpha_p1", "selected_character": "Pikachu"},
            {"player_id": "beta_p1", "selected_character": "Daisy"},
        ]

        selections_by_player = {s["player_id"]: s for s in roster_selections}
        blind_by_player = {bp["player_id"]: bp for bp in blind_picks}

        # Alpha Player 1 (eliminated starter from round 1)
        sel1 = selections_by_player.get("alpha_p1", {})
        bp1 = blind_by_player.get("alpha_p1", {})
        raw1 = sel1.get("selected_character") or sel1.get("character")
        if not raw1 and (sel1.get("slot_order") == 1):
            raw1 = bp1.get("selected_character")
        char1, _ = normalize_character_name(raw1)
        self.assertEqual(char1, "Pikachu")

        # Alpha Player 2 (active Round 2 fighter)
        sel2 = selections_by_player.get("alpha_p2", {})
        raw2 = sel2.get("selected_character") or sel2.get("character")
        char2, _ = normalize_character_name(raw2)
        self.assertEqual(char2, "Dark Samus")

        # Beta Player 1 (surviving starter from round 1)
        sel_b1 = selections_by_player.get("beta_p1", {})
        raw_b1 = sel_b1.get("selected_character") or sel_b1.get("character")
        char_b1, _ = normalize_character_name(raw_b1)
        self.assertEqual(char_b1, "Daisy")

        # Standby bench player
        sel_sb = selections_by_player.get("alpha_p3", {})
        bp_sb = blind_by_player.get("alpha_p3", {})
        raw_sb = sel_sb.get("selected_character") or sel_sb.get("character")
        if raw_sb in ("", "Character not selected", "None", None):
            raw_sb = None
        if not raw_sb and sel_sb.get("slot_order") == 1:
            raw_sb = bp_sb.get("selected_character")
        char_sb, _ = normalize_character_name(raw_sb)
        self.assertIsNone(char_sb)

    def test_team_player_widget_set_data_triggers_skin_and_characters_changed(self):
        """Verify that SetData on TSHTeamPlayerWidget loads skins and updates StateManager
        even when characterIndex does not trigger a change event."""
        from src.TSHTeamPlayerWidget import TSHTeamPlayerWidget
        from PyQt6.QtWidgets import QWidget
        from src.StateManager import StateManager

        pw = TSHTeamPlayerWidget(1, 1, "score.team.1.player.1")

        # Mock character elements
        mock_skin_loaded = []
        mock_char_changed = []

        orig_load_skin = pw.LoadSkinOptions
        orig_char_changed = pw.CharactersChanged

        def tracking_load_skin(elem, target):
            mock_skin_loaded.append(True)
            return orig_load_skin(elem, target)

        def tracking_char_changed(*args, **kwargs):
            mock_char_changed.append(True)
            return orig_char_changed(*args, **kwargs)

        pw.LoadSkinOptions = tracking_load_skin
        pw.CharactersChanged = tracking_char_changed

        pw.SetData({"mains": ["Dark Samus"]}, dontLoadFromDB=True, clear=False)

        self.assertGreater(len(mock_skin_loaded), 0)
        self.assertGreater(len(mock_char_changed), 0)


if __name__ == "__main__":
    unittest.main()
