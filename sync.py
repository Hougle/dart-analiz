"""
Sync a connected player's DartCounter history into the database.

One token is enough: the DartCounter API returns the token owner's own
matches and practice sessions. Everything already stored is skipped, so
syncing again only adds what's new.

Ported from the former list_all_matches.py, practice_import.py,
around_import.py and singles_import.py scripts.
"""
import math
import sqlite3
from collections import Counter
from datetime import datetime

import requests

from dartcounter_api import (
    API_BASE, DB_PATH, _turso_available, turso_batch, turso_execute_script,
    turso_query, setup_database, match_exists, fetch_match, save_match, match_duration,
)

FIRST_YEAR = 2015  # DartCounter's online stats don't go back further than this

PRACTICE_SCHEMA = """
CREATE TABLE IF NOT EXISTS practice_sessions (
    session_id INTEGER, user_id INTEGER, date TEXT, started_at INTEGER,
    duration_sec INTEGER, training_mode TEXT, rounds INTEGER, player_name TEXT,
    total_score INTEGER, darts_thrown INTEGER, avg_3dart REAL,
    PRIMARY KEY (session_id, user_id)
);
CREATE TABLE IF NOT EXISTS practice_turns (
    session_id INTEGER, user_id INTEGER, turn INTEGER, score INTEGER,
    PRIMARY KEY (session_id, user_id, turn)
);
CREATE TABLE IF NOT EXISTS around_sessions (
    atc_user_id INTEGER PRIMARY KEY, session_id INTEGER, user_id INTEGER,
    date TEXT, started_at INTEGER, duration_sec INTEGER, mode TEXT,
    number_segment TEXT, hits TEXT, throwout TEXT, has_opponents INTEGER,
    player_name TEXT, is_cpu INTEGER, cpu_level INTEGER, result TEXT,
    total_score INTEGER, darts_thrown INTEGER, darts_hit INTEGER, hit_rate REAL
);
CREATE TABLE IF NOT EXISTS around_targets (
    atc_user_id INTEGER, seq INTEGER, target INTEGER, darts_needed INTEGER,
    PRIMARY KEY (atc_user_id, seq)
);
CREATE TABLE IF NOT EXISTS singles_sessions (
    singles_user_id INTEGER PRIMARY KEY, session_id INTEGER, user_id INTEGER,
    date TEXT, started_at INTEGER, duration_sec INTEGER, mode TEXT,
    training_mode TEXT, player_name TEXT, result TEXT, total_score INTEGER,
    darts_thrown INTEGER, darts_hit INTEGER, hit_rate REAL
);
CREATE TABLE IF NOT EXISTS singles_targets (
    singles_user_id INTEGER, seq INTEGER, target INTEGER, hits INTEGER,
    total_score INTEGER, PRIMARY KEY (singles_user_id, seq)
);
CREATE TABLE IF NOT EXISTS doubles_sessions (
    doubles_user_id INTEGER PRIMARY KEY, session_id INTEGER, user_id INTEGER,
    date TEXT, started_at INTEGER, duration_sec INTEGER, mode TEXT,
    training_mode TEXT, player_name TEXT, result TEXT, darts_thrown INTEGER,
    darts_hit INTEGER, hit_rate REAL
);
CREATE TABLE IF NOT EXISTS doubles_targets (
    doubles_user_id INTEGER, seq INTEGER, target INTEGER, darts_thrown INTEGER,
    hits INTEGER, PRIMARY KEY (doubles_user_id, seq)
);
"""

ENDPOINTS = {
    "matches": "/matches",
    "score": "/score-trainings/opensearch",
    "atc": "/around-the-clocks/opensearch",
    "singles": "/singles-trainings/opensearch",
    "doubles": "/doubles-trainings/opensearch",
}


# ---------------------------------------------------------------- helpers
def _headers(token):
    return {
        "accept": "application/json",
        "authorization": f"Bearer {token}",
        "origin": "https://app.dartcounter.net",
        "referer": "https://app.dartcounter.net/",
    }


def _page(kind, token, year, page=1, limit=25):
    params = {
        "from_date": f"{year}-01-01T00:00:00.000+03:00",
        "to_date": f"{year}-12-31T23:59:59.999+03:00",
        "is_verified": "true", "limit": limit, "page": page,
    }
    r = requests.get(API_BASE + ENDPOINTS[kind], params=params,
                     headers=_headers(token), timeout=30)
    if r.status_code == 401:
        raise PermissionError("DartCounter rejected the token (401). Connect a fresh one.")
    r.raise_for_status()
    return r.json()


def _items(kind, token, year):
    page = 1
    while True:
        data = _page(kind, token, year, page)
        items = data.get("data", [])
        yield from items
        if page >= data.get("last_page", 1) or not items:
            break
        page += 1


def _ts(v):
    """Any DartCounter timestamp (seconds, ms, numeric string or ISO) -> unix seconds."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v / 1000) if v > 1e11 else int(v)
    s = str(v).strip()
    if not s:
        return None
    try:
        f = float(s)
        return int(f / 1000) if f > 1e11 else int(f)
    except ValueError:
        pass
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def _date(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""


def _i(x):
    try:
        return int(float(x)) if x is not None else None
    except (ValueError, TypeError):
        return None


def _f(x):
    try:
        f = float(x)
        return None if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return None


class _DB:
    """Tiny writer over Turso or local SQLite.

    On Turso, writes are buffered and sent as one all-or-nothing batch per
    session (flushed before the next existence check), instead of one HTTP
    request per row.
    """

    def __init__(self):
        self.turso = _turso_available()
        self.conn = None if self.turso else sqlite3.connect(DB_PATH)
        self.pending = []
        if self.turso:
            turso_execute_script(PRACTICE_SCHEMA)
        else:
            self.conn.executescript(PRACTICE_SCHEMA)

    def exists(self, sql, args):
        self.flush()
        if self.turso:
            return len(turso_query(sql, list(args))[1]) > 0
        return self.conn.execute(sql, args).fetchone() is not None

    def run(self, sql, args):
        if self.turso:
            self.pending.append((sql, list(args)))
        else:
            self.conn.execute(sql, args)

    def flush(self):
        if self.pending:
            batch, self.pending = self.pending, []
            turso_batch(batch)

    def discard(self):
        """Drop writes from a session that failed half-way, so it isn't saved incomplete."""
        self.pending = []
        if self.conn:
            self.conn.rollback()

    def commit(self):
        self.flush()
        if self.conn:
            self.conn.commit()

    def close(self):
        self.commit()
        if self.conn:
            self.conn.close()


def _duration(s):
    a, b = _ts(s.get("started_at")), _ts(s.get("finished_at"))
    return (b - a) if a is not None and b is not None else None


# ---------------------------------------------------------- per-type savers
def _save_score(db, s):
    sid, settings = s["id"], s.get("settings", {})
    started = _ts(s.get("started_at"))
    added = 0
    for u in s.get("users", []):
        uid = u.get("user_id")
        if db.exists("SELECT 1 FROM practice_sessions WHERE session_id=? AND user_id=?", (sid, uid)):
            continue
        turns = u.get("turns", [])
        total = u.get("total_score")
        if total is None:
            total = sum((t.get("total_score") or 0) for t in turns)
        darts = u.get("darts_thrown") or len(turns) * 3
        avg = u.get("three_dart_average")
        if avg is None:
            avg = (total / darts * 3) if darts else None
        db.run("""INSERT INTO practice_sessions (session_id, user_id, date, started_at, duration_sec,
                  training_mode, rounds, player_name, total_score, darts_thrown, avg_3dart)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
               (_i(sid), _i(uid), _date(started), started, _i(_duration(s)),
                settings.get("training_mode"), _i(settings.get("number_of_rounds")),
                u.get("player_name"), _i(total), _i(darts), _f(avg)))
        for i, t in enumerate(turns, start=1):
            db.run("INSERT INTO practice_turns (session_id, user_id, turn, score) VALUES (?, ?, ?, ?)",
                   (_i(sid), _i(uid), i, _i(t.get("total_score") or 0)))
        added += 1
    return added


def _save_atc(db, s):
    settings = s.get("settings", {})
    started = _ts(s.get("started_at"))
    added = 0
    for u in s.get("users", []):
        auid = u.get("around_the_clock_user_id")
        if auid is None or db.exists("SELECT 1 FROM around_sessions WHERE atc_user_id=?", (auid,)):
            continue
        turns = u.get("turns", [])
        darts = u.get("darts_thrown")
        if darts is None:
            darts = sum((t.get("amount_of_throws_needed") or 0) for t in turns)
        db.run("""INSERT INTO around_sessions (atc_user_id, session_id, user_id, date, started_at,
                  duration_sec, mode, number_segment, hits, throwout, has_opponents, player_name,
                  is_cpu, cpu_level, result, total_score, darts_thrown, darts_hit, hit_rate)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
               (auid, s["id"], u.get("user_id"), _date(started), started, _i(_duration(s)),
                settings.get("mode"), settings.get("number_segment"), settings.get("hits"),
                settings.get("throwout"), 1 if settings.get("has_opponents") else 0,
                u.get("player_name"), 1 if u.get("is_cpu") else 0, u.get("cpu_level"),
                u.get("result"), u.get("total_score"), darts, u.get("darts_hit"), _f(u.get("hit_rate"))))
        for seq, t in enumerate(turns, start=1):
            db.run("INSERT INTO around_targets (atc_user_id, seq, target, darts_needed) VALUES (?, ?, ?, ?)",
                   (auid, seq, t.get("number_to_throw"), t.get("amount_of_throws_needed")))
        added += 1
    return added


