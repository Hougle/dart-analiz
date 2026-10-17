"""
DartCounter practice (score training) oturumlarını çeker ve Turso'ya yazar.
Kullanım:
    python3 practice_import.py              # bu yıl
    python3 practice_import.py 2025 2026    # belirli yıllar
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from dartcounter_api import (
    load_token, DB_PATH, API_BASE,
    turso_execute, turso_query, turso_execute_script, _turso_available,
)


PRACTICE_SCHEMA = """
CREATE TABLE IF NOT EXISTS practice_sessions (
    session_id INTEGER,
    user_id INTEGER,
    date TEXT,
    started_at INTEGER,
    duration_sec INTEGER,
    training_mode TEXT,
    rounds INTEGER,
    player_name TEXT,
    total_score INTEGER,
    darts_thrown INTEGER,
    avg_3dart REAL,
    PRIMARY KEY (session_id, user_id)
);
CREATE TABLE IF NOT EXISTS practice_turns (
    session_id INTEGER,
    user_id INTEGER,
    turn INTEGER,
    score INTEGER,
    PRIMARY KEY (session_id, user_id, turn)
);
"""


def _parse_dt(v):
    """
    Tarih değerini unix timestamp (int) olarak döndürür.
    Hem int/float hem ISO string kabul eder.
    """
    if v is None:
        return None
    # Zaten sayıysa
    if isinstance(v, (int, float)):
        if v > 1e11:  # milisaniye
            return int(v / 1000)
        return int(v)
    # String ise
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        # Sayı string mi?
        try:
            f = float(s)
            if f > 1e11:
                return int(f / 1000)
            return int(f)
        except ValueError:
            pass
        # ISO 8601: "2026-10-17T18:06:09.000000Z"
        try:
            s_clean = s.replace('Z', '+00:00')
            if '.' in s_clean:
                # mikrosaniyeleri temizle
                base, frac = s_clean.split('.', 1)
                if '+' in frac:
                    s_clean = base + '+' + frac.split('+', 1)[1]
                else:
                    s_clean = base + '+00:00'
            dt = datetime.fromisoformat(s_clean)
            return int(dt.timestamp())
        except Exception:
            pass
    return None


def _to_date_str(ts):
    """Unix timestamp → 'YYYY-MM-DD HH:MM' formatı."""
    if ts is None:
        return ""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def setup_practice_tables():
    """Turso varsa Turso'da, yoksa lokal SQLite'ta tabloları oluşturur."""
    if _turso_available():
        turso_execute_script(PRACTICE_SCHEMA)
        print("📦 Tablolar Turso'da hazır.")
        return None
    else:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(PRACTICE_SCHEMA)
        conn.commit()
        print(f"📦 Tablolar lokal SQLite'ta hazır: {DB_PATH}")
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
    r = requests.get(f"{API_BASE}/score-trainings/opensearch",
                     params=params, headers=headers, timeout=30)
    if r.status_code == 401:
        raise PermissionError("Token geçersiz. Yeni token al.")
    r.raise_for_status()
    return r.json()


def _session_exists(session_id, user_id, conn):
    if _turso_available():
        _, rows = turso_query(
            "SELECT 1 FROM practice_sessions WHERE session_id=? AND user_id=?",
            [session_id, user_id])
        return len(rows) > 0
    c = conn.cursor()
    c.execute("SELECT 1 FROM practice_sessions WHERE session_id=? AND user_id=?",
              (session_id, user_id))
    return c.fetchone() is not None


def _insert(sql, args, conn):
    if _turso_available():
        turso_execute(sql, list(args))
    else:
        conn.execute(sql, args)


def _f(x):
    """Garantili float."""
    if x is None:
        return None
    try:
        import math
        f = float(x)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _i(x):
    """Garantili int."""
    if x is None:
        return None
    try:
        return int(float(x))
    except (ValueError, TypeError):
        return None


def save_session(conn, s):
    """Bir oturumu yazar. Yeni eklenen oyuncu satırı sayısını döndürür."""
    session_id = s["id"]
    settings = s.get("settings", {})

    # Tarihleri güvenli parse et
    started = _parse_dt(s.get("started_at"))
    finished = _parse_dt(s.get("finished_at"))
    duration = (finished - started) if (started is not None and finished is not None) else None

    added = 0

    for u in s.get("users", []):
        uid = u.get("user_id")

        if _session_exists(session_id, uid, conn):
            continue

        turns = u.get("turns", [])
        total = u.get("total_score")
        if total is None:
            total = sum((t.get("total_score") or 0) for t in turns)
        darts = u.get("darts_thrown") or len(turns) * 3
        avg = u.get("three_dart_average")
        if avg is None:
            avg = (total / darts * 3) if darts else None

        _insert(
            """INSERT INTO practice_sessions
               (session_id, user_id, date, started_at, duration_sec,
                training_mode, rounds, player_name, total_score,
                darts_thrown, avg_3dart)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                _i(session_id),
                _i(uid),
                _to_date_str(started),
                _i(started),
                _i(duration),
                str(settings.get("training_mode")) if settings.get("training_mode") else None,
                _i(settings.get("number_of_rounds")),
                str(u.get("player_name")) if u.get("player_name") else None,
                _i(total),
                _i(darts),
                _f(avg),
            ),
            conn,
        )

        for i, t in enumerate(turns, start=1):
            _insert(
                """INSERT INTO practice_turns
                   (session_id, user_id, turn, score)
                   VALUES (?, ?, ?, ?)""",
                (_i(session_id), _i(uid), _i(i), _i(t.get("total_score") or 0)),
                conn,
            )
        added += 1

    if not _turso_available() and added:
        conn.commit()
    return added


def main():
    token = load_token()
    conn = setup_practice_tables()
    years = [int(y) for y in sys.argv[1:]] or [datetime.now().year]

    new = skipped = errors = 0
    for year in years:
        print(f"\n📅 {year} practice oturumları çekiliyor...")
        page = 1
        while True:
            data = fetch_page(token, year, page=page)
            sessions = data.get("data", [])
            last_page = data.get("last_page", 1)
            print(f"  Sayfa {page}/{last_page} — {len(sessions)} oturum "
                  f"(toplam {data.get('total', 0)})")

            for s in sessions:
                try:
                    added = save_session(conn, s)
                    if added:
                        new += added
                        print(f"  ✅ {_to_date_str(_parse_dt(s.get('started_at')))} kaydedildi")
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