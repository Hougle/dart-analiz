"""
DartCounter Around the Clock oturumlarını çeker ve dart.db'ye yazar.
Kullanım:
    python3 around_import.py              # bu yıl
    python3 around_import.py 2025 2026    # belirli yıllar
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from dartcounter_api import load_token, DB_PATH, API_BASE
from practice_import import to_date_str


def setup_tables():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS around_sessions (
        atc_user_id INTEGER PRIMARY KEY,
        session_id INTEGER,
        user_id INTEGER,
        date TEXT,
        started_at INTEGER,
        duration_sec INTEGER,
        mode TEXT,
        number_segment TEXT,
        hits TEXT,
        throwout TEXT,
        has_opponents INTEGER,
        player_name TEXT,
        is_cpu INTEGER,
        cpu_level INTEGER,
        result TEXT,
        total_score INTEGER,
        darts_thrown INTEGER,
        darts_hit INTEGER,
        hit_rate REAL
    );
    CREATE TABLE IF NOT EXISTS around_targets (
        atc_user_id INTEGER,
        seq INTEGER,
        target INTEGER,
        darts_needed INTEGER,
        PRIMARY KEY (atc_user_id, seq)
    );
    """)
    conn.commit()
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
    r = requests.get(f"{API_BASE}/around-the-clocks/opensearch",
                     params=params, headers=headers, timeout=30)
    if r.status_code == 401:
        raise PermissionError("Token geçersiz. Yeni token al.")
    r.raise_for_status()
    return r.json()


def save_session(conn, s):
    """Oturumdaki her oyuncu satırını yazar. Yeni eklenen satır sayısını döndürür."""
    settings = s.get("settings", {})
    started = s.get("started_at")
    finished = s.get("finished_at")
    duration = (finished - started) if isinstance(started, (int, float)) \
        and isinstance(finished, (int, float)) else None
    added = 0
    c = conn.cursor()

    for u in s.get("users", []):
        atc_user_id = u.get("around_the_clock_user_id")
        if atc_user_id is None:
            continue
        c.execute("SELECT 1 FROM around_sessions WHERE atc_user_id=?", (atc_user_id,))
        if c.fetchone():
            continue

        turns = u.get("turns", [])
        darts = u.get("darts_thrown")
        if darts is None:
            darts = sum((t.get("amount_of_throws_needed") or 0) for t in turns)

        c.execute("""INSERT INTO around_sessions
                     (atc_user_id, session_id, user_id, date, started_at, duration_sec,
                      mode, number_segment, hits, throwout, has_opponents,
                      player_name, is_cpu, cpu_level, result,
                      total_score, darts_thrown, darts_hit, hit_rate)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (atc_user_id, s["id"], u.get("user_id"), to_date_str(started),
                   started, duration, settings.get("mode"),
                   settings.get("number_segment"), settings.get("hits"),
                   settings.get("throwout"),
                   1 if settings.get("has_opponents") else 0,
                   u.get("player_name"), 1 if u.get("is_cpu") else 0,
                   u.get("cpu_level"), u.get("result"), u.get("total_score"),
                   darts, u.get("darts_hit"), u.get("hit_rate")))

        for seq, t in enumerate(turns, start=1):
            c.execute("""INSERT INTO around_targets
                         (atc_user_id, seq, target, darts_needed)
                         VALUES (?, ?, ?, ?)""",
                      (atc_user_id, seq, t.get("number_to_throw"),
                       t.get("amount_of_throws_needed")))
        added += 1

    conn.commit()
    return added


def main():
    token = load_token()
    conn = setup_tables()
    years = [int(y) for y in sys.argv[1:]] or [datetime.now().year]

    new = skipped = errors = 0
    for year in years:
        print(f"\n📅 {year} Around the Clock oturumları çekiliyor...")
        page = 1
        while True:
            data = fetch_page(token, year, page=page)
            sessions = data.get("data", [])
            last_page = data.get("last_page", 1)
            print(f"  Sayfa {page}/{last_page} — {len(sessions)} oturum (toplam {data.get('total', 0)})")

            for s in sessions:
                try:
                    if save_session(conn, s):
                        new += 1
                        print(f"  ✅ {to_date_str(s.get('started_at'))} kaydedildi")
                    else:
                        skipped += 1
                except Exception as e:
                    conn.rollback()
                    errors += 1
                    print(f"  ❌ {s.get('id')}: {e}")

            if page >= last_page or not sessions:
                break
            page += 1

    conn.close()
    print(f"\n✅ Yeni: {new}  ⏭  Atlanan: {skipped}  ❌ Hata: {errors}")


if __name__ == "__main__":
    main()