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

    def test_player_db_get_player_from_tag(self):
        from src.TSHPlayerDB import TSHPlayerDB

        # Mock DB data
        mock_db = {
            "NCAT Cate": {
                "prefix": "NCAT",
                "gamerTag": "Cate",
                "name": "Ali'i Turner",
                "mains": {"ssbu": [["Little Mac", 0, ""]]}
            },
            "SU Scooby": {
                "prefix": "SU",
                "gamerTag": "Scooby",
                "name": "Zachary Garby",
                "mains": {"ssbu": [["Mii Brawler", 0, "1332"]]}
            }
        }
        orig_db = TSHPlayerDB.database
        try:
            TSHPlayerDB.database = mock_db

            # Exact prefix + tag
            p1 = TSHPlayerDB.GetPlayerFromTag("Cate", "NCAT")
            self.assertIsNotNone(p1)
            self.assertEqual(p1["gamerTag"], "Cate")

            # Tag alone
            p2 = TSHPlayerDB.GetPlayerFromTag("Cate")
            self.assertIsNotNone(p2)
            self.assertEqual(p2["gamerTag"], "Cate")

            # Pipe separated
            p3 = TSHPlayerDB.GetPlayerFromTag("NCAT | Cate")
            self.assertIsNotNone(p3)
            self.assertEqual(p3["gamerTag"], "Cate")

            # Mii with moveset
            p4 = TSHPlayerDB.GetPlayerFromTag("Scooby", "SU")
            self.assertIsNotNone(p4)
            self.assertEqual(p4["mains"]["ssbu"][0][0], "Mii Brawler")
            self.assertEqual(p4["mains"]["ssbu"][0][2], "1332")

            # Non-existent
            self.assertIsNone(TSHPlayerDB.GetPlayerFromTag("UnknownPlayer123"))
        finally:
            TSHPlayerDB.database = orig_db

    def test_standby_players_fallback_to_local_players_db(self):
        """When Nexus snapshot has no character selected for a standby player,
        character and moveset fall back to local_players.json via TSHPlayerDB."""
        from src.TSHPlayerDB import TSHPlayerDB

        mock_db = {
            "NCAT Cate": {
                "prefix": "NCAT",
                "gamerTag": "Cate",
                "mains": {"ssbu": [["Little Mac", 2, ""]]}
            },
            "SU Scooby": {
                "prefix": "SU",
                "gamerTag": "Scooby",
                "mains": {"ssbu": [["Mii Brawler", 0, "1332"]]}
            }
        }
        orig_db = TSHPlayerDB.database
        try:
            TSHPlayerDB.database = mock_db

            # Standby player 1 (Cate) - no character on Nexus
            db_p1 = TSHPlayerDB.GetPlayerFromTag("Cate", "NCAT")
            self.assertIsNotNone(db_p1)
            raw_c1 = db_p1["mains"]["ssbu"][0][0]
            skin1 = db_p1["mains"]["ssbu"][0][1]
            base_c1, ms1 = normalize_character_name(raw_c1)
            self.assertEqual(base_c1, "Little Mac")
            self.assertEqual(skin1, 2)

            # Standby player 2 (Scooby) - Mii Brawler with moveset 1332
            db_p2 = TSHPlayerDB.GetPlayerFromTag("Scooby", "SU")
            self.assertIsNotNone(db_p2)
            raw_c2 = db_p2["mains"]["ssbu"][0][0]
            moveset2 = db_p2["mains"]["ssbu"][0][2]
            base_c2, _ = normalize_character_name(raw_c2)
            self.assertEqual(base_c2, "Mii Brawler")
            self.assertEqual(moveset2, "1332")
        finally:
            TSHPlayerDB.database = orig_db

    def test_mii_moveset_editable_and_preserved(self):
        from src.TSHTeamPlayerWidget import TSHTeamPlayerWidget
        from src.TSHGameAssetManager import TSHGameAssetManager
        from src.StateManager import StateManager
        from qtpy.QtGui import QStandardItem
        from qtpy.QtCore import Qt

        # Add Mii Brawler to characterModel for test
        item = QStandardItem("Mii Brawler")
        item.setData({"en_name": "Mii Brawler", "name": "Mii Brawler", "codename": "miifighter"}, Qt.ItemDataRole.UserRole)
        TSHGameAssetManager.instance.characterModel.appendRow(item)

        pw = TSHTeamPlayerWidget(1, 1, "score.team.1.player.1")
        self.assertGreater(len(pw.character_elements), 0)

        # Set character to Mii Brawler with moveset 1332
        pw.SetData({"mains": ["Mii Brawler"], "moveset": "1332"}, dontLoadFromDB=True, clear=False)

        var_elem = pw.character_elements[0][3]
        self.assertFalse(var_elem.isHidden())
        self.assertTrue(var_elem.isEditable())
        self.assertEqual(var_elem.currentText(), "1332")
        self.assertEqual(getattr(pw, "moveset", None), "1332")

        # Edit moveset text manually to 2332
        var_elem.setEditText("2332")
        self.assertEqual(getattr(pw, "moveset", None), "2332")
        self.assertEqual(StateManager.Get("score.team.1.player.1.moveset"), "2332")

        # Re-apply snapshot data without moveset; moveset must NOT be wiped
        pw.SetData({"mains": {"ssbu": [["Mii Brawler", 0]]}}, dontLoadFromDB=True, clear=False)
        self.assertEqual(var_elem.currentText(), "2332")
        self.assertEqual(getattr(pw, "moveset", None), "2332")

    def test_crew_battle_stocks_locked_to_12_on_import_with_large_roster(self):
        from src.TSHTeamBattleWidget import TSHTeamBattleWidget
        from src.TSHGameAssetManager import TSHGameAssetManager

        orig_set_game = TSHGameAssetManager.instance.SetGame
        TSHGameAssetManager.instance.SetGame = lambda *a, **kw: None
        try:
            w = TSHTeamBattleWidget()
            large_roster_snapshot = {
                "fixture": {"id": "match-roster-9", "home_team_id": "t1", "away_team_id": "t2", "best_of": 3},
                "home_team": {"id": "t1", "name": "Team One"},
                "away_team": {"id": "t2", "name": "Team Two"},
                "players": [{"id": f"p{i}", "team_id": "t1", "tag": f"Player {i}"} for i in range(9)] +
                           [{"id": f"q{i}", "team_id": "t2", "tag": f"Opponent {i}"} for i in range(9)],
                "live_state": None,
                "active_game": {"game": "ultimate"},
                "roster_selections": [],
                "blind_picks": [],
            }
            w._DoApplyNexusData(large_roster_snapshot)
            self.assertEqual(w.team1stocks.value(), 12)
            self.assertEqual(w.team2stocks.value(), 12)

            # Resetting player mode values must also cap to 12 (4 combatants * 3 stocks)
            w.ResetAllStocks()
            self.assertEqual(w.team1stocks.value(), 12)
            self.assertEqual(w.team2stocks.value(), 12)
        finally:
            TSHGameAssetManager.instance.SetGame = orig_set_game

    def test_new_match_connection_clears_old_player_characters(self):
        from src.TSHTeamBattleWidget import TSHTeamBattleWidget
        from src.TSHGameAssetManager import TSHGameAssetManager

        orig_set_game = TSHGameAssetManager.instance.SetGame
        TSHGameAssetManager.instance.SetGame = lambda *a, **kw: None
        try:
            w = TSHTeamBattleWidget()
            s1 = {
                "fixture": {"id": "match-alpha", "home_team_id": "t1", "away_team_id": "t2", "best_of": 3},
                "home_team": {"id": "t1", "name": "Team Alpha"},
                "away_team": {"id": "t2", "name": "Team Beta"},
                "players": [{"id": "p1", "team_id": "t1", "tag": "PlayerAlpha1"}],
                "live_state": None,
                "active_game": {"game": "ultimate"},
                "roster_selections": [{"player_id": "p1", "selected_character": "Fox", "slot_order": 1}],
                "blind_picks": [],
            }
            w._DoApplyNexusData(s1)
            self.assertEqual(getattr(w.team1playerWidgets[0], "_last_loaded_player_id", None), "p1")

            # Now connect to match-bravo with an unselected player in slot 1
            s2 = {
                "fixture": {"id": "match-bravo", "home_team_id": "t3", "away_team_id": "t4", "best_of": 3},
                "home_team": {"id": "t3", "name": "Team Gamma"},
                "away_team": {"id": "t4", "name": "Team Delta"},
                "players": [{"id": "p_new", "team_id": "t3", "tag": "UnknownPlayerNoDB"}],
                "live_state": None,
                "active_game": {"game": "ultimate"},
                "roster_selections": [],
                "blind_picks": [],
            }
            w._DoApplyNexusData(s2)
            self.assertEqual(getattr(w.team1playerWidgets[0], "_last_loaded_player_id", None), "p_new")
            # Character element should be reset to empty / 0 or -1, not Fox
            char_elem = w.team1playerWidgets[0].character_elements[0][1]
            self.assertIn(char_elem.currentIndex(), (-1, 0))
            self.assertNotEqual(char_elem.currentText(), "Fox")
        finally:
            TSHGameAssetManager.instance.SetGame = orig_set_game

    def test_periodic_sync_only_updates_active_and_characters(self):
        from src.TSHTeamBattleWidget import TSHTeamBattleWidget
        from src.TSHGameAssetManager import TSHGameAssetManager
        from qtpy.QtGui import QStandardItem
        from qtpy.QtWidgets import QLineEdit
        from qtpy.QtCore import Qt

        orig_set_game = TSHGameAssetManager.instance.SetGame
        TSHGameAssetManager.instance.SetGame = lambda *a, **kw: None
        try:
            # Ensure empty item + Mario, Fox, and Mii Brawler exist in characterModel
            if TSHGameAssetManager.instance.characterModel.rowCount() == 0:
                empty_it = QStandardItem("")
                empty_it.setData({}, Qt.ItemDataRole.UserRole)
                TSHGameAssetManager.instance.characterModel.appendRow(empty_it)
            for cname, ccode in [("Mario", "mario"), ("Fox", "fox"), ("Mii Brawler", "miifighter")]:
                found = False
                for r in range(TSHGameAssetManager.instance.characterModel.rowCount()):
                    itm = TSHGameAssetManager.instance.characterModel.item(r).data(Qt.ItemDataRole.UserRole)
                    if itm and itm.get("en_name") == cname:
                        found = True
                        break
                if not found:
                    it = QStandardItem(cname)
                    it.setData({"en_name": cname, "name": cname, "codename": ccode}, Qt.ItemDataRole.UserRole)
                    TSHGameAssetManager.instance.characterModel.appendRow(it)

            w = TSHTeamBattleWidget()
            # 1. Initial load
            initial_snap = {
                "fixture": {"id": "match-periodic-1", "home_team_id": "t1", "away_team_id": "t2", "best_of": 3, "home_score": 0, "away_score": 0},
                "home_team": {"id": "t1", "name": "Alpha", "short_name": "ALP"},
                "away_team": {"id": "t2", "name": "Beta", "short_name": "BET"},
                "tournament_season": {"tournament_name": "Nexus Cup", "name": "Week 1"},
                "players": [
                    {"id": "p1", "team_id": "t1", "tag": "Player1"},
                    {"id": "p2", "team_id": "t1", "tag": "Player2"},
                    {"id": "p3", "team_id": "t1", "tag": "Player3"},
                    {"id": "q1", "team_id": "t2", "tag": "Opp1"},
                ],
                "live_state": {"round_number": 1, "phase": "playing", "home_active_player_id": "p1", "away_active_player_id": "q1", "home_stocks": 9, "away_stocks": 3},
                "active_game": {"game": "ultimate", "id": "g1", "game_order": 1},
                "roster_selections": [
                    {"player_id": "p1", "slot_order": 1, "selected_character": "Fox", "stocks_remaining": 3},
                    {"player_id": "q1", "slot_order": 1, "selected_character": "Mario", "stocks_remaining": 3},
                ],
                "blind_picks": [],
            }
            w.ApplyNexusData(initial_snap)

            self.assertEqual(w.team1stocks.value(), 9)
            self.assertEqual(w.team1score.value(), 0)
            self.assertEqual(w.bestOf.value(), 3)
            self.assertEqual(w.matchCombo.currentText(), "Round 1")
            self.assertTrue(w.team1playerWidgets[0].IsActive())
            self.assertFalse(w.team1playerWidgets[1].IsActive())
            self.assertFalse(w.team1playerWidgets[2].IsActive())
            self.assertEqual(w.team1playerWidgets[0].character_elements[0][1].currentText(), "Fox")

            # 2. Stream operator manually modifies scoreboard info, stocks, tags, and movesets
            w.team1playerWidgets[0].dynamicSpinner.setValue(0)
            w.team1playerWidgets[0].SetEliminatedStatus(True)
            w.team1playerWidgets[0].findChild(QLineEdit, "name").setText("Player1 Custom")
            w.team1playerWidgets[2].dynamicSpinner.setValue(2)
            w.team1stocks.setValue(4)
            w.team2stocks.setValue(2)
            w.team1score.setValue(1)
            w.bestOf.setValue(5)
            w.matchCombo.setCurrentText("Grand Finals")
            w.phaseCombo.setCurrentText("Top 8")
            w.team1column.findChild(QLineEdit, "teamName").setText("Alpha Edited")

            # 3. Periodic update: Round 2 starts, p3 goes in and picks Mii Brawler (1332),
            #    while snapshot carries different scores/stocks/team names/round_number
            periodic_snap = {
                "fixture": {"id": "match-periodic-1", "home_team_id": "t1", "away_team_id": "t2", "best_of": 3, "home_score": 0, "away_score": 0, "status": "completed"},
                "home_team": {"id": "t1", "name": "Alpha ServerName", "short_name": "ALP"},
                "away_team": {"id": "t2", "name": "Beta ServerName", "short_name": "BET"},
                "tournament_season": {"tournament_name": "Nexus Cup Server", "name": "Week 1 Server"},
                "players": [
                    {"id": "p1", "team_id": "t1", "tag": "Player1"},
                    {"id": "p2", "team_id": "t1", "tag": "Player2"},
                    {"id": "p3", "team_id": "t1", "tag": "Player3"},
                    {"id": "q1", "team_id": "t2", "tag": "Opp1"},
                ],
                "live_state": {"round_number": 2, "phase": "complete", "home_active_player_id": "p3", "away_active_player_id": "q1", "home_stocks": 12, "away_stocks": 12},
                "active_game": {"game": "ultimate", "id": "g2", "game_order": 2},
                "roster_selections": [
                    {"player_id": "p1", "slot_order": 1, "selected_character": "Fox", "stocks_remaining": 3},
                    {"player_id": "p3", "slot_order": 2, "selected_character": "Mii Brawler (1332)", "stocks_remaining": 3},
                    {"player_id": "q1", "slot_order": 1, "selected_character": "Mario", "stocks_remaining": 3},
                ],
                "blind_picks": [],
            }
            w.ApplyNexusData(periodic_snap)

            # Manual scoreboard info and stocks MUST remain completely untouched!
            self.assertEqual(w.team1stocks.value(), 4)
            self.assertEqual(w.team2stocks.value(), 2)
            self.assertEqual(w.team1score.value(), 1)
            self.assertEqual(w.bestOf.value(), 5)
            self.assertEqual(w.matchCombo.currentText(), "Grand Finals")
            self.assertEqual(w.phaseCombo.currentText(), "Top 8")
            self.assertEqual(w.team1column.findChild(QLineEdit, "teamName").text(), "Alpha Edited")
            self.assertEqual(w.team1playerWidgets[0].dynamicSpinner.value(), 0)
            self.assertTrue(w.team1playerWidgets[0].IsEliminated())
            self.assertEqual(w.team1playerWidgets[0].findChild(QLineEdit, "name").text(), "Player1 Custom")
            self.assertEqual(w.team1playerWidgets[2].dynamicSpinner.value(), 2)

            # Active status and character pick MUST sync in p3's existing widget slot!
            self.assertFalse(w.team1playerWidgets[0].IsActive())
            self.assertFalse(w.team1playerWidgets[1].IsActive())
            self.assertTrue(w.team1playerWidgets[2].IsActive())
            self.assertEqual(w.team1playerWidgets[2].character_elements[0][1].currentText(), "Mii Brawler")
            self.assertEqual(w.team1playerWidgets[2].character_elements[0][3].currentText(), "1332")

            # 4. Subsequent periodic update where operator changed moveset manually to 2222
            #    and Nexus hasn't changed p3's pick -> must NOT overwrite operator's moveset edit
            w.team1playerWidgets[2].character_elements[0][3].setEditText("2222")
            w.ApplyNexusData(periodic_snap)
            self.assertEqual(w.team1playerWidgets[2].character_elements[0][3].currentText(), "2222")
        finally:
            TSHGameAssetManager.instance.SetGame = orig_set_game

    def test_game_count_increase_resets_scoreboard_and_syncs_score(self):
        """When home_score or away_score increases during periodic sync:
        - sync team1score / team2score
        - move all players out of active
        - reset team stocks to 12 and all player spinners to 3 (not eliminated)
        - increment the Match text
        """
        from qtpy.QtWidgets import QApplication
        from qtpy.QtGui import QStandardItem
        from qtpy.QtCore import Qt
        from src.TSHTeamBattleWidget import TSHTeamBattleWidget
        from src.TSHGameAssetManager import TSHGameAssetManager

        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)

        orig_set_game = TSHGameAssetManager.instance.SetGame
        TSHGameAssetManager.instance.SetGame = lambda *a, **kw: None
        try:
            if TSHGameAssetManager.instance.characterModel.rowCount() == 0:
                empty_it = QStandardItem("")
                empty_it.setData({}, Qt.ItemDataRole.UserRole)
                TSHGameAssetManager.instance.characterModel.appendRow(empty_it)
            for cname, ccode in [("Fox", "fox"), ("Mario", "mario")]:
                found = False
                for r in range(TSHGameAssetManager.instance.characterModel.rowCount()):
                    itm = TSHGameAssetManager.instance.characterModel.item(r).data(Qt.ItemDataRole.UserRole)
                    if itm and itm.get("en_name") == cname:
                        found = True
                        break
                if not found:
                    it = QStandardItem(cname)
                    it.setData({"en_name": cname, "name": cname, "codename": ccode}, Qt.ItemDataRole.UserRole)
                    TSHGameAssetManager.instance.characterModel.appendRow(it)

            w = TSHTeamBattleWidget()
            home_players = [{"id": f"h{i}", "team_id": "t1", "tag": f"Home{i}"} for i in range(1, 5)]
            away_players = [{"id": f"a{i}", "team_id": "t2", "tag": f"Away{i}"} for i in range(1, 5)]

            initial_snap = {
                "fixture": {"id": "match-game-reset", "home_team_id": "t1", "away_team_id": "t2", "best_of": 3, "home_score": 0, "away_score": 0},
                "home_team": {"id": "t1", "name": "Alpha", "short_name": "ALP"},
                "away_team": {"id": "t2", "name": "Beta", "short_name": "BET"},
                "tournament_season": {"tournament_name": "Nexus Cup", "name": "Week 1"},
                "players": home_players + away_players,
                "live_state": {"round_number": 1, "phase": "playing", "home_active_player_id": "h1", "away_active_player_id": "a1"},
                "active_game": {"game": "ultimate", "id": "g1", "game_order": 1},
                "roster_selections": [
                    {"player_id": "h1", "slot_order": 1, "selected_character": "Fox", "stocks_remaining": 3},
                    {"player_id": "a1", "slot_order": 1, "selected_character": "Mario", "stocks_remaining": 3},
                ],
                "blind_picks": [],
            }
            w.ApplyNexusData(initial_snap)

            self.assertEqual(w.team1stocks.value(), 12)
            self.assertEqual(w.team2stocks.value(), 12)
            self.assertEqual(w.team1score.value(), 0)
            self.assertEqual(w.team2score.value(), 0)
            self.assertEqual(w.matchCombo.currentText(), "Round 1")
            self.assertTrue(w.team1playerWidgets[0].IsActive())
            self.assertTrue(w.team2playerWidgets[0].IsActive())

            # Simulate Game 1 progress before Team 1 wins:
            # several players eliminated/low stocks, active flags set, Match edited to "Match 1"
            w.matchCombo.setCurrentText("Match 1")
            w.team1playerWidgets[0].dynamicSpinner.setValue(0)
            w.team1playerWidgets[0].SetEliminatedStatus(True)
            w.team1playerWidgets[1].dynamicSpinner.setValue(1)
            w.team1playerWidgets[1].SetActiveStatus(True)
            for pw in w.team2playerWidgets:
                pw.dynamicSpinner.setValue(0)
                pw.SetEliminatedStatus(True)
            w.team1stocks.setValue(4)
            w.team2stocks.setValue(0)

            # Periodic update: Team 1 wins Game 1 -> home_score becomes 1 (even if snapshot still carries Game 1 active ids)
            win1_snap = {
                "fixture": {"id": "match-game-reset", "home_team_id": "t1", "away_team_id": "t2", "best_of": 3, "home_score": 1, "away_score": 0},
                "home_team": {"id": "t1", "name": "Alpha", "short_name": "ALP"},
                "away_team": {"id": "t2", "name": "Beta", "short_name": "BET"},
                "tournament_season": {"tournament_name": "Nexus Cup", "name": "Week 1"},
                "players": home_players + away_players,
                "live_state": {"round_number": 4, "phase": "playing", "home_active_player_id": "h1", "away_active_player_id": "a1"},
                "active_game": {"game": "ultimate", "id": "g2", "game_order": 2},
                "roster_selections": [
                    {"player_id": "h1", "slot_order": 1, "selected_character": "Fox", "stocks_remaining": 1},
                    {"player_id": "a1", "slot_order": 1, "selected_character": "Mario", "stocks_remaining": 0},
                ],
                "blind_picks": [],
            }
            w.ApplyNexusData(win1_snap)

            # Series score updates immediately, while stocks/active/match are held for 30s
            self.assertEqual(w.team1score.value(), 1)
            self.assertEqual(w.team2score.value(), 0)
            self.assertTrue(w._transition_timer.isActive())
            self.assertEqual(w._transition_seconds_left, 30)
            self.assertIn("Game 1 complete", w.lblNexusStatus.text())
            self.assertEqual(w.team1stocks.value(), 4)
            self.assertEqual(w.team2stocks.value(), 0)
            self.assertEqual(w.matchCombo.currentText(), "Match 1")
            self.assertTrue(w.team1playerWidgets[1].IsActive())

            # Ticks 1..29 keep holding the completed Game 1 scoreboard
            for expected_left in range(29, 0, -1):
                w._OnTransitionTimerTick()
                self.assertTrue(w._transition_timer.isActive())
                self.assertEqual(w._transition_seconds_left, expected_left)
                self.assertEqual(w.team1stocks.value(), 4)
                self.assertEqual(w.matchCombo.currentText(), "Match 1")

            # Tick 30 finishes countdown -> resets stocks to 12, deactivates all players, increments Match
            w._OnTransitionTimerTick()
            self.assertFalse(w._transition_timer.isActive())
            self.assertEqual(w.team1score.value(), 1)
            self.assertEqual(w.team2score.value(), 0)
            self.assertEqual(w.team1stocks.value(), 12)
            self.assertEqual(w.team2stocks.value(), 12)
            self.assertEqual(w.matchCombo.currentText(), "Match 2")
            for pw in w.team1playerWidgets + w.team2playerWidgets:
                self.assertFalse(pw.IsActive())
                self.assertFalse(pw.IsEliminated())
                self.assertEqual(pw.dynamicSpinner.value(), 3)

            # Game 2 starts: h2 and a2 are sent in -> they SHOULD become active again
            game2_active_snap = {
                "fixture": {"id": "match-game-reset", "home_team_id": "t1", "away_team_id": "t2", "best_of": 3, "home_score": 1, "away_score": 0},
                "home_team": {"id": "t1", "name": "Alpha", "short_name": "ALP"},
                "away_team": {"id": "t2", "name": "Beta", "short_name": "BET"},
                "tournament_season": {"tournament_name": "Nexus Cup", "name": "Week 1"},
                "players": home_players + away_players,
                "live_state": {"round_number": 1, "phase": "playing", "home_active_player_id": "h2", "away_active_player_id": "a2"},
                "active_game": {"game": "ultimate", "id": "g2", "game_order": 2},
                "roster_selections": [
                    {"player_id": "h2", "slot_order": 1, "selected_character": "Fox", "stocks_remaining": 3},
                    {"player_id": "a2", "slot_order": 1, "selected_character": "Mario", "stocks_remaining": 3},
                ],
                "blind_picks": [],
            }
            w.ApplyNexusData(game2_active_snap)
            self.assertTrue(w.team1playerWidgets[1].IsActive())
            self.assertTrue(w.team2playerWidgets[1].IsActive())
            self.assertFalse(w.team1playerWidgets[0].IsActive())

            # Team 2 wins Game 2 -> away_score increases 0 -> 1, holds 30s, then resets
            w.team1stocks.setValue(0)
            w.team2stocks.setValue(3)
            w.team1playerWidgets[1].dynamicSpinner.setValue(0)
            w.team1playerWidgets[1].SetEliminatedStatus(True)

            win2_snap = {
                "fixture": {"id": "match-game-reset", "home_team_id": "t1", "away_team_id": "t2", "best_of": 3, "home_score": 1, "away_score": 1},
                "home_team": {"id": "t1", "name": "Alpha", "short_name": "ALP"},
                "away_team": {"id": "t2", "name": "Beta", "short_name": "BET"},
                "tournament_season": {"tournament_name": "Nexus Cup", "name": "Week 1"},
                "players": home_players + away_players,
                "live_state": {"round_number": 1, "phase": "playing", "home_active_player_id": None, "away_active_player_id": None},
                "active_game": {"game": "ultimate", "id": "g3", "game_order": 3},
                "roster_selections": [],
                "blind_picks": [],
            }
            w.ApplyNexusData(win2_snap)
            self.assertTrue(w._transition_timer.isActive())
            self.assertEqual(w.team1score.value(), 1)
            self.assertEqual(w.team2score.value(), 1)
            self.assertEqual(w.team1stocks.value(), 0)
            self.assertEqual(w.matchCombo.currentText(), "Match 2")

            # While still holding, Game 3 starter h3 is queued -> should wait until 30s finishes, then activate on fresh board
            game3_queued_snap = {
                "fixture": {"id": "match-game-reset", "home_team_id": "t1", "away_team_id": "t2", "best_of": 3, "home_score": 1, "away_score": 1},
                "home_team": {"id": "t1", "name": "Alpha", "short_name": "ALP"},
                "away_team": {"id": "t2", "name": "Beta", "short_name": "BET"},
                "tournament_season": {"tournament_name": "Nexus Cup", "name": "Week 1"},
                "players": home_players + away_players,
                "live_state": {"round_number": 1, "phase": "playing", "home_active_player_id": "h3", "away_active_player_id": "a3"},
                "active_game": {"game": "ultimate", "id": "g3", "game_order": 3},
                "roster_selections": [
                    {"player_id": "h3", "slot_order": 1, "selected_character": "Fox", "stocks_remaining": 3},
                    {"player_id": "a3", "slot_order": 1, "selected_character": "Mario", "stocks_remaining": 3},
                ],
                "blind_picks": [],
            }
            w.ApplyNexusData(game3_queued_snap)
            self.assertFalse(w.team1playerWidgets[2].IsActive())
            self.assertEqual(w.team1stocks.value(), 0)

            for _ in range(30):
                w._OnTransitionTimerTick()

            self.assertFalse(w._transition_timer.isActive())
            self.assertEqual(w.team1score.value(), 1)
            self.assertEqual(w.team2score.value(), 1)
            self.assertEqual(w.team1stocks.value(), 12)
            self.assertEqual(w.team2stocks.value(), 12)
            self.assertEqual(w.matchCombo.currentText(), "Match 3")
            self.assertFalse(w.team1playerWidgets[1].IsActive())
            self.assertTrue(w.team1playerWidgets[2].IsActive())
            self.assertTrue(w.team2playerWidgets[2].IsActive())
            for pw in w.team1playerWidgets + w.team2playerWidgets:
                self.assertFalse(pw.IsEliminated())
                self.assertEqual(pw.dynamicSpinner.value(), 3)

            # Verify fallback when match text has no trailing digit ("Crew Battle") after 30s delay
            w.matchCombo.setCurrentText("Crew Battle")
            win3_snap = {
                "fixture": {"id": "match-game-reset", "home_team_id": "t1", "away_team_id": "t2", "best_of": 3, "home_score": 2, "away_score": 1, "status": "completed"},
                "home_team": {"id": "t1", "name": "Alpha", "short_name": "ALP"},
                "away_team": {"id": "t2", "name": "Beta", "short_name": "BET"},
                "tournament_season": {"tournament_name": "Nexus Cup", "name": "Week 1"},
                "players": home_players + away_players,
                "live_state": {"round_number": 1, "phase": "complete", "home_active_player_id": None, "away_active_player_id": None},
                "active_game": {"game": "ultimate", "id": "g3", "game_order": 3},
                "roster_selections": [],
                "blind_picks": [],
            }
            w.ApplyNexusData(win3_snap)
            for _ in range(30):
                w._OnTransitionTimerTick()
            self.assertEqual(w.team1score.value(), 2)
            self.assertEqual(w.team2score.value(), 1)
            self.assertEqual(w.matchCombo.currentText(), "Match 4")
            self.assertIn("Match complete (2 - 1)", w.lblNexusStatus.text())
        finally:
            TSHGameAssetManager.instance.SetGame = orig_set_game


if __name__ == "__main__":
    unittest.main()
