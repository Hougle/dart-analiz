"""
Tüm maç listesini API'den çeker ve her maçın detayını indirir.
Kullanım:
    python3 list_all_matches.py              # Bu yılın tüm maçları
    python3 list_all_matches.py 2025         # 2025 yılının maçları
    python3 list_all_matches.py 2025 2026    # 2025-2026 arası
"""
import sys
from datetime import datetime
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).parent))
from dartcounter_api import (
    load_token, setup_database, save_match, fetch_match, match_exists
)

API_BASE = "https://api.dartcounter.net"


def fetch_matches_page(token, year, page=1, limit=25):
    from_date = f"{year}-01-01T00:00:00.000+03:00"
    to_date = f"{year}-12-31T23:59:59.999+03:00"
    url = f"{API_BASE}/matches"
    params = {
        "from_date": from_date,
        "to_date": to_date,
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
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_all_match_ids(token, years):
    all_ids = []
    for year in years:
        print(f"\n📅 {year} yılı maçları çekiliyor...")
        page = 1
        while True:
            data = fetch_matches_page(token, year, page=page)
            matches = data.get("data", [])
            total = data.get("total", 0)
            last_page = data.get("last_page", 1)

            print(f"  Sayfa {page}/{last_page} — {len(matches)} maç (toplam {total})")

            for m in matches:
                all_ids.append(m["id"])

            if page >= last_page or not matches:
                break
            page += 1
    return all_ids


def main():
    token = load_token()
    conn = setup_database()

    if len(sys.argv) > 1:
        years = [int(y) for y in sys.argv[1:]]
    else:
        years = [datetime.now().year]

    print(f"🎯 Yıllar: {years}")
    print("=" * 50)

    match_ids = fetch_all_match_ids(token, years)
    print(f"\n✅ Toplam {len(match_ids)} maç ID'si bulundu.\n")
    print("=" * 50)

    new_count = 0
    skip_count = 0
    error_count = 0

    for i, mid in enumerate(match_ids, 1):
        print(f"[{i}/{len(match_ids)}] ", end="")
        try:
            if match_exists(conn, mid):
                print(f"⏭  {mid[:8]} zaten kayıtlı")
                skip_count += 1
                continue

            data = fetch_match(mid, token)
            if save_match(conn, data):
                new_count += 1
            else:
                skip_count += 1
        except Exception as e:
            print(f"❌ {mid[:8]}: {e}")
            error_count += 1

    print("\n" + "=" * 50)
    print(f"✅ Yeni: {new_count}")
    print(f"⏭  Atlanan: {skip_count}")
    print(f"❌ Hata: {error_count}")
    conn.close()


if __name__ == "__main__":
    main()