"""Economy: every payout happens once, even when a button is pressed twice."""
import time
import unittest
from unittest import mock

import tests  # noqa: F401  (sets up the throwaway database)

from models import economy
from models.database import db, init_db
from models.users import get_user, inv


def fresh(uid, money=0, diamonds=0):
    con = db()
    con.execute("INSERT INTO users(user_id) VALUES(?) ON CONFLICT DO NOTHING", (uid,))
    con.execute("UPDATE users SET money=?, diamonds=?, protection=0 WHERE user_id=?", (money, diamonds, uid))
    for t in ("chest_opens", "admin_vips", "heroes", "admin_active_roles"):
        con.execute(f"DELETE FROM {t} WHERE user_id=?", (uid,))
    con.commit(); con.close()


class EconomyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): init_db()

    def test_giveaway_claims_once_and_runs_out(self):
        for u in (5001, 5002, 5003): fresh(u)
        gid = economy.create_giveaway(-50, 5001, "diamonds", 1)
        self.assertEqual(economy.claim_giveaway(gid, 5001)[0], "own")
        self.assertEqual(economy.claim_giveaway(gid, 5002)[0], "ok")
        self.assertEqual(economy.claim_giveaway(gid, 5002)[0], "again")
        self.assertEqual(economy.claim_giveaway(gid, 5003)[0], "empty")
        self.assertEqual(get_user(5002)["diamonds"], 1)
        gid = economy.create_giveaway(-50, 5001, "protection", 2)
        economy.claim_giveaway(gid, 5003)
        self.assertEqual(inv(5003)["protection"], 1)

    def test_lottery_pays_once_and_refunds_when_empty(self):
        for u in (5011, 5012): fresh(u)
        lid = economy.create_lottery(-50, 5011, 7)
        self.assertEqual(economy.join_lottery(lid, 5012), "ok")
        self.assertEqual(economy.join_lottery(lid, 5012), "again")
        self.assertEqual(economy.draw_lottery(lid, 5012)[0], "not_creator")
        self.assertEqual(economy.draw_lottery(lid, 5011)[:2], ("ok", 5012))
        self.assertEqual(economy.draw_lottery(lid, 5011)[0], "gone")
        self.assertEqual(get_user(5012)["diamonds"], 7)
        lid = economy.create_lottery(-50, 5011, 4)
        self.assertEqual(economy.draw_lottery(lid, 5011)[:2], ("refunded", 5011))
        self.assertEqual(get_user(5011)["diamonds"], 4)

    def test_payment_credits_stored_amount_once(self):
        fresh(5021)
        economy.record_payment("inv-1", 5021, "mirpay", 10, 12750)
        self.assertIsNotNone(economy.complete_payment("inv-1"))
        self.assertIsNone(economy.complete_payment("inv-1"))
        self.assertIsNone(economy.complete_payment("inv-unknown"))
        self.assertEqual(get_user(5021)["diamonds"], 10)

    def test_super_chest_cooldown_and_vip(self):
        fresh(5031, money=20000)
        self.assertEqual(economy.open_super_chest(5031)[0], "ok")
        self.assertEqual(economy.open_super_chest(5031)[0], "wait")
        fresh(5032, money=20000, diamonds=40)
        self.assertIsNotNone(economy.buy_vip(5032))
        self.assertEqual(get_user(5032)["diamonds"], 10)
        for _ in range(2): self.assertEqual(economy.open_super_chest(5032)[0], "ok")
        fresh(5033, money=100)
        self.assertEqual(economy.open_super_chest(5033)[0], "money")

    def test_mega_chest(self):
        fresh(5041, money=100, diamonds=20)
        with mock.patch.object(economy.random, "randrange", return_value=0):
            self.assertEqual(economy.open_mega_chest(5041)[0], "double")
        self.assertEqual((get_user(5041)["money"], get_user(5041)["diamonds"]), (200, 10))
        fresh(5042, money=100, diamonds=20)
        with mock.patch.object(economy.random, "randrange", return_value=3):
            self.assertEqual(economy.open_mega_chest(5042)[0], "bankrupt")
        self.assertEqual((get_user(5042)["money"], get_user(5042)["diamonds"]), (0, 0))

    def test_group_quota(self):
        con = db(); con.execute("DELETE FROM group_balance WHERE chat_id IN (-60,-61)"); con.commit(); con.close()
        self.assertTrue(economy.use_group_quota(-60, "diamonds", 40))
        self.assertFalse(economy.use_group_quota(-60, "diamonds", 20))  # 60 > 50 per day
        fresh(5051, diamonds=100)
        self.assertTrue(economy.donate_to_group(5051, -61, 50))
        self.assertTrue(economy.use_group_quota(-61, "diamonds", 1000))  # rich groups are unlimited

    def test_profile_swap_needs_a_fresh_offer(self):
        fresh(5061, diamonds=10); fresh(5062, money=999)
        self.assertEqual(economy.accept_swap(5061, 5062), "no_offer")
        economy.offer_swap(5061, 5062)
        self.assertEqual(economy.accept_swap(5061, 5062), "ok")
        self.assertEqual(economy.accept_swap(5061, 5062), "no_offer")
        self.assertEqual((get_user(5061)["money"], get_user(5062)["diamonds"]), (999, 5))
        economy.offer_swap(5061, 5062)
        con = db(); con.execute("UPDATE profile_offers SET created_at=? WHERE from_id=5061", (time.time() - 3600,)); con.commit(); con.close()
        self.assertEqual(economy.accept_swap(5061, 5062), "no_offer")

    def test_item_switches(self):
        fresh(5071)
        self.assertEqual(economy.toggle_item(5071, "mask"), {"mask"})
        self.assertEqual(economy.toggle_item(5071, "mask"), set())
        self.assertEqual(economy.toggle_item(5071, "money"), set())


if __name__ == "__main__":
    unittest.main()
