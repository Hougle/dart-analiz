"""
DartCounter Singles Training oturumlarını çeker ve Turso/SQLite'a yazar.
"""
import sys
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from dartcounter_api import (
    load_token, DB_PATH, API_BASE,
    turso_execute, turso_query, turso_execute_script, _turso_available, to_date_str,
)


SINGLES_SCHEMA = """
CREATE TABLE IF NOT EXISTS singles_sessions (
    singles_user_id INTEGER PRIMARY KEY,
    session_id INTEGER,
    user_id INTEGER,
    date TEXT,
    started_at INTEGER,
    duration_sec INTEGER,
    mode TEXT,
    training_mode TEXT,
    player_name TEXT,
    result TEXT,
    total_score INTEGER,
    darts_thrown INTEGER,
    darts_hit INTEGER,
    hit_rate REAL
);
CREATE TABLE IF NOT EXISTS singles_targets (
    singles_user_id INTEGER,
    seq INTEGER,
    target INTEGER,
    hits INTEGER,
    total_score INTEGER,
    PRIMARY KEY (singles_user_id, seq)
);
"""


def setup_tables():
    if _turso_available():
        turso_execute_script(SINGLES_SCHEMA)
        print("📦 Singles tabloları Turso'da hazır.")
        return None
    else:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(SINGLES_SCHEMA)
        conn.commit()
        print(f"📦 Singles tabloları lokal SQLite'ta hazır: {DB_PATH}")
        return conn


def fetch_page(token, year, page=1, limit=25):
    params = {
        "from_date": f"{year}-01-01T00:00:00.000+03:00",
        "to_date": f"{year}-12-31T23:59:59.999+03:00",
        "is_verified": "true",
        "limit": limit,
        "page": page,
    }
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {token}",
        "origin": "https://app.dartcounter.net",
        "referer": "https://app.dartcounter.net/",
    }
    r = requests.get(f"{API_BASE}/singles-trainings/opensearch",
                     params=params, headers=headers, timeout=30)
    if r.status_code == 401:
        raise PermissionError("Token geçersiz. Yeni token al.")
    r.raise_for_status()
    return r.json()


def _exists(singles_user_id, conn):
    if _turso_available():
        _, rows = turso_query(
            "SELECT 1 FROM singles_sessions WHERE singles_user_id=?",
            [singles_user_id])
        return len(rows) > 0
    c = conn.cursor()
    c.execute("SELECT 1 FROM singles_sessions WHERE singles_user_id=?", (singles_user_id,))
    return c.fetchone() is not None


def _insert(sql, args, conn):
    if _turso_available():
        turso_execute(sql, list(args))
    else:
        conn.execute(sql, args)


def save_session(conn, s):
    settings = s.get("settings", {})
    started = s.get("started_at")
    finished = s.get("finished_at")
    duration = (finished - started) if isinstance(started, (int, float)) \
        and isinstance(finished, (int, float)) else None
    added = 0

    for u in s.get("users", []):
        singles_user_id = u.get("singles_training_user_id")
        if singles_user_id is None:
            continue
        if _exists(singles_user_id, conn):
            continue

        turns = u.get("turns", [])
        darts = u.get("darts_thrown", 0)

        _insert("""INSERT INTO singles_sessions
                   (singles_user_id, session_id, user_id, date, started_at,
                    duration_sec, mode, training_mode, player_name, result,
                    total_score, darts_thrown, darts_hit, hit_rate)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (singles_user_id, s["id"], u.get("user_id"),
                 to_date_str(started), started, duration,
                 settings.get("mode"), settings.get("training_mode"),
                 u.get("player_name"), u.get("result"), u.get("total_score"),
                 darts, u.get("darts_hit"), u.get("hit_rate")),
                conn)

        for seq, t in enumerate(turns, start=1):
            _insert("""INSERT INTO singles_targets
                       (singles_user_id, seq, target, hits, total_score)
                       VALUES (?, ?, ?, ?, ?)""",
                    (singles_user_id, seq, t.get("number_to_throw"),
                     t.get("hits"), t.get("total_score")),
                    conn)
        added += 1

    if not _turso_available() and added:
        conn.commit()
    return added


def main():
    token = load_token()
    conn = setup_tables()
    years = [int(y) for y in sys.argv[1:]] or [datetime.now().year]

    new = skipped = errors = 0
    for year in years:
        print(f"\n📅 {year} Singles Training oturumları çekiliyor...")
        page = 1
        while True:
            data = fetch_page(token, year, page=page)
            sessions = data.get("data", [])
            last_page = data.get("last_page", 1)
            print(f"  Sayfa {page}/{last_page} — {len(sessions)} oturum "
                  f"(toplam {data.get('total', 0)})")

            for s in sessions:
                try:
                    if save_session(conn, s):
                        new += 1
                        print(f"  ✅ {to_date_str(s.get('started_at'))} kaydedildi")
                    else:
                        skipped += 1
                except Exception as e:
                    errors += 1
                    print(f"  ❌ {s.get('id')}: {e}")

            if page >= last_page or not sessions:
                break
            page += 1

    if conn:
        conn.close()
    print(f"\n✅ Yeni: {new}  ⏭  Atlanan: {skipped}  ❌ Hata: {errors}")


if __name__ == "__main__":
    main()