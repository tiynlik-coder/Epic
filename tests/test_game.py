import asyncio
import unittest

import tests  # noqa: F401  (sets up the throwaway database)
from telegram.error import TelegramError

from models.database import db, init_db
from models.users import consume_inventory, get_user, inv, set_inv
from utils.night_actions import apply_protection
from utils.players import new_player
from utils.state import cancel_game, games
from utils.victory import game_over, winners


class U:
    def __init__(self, i):
        self.id, self.username, self.first_name = i, "", f"P{i}"


def make_game(roles, mode=None):
    g = {"id": "t", "chat_id": -1, "mode": mode, "players": {}, "jobs": [], "bounties": [], "ended": False, "phase": "night", "phase_id": 1}
    for i, r in enumerate(roles, 1):
        p = new_player(U(i)); p["role"] = r; g["players"][i] = p
    return g


def won(g):
    return sorted(p["role"] for p in winners(g))


class VictoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_town_wins_with_harmless_solo(self):
        g = make_game(["Shifokor", "Tabib"])
        self.assertTrue(game_over(g)); self.assertEqual(won(g), ["Shifokor", "Tabib"])

    def test_mafia_wins_with_harmless_solo(self):
        g = make_game(["Don", "Tabib"])
        self.assertTrue(game_over(g)); self.assertEqual(won(g), ["Don", "Tabib"])

    def test_hostile_solo_keeps_game_going(self):
        self.assertFalse(game_over(make_game(["Shifokor", "Qotil"])))
        self.assertFalse(game_over(make_game(["Don", "Qotil"])))
        self.assertFalse(game_over(make_game(["Shifokor", "Don"])))

    def test_suidsid_does_not_win_without_hanging(self):
        self.assertEqual(won(make_game(["Shifokor", "Suidsid"])), ["Shifokor"])

    def test_zodagon_wins_with_town_and_lanatchi_survives(self):
        self.assertEqual(won(make_game(["Zodagon", "La’natchi"])), ["La’natchi", "Zodagon"])

    def test_kamikaze_wins_after_retaliation(self):
        g = make_game(["Kamikaze", "Don", "Mafia"])
        g["players"][1]["alive"] = False; g["players"][1]["kamikaze_used"] = True
        self.assertIn("Kamikaze", won(g))

    def test_zombie_mode(self):
        g = make_game(["Zombi", "Zombi", "Shifokor"], "zombie")
        g["players"][3]["alive"] = False
        self.assertTrue(game_over(g)); self.assertEqual(won(g), ["Zombi", "Zombi"])


class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_mask_is_consumed(self):
        p = new_player(U(50)); set_inv(50, {"mask": 2})
        self.assertTrue(consume_inventory(p, "mask")); self.assertEqual(inv(50)["mask"], 1)

    def test_supper_shield_is_consumed(self):
        t = new_player(U(51)); set_inv(51, {"supper_shield": 1})
        t["supper"] = True
        self.assertEqual(apply_protection(t, "Don"), "supper"); self.assertEqual(inv(51)["supper_shield"], 0)

    def test_rifle_pierces_protection(self):
        t = new_player(U(52)); set_inv(52, {"protection": 1}); t["protected"] = True
        a = new_player(U(53)); set_inv(53, {"rifle": 1}); a["rifle"] = True
        self.assertIsNone(apply_protection(t, "Don", a))
        self.assertEqual(inv(53)["rifle"], 0); self.assertFalse(a["rifle"]); self.assertTrue(t["protected"])

    def test_cancel_refunds_bounties(self):
        new_player(U(54))
        con = db(); con.execute("UPDATE users SET money=0 WHERE user_id=54"); con.commit(); con.close()
        g = {"chat_id": -9, "jobs": [], "bounties": [{"owner": 54, "target": 1, "amount": 300}]}
        games[-9] = g
        cancel_game(g)
        self.assertEqual(get_user(54)["money"], 300); self.assertNotIn(-9, games)


class EndGameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_winners_get_reward(self):
        from utils.game_logic import end_game

        class Bot:
            sent = []
            async def send_message(self, cid, text, **k): self.sent.append(text)
            async def get_chat_member(self, c, u):
                if u == 61:
                    class M: status = "member"
                    return M()
                raise TelegramError("x")

        class App:
            bot = Bot(); job_queue = None

        g = make_game([])
        for i, r in [(61, "Shifokor"), (62, "Tabib")]:
            p = new_player(U(i)); p["role"] = r; g["players"][i] = p
        con = db(); con.execute("UPDATE users SET money=0 WHERE user_id IN (61,62)"); con.commit(); con.close()
        asyncio.run(end_game(App(), g))
        self.assertEqual(get_user(61)["money"], 200)  # channel member: 2x
        self.assertEqual(get_user(62)["money"], 100)


class WiringTests(unittest.TestCase):
    def test_all_handlers_registered(self):
        import bot
        app = bot.build_app("123:TEST")
        self.assertEqual(sum(len(h) for h in app.handlers.values()), 92)


if __name__ == "__main__":
    unittest.main()
