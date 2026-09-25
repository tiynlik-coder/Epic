"""Night resolution of the roles brought over from Baku Mafia."""
import asyncio
import random
import unittest
from unittest import mock

import tests  # noqa: F401  (sets up the throwaway database)

from models.database import db, init_db
from models.users import get_user, set_inv
from utils.night_actions import resolve_night_effects
from utils.players import new_player


class U:
    def __init__(self, i):
        self.id, self.username, self.first_name = i, "", f"P{i}"


class Bot:
    def __init__(self): self.sent = []
    async def send_message(self, chat_id, text, **k): self.sent.append((chat_id, text))


class Ctx:
    def __init__(self): self.bot = Bot()


def game(*roles, base=1000):
    g = {"id": "r", "chat_id": -5, "mode": None, "players": {}, "jobs": [], "bounties": [], "ended": False, "phase": "night", "phase_id": 1}
    for i, r in enumerate(roles, base):
        p = new_player(U(i)); p["role"] = r; g["players"][i] = p
    return g


def act(g, actor, target, mode=None, t=0.0):
    g["players"][actor]["action"] = {"type": "target", "target": target, "selected_at": t, "mode": mode}


def night(g):
    ctx = Ctx(); asyncio.run(resolve_night_effects(ctx, g)); return ctx.bot.sent


def alive(g, pid): return g["players"][pid]["alive"]


class NightRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): init_db()

    def test_mine_kills_visitors_and_cancels_their_action(self):
        g = game("Minior", "Tinch axoli", "Shifokor", "Mafia")
        act(g, 1000, 1001); act(g, 1002, 1001); act(g, 1003, 1001)
        night(g)
        self.assertFalse(alive(g, 1002))           # the doctor stepped on the mine
        self.assertFalse(alive(g, 1001))           # so the heal never happened and the Don's shot killed
        self.assertTrue(alive(g, 1003))            # a plain Mafia does not step on mines (the Don would)
        self.assertTrue(g["players"][1000]["won_flag"])

    def test_kimyogar_heal_blocks_attacks(self):
        g = game("Kimyogar", "Tinch axoli", "Don")
        act(g, 1000, 1001, "heal"); act(g, 1002, 1001)
        night(g)
        self.assertTrue(alive(g, 1001))

    def test_labarant_heals_mafia_and_kills_others(self):
        g = game("Labarant", "Mafia", "Komissar Katani", "Tinch axoli")
        act(g, 1000, 1001); g["players"][1002]["action"] = {"type": "kill", "target": 1001, "selected_at": 0}
        night(g)
        self.assertTrue(alive(g, 1001))
        g = game("Labarant", "Tinch axoli", base=1010); act(g, 1010, 1011); night(g)
        self.assertFalse(alive(g, 1011))

    def test_wolf_turns_into_mafia_or_serjant(self):
        g = game("Bo‘ri", "Don"); act(g, 1001, 1000); night(g)
        self.assertEqual(g["players"][1000]["role"], "Mafia"); self.assertTrue(alive(g, 1000))
        g = game("Bo‘ri", "Komissar Katani", base=1020); g["players"][1021]["action"] = {"type": "kill", "target": 1020, "selected_at": 0}; night(g)
        self.assertEqual(g["players"][1020]["role"], "Serjant")

    def test_hitman(self):
        g = game("Yollanma qotil", "Komissar Katani"); act(g, 1000, 1001); night(g)
        self.assertFalse(alive(g, 1000)); self.assertTrue(alive(g, 1001))
        g = game("Yollanma qotil", "Tinch axoli", "Shifokor", base=1030); act(g, 1030, 1031); act(g, 1032, 1031); night(g)
        self.assertFalse(alive(g, 1031))  # heals do not stop the hitman
        g = game("Yollanma qotil", "Don", base=1040); act(g, 1041, 1040); night(g)
        self.assertTrue(alive(g, 1040))   # nobody kills him at night

    def test_admiral_is_immune(self):
        g = game("Admiral", "Don"); act(g, 1001, 1000); night(g)
        self.assertTrue(alive(g, 1000))

    def test_afsungar_takes_killer_along(self):
        g = game("Afsungar", "Don"); act(g, 1001, 1000); night(g)
        self.assertFalse(alive(g, 1000)); self.assertFalse(alive(g, 1001))
        self.assertTrue(g["players"][1000]["won_flag"])

    def test_robin_dies_after_second_town_kill(self):
        g = game("Robin Gud", "Tinch axoli", "Tinch axoli")
        g["players"][1000]["robin_mistakes"] = 1; act(g, 1000, 1001); night(g)
        self.assertFalse(alive(g, 1001)); self.assertFalse(alive(g, 1000))

    def test_gazabkor_takes_picks(self):
        g = game("G‘azabkor", "Tinch axoli", "Tinch axoli")
        g["players"][1000]["gazab_picks"] = [1001, 1002]; act(g, 1000, 1000); night(g)
        self.assertEqual([alive(g, i) for i in (1000, 1001, 1002)], [False, False, False])
        self.assertTrue(g["players"][1000]["won_flag"])

    def test_robber_beats_without_money(self):
        g = game("Qaroqchi", "Tinch axoli")
        con = db(); con.execute("UPDATE users SET money=0 WHERE user_id=1001"); con.commit(); con.close()
        act(g, 1000, 1001, "pul"); night(g)
        self.assertTrue(alive(g, 1001)); self.assertEqual(g["players"][1001]["hp"], 50)

    def test_robber_takes_money(self):
        g = game("Qaroqchi", "Tinch axoli", base=1050)
        con = db(); con.execute("UPDATE users SET money=500 WHERE user_id IN (1050,1051)"); con.commit(); con.close()
        act(g, 1050, 1051, "pul"); night(g)
        self.assertLess(get_user(1051)["money"], 500); self.assertEqual(get_user(1050)["money"] + get_user(1051)["money"], 1000)

    def test_lucky_survives(self):
        g = game("Omadli", "Don"); act(g, 1001, 1000)
        with mock.patch.object(random, "random", return_value=0.1): night(g)
        self.assertTrue(alive(g, 1000))

    def test_fox_joins_side(self):
        g = game("Tulki", "Don"); act(g, 1000, 1001); night(g)
        self.assertEqual(g["players"][1000]["role"], "Mafia")

    def test_miner_death_mine_and_slip_protection(self):
        g = game("Konchi"); g["konchi"] = {"1000": {"1": "o‘lim", "2": "o‘lim"}}
        g["players"][1000]["action"] = {"type": "kon", "kon": "1", "selected_at": 0}; night(g)
        self.assertFalse(alive(g, 1000))
        g = game("Konchi", base=1060); g["konchi"] = {"1060": {"1": "o‘lim"}}
        set_inv(1060, {"slip_protection": 1}); g["players"][1060]["slip_protection"] = True
        g["players"][1060]["action"] = {"type": "kon", "kon": "1", "selected_at": 0}; night(g)
        self.assertTrue(alive(g, 1060)); self.assertEqual(g["konchi"]["1060"], {})

    def test_joker_sends_cards(self):
        g = game("Joker", "Tinch axoli"); act(g, 1000, 1001, "3"); night(g)
        self.assertEqual(g["joker_cards"]["1001"], {"joker": 1000, "death": "3"})

    def test_kezuvchi_block_and_medicine(self):
        g = game("Kezuvchi", "Don", "Tinch axoli"); act(g, 1000, 1001); act(g, 1001, 1002); night(g)
        self.assertTrue(alive(g, 1002))
        g = game("Kezuvchi", "Don", "Tinch axoli", base=1070)
        set_inv(1071, {"medicine_protection": 1}); g["players"][1071]["medicine"] = True
        act(g, 1070, 1071); act(g, 1071, 1072); night(g)
        self.assertFalse(alive(g, 1072))

    def test_sehrgar_gets_a_decision(self):
        g = game("Sehrgar", "Don"); act(g, 1001, 1000)
        ctx = Ctx(); pending = asyncio.run(resolve_night_effects(ctx, g))
        self.assertTrue(pending); self.assertTrue(alive(g, 1000))


