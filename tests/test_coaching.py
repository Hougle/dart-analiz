import unittest

import pandas as pd

import coaching
from coaching import Data, Skill
from match_stats import mark_double_attempts

TZ = "Europe/Istanbul"


def ts(s):
    return pd.Timestamp(s, tz=TZ)


def leg(match_id, leg_id, scores, when, start=501):
    rows, rem = [], start
    for i, s in enumerate(scores, start=1):
        rows.append(dict(match_id=match_id, leg_id=leg_id, turn=i, remaining_before=rem, score_thrown=s,
                         remaining_after=rem - s, darts_thrown=3, when=ts(when)))
        rem -= s
    return rows


def empty(cols):
    return pd.DataFrame(columns=cols)


def data(match_rows=(), practice=(), doubles=(), games=()):
    m = mark_double_attempts(pd.DataFrame(list(match_rows))) if match_rows else empty(
        ["match_id", "leg_id", "turn", "score_thrown", "darts_thrown", "remaining_before",
         "remaining_after", "is_dbl", "when"])
    pt = pd.DataFrame(list(practice)) if practice else empty(["session_id", "turn", "score", "when"])
    ps = (pt.groupby("session_id").agg(avg_3dart=("score", "mean"), when=("when", "first")).reset_index()
          if practice else empty(["session_id", "avg_3dart", "when"]))
    d = pd.DataFrame(list(doubles)) if doubles else empty(["when", "target", "hits", "attempts"])
    g = pd.DataFrame(list(games)) if games else empty(["when", "sec"])
    return Data(m, ps, pt, d, g)


def session(sid, scores, when):
    return [dict(session_id=sid, turn=i, score=s, when=ts(when)) for i, s in enumerate(scores, start=1)]


class Levels(unittest.TestCase):
    def test_bands(self):
        self.assertEqual(coaching.level(41.2)[1], "Developing")
        self.assertEqual(coaching.level(45)[1], "Club")
        self.assertEqual(coaching.level(91)[1:], ("Elite", 80, None))
        self.assertEqual(coaching.level(None)[0], None)

    def test_targets_are_the_next_level(self):
        t = coaching.targets(1)  # Developing -> Club targets
        self.assertEqual((t["scoring"], t["finishing"], t["doubles"]), (45, 16, 14))
        self.assertEqual(coaching.targets(5)["scoring"], coaching.ELITE_TARGET)


class RawValues(unittest.TestCase):
    def test_scoring_uses_match_scoring_turns_with_3_matches(self):
        rows = []
        for i in range(3):
            rows += leg(f"m{i}", f"l{i}", [60, 60, 60, 60, 60, 60, 60, 41, 40], f"2026-10-0{i + 1} 20:00")
        value, src, n = coaching.scoring(data(rows))
        # 7 scoring visits of 60 and one of 41 per leg (the 40 visit is the double zone)
        self.assertEqual((src, n), ("matches", 3))
        self.assertAlmostEqual(value, (7 * 60 + 41) / 8)

    def test_scoring_falls_back_to_practice(self):
        p = session(1, [45] * 10, "2026-10-01 18:00") + session(2, [60] * 10, "2026-10-02 18:00") \
            + session(3, [30] * 10, "2026-10-03 18:00")
        value, src, n = coaching.scoring(data(practice=p))
        self.assertEqual((src, n), ("Score Training", 3))
        self.assertAlmostEqual(value, 45)

    def test_recovery_compares_after_bad_with_normal(self):
        # Average visit is 50; 3 of 6 visits reach it (50%). Of the 3 visits that follow a
        # visit of 40 or less, 2 reach it (66.7%), so recovery is 66.7 / 50 = 133%.
        p = session(1, [20, 80, 20, 20, 80, 80], "2026-10-01 18:00")
        v = coaching.visits(data(practice=p))
        after, base, n = coaching.recovery_rates(v)
        self.assertEqual(n, 3)
        self.assertAlmostEqual(after, 200 / 3)
        self.assertAlmostEqual(base, 50)
        self.assertAlmostEqual(coaching.recovery(v)[0], 400 / 3)

    def test_recovery_100_when_bad_visits_dont_matter(self):
        p = session(1, [20, 80, 80, 20, 20, 20, 80, 80], "2026-10-01 18:00")  # after-bad 2 of 4, all 4 of 8
        v = coaching.visits(data(practice=p))
        after, base, _ = coaching.recovery_rates(v)
        self.assertAlmostEqual(after, base)
        self.assertAlmostEqual(coaching.recovery(v)[0], 100)

    def test_stamina_last_three_vs_first_three(self):
        p = session(1, [60, 60, 60, 50, 45, 45, 45], "2026-10-01 18:00")
        value, n = coaching.stamina(data(practice=p))
        self.assertEqual(n, 1)
        self.assertAlmostEqual(value, -25)

    def test_volume_per_week_across_empty_weeks(self):
        g = [dict(when=ts("2026-10-05 18:00"), sec=3600), dict(when=ts("2026-10-19 18:00"), sec=3600)]
        value, n = coaching.volume(data(games=g))
        self.assertAlmostEqual(value, 2 / 3)  # 2 hours over 3 Monday weeks


class Assess(unittest.TestCase):
    def test_small_samples_are_not_rated(self):
        skills = {s.key: s for s in coaching.assess(data(doubles=[dict(when=ts("2026-10-01"), target=20,
                                                                         hits=2, attempts=10)]))}
        self.assertFalse(skills["doubles"].rated)
        self.assertEqual(skills["doubles"].status, "Not enough data")

    def test_score_and_status(self):
        d = data(doubles=[dict(when=ts("2026-10-01"), target=20, hits=12, attempts=100)])
        s = {k.key: k for k in coaching.assess(d, level_index=1)}["doubles"]  # target 14%
        self.assertAlmostEqual(s.score, 12 / 14 * 100)
        self.assertEqual(s.status, "Close")

    def test_stamina_score(self):
        d = data(practice=[r for i in range(3) for r in
                           session(i, [60, 60, 60, 60, 60, 54, 54, 54], f"2026-10-0{i + 1} 18:00")])
        s = {k.key: k for k in coaching.assess(d, level_index=1)}["stamina"]
        self.assertAlmostEqual(s.value, -10)
        self.assertAlmostEqual(s.score, 75)
        self.assertEqual(s.status, "Focus")


class Explain(unittest.TestCase):
    def test_every_skill_is_explained(self):
        for key in coaching.SKILLS:
            e = coaching.EXPLAIN[key]
            self.assertTrue(e["measures"] and e["how"] and e["why"])
            self.assertIn(e["kind"], ("level", "fixed"))

    def test_fixed_targets_and_ladder(self):
        t = coaching.targets(2)
        self.assertEqual((t["start"], t["recovery"], t["stamina"]), (100, 100, -5))
        self.assertEqual(coaching.ladder("doubles")[1], ("Developing", 14))  # Developing works towards Club


class Priorities(unittest.TestCase):
    def test_weakest_first_and_volume_last(self):
        skills = [Skill("doubles", score=40), Skill("volume", score=20), Skill("finishing", score=70),
                  Skill("scoring", score=110), Skill("recovery", score=None)]
        self.assertEqual([s.key for s in coaching.priorities(skills)], ["doubles", "finishing", "volume"])


class Plan(unittest.TestCase):
    def test_plan_size_from_current_time(self):
        g = [dict(when=ts(f"2026-10-0{d} 18:00"), sec=1800) for d in (5, 7, 9)]  # 90 min in 1 week, 3 days
        prio = [Skill("doubles", score=40), Skill("finishing", score=60)]
        plan = coaching.weekly_plan(prio, data(games=g), pace_sec=6)
        self.assertEqual(plan["weekly"], 105)      # 90 min + 15%, rounded to 5
        self.assertEqual(plan["sessions"], 3)
        labels = [b["label"] for b in plan["blocks"]]
        self.assertEqual(labels, ["Warm-up", "Priority 1", "Priority 2", "Match play"])
        self.assertEqual(plan["blocks"][1]["skill"], "Doubles accuracy")
        warm = plan["blocks"][0]
        self.assertEqual(warm["darts"], int(round(warm["minutes"] * 60 / 6 / 5)) * 5)


class Progress(unittest.TestCase):
    def test_then_vs_now_needs_four_days(self):
        g = [dict(when=ts(f"2026-10-0{d} 18:00"), sec=600) for d in (1, 2, 3)]
        self.assertEqual(coaching.then_vs_now(data(games=g), 1), (None, []))

    def test_split_by_middle_day(self):
        g = [dict(when=ts(f"2026-10-0{d} 18:00"), sec=600 * d) for d in (1, 2, 3, 4)]
        cutoff, rows = coaching.then_vs_now(data(games=g), 1)
        self.assertEqual(cutoff.strftime("%Y-%m-%d"), "2026-10-03")
        vol = dict((k, (a, b)) for k, a, b in rows)["volume"]
        self.assertAlmostEqual(vol[0], (600 + 1200) / 3600)
        self.assertAlmostEqual(vol[1], (1800 + 2400) / 3600)


class Format(unittest.TestCase):
    def test_fmt(self):
        self.assertEqual(coaching.fmt("scoring", 41.234), "41.2")
        self.assertEqual(coaching.fmt("stamina", 2.3), "+2.3%")
        self.assertEqual(coaching.fmt("volume", 1.55), "1 h 33 m / wk")
        self.assertEqual(coaching.fmt("doubles", None), "–")


if __name__ == "__main__":
    unittest.main()