def _save_singles(db, s):
    settings = s.get("settings", {})
    started = _ts(s.get("started_at"))
    added = 0
    for u in s.get("users", []):
        suid = u.get("singles_training_user_id")
        if suid is None or db.exists("SELECT 1 FROM singles_sessions WHERE singles_user_id=?", (suid,)):
            continue
        db.run("""INSERT INTO singles_sessions (singles_user_id, session_id, user_id, date, started_at,
                  duration_sec, mode, training_mode, player_name, result, total_score, darts_thrown,
                  darts_hit, hit_rate) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
               (suid, s["id"], u.get("user_id"), _date(started), started, _i(_duration(s)),
                settings.get("mode"), settings.get("training_mode"), u.get("player_name"),
                u.get("result"), u.get("total_score"), u.get("darts_thrown", 0),
                u.get("darts_hit"), _f(u.get("hit_rate"))))
        for seq, t in enumerate(u.get("turns", []), start=1):
            db.run("""INSERT INTO singles_targets (singles_user_id, seq, target, hits, total_score)
                      VALUES (?, ?, ?, ?, ?)""",
                   (suid, seq, t.get("number_to_throw"), t.get("hits"), t.get("total_score")))
        added += 1
    return added


def _save_doubles(db, s):
    """Doubles Training: each target (D1..D20, bull = 25) is thrown at until it is hit.

    A hit is a throw with multiplier 2 on the target number. If the throw list
    is missing, hits fall back to the target's hit_rate x darts_thrown.
    """
    settings = s.get("settings", {})
    started = _ts(s.get("started_at"))
    added = 0
    for u in s.get("users", []):
        duid = u.get("doubles_training_user_id")
        if duid is None or db.exists("SELECT 1 FROM doubles_sessions WHERE doubles_user_id=?", (duid,)):
            continue
        rows, total_hits = [], 0
        for seq, t in enumerate(u.get("turns", []), start=1):
            target = _i(t.get("number_to_throw"))
            darts = _i(t.get("darts_thrown")) or 0
            throws = t.get("throws") or []
            if throws:
                hits = sum(1 for x in throws
                           if _i(x.get("multiplier")) == 2 and _i(x.get("number")) == target)
            else:
                hits = round(darts * (_f(t.get("hit_rate")) or 0) / 100)
            total_hits += hits
            rows.append((duid, seq, target, darts, hits))
        db.run("""INSERT INTO doubles_sessions (doubles_user_id, session_id, user_id, date, started_at,
                  duration_sec, mode, training_mode, player_name, result, darts_thrown, darts_hit,
                  hit_rate) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
               (duid, s["id"], u.get("user_id"), _date(started), started, _i(_duration(s)),
                settings.get("mode"), settings.get("training_mode"), u.get("player_name"),
                u.get("result"), _i(u.get("darts_thrown")), total_hits, _f(u.get("hit_rate"))))
        for r in rows:
            db.run("""INSERT INTO doubles_targets (doubles_user_id, seq, target, darts_thrown, hits)
                      VALUES (?, ?, ?, ?, ?)""", r)
        added += 1
    return added


