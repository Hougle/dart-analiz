import unittest
from unittest import mock

import pandas as pd

import dartcounter_api
import ui_helpers
from doubles_section import _wilson_low, double_name, ranked


class DoublesRanking(unittest.TestCase):
    def test_wilson_rewards_more_evidence(self):
        # Same 50% hit rate: 50 of 100 is more reliable than 2 of 4.
        self.assertGreater(_wilson_low(50, 100), _wilson_low(2, 4))
        self.assertLess(_wilson_low(50, 100), 0.5)
        self.assertEqual(_wilson_low(0, 10), 0.0)

    def test_ranked_filters_and_orders(self):
        stats = pd.DataFrame({"target": [20, 16, 25, 1], "hits": [10, 30, 5, 9],
                              "attempts": [100, 100, 10, 10]})
        stats["value"] = stats.hits / stats.attempts
        r = ranked(stats, min_darts=20)
        self.assertEqual(r["name"].tolist(), ["D16", "D20"])  # 10-dart doubles left out
        self.assertAlmostEqual(r.loc[0, "per_hit"], 100 / 30)

    def test_double_names(self):
        self.assertEqual(double_name(8.0), "D8")
        self.assertEqual(double_name(25), "DBull")


class PeriodFilter(unittest.TestCase):
    start = pd.Timestamp("2026-11-10", tz=ui_helpers.TZ)

    def test_match_dates_are_istanbul_local(self):
        df = pd.DataFrame({"date": ["2026-11-09 23:59", "2026-11-10 00:00", "2026-11-15 12:00"]})
        self.assertEqual(len(ui_helpers.in_period(df, date_col="date", start=self.start)), 2)

    def test_practice_unix_seconds(self):
        # 2026-11-09 21:30 UTC is 00:30 on the 10th in Istanbul, so it counts.
        inside = pd.Timestamp("2026-11-09 21:30", tz="UTC").timestamp()
        outside = pd.Timestamp("2026-11-09 20:30", tz="UTC").timestamp()
        df = pd.DataFrame({"started_at": [inside, outside]})
        self.assertEqual(ui_helpers.in_period(df, start=self.start)["started_at"].tolist(), [inside])

    def test_all_time_returns_everything(self):
        df = pd.DataFrame({"date": ["2001-01-01 10:00"]})
        with mock.patch.object(ui_helpers, "period_start", return_value=None):
            self.assertEqual(len(ui_helpers.in_period(df, date_col="date")), 1)


class TursoBatch(unittest.TestCase):
    def test_body_is_one_conditional_transaction(self):
        body = dartcounter_api._batch_body([("INSERT 1", [1]), ("INSERT 2", ["a"])])
        steps = body["requests"][0]["batch"]["steps"]
        self.assertEqual([s["stmt"]["sql"] for s in steps], ["BEGIN", "INSERT 1", "INSERT 2", "COMMIT", "ROLLBACK"])
        self.assertEqual(steps[2]["condition"], {"type": "ok", "step": 1})
        self.assertEqual(steps[4]["condition"], {"type": "not", "cond": {"type": "ok", "step": 3}})
        self.assertEqual(steps[1]["stmt"]["args"], [{"type": "integer", "value": "1"}])

    def test_step_error_raises(self):
        reply = mock.Mock(status_code=200)
        reply.json.return_value = {"results": [{"type": "ok", "response": {"type": "batch", "result": {
            "step_results": [{}, None], "step_errors": [None, {"message": "UNIQUE constraint failed"}]}}}]}
        with mock.patch.object(dartcounter_api, "_get_turso_credentials", return_value=("https://x", "t")), \
                mock.patch.object(dartcounter_api.requests, "post", return_value=reply):
            with self.assertRaisesRegex(RuntimeError, "UNIQUE"):
                dartcounter_api.turso_batch([("INSERT 1", [])])

    def test_empty_batch_sends_nothing(self):
        with mock.patch.object(dartcounter_api.requests, "post") as post:
            dartcounter_api.turso_batch([])
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
