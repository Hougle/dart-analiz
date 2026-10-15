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
    # 1) Streamlit Cloud (st.secrets)
    try:
        import streamlit as st
        url = st.secrets.get("TURSO_DATABASE_URL")
        token = st.secrets.get("TURSO_AUTH_TOKEN")
        if url and token:
            # libsql:// -> https://
            if url.startswith("libsql://"):
                url = url.replace("libsql://", "https://", 1)
            return url, token
    except Exception:
        pass

    # 2) Lokal .env
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


def turso_execute(sql, args=None):
    """
    Turso HTTP API'sine tek bir SQL komutu gönderir.
    Sonuç: dict (cols, rows, affected_row_count, last_insert_rowid)
    """
    url, token = _get_turso_credentials()
    if not url or not token:
        raise RuntimeError("Turso credentials not found")

    endpoint = f"{url}/v2/pipeline"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Positional args -> Turso format
    turso_args = []
    if args:
        for a in args:
            if a is None:
                turso_args.append({"type": "null"})
            elif isinstance(a, bool):
                turso_args.append({"type": "integer", "value": str(int(a))})
            elif isinstance(a, int):
                turso_args.append({"type": "integer", "value": str(a)})
            elif isinstance(a, float):
                turso_args.append({"type": "float", "value": str(a)})
            else:
                turso_args.append({"type": "text", "value": str(a)})

    body = {
        "requests": [
            {
                "type": "execute",
                "stmt": {"sql": sql, "args": turso_args},
            },
            {"type": "close"},
        ]
    }

    r = requests.post(endpoint, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    data = r.json()

    if "results" not in data or len(data["results"]) == 0:
        raise RuntimeError(f"Turso error: {data}")

    result = data["results"][0]
    if result.get("type") == "error":
        raise RuntimeError(f"Turso SQL error: {result.get('error')}")

    return result.get("response", {}).get("result", {})


def turso_query(sql, args=None):
    """
    SELECT sorgusu çalıştırır, pandas DataFrame'e uygun liste döndürür.
    Dönüş: (columns, rows)
    """
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
    """
    Birden fazla SQL komutunu (CREATE TABLE IF NOT EXISTS) sırayla çalıştırır.
    """
    # executescript içindeki komutları ayır
    statements = [s.strip() for s in script.split(";") if s.strip()]
    for stmt in statements:
        if stmt:
            turso_execute(stmt)


def _turso_available():
    url, token = _get_turso_credentials()
    return bool(url and token)


def get_db_connection():
    """
    Eski API uyumluluğu için. Artık kullanılmıyor ama import'ları bozmamak için bırakıldı.
    """
    return sqlite3.connect(DB_PATH)


# ============================================================================
# DARtCounter API
# ============================================================================

def load_token():
    # 1) Streamlit Cloud (st.secrets) — varsa öncelikli
    try:
        import streamlit as st
        if "DARTCOUNTER_TOKEN" in st.secrets:
            token = str(st.secrets["DARTCOUNTER_TOKEN"]).strip()
            if token and len(token) > 20:
                return token
    except Exception:
        pass

    # 2) Lokal .env dosyası
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
        """)
        conn.commit()
        conn.close()
    return conn


def match_exists(conn, match_id):
    if _turso_available():
        _, rows = turso_query("SELECT 1 FROM matches WHERE match_id=?", [match_id])
        return len(rows) > 0
    c = conn.cursor()
    c.execute("SELECT 1 FROM matches WHERE match_id=?", (match_id,))
    return c.fetchone() is not None


def save_match(conn, data):
    match_id = data["id"]

    if match_exists(conn, match_id):
        print(f"  ⏭  {match_id[:8]} zaten kayıtlı, atlanıyor.")
        return False

    started_at = data.get("started_at")
    if isinstance(started_at, (int, float)):
        date_str = datetime.fromtimestamp(started_at).strftime("%Y-%m-%d %H:%M")
    else:
        date_str = str(started_at or "")

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
    p1_uid = p1.get("user_id")
    p2_uid = p2.get("user_id")
    p1_result = p1.get("result", "")
    p2_result = p2.get("result", "")
    p1_score = p1.get("checked_legs") or 0
    p2_score = p2.get("checked_legs") or 0

    def safe_float(v):
        try:
            return float(v) if v is not None else None
        except (ValueError, TypeError):
            return None

    def safe_int(v):
        try:
            return int(v) if v is not None else None
        except (ValueError, TypeError):
            return None

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
                  p1_180s, p2_180s, source)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    args = (match_id, date_str, game_type, p1_name, p2_name,
            p1_uid, p2_uid, p1_result, p2_result, p1_score, p2_score,
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
            p1_180s, p2_180s, "api")

    if _turso_available():
        turso_execute(insert_sql, list(args))
    else:
        conn.execute(insert_sql, args)

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

        if _turso_available():
            turso_execute(leg_sql, leg_args)
        else:
            conn.execute(leg_sql, leg_args)

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
                    if uid == p1_uid:
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
                    remaining_before, score, remaining_after, darts
                ]

                if _turso_available():
                    turso_execute(throw_sql, throw_args)
                else:
                    conn.execute(throw_sql, throw_args)

    update_sql = "UPDATE matches SET p1_180s=?, p2_180s=? WHERE match_id=?"
    update_args = [p1_180s, p2_180s, match_id]
    if _turso_available():
        turso_execute(update_sql, update_args)
    else:
        conn.execute(update_sql, update_args)
        conn.commit()

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
            conn.close()
            return
        lines = [l.strip() for l in ids_file.read_text().splitlines()
                 if l.strip() and not l.startswith("#")]
        print(f"{len(lines)} maç bulundu.\n")
        for line in lines:
            import_match(line, conn, token)
            print()

    conn.close()
    print("✅ Bitti.")


if __name__ == "__main__":
    main()