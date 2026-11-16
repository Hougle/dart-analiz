import unittest

import pandas as pd

from match_stats import adjusted_stats, darts_stats, mark_double_attempts, per_match_stats


def leg(leg_id, scores, darts=None, start=501, match_id="m1"):
    """Turns of one leg from a list of scores; the last turn's darts can be overridden."""
    rows, remaining = [], start
    darts = darts or [3] * len(scores)
    for i, (s, d) in enumerate(zip(scores, darts), start=1):
        rows.append(dict(match_id=match_id, leg_id=leg_id, turn=i, remaining_before=remaining,
                         score_thrown=s, remaining_after=remaining - s, darts_thrown=d))
        remaining -= s
    return rows


# 501 -> 0 in 6 turns: 100, 100, 100, 100, 61 (leaves 40), 40 checkout with 2 darts.
WON = leg("L1", [100, 100, 100, 100, 61, 40], [3, 3, 3, 3, 3, 2])
# Lost leg: reaches 32, misses twice (0, 0), never finishes.
LOST = leg("L2", [60, 60, 60, 60, 60, 60, 60, 49, 0, 0])


class DoubleZone(unittest.TestCase):
    def test_marks_from_first_turn_on_40_or_less_to_end_of_leg(self):
        df = mark_double_attempts(pd.DataFrame(WON + LOST))
        won = df[df.leg_id == "L1"].sort_values("turn")
        self.assertEqual(won.is_dbl.tolist(), [False] * 5 + [True])
        lost = df[df.leg_id == "L2"].sort_values("turn")
        self.assertEqual(lost.is_dbl.tolist(), [False] * 8 + [True, True])

    def test_50_counts_as_double_zone(self):
        df = mark_double_attempts(pd.DataFrame(leg("L", [451, 50], start=501)))
        self.assertEqual(df.is_dbl.tolist(), [False, True])

    def test_turns_after_dropping_back_above_40_stay_marked(self):
        # On 40, scores 1: the odd leave of 39 is still part of the double zone.
        df = mark_double_attempts(pd.DataFrame(leg("L", [461, 1, 39], start=501)))
        self.assertEqual(df.is_dbl.tolist(), [False, True, True])


class Averages(unittest.TestCase):
    def test_adjusted_average_leaves_out_double_zone_turns(self):
        adj, adj_darts, dbl, failed, raw = adjusted_stats(pd.DataFrame(WON))
        self.assertAlmostEqual(raw, 501 / 17 * 3)
        self.assertAlmostEqual(adj, 461 / 15 * 3)
        self.assertEqual((adj_darts, dbl, failed), (15, 1, 0))

    def test_failed_doubles_are_double_zone_turns_without_checkout(self):
        _, _, dbl, failed, _ = adjusted_stats(pd.DataFrame(LOST))
        self.assertEqual((dbl, failed), (2, 2))

    def test_per_match_matches_adjusted_stats(self):
        throws = pd.DataFrame(WON + leg("L3", [140, 140, 140, 81], match_id="m2"))
        per = per_match_stats(mark_double_attempts(throws)).set_index("match_id")
        for mid, g in throws.groupby("match_id"):
            adj, _, dbl, failed, raw = adjusted_stats(g)
            self.assertAlmostEqual(per.loc[mid, "adjusted_avg"], adj)
            self.assertAlmostEqual(per.loc[mid, "calculated_avg"], raw)
            self.assertEqual(per.loc[mid, "num_double_attempts"], dbl)
            self.assertEqual(per.loc[mid, "num_failed_doubles"], failed)

    def test_empty(self):
        self.assertEqual(adjusted_stats(pd.DataFrame()), (0, 0, 0, 0, 0))
        self.assertTrue(per_match_stats(pd.DataFrame()).empty)


class DartsStats(unittest.TestCase):
    def setUp(self):
        self.s = darts_stats(pd.DataFrame(WON + LOST))

    def test_first_nine(self):
        # Won leg: 300 in 9 darts; lost leg: 180 in 9 darts.
        self.assertAlmostEqual(self.s["first9"], 480 / 18 * 3)

    def test_checkout_rate_counts_turns_with_a_chance_to_finish(self):
        self.assertEqual((self.s["checkouts"], self.s["checkout_chances"]), (1, 3))
        self.assertAlmostEqual(self.s["checkout"], 100 / 3)

    def test_finish_from_above_40_counts_as_a_chance(self):
        s = darts_stats(pd.DataFrame(leg("L", [180, 180, 141], [3, 3, 3])))
        self.assertEqual((s["checkouts"], s["checkout_chances"], s["high_out"]), (1, 1, 141))
        self.assertEqual(s["best_leg"], 9)

    def test_highest_checkout_and_best_leg(self):
        self.assertEqual(self.s["high_out"], 40)
        self.assertEqual(self.s["best_leg"], 17)  # lost leg is not a candidate

    def test_best_leg_only_counts_501(self):
        s = darts_stats(pd.DataFrame(leg("L", [100, 100, 101], start=301)))
        self.assertIsNone(s["best_leg"])
        self.assertEqual(s["high_out"], 101)

    def test_big_scores(self):
        s = darts_stats(pd.DataFrame(leg("L", [180, 140, 100, 99], start=1001)))
        self.assertEqual((s["t180"], s["t140"], s["t100"]), (1, 2, 3))

    def test_empty(self):
        s = darts_stats(pd.DataFrame())
        self.assertIsNone(s["first9"])
        self.assertIsNone(s["checkout"])
        self.assertEqual(s["t180"], 0)


if __name__ == "__main__":
    unittest.main()
