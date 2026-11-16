"""
DartCounter API Client v2 — Turso HTTP API üzerinden
Maç verilerini DartCounter API'sinden çeker ve Turso'ya yazar.
"""
import os
import sqlite3
import json
import requests
from datetime import datetime
from pathlib import Path
import sys

# --- AYARLAR ---
DB_PATH = "dart.db"  # Lokal fallback (import sırasında kullanılır)
ENV_FILE = ".env"
API_BASE = "https://api.dartcounter.net"


def _get_turso_credentials():
    """Turso URL ve token'ı Streamlit secrets veya .env'den alır."""
    try:
        import streamlit as st
        url = st.secrets.get("TURSO_DATABASE_URL")
        token = st.secrets.get("TURSO_AUTH_TOKEN")
        if url and token:
            if url.startswith("libsql://"):
                url = url.replace("libsql://", "https://", 1)
            return url, token
    except Exception:
        pass

    env_path = Path(ENV_FILE)
    if env_path.exists():
        url = token = None
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("TURSO_DATABASE_URL="):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("TURSO_AUTH_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"').strip("'")
        if url and token:
            if url.startswith("libsql://"):
                url = url.replace("libsql://", "https://", 1)
            return url, token

    return None, None


def _to_turso_arg(a):
    """
    Python değerini Turso arg formatına çevirir.
    - Integer değerlerin value kısımları string olmalıdır.
    - Float değerlerin value kısımları sayı (float) olmalıdır.
    """
    if a is None:
        return {"type": "null"}

    if isinstance(a, bool):
        return {"type": "integer", "value": str(int(a))}

    try:
        import numpy as np
        if isinstance(a, np.bool_):
            return {"type": "integer", "value": str(int(a))}
        if isinstance(a, np.integer):
            return {"type": "integer", "value": str(int(a))}
        if isinstance(a, np.floating):
            return {"type": "float", "value": float(a)}
    except ImportError:
        pass

    if isinstance(a, int):
        return {"type": "integer", "value": str(a)}
    if isinstance(a, float):
        return {"type": "float", "value": a}

    if isinstance(a, str):
        s = a.strip()
        if not s:
            return {"type": "null"}
        try:
            if "." not in s and "e" not in s.lower():
                int(s)
                return {"type": "integer", "value": s}
            return {"type": "float", "value": float(s)}
        except ValueError:
            return {"type": "text", "value": s}

    return {"type": "text", "value": str(a)}


def turso_execute(sql, args=None):
    """Turso HTTP API'sine tek SQL komutu gönderir."""
    url, token = _get_turso_credentials()
    if not url or not token:
        raise RuntimeError("Turso credentials not found")

    endpoint = f"{url}/v2/pipeline"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    turso_args = [_to_turso_arg(a) for a in (args or [])]

    body = {
        "requests": [
            {"type": "execute", "stmt": {"sql": sql, "args": turso_args}},
            {"type": "close"},
        ]
    }

    r = requests.post(endpoint, headers=headers, json=body, timeout=30)
    if r.status_code != 200:
        print(f"[TURSO HATA {r.status_code}] SQL: {sql[:200]}")
        print(f"[TURSO HATA] Body: {r.text[:1000]}")
    r.raise_for_status()
    data = r.json()

    if "results" not in data or len(data["results"]) == 0:
        raise RuntimeError(f"Turso error: {data}")

    result = data["results"][0]
    if result.get("type") == "error":
        raise RuntimeError(f"Turso SQL error: {result.get('error')}")

    return result.get("response", {}).get("result", {})


def _batch_body(statements):
    """One Hrana pipeline request that runs every statement in a transaction.

    Each step only runs if the one before it succeeded; COMMIT runs only if the
    last statement did, otherwise ROLLBACK, so a failure writes nothing.
    """
    steps = [{"stmt": {"sql": "BEGIN"}}]
    for sql, args in statements:
        steps.append({"stmt": {"sql": sql, "args": [_to_turso_arg(a) for a in (args or [])]},
                      "condition": {"type": "ok", "step": len(steps) - 1}})
    commit = len(steps)
    steps.append({"stmt": {"sql": "COMMIT"}, "condition": {"type": "ok", "step": commit - 1}})
    steps.append({"stmt": {"sql": "ROLLBACK"},
                  "condition": {"type": "not", "cond": {"type": "ok", "step": commit}}})
    return {"requests": [{"type": "batch", "batch": {"steps": steps}}, {"type": "close"}]}


def turso_batch(statements):
    """Run many (sql, args) writes in one HTTP request, all or nothing.

    Much faster than turso_execute per row: a match with 60 turns is one
    request instead of 60.
    """
    statements = list(statements)
    if not statements:
        return
    url, token = _get_turso_credentials()
    if not url or not token:
        raise RuntimeError("Turso credentials not found")
    r = requests.post(f"{url}/v2/pipeline", json=_batch_body(statements), timeout=60,
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    r.raise_for_status()
    result = (r.json().get("results") or [{}])[0]
    if result.get("type") == "error":
        raise RuntimeError(f"Turso error: {result.get('error')}")
    errors = [e for e in result.get("response", {}).get("result", {}).get("step_errors", []) if e]
    if errors:
        raise RuntimeError(f"Turso SQL error (nothing written): {errors[0].get('message', errors[0])}")


def turso_query(sql, args=None):
    """SELECT sorgusu çalıştırır, (columns, rows) döndürür."""
    result = turso_execute(sql, args)
    cols = [c["name"] for c in result.get("cols", [])]
    rows = []
    for row in result.get("rows", []):
        new_row = []
        for v in row:
            if v.get("type") == "null":
                new_row.append(None)
            elif v.get("type") == "integer":
                new_row.append(int(v["value"]))
            elif v.get("type") == "float":
                new_row.append(float(v["value"]))
            else:
                new_row.append(v.get("value"))
        rows.append(new_row)
    return cols, rows


def turso_execute_script(script):
    """Birden fazla SQL komutunu sırayla çalıştırır."""
    statements = [s.strip() for s in script.split(";") if s.strip()]
    for stmt in statements:
        if stmt:
            turso_execute(stmt)


def _turso_available():
    url, token = _get_turso_credentials()
    return bool(url and token)


def get_db_connection():
    """Eski API uyumluluğu için."""
    return sqlite3.connect(DB_PATH)


def to_date_str(timestamp):
    """Timestamp değerini okunabilir tarih formatına çevirir."""
    if isinstance(timestamp, (int, float)):
        # Milisaniye cinsindense saniyeye çevir
        ts = timestamp / 1000.0 if timestamp > 1e11 else timestamp
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    return str(timestamp or "")


# ============================================================================
# DARtCounter API
# ============================================================================

# ----------------------------------------------------------------------------
# Connect DartCounter: token stored encrypted in the database
# ----------------------------------------------------------------------------
# The token is encrypted with TOKEN_ENCRYPTION_KEY (a Fernet key kept in
# st.secrets or .env) so a leaked database does not leak a usable token.

def _secret(name):
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    env_path = Path(ENV_FILE)
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _fernet():
    key = _secret("TOKEN_ENCRYPTION_KEY")
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode())


def encryption_ready():
    try:
        return _fernet() is not None
    except Exception:
        return False


def _settings_sql(sql, args=None):
    """Run SQL against the app_settings table on Turso or local SQLite."""
    create = ("CREATE TABLE IF NOT EXISTS app_settings "
              "(key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
    if _turso_available():
        turso_execute(create)
        return turso_query(sql, args)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(create)
        cur = conn.execute(sql, args or [])
        rows = cur.fetchall()
        conn.commit()
        return [d[0] for d in (cur.description or [])], rows
    finally:
        conn.close()


def validate_token(token):
    """Check a token against the DartCounter API and find out whose it is.

    Returns (ok, message, (user_id, player_name) or None).
    """
    token = (token or "").strip().removeprefix("Bearer ").strip()
    if len(token) <= 20 or "|" not in token:
        return False, "That doesn't look like a DartCounter token (expected something like 12345678|AbCd...).", None
    from sync import detect_player  # local import: sync imports this module
    try:
        uid, name = detect_player(token)
        return True, f"Connected as {name or uid}.", (uid, name)
    except PermissionError:
        return False, "DartCounter rejected this token (401). Copy a fresh one.", None
    except LookupError:
        return False, "The token works, but this DartCounter account has no games yet. Play one and try again.", None
    except Exception as e:
        return False, f"Could not reach DartCounter to check the token: {e}", None


def save_setting(key, value):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    _settings_sql("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
                  [key, str(value), now])


def mark_synced():
    """Store when the last sync ran, in Istanbul time (Streamlit Cloud's server clock is UTC)."""
    from zoneinfo import ZoneInfo
    save_setting("last_sync", datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d %b %Y, %H:%M"))


def get_setting(key):
    """Return the stored value for key, or None."""
    try:
        _, rows = _settings_sql("SELECT value FROM app_settings WHERE key = ?", [key])
        return rows[0][0] if rows else None
    except Exception:
        return None


def save_connected_player(user_id, player_name):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for key, val in (("player_user_id", str(user_id)), ("player_name", player_name or "")):
        _settings_sql("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
                      [key, val, now])


def connected_player():
    """(user_id, player_name) of the connected DartCounter account, or (None, None)."""
    try:
        _, rows = _settings_sql("SELECT key, value FROM app_settings WHERE key IN (?, ?)",
                                ["player_user_id", "player_name"])
        d = {k: v for k, v in rows}
        uid = int(d["player_user_id"]) if d.get("player_user_id") else None
        return uid, (d.get("player_name") or None)
    except Exception:
        return None, None


def save_connected_token(token):
    """Encrypt and store the token. Raises if no encryption key is configured."""
    f = _fernet()
    if f is None:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not set in secrets, so the token can't be stored safely.")
    token = token.strip().removeprefix("Bearer ").strip()
    enc = f.encrypt(token.encode()).decode()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    _settings_sql("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
                  ["dartcounter_token", enc, now])


def disconnect_token():
    _settings_sql("DELETE FROM app_settings WHERE key IN (?, ?, ?)",
                  ["dartcounter_token", "player_user_id", "player_name"])


def connected_token_info():
    """Return (token or None, updated_at or None) for the token saved via Connect."""
    try:
        _, rows = _settings_sql("SELECT value, updated_at FROM app_settings WHERE key = ?",
                                ["dartcounter_token"])
        if not rows:
            return None, None
        f = _fernet()
        if f is None:
            return None, rows[0][1]
        return f.decrypt(rows[0][0].encode()).decode(), rows[0][1]
    except Exception:
        return None, None


def load_token():
    # 1) Token connected from the app (encrypted in the database)
    stored, _ = connected_token_info()
    if stored:
        return stored
    # 2) st.secrets / 3) .env
    try:
        import streamlit as st
        if "DARTCOUNTER_TOKEN" in st.secrets:
            token = str(st.secrets["DARTCOUNTER_TOKEN"]).strip()
            if token and len(token) > 20:
                return token
    except Exception:
        pass

    env_path = Path(ENV_FILE)
    if not env_path.exists():
        raise FileNotFoundError(
            f"{ENV_FILE} bulunamadı ve st.secrets'ta DARTCOUNTER_TOKEN yok.")
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("DARTCOUNTER_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise ValueError("DARTCOUNTER_TOKEN bulunamadı.")


def fetch_match(match_id, token):
    url = f"{API_BASE}/matches/{match_id}"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {token}",
        "origin": "https://app.dartcounter.net",
        "referer": "https://app.dartcounter.net/",
    }
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code == 401:
        raise PermissionError("Token geçersiz. Yeni token al.")
    if r.status_code == 404:
        raise ValueError(f"Maç bulunamadı: {match_id}")
    r.raise_for_status()
    return r.json()


def parse_match_id(url_or_id):
    url_or_id = url_or_id.strip()
    if "/" in url_or_id:
        return url_or_id.rstrip("/").split("/")[-1]
    return url_or_id


def setup_database(conn=None):
    """Tabloları oluşturur. Turso varsa Turso'da, yoksa lokal SQLite'ta."""
    if _turso_available():
        script = """
        CREATE TABLE IF NOT EXISTS matches (
            match_id TEXT PRIMARY KEY,
            date TEXT,
            game_type TEXT,
            player1_name TEXT,
            player2_name TEXT,
            p1_user_id INTEGER,
            p2_user_id INTEGER,
            p1_result TEXT,
            p2_result TEXT,
            final_score_p1 INTEGER,
            final_score_p2 INTEGER,
            p1_avg_3dart REAL,
            p2_avg_3dart REAL,
            p1_first9_avg REAL,
            p2_first9_avg REAL,
            p1_darts INTEGER,
            p2_darts INTEGER,
            p1_highest_score INTEGER,
            p2_highest_score INTEGER,
            p1_highest_finish INTEGER,
            p2_highest_finish INTEGER,
            p1_checkout_rate REAL,
            p2_checkout_rate REAL,
            p1_180s INTEGER DEFAULT 0,
            p2_180s INTEGER DEFAULT 0,
            source TEXT
        );
        CREATE TABLE IF NOT EXISTS legs (
            leg_id TEXT PRIMARY KEY,
            match_id TEXT,
            leg_no INTEGER,
            winner_name TEXT,
            winner_match_user_id TEXT
        );
        CREATE TABLE IF NOT EXISTS throws (
            throw_id TEXT PRIMARY KEY,
            leg_id TEXT,
            match_id TEXT,
            turn INTEGER,
            player_name TEXT,
            player_user_id INTEGER,
            remaining_before INTEGER,
            score_thrown INTEGER,
            remaining_after INTEGER,
            darts_thrown INTEGER
        );
        """
        turso_execute_script(script)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id TEXT PRIMARY KEY, date TEXT, game_type TEXT,
            player1_name TEXT, player2_name TEXT,
            p1_user_id INTEGER, p2_user_id INTEGER,
            p1_result TEXT, p2_result TEXT,
            final_score_p1 INTEGER, final_score_p2 INTEGER,
            p1_avg_3dart REAL, p2_avg_3dart REAL,
            p1_first9_avg REAL, p2_first9_avg REAL,
            p1_darts INTEGER, p2_darts INTEGER,
            p1_highest_score INTEGER, p2_highest_score INTEGER,
            p1_highest_finish INTEGER, p2_highest_finish INTEGER,
            p1_checkout_rate REAL, p2_checkout_rate REAL,
            p1_180s INTEGER DEFAULT 0, p2_180s INTEGER DEFAULT 0,
            source TEXT
        );
        CREATE TABLE IF NOT EXISTS legs (
            leg_id TEXT PRIMARY KEY, match_id TEXT, leg_no INTEGER,
            winner_name TEXT, winner_match_user_id TEXT
        );
        CREATE TABLE IF NOT EXISTS throws (
            throw_id TEXT PRIMARY KEY, leg_id TEXT, match_id TEXT,
            turn INTEGER, player_name TEXT, player_user_id INTEGER,
            remaining_before INTEGER, score_thrown INTEGER,
            remaining_after INTEGER, darts_thrown INTEGER
        );
        """)
        conn.commit()
        conn.close()
    _ensure_column("matches", "duration_sec", "INTEGER")
    return conn


def _ensure_column(table, column, sql_type):
    """Add a column to an existing table if it's missing (both backends)."""
    if _turso_available():
        cols = [r[1] for r in turso_query(f"PRAGMA table_info({table})")[1]]
        if column not in cols:
            turso_execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")
            conn.commit()
    finally:
        conn.close()


def _unix(v):
    """Unix seconds from DartCounter's mix of Unix numbers (s or ms) and ISO strings."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return v / 1000 if v > 1e11 else float(v)
    try:
        return float(v) / 1000 if float(v) > 1e11 else float(v)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def match_duration(data):
    """Seconds from a match's start to its finish, or None when either is missing."""
    start, end = _unix(data.get("started_at")), _unix(data.get("finished_at"))
    if start is None or end is None or end < start:
        return None
    return int(round(end - start))


def match_exists(conn, match_id):
    if _turso_available():
        _, rows = turso_query("SELECT 1 FROM matches WHERE match_id=?", [match_id])
        return len(rows) > 0
    c = conn.cursor()
    c.execute("SELECT 1 FROM matches WHERE match_id=?", (match_id,))
    return c.fetchone() is not None


def safe_float(v):
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def safe_int(v):
    try:
        return int(float(v)) if v is not None else None
    except (ValueError, TypeError):
        return None


def _delete_match(conn, match_id):
    """Remove every row of one match (used to undo a failed, partial import)."""
    stmts = ["DELETE FROM throws WHERE match_id=?", "DELETE FROM legs WHERE match_id=?",
             "DELETE FROM matches WHERE match_id=?"]
    try:
        if _turso_available():
            for s in stmts:
                turso_execute(s, [match_id])
        else:
            conn.rollback()
            for s in stmts:
                conn.execute(s, (match_id,))
            conn.commit()
    except Exception as e:
        print(f"  ⚠  Could not clean up partial match {match_id[:8]}: {e}")


def save_match(conn, data):
    match_id = data["id"]

    if match_exists(conn, match_id):
        print(f"  ⏭  {match_id[:8]} zaten kayıtlı, atlanıyor.")
        return False

    started_at = data.get("started_at")
    date_str = to_date_str(started_at)

    settings = data.get("settings", {})
    start_score = settings.get("start_score", 501)
    goal_amount = settings.get("goal_amount", 1)
    game_type = f"Best of {goal_amount} - {start_score}"

    users = data.get("users", [])
    if len(users) < 2:
        print(f"  ⚠  {match_id[:8]}: 2 oyuncu yok, atlanıyor.")
        return False

    p1, p2 = users[0], users[1]
    p1_name = p1.get("player_name", f"P{p1.get('user_id', '1')}")
    p2_name = p2.get("player_name", f"P{p2.get('user_id', '2')}")
    p1_uid = safe_int(p1.get("user_id"))
    p2_uid = safe_int(p2.get("user_id"))
    p1_result = p1.get("result", "")
    p2_result = p2.get("result", "")
    p1_score = safe_int(p1.get("checked_legs")) or 0
    p2_score = safe_int(p2.get("checked_legs")) or 0

    p1_180s = 0
    p2_180s = 0

    insert_sql = """INSERT INTO matches
                 (match_id, date, game_type, player1_name, player2_name,
                  p1_user_id, p2_user_id, p1_result, p2_result,
                  final_score_p1, final_score_p2,
                  p1_avg_3dart, p2_avg_3dart,
                  p1_first9_avg, p2_first9_avg,
                  p1_darts, p2_darts,
                  p1_highest_score, p2_highest_score,
                  p1_highest_finish, p2_highest_finish,
                  p1_checkout_rate, p2_checkout_rate,
                  p1_180s, p2_180s, source, duration_sec)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    args = (
        match_id, date_str, game_type, p1_name, p2_name,
        p1_uid, p2_uid, p1_result, p2_result,
        p1_score, p2_score,
        safe_float(p1.get("three_dart_average")),
        safe_float(p2.get("three_dart_average")),
        safe_float(p1.get("first_nine_average")),
        safe_float(p2.get("first_nine_average")),
        safe_int(p1.get("darts_thrown")),
        safe_int(p2.get("darts_thrown")),
        safe_int(p1.get("highest_score")),
        safe_int(p2.get("highest_score")),
        safe_int(p1.get("highest_finish")),
        safe_int(p2.get("highest_finish")),
        safe_float(p1.get("checkout_rate")),
        safe_float(p2.get("checkout_rate")),
        p1_180s, p2_180s, "api", match_duration(data),
    )

    # On Turso the whole match goes out as one all-or-nothing batch at the end.
    turso = _turso_available()
    pending = []

    def write(sql, a):
        if turso:
            pending.append((sql, list(a)))
        else:
            conn.execute(sql, a)

    try:
        write(insert_sql, args)

        legs = data.get("legs", [])
        leg_no = 0
        for leg in legs:
            leg_no += 1
            leg_id = leg["leg_id"]
            winner_muid = leg.get("winner_match_user_id")

            winner_name = None
            for lu in leg.get("users", []):
                if lu.get("match_user_id") == winner_muid:
                    for u in users:
                        if u.get("user_id") == lu.get("user_id"):
                            winner_name = u.get("player_name")
                            break
                    break

            leg_sql = "INSERT INTO legs (leg_id, match_id, leg_no, winner_name, winner_match_user_id) VALUES (?, ?, ?, ?, ?)"
            leg_args = [leg_id, match_id, leg_no, winner_name, winner_muid]

            write(leg_sql, leg_args)

            for leg_user in leg.get("users", []):
                uid = leg_user.get("user_id")
                p_name = None
                for u in users:
                    if u.get("user_id") == uid:
                        p_name = u.get("player_name")
                        break
                p_name = p_name or f"P{uid}"

                turns = leg_user.get("turns", [])
                for turn_no, turn in enumerate(turns, start=1):
                    score = turn.get("total_score") or 0
                    remaining_after = turn.get("remaining_score")
                    darts = turn.get("darts_thrown") or 3

                    if turn_no == 1:
                        remaining_before = start_score
                    else:
                        prev = turns[turn_no - 2].get("remaining_score")
                        remaining_before = prev if prev is not None else start_score

                    if score == 180:
                        if safe_int(uid) == p1_uid:
                            p1_180s += 1
                        else:
                            p2_180s += 1

                    throw_sql = """INSERT INTO throws
                                 (throw_id, leg_id, match_id, turn, player_name,
                                  player_user_id, remaining_before, score_thrown,
                                  remaining_after, darts_thrown)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                    throw_args = [
                        turn.get("turn_id", f"{leg_id}_{uid}_{turn_no}"),
                        leg_id, match_id, turn_no, p_name, uid,
                        remaining_before, score, remaining_after, darts,
                    ]

                    write(throw_sql, throw_args)

        update_sql = "UPDATE matches SET p1_180s=?, p2_180s=? WHERE match_id=?"
        update_args = [p1_180s, p2_180s, match_id]
        write(update_sql, update_args)
        if turso:
            turso_batch(pending)
        else:
            conn.commit()
    except Exception:
        # Don't leave a half-saved match behind: match_exists() would then skip it forever.
        _delete_match(conn, match_id)
        raise

    print(f"  ✅ {p1_name} vs {p2_name} | Sonuç: {p1_result}")
    return True


def import_match(url_or_id, conn, token):
    match_id = parse_match_id(url_or_id)
    print(f"📥 Çekiliyor: {match_id[:8]}...")
    try:
        data = fetch_match(match_id, token)
        save_match(conn, data)
    except Exception as e:
        print(f"  ❌ Hata: {e}")


def main():
    token = load_token()
    conn = get_db_connection()
    setup_database(conn)

    if len(sys.argv) > 1:
        urls = sys.argv[1:]
        for url in urls:
            import_match(url, conn, token)
    else:
        ids_file = Path("match_ids.txt")
        if not ids_file.exists():
            print("Kullanım: python3 dartcounter_api.py <URL_veya_ID>")
            print("Veya 'match_ids.txt' dosyasına her satıra bir URL/ID yaz.")
            if conn is not None:
                conn.close()
            return
        lines = [l.strip() for l in ids_file.read_text().splitlines()
                 if l.strip() and not l.startswith("#")]
        print(f"{len(lines)} maç bulundu.\n")
        for line in lines:
            import_match(line, conn, token)
            print()

    if conn is not None:
        conn.close()
    print("✅ Bitti.")


def only_player(df, user_id=None, player_name=None, id_col="user_id"):
    """Keep only the connected player's rows (practice tables also hold opponents and CPUs)."""
    if df is None or df.empty:
        return df
    import pandas as pd
    if user_id is not None and id_col in df.columns:
        return df[pd.to_numeric(df[id_col], errors="coerce") == user_id]
    if player_name and "player_name" in df.columns:
        return df[df["player_name"] == player_name]
    return df


if __name__ == "__main__":
    main()
