import unittest

import pandas as pd

from dartcounter_api import match_duration
from playing_time import ACTIVITIES, fmt_minutes, weekly

TZ = "Europe/Istanbul"


def game(activity, when, minutes):
    return {"activity": activity, "when": pd.Timestamp(when, tz=TZ), "sec": minutes * 60}


class Weekly(unittest.TestCase):
    def test_sums_per_monday_week_and_keeps_empty_weeks(self):
        df = pd.DataFrame([
            game("Matches", "2026-10-12 21:00", 20),          # Monday
            game("Score Training", "2026-10-18 23:30", 10),   # Sunday night, same week
            game("Matches", "2026-10-19 00:10", 5),           # next Monday
            game("Singles", "2026-11-02 18:00", 7),           # two weeks later
        ])
        t = weekly(df)
        self.assertEqual(list(t.columns), ACTIVITIES)
        self.assertEqual([d.strftime("%Y-%m-%d") for d in t.index],
                         ["2026-10-12", "2026-10-19", "2026-10-26", "2026-11-02"])
        self.assertEqual(t.sum(axis=1).tolist(), [30, 5, 0, 7])
        self.assertEqual(t.loc["2026-10-12", "Score Training"], 10)

    def test_empty(self):
        self.assertTrue(weekly(pd.DataFrame(columns=["activity", "when", "sec"])).empty)


class Format(unittest.TestCase):
    def test_minutes(self):
        self.assertEqual(fmt_minutes(12.4), "12 m")
        self.assertEqual(fmt_minutes(95), "1 h 35 m")
        self.assertEqual(fmt_minutes(120), "2 h 00 m")


class MatchDuration(unittest.TestCase):
    def test_unix_start_and_iso_finish(self):
        # DartCounter sends started_at as Unix seconds and finished_at as an ISO string.
        start = pd.Timestamp("2026-11-13 13:58:38", tz="UTC").timestamp()
        self.assertEqual(match_duration({"started_at": int(start),
                                         "finished_at": "2026-11-13T14:04:24.000000Z"}), 346)

    def test_milliseconds_and_missing(self):
        self.assertEqual(match_duration({"started_at": 1_000_000_000_000, "finished_at": 1_000_000_600}), 600)
        self.assertIsNone(match_duration({"started_at": 1_000_000_000}))
        self.assertIsNone(match_duration({"started_at": 2_000_000_000, "finished_at": 1_000_000_000}))


if __name__ == "__main__":
    unittest.main()