class FakeJobQueue:
    def run_once(self, fn, when, data=None, name=None):
        class Job:
            def schedule_removal(self): pass
        return Job()


class FakeBot(Bot):
    def __init__(self):
        super().__init__(); self.markups = []
    async def send_message(self, chat_id, text, **k):
        self.sent.append((chat_id, text)); self.markups.append(k.get("reply_markup"))
        class Msg: message_id = len(self.sent)
        return Msg()

    async def delete_message(self, *a, **k): pass
    async def send_photo(self, chat_id, photo, **k): pass
    async def unpin_chat_message(self, **k): pass
    async def get_me(self):
        class Me: username = "epic_test_bot"
        return Me()


class FakeApp:
    def __init__(self): self.bot = FakeBot(); self.job_queue = FakeJobQueue()


class GameFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): init_db()

    def test_successors_take_over(self):
        from utils.game_logic import promote_successors
        g = game("Komissar Katani", "Admiral", "Shifokor", "Hamshira", "Don", "Mafia", base=1100)
        for dead in (1100, 1102, 1104): g["players"][dead]["alive"] = False
        asyncio.run(promote_successors(Bot(), g))
        self.assertEqual([g["players"][i]["role"] for i in (1101, 1103, 1105)], ["Komissar Katani", "Shifokor", "Don"])

    def test_conditional_solo_wins_dead(self):
        from utils.victory import winners
        g = game("Minior", "Tinch axoli", base=1110)
        g["players"][1110]["alive"] = False; g["players"][1110]["won_flag"] = True
        self.assertEqual(sorted(p["role"] for p in winners(g)), ["Minior", "Tinch axoli"])

    def test_every_roleset_starts_and_offers_actions(self):
        """Start real games of 45 players for every role set; every night button must fit Telegram's 64 bytes."""
        from utils import game_logic
        for n, roleset in enumerate(("classic", "super", "mega", "real", "epic")):
            g = game(*([None] * 45), base=2000 + n * 100)
            g.update({"id": f"{1790000000000000000+n}-1234", "phase": "lobby", "roleset": roleset, "mode_state": {}, "night": 0, "start_time": None})
            app = FakeApp()
            with mock.patch.object(game_logic, "is_epic_channel_member", return_value=False):
                asyncio.run(game_logic.start_game(app, g))
            self.assertEqual(g["phase"], "night")
            self.assertEqual(len({p["role"] for p in g["players"].values()} - set(__import__("config").ROLES)), 0)
            for markup in filter(None, app.bot.markups):
                for row in markup.inline_keyboard:
                    for b in row:
                        if b.callback_data: self.assertLessEqual(len(b.callback_data.encode()), 64, b.callback_data)


if __name__ == "__main__":
    unittest.main()