# ------------------------------------------------------------- public API
def detect_player(token):
    """Work out who owns the token: the user present in all of their own games.

    Returns (user_id, player_name). Raises PermissionError for a rejected token
    and LookupError if the account has no games to look at yet.
    """
    seen, names = Counter(), {}
    year = datetime.now().year
    for y in (year, year - 1):
        for kind in ENDPOINTS:
            data = _page(kind, token, y, limit=25)
            for item in data.get("data", []):
                for u in item.get("users", []):
                    uid = u.get("user_id")
                    if uid is None or u.get("is_cpu"):
                        continue
                    seen[uid] += 1
                    if u.get("player_name"):
                        names[uid] = u["player_name"]
        if seen:
            break
    if not seen:
        raise LookupError("No games found on this DartCounter account yet.")
    uid, _ = seen.most_common(1)[0]
    return int(uid), names.get(uid)


def backfill_match_durations(token, log=print):
    """Fill matches.duration_sec for matches stored before it existed. Returns how many were filled."""
    sql = "SELECT match_id FROM matches WHERE duration_sec IS NULL"
    turso = _turso_available()
    if turso:
        ids = [r[0] for r in turso_query(sql)[1]]
    else:
        with sqlite3.connect(DB_PATH) as conn:
            ids = [r[0] for r in conn.execute(sql)]
    if not ids:
        return 0
    log(f"⏱ Fetching match length for {len(ids)} older matches")
    updates = []
    for mid in ids:
        try:
            sec = match_duration(fetch_match(mid, token))
        except PermissionError:
            raise
        except Exception as e:
            log(f"  ❌ match {mid[:8]}: {e}")
            continue
        if sec is not None:
            updates.append(("UPDATE matches SET duration_sec=? WHERE match_id=?", [sec, mid]))
    if turso:
        turso_batch(updates)
    elif updates:
        with sqlite3.connect(DB_PATH) as conn:
            conn.executemany(updates[0][0], [args for _, args in updates])
    return len(updates)


def sync_all(token, years=None, log=print):
    """Import every match and practice session for the given years.

    With years=None, walks back from this year until two empty years in a row.
    Returns a dict of new rows per type.
    """
    current = datetime.now().year
    years = list(years) if years else list(range(current, FIRST_YEAR - 1, -1))
    stats = {"matches": 0, "score": 0, "atc": 0, "singles": 0, "doubles": 0, "errors": 0}
    savers = {"score": _save_score, "atc": _save_atc, "singles": _save_singles,
              "doubles": _save_doubles}

    setup_database()
    match_conn = None if _turso_available() else sqlite3.connect(DB_PATH)
    db = _DB()
    empty_streak = 0
    try:
        try:
            backfill_match_durations(token, log)
        except PermissionError:
            raise
        except Exception as e:
            stats["errors"] += 1
            log(f"  ❌ match length backfill: {e}")
        for year in years:
            found = 0
            log(f"📅 {year}")
            for m in _items("matches", token, year):
                found += 1
                try:
                    if not match_exists(match_conn, m["id"]):
                        if save_match(match_conn, fetch_match(m["id"], token)):
                            stats["matches"] += 1
                except PermissionError:
                    raise
                except Exception as e:
                    stats["errors"] += 1
                    log(f"  ❌ match {str(m.get('id'))[:8]}: {e}")
            for kind, saver in savers.items():
                for s in _items(kind, token, year):
                    found += 1
                    try:
                        stats[kind] += saver(db, s)
                        db.commit()
                    except Exception as e:
                        db.discard()
                        stats["errors"] += 1
                        log(f"  ❌ {kind} {s.get('id')}: {e}")
                db.commit()
            log(f"  {found} games checked")
            empty_streak = empty_streak + 1 if found == 0 else 0
            if empty_streak >= 2 and len(years) > 1:
                break
    finally:
        db.close()
        if match_conn:
            match_conn.close()
    return stats


# ------------------------------------------------------------------ CLI
def main(argv=None):
    """python sync.py        -> this year and last year
       python sync.py --all  -> the whole history
    Writes to Turso when its credentials are set (the live site reads the same database)."""
    import sys
    from dartcounter_api import load_token, mark_synced

    args = sys.argv[1:] if argv is None else argv
    token = load_token()
    if not token:
        print("No DartCounter token found. Add DARTCOUNTER_TOKEN to .streamlit/secrets.toml or .env.")
        return 1
    year = datetime.now().year
    years = None if "--all" in args else [year, year - 1]
    print("Database:", "Turso" if _turso_available() else DB_PATH)
    try:
        stats = sync_all(token, years=years)
    except PermissionError as e:
        print(f"Token rejected: {e}")
        return 1
    new = sum(v for k, v in stats.items() if k != "errors")
    print(f"Done: {new} new games ({stats}).")
    if stats["errors"]:
        return 1
    mark_synced()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
