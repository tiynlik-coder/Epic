"""Day flow: votes, hanging confirmation, protections, Afsungar revenge, idle players, settings."""
import asyncio
import unittest
from unittest import mock

import tests  # noqa: F401  (sets up the throwaway database)

from models.chat_settings import DEFAULTS, get_settings, update_setting
from models.database import init_db
from tests.test_roles import FakeApp, game
from utils import game_logic
from utils.state import games


class Job:
    def __init__(self, g): self.data = {"gid": g["id"], "phase": g["phase_id"]}


class Ctx:
    def __init__(self, app, g): self.application = app; self.bot = app.bot; self.job = Job(g)


def day_game(*roles, base=3000, **settings):
    g = game(*roles, base=base)
    g.update({"id": f"day-{base}", "chat_id": -base, "night": 1, "votes": {}, "settings": {**DEFAULTS, **settings}})
    for i, p in enumerate(g["players"].values(), 1): p["num"] = i
    games[g["chat_id"]] = g
    return g


def run(coro): return asyncio.run(coro)


class DayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): init_db()

    def setUp(self):
        self.app = FakeApp()
        self.night = mock.patch.object(game_logic, "start_night", mock.AsyncMock())
        self.night.start()

    def tearDown(self):
        self.night.stop(); games.clear()

    def vote(self, g, votes):
        g["phase"] = "voting"; g["votes"] = {str(k): v for k, v in votes.items()}
        run(game_logic.resolve_vote(Ctx(self.app, g)))

    def test_janob_vote_counts_double(self):
        g = day_game("Janob", "Tinch axoli", "Tinch axoli", "Don", "Mafia", confirm_hanging=False)
        self.vote(g, {3000: 3003, 3001: 3004, 3004: 3001})  # Janob 2 vs 1 vs 1
        self.assertFalse(g["players"][3003]["alive"])

    def test_tie_hangs_nobody(self):
        g = day_game("Tinch axoli", "Tinch axoli", "Don", "Mafia", base=3010, confirm_hanging=False)
        self.vote(g, {3010: 3012, 3011: 3013})
        self.assertTrue(all(p["alive"] for p in g["players"].values()))

    def test_confirmation_needs_more_likes(self):
        g = day_game("Tinch axoli", "Tinch axoli", "Janob", "Don", "Mafia", base=3020)
        self.vote(g, {3020: 3023})
        self.assertEqual(g["phase"], "confirm")
        g["hang_votes"] = {"3020": True, "3021": True, "3022": False}  # Janob's 👎 weighs 4
        run(game_logic.resolve_confirm(Ctx(self.app, g)))
        self.assertTrue(g["players"][3023]["alive"])
        g2 = day_game("Tinch axoli", "Tinch axoli", "Don", "Mafia", "Tinch axoli", base=3030)
        self.vote(g2, {3030: 3032}); g2["hang_votes"] = {"3030": True, "3031": True, "3034": False}
        run(game_logic.resolve_confirm(Ctx(self.app, g2)))
        self.assertFalse(g2["players"][3032]["alive"])

    def test_advokat_saves_from_hanging(self):
        g = day_game("Tinch axoli", "Don", "Mafia", "Tinch axoli", base=3040, confirm_hanging=False)
        g["players"][3041]["advokat_result"] = True
        self.vote(g, {3040: 3041})
        self.assertTrue(g["players"][3041]["alive"])

    def test_hanged_afsungar_takes_one_along(self):
        g = day_game("Afsungar", "Don", "Mafia", "Tinch axoli", "Tinch axoli", base=3050, confirm_hanging=False)
        self.vote(g, {3051: 3050})
        self.assertEqual(g["phase"], "revenge")
        run(game_logic.take_along(self.app, g, g["players"][3051]))
        self.assertFalse(g["players"][3051]["alive"]); self.assertTrue(g["players"][3050]["won_flag"])

    def test_hanged_player_gets_last_words(self):
        g = day_game("Tinch axoli", "Don", "Mafia", "Tinch axoli", base=3060, confirm_hanging=False)
        self.vote(g, {3060: 3061})
        self.assertIn("3061", g["last_words"])

    def test_idle_active_role_is_kicked_after_two_nights(self):
        g = day_game("Shifokor", "Tinch axoli", "Don", base=3070)
        for _ in range(2): run(game_logic.kick_idle_players(self.app.bot, g))
        self.assertFalse(g["players"][3070]["alive"]); self.assertTrue(g["players"][3071]["alive"])

    def test_banned_roles_become_citizens(self):
        s = {**DEFAULTS, "banned_roles": ["Kimyogar", "Don"]}
        self.assertEqual(game_logic.apply_role_bans(["Don", "Kimyogar", "Shifokor"], s), ["Don", "Tinch axoli", "Shifokor"])

    def test_settings_are_clamped_and_persisted(self):
        update_setting(-777, "night_time", 5)
        self.assertEqual(get_settings(-777)["night_time"], 20)
        update_setting(-777, "roleset", "mega")
        self.assertEqual(get_settings(-777)["roleset"], "mega")
        self.assertEqual(get_settings(-778)["roleset"], "epic")


if __name__ == "__main__":
    unittest.main()
