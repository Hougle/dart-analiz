"""
🎯 Dart Analysis — Streamlit Main Application File
"""
import re
import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import streamlit_authenticator as stauth
import practice_tab
import coaching_page
import ui_helpers

st.set_page_config(page_title="Dart Analysis", page_icon="🎯", layout="wide")

ui_helpers.inject_mobile_css()

DB_PATH = "dart.db"
ENV_FILE = ".env"
PLAYER = "Efe"

# ============================================================
# AUTHENTICATION (Admin Login)
# ============================================================
credentials = {
    "usernames": {
        username: dict(st.secrets["credentials"]["usernames"][username])
        for username in st.secrets["credentials"]["usernames"]
    }
}
cookie_config = {
    "name": st.secrets["cookie"]["name"],
    "key": st.secrets["cookie"]["key"],
    "expiry_days": st.secrets["cookie"]["expiry_days"],
}

authenticator = stauth.Authenticate(
    credentials,
    cookie_config["name"],
    cookie_config["key"],
    cookie_config["expiry_days"],
)

if "role" not in st.session_state:
    st.session_state["role"] = "visitor"
    st.session_state["name"] = "Visitor"
    st.session_state["username"] = None

# ---------------------------------------------------------------- LANGUAGE
LANG = st.sidebar.radio("🌐 Language", ["EN", "TR"], horizontal=True, key="lang")

EN = {
    "🎯 DartCounter Analysis Dashboard": "🎯 DartCounter Analysis Dashboard",
    "⚠️ DartCounter token not found or invalid.": "⚠️ DartCounter token not found or invalid.",
    "### 🔑 How to get the token": "### 🔑 How to get the token",
    "**1.** Log in to DartCounter in your browser: `https://app.dartcounter.net`": "**1.** Log in to DartCounter in your browser: `https://app.dartcounter.net`",
    "**2.** Open any match page (Statistics → a match)": "**2.** Open any match page (Statistics → a match)",
    "**3.** Open Developer Tools with `F12`": "**3.** Open Developer Tools with `F12`",
    "**4.** Click the **Network** tab": "**4.** Click the **Network** tab",
    "**5.** Select the **Fetch/XHR** filter": "**5.** Select the **Fetch/XHR** filter",
    "**6.** Refresh the page (Cmd+R)": "**6.** Refresh the page (Cmd+R)",
    "**7.** Find a request containing `api.dartcounter.net`": "**7.** Find a request containing `api.dartcounter.net`",
    "**8.** Right-click → Copy → Copy as cURL": "**8.** Right-click → Copy → Copy as cURL",
    "**9.** The part after `Bearer ` is your token": "**9.** The part after `Bearer ` is your token",
    "**10.** Put it in the `.env` file in the project folder: `DARTCOUNTER_TOKEN=37520203|AbCdEf...`": "**10.** Put it in the `.env` file in the project folder: `DARTCOUNTER_TOKEN=37520203|AbCdEf...`",
    "**11.** Save and refresh the page.": "**11.** Save and refresh the page.",
    "💡 Once you have the token you can use it for a long time.": "💡 Once you have the token you can use it for a long time.",
    "🔑 How to get the token": "🔑 How to get the token",
    "🔑 Admin Login": "🔑 Admin Login",
    "👤 Visitor": "👤 Visitor",
    "🚪 Admin Logout": "🚪 Admin Logout",
    "✅ Token active": "✅ Token active",
    "⚙️ Actions": "⚙️ Actions",
    "🔄 FETCH NEW MATCHES": "🔄 FETCH NEW MATCHES",
    "matches are being fetched...": "matches are being fetched...",
    "(no output)": "(no output)",
    "✅ Update completed!": "✅ Update completed!",
    "Update completed!": "Update completed!",
    "❌ An error occurred": "❌ An error occurred",
    "An error occurred": "An error occurred",
    "❌ Invalid login": "❌ Invalid login",
    "Error": "Error",
    "📥 Add Match by URL": "📥 Add Match by URL",
    "DartCounter match URL:": "DartCounter match URL:",
    "Add This Match": "Add This Match",
    "A token is required first.": "A token is required first.",
    "Downloading...": "Downloading...",
    "Match added!": "Match added!",
    "URL is empty.": "URL is empty.",
    "🔄 Fetch a Specific Year": "🔄 Fetch a Specific Year",
    "Year:": "Year:",
    "Fetch This Year's Matches": "Fetch This Year's Matches",
    "Player": "Player",
    "Database": "Database",
    "No data yet. Press the 🔄 FETCH NEW MATCHES button in the sidebar.": "No data yet. Press the 🔄 FETCH NEW MATCHES button in the sidebar.",
    "Total Matches": "Total Matches",
    "Wins": "Wins",
    "Losses": "Losses",
    "Win %": "Win %",
    "Raw Avg.": "Raw Avg.",
    "Adjusted": "Adjusted",
    "180s / 100+": "180s / 100+",
    "📊 Overview": "📊 Overview",
    "📈 Progress": "📈 Progress",
    "👥 Opponents": "👥 Opponents",
    "🎯 Double Trouble": "🎯 Double Trouble",
    "🏆 Best / Worst": "🏆 Best / Worst",
    "📋 Match List": "📋 Match List",
    "🎯 Practice": "🎯 Practice",
    "Date": "Date",
    "Opponent": "Opponent",
    "Result": "Result",
    "Opp. Avg.": "Opp. Avg.",
    "Match": "Match",
    "Average": "Average",
    "✅ Won": "✅ Won",
    "❌ Lost": "❌ Lost",
    "Last 10 Matches": "Last 10 Matches",
    "Throw Score Distribution": "Throw Score Distribution",
    "Score Distribution of All Throws": "Score Distribution of All Throws",
    "Score": "Score",
    "Frequency": "Frequency",
    "Average Over Time — Raw vs Adjusted": "Average Over Time — Raw vs Adjusted",
    "Raw Average Progress": "Raw Average Progress",
    "Adjusted Average Progress": "Adjusted Average Progress",
    "Adjusted Average": "Adjusted Average",
    "Average Performance by Turn": "Average Performance by Turn",
    "Average Score by Turn Number": "Average Score by Turn Number",
    "Turn": "Turn",
    "Average Score": "Average Score",
    "Stats by Opponent": "Stats by Opponent",
    "My Average by Opponent": "My Average by Opponent",
    "🎯 Double Attempt Analysis": "🎯 Double Attempt Analysis",
    "Double attempt: Once remaining score first drops to ≤ 40 in a leg, all subsequent turns in that leg count as double attempts.": "Double attempt: Once remaining score first drops to ≤ 40 in a leg, all subsequent turns in that leg count as double attempts.",
    "Total Double Attempts": "Total Double Attempts",
    "Failed Doubles": "Failed Doubles",
    "Double Success %": "Double Success %",
    "Double Attempts by Match": "Double Attempts by Match",
    "Double Attempts": "Double Attempts",
    "Failed": "Failed",
    "Diff": "Diff",
    "Raw vs Adjusted Comparison": "Raw vs Adjusted Comparison",
    "Raw vs Adjusted by Match": "Raw vs Adjusted by Match",
    "Raw": "Raw",
    "Type": "Type",
    "🏆 Top 5 Matches (by Raw Average)": "🏆 Top 5 Matches (by Raw Average)",
    "💀 Bottom 5 Matches (by Raw Average)": "💀 Bottom 5 Matches (by Raw Average)",
    "🏆 Top 5 Matches (by Adjusted Average)": "🏆 Top 5 Matches (by Adjusted Average)",
    "All Matches": "All Matches",
    "Result:": "Result:",
    "Opponent:": "Opponent:",
    "Showing": "Showing",
    "matches": "matches",
    "🎯 Match Detail": "🎯 Match Detail",
    "No matches fit the filters.": "No matches fit the filters.",
    "Select match:": "Select match:",
    "This match has no leg data.": "This match has no leg data.",
    "This match has **{n} legs**.": "This match has **{n} legs**.",
    "Winner": "Winner",
    "**{p}** — {n} turns": "**{p}** — {n} turns",
    "Start": "Start",
    "Throw": "Throw",
    "Remaining": "Remaining",
}


def t(s):
    return EN.get(s, s) if LANG == "EN" else s


st.title(t("🎯 DartCounter Analysis Dashboard"))


def check_token():
    try:
        if "DARTCOUNTER_TOKEN" in st.secrets:
            token = str(st.secrets["DARTCOUNTER_TOKEN"]).strip()
            if token and len(token) > 20:
                return True, "ok"
    except Exception:
        pass

    env_path = Path(ENV_FILE)
    if not env_path.exists():
        return False, "no_file"
    try:
        content = env_path.read_text()
    except Exception:
        return False, "read_error"
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("DARTCOUNTER_TOKEN="):
            token = line.split("=", 1)[1].strip()
            if token and len(token) > 20:
                return True, "ok"
            return False, "empty"
    return False, "no_token"


def show_token_help():
    st.error(t("⚠️ DartCounter token not found or invalid."))
    st.markdown(t("### 🔑 How to get the token"))
    st.markdown(t("**1.** Log in to DartCounter in your browser: `https://app.dartcounter.net`"))
    st.markdown(t("**2.** Open any match page (Statistics → a match)"))
    st.markdown(t("**3.** Open Developer Tools with `F12`"))
    st.markdown(t("**4.** Click the **Network** tab"))
    st.markdown(t("**5.** Select the **Fetch/XHR** filter"))
    st.markdown(t("**6.** Refresh the page (Cmd+R)"))
    st.markdown(t("**7.** Find a request containing `api.dartcounter.net`"))
    st.markdown(t("**8.** Right-click → Copy → Copy as cURL"))
    st.markdown(t("**9.** The part after `Bearer ` is your token"))
    st.markdown(t("**10.** Put it in the `.env` file in the project folder: `DARTCOUNTER_TOKEN=37520203|AbCdEf...`"))
    st.markdown(t("**11.** Save and refresh the page."))
    st.info(t("💡 Once you have the token you can use it for a long time."))


@st.cache_data(ttl=300)
def load_data():
    try:
        import dartcounter_api
        matches_cols, matches_rows = dartcounter_api.turso_query(
            "SELECT * FROM matches ORDER BY date DESC")
        throws_cols, throws_rows = dartcounter_api.turso_query(
            "SELECT * FROM throws")
        legs_cols, legs_rows = dartcounter_api.turso_query(
            "SELECT * FROM legs")
        matches = pd.DataFrame(matches_rows, columns=matches_cols) if matches_rows else pd.DataFrame()
        throws = pd.DataFrame(throws_rows, columns=throws_cols) if throws_rows else pd.DataFrame()
        legs = pd.DataFrame(legs_rows, columns=legs_cols) if legs_rows else pd.DataFrame()
        return matches, throws, legs
    except Exception:
        try:
            conn = sqlite3.connect(DB_PATH)
            matches = pd.read_sql_query("SELECT * FROM matches ORDER BY date DESC", conn)
            throws = pd.read_sql_query("SELECT * FROM throws", conn)
            legs = pd.read_sql_query("SELECT * FROM legs", conn)
            conn.close()
            return matches, throws, legs
        except Exception:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


def clean_name(name):
    """Strip the UUID suffix DartCounter appends to bot names, e.g. 'DartBot (6)-de0d…'."""
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return None
    return re.sub(r'-[0-9a-f]{8}-[0-9a-f-]{20,}$', '', str(name))


def run_script(script, args, timeout):
    """Run a helper script, failing clearly if it is missing from the project."""
    if not Path(script).exists():
        st.error(f"{t('Error')}: `{script}` not found in the project folder.")
        return None
    return subprocess.run([sys.executable, script, *args],
                          capture_output=True, text=True, timeout=timeout)


def make_label(date, opponent, n=12):
    opp = clean_name(opponent) or ""
    if len(opp) > n:
        opp = opp[:n - 1] + "…"
    return f"{str(date)[5:16]} {opp}"


def refresh_cache():
    st.cache_data.clear()


def is_double_attempt(remaining_before):
    if remaining_before is None:
        return False
    try:
        rb = int(remaining_before)
    except (ValueError, TypeError):
        return False
    if 0 < rb <= 40 and rb % 2 == 0:
        return True
    if rb == 50:
        return True
    return False


def mark_double_attempts(throws_df):
    if throws_df.empty or "leg_id" not in throws_df.columns:
        df = throws_df.copy()
        df["is_dbl"] = df["remaining_before"].apply(is_double_attempt)
        return df

    df = throws_df.sort_values(["leg_id", "turn"]).reset_index(drop=True).copy()
    
    # Optimize edilmiş vektörel yöntem
    rb_numeric = pd.to_numeric(df["remaining_before"], errors="coerce")
    trigger = ((rb_numeric > 0) & (rb_numeric <= 40)) | (rb_numeric == 50)
    df["is_dbl"] = trigger.groupby(df["leg_id"]).cumsum() > 0

    return df


def adjusted_stats(throws_df):
    if throws_df.empty:
        return 0, 0, 0, 0, 0

    total_score = throws_df['score_thrown'].sum()
    total_darts = throws_df['darts_thrown'].sum()
    normal_avg = (total_score / total_darts * 3) if total_darts > 0 else 0

    tdf = mark_double_attempts(throws_df)

    num_dbl = int(tdf['is_dbl'].sum())
    # A double attempt only succeeds when it checks out (remaining hits 0);
    # setup shots like 32 -> 16 are not successes.
    checked_out = pd.to_numeric(tdf['remaining_after'], errors='coerce') == 0
    num_failed = int((tdf['is_dbl'] & ~checked_out).sum())

    filtered = tdf[~tdf['is_dbl']]
    if filtered.empty or filtered['darts_thrown'].sum() == 0:
        return normal_avg, 0, num_dbl, num_failed, normal_avg

    adj_avg = (filtered['score_thrown'].sum() / filtered['darts_thrown'].sum()) * 3
    return adj_avg, int(filtered['darts_thrown'].sum()), num_dbl, num_failed, normal_avg


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    if st.session_state.get("role") == "visitor":
        with st.expander(t("🔑 Admin Login"), expanded=False):
            authenticator.login(
                location="sidebar",
                key="admin_login",
            )
            
            auth_status = st.session_state.get("authentication_status")
            name_input = st.session_state.get("name")
            username_input = st.session_state.get("username")
            
            if auth_status:
                st.session_state["role"] = credentials["usernames"][username_input].get("role", "user")
                st.session_state["name"] = name_input
                st.session_state["username"] = username_input
                st.rerun()
            elif auth_status is False:
                st.error(t("❌ Invalid login"))
    else:
        st.success(f"👤 {st.session_state.get('name', '')}")
        if st.button(t("🚪 Admin Logout"), use_container_width=True):
            # Clear the authenticator's own state and cookie too; otherwise the
            # next rerun sees authentication_status=True and logs straight back in.
            try:
                authenticator.logout(location="unrendered")
            except Exception:
                pass
            st.session_state["authentication_status"] = None
            st.session_state["role"] = "visitor"
            st.session_state["name"] = "Visitor"
            st.session_state["username"] = None
            st.rerun()

    st.divider()

    token_ok, token_status = check_token()
    if not token_ok:
        with st.expander(t("🔑 How to get the token"), expanded=True):
            show_token_help()
        st.divider()
    else:
        st.success(t("✅ Token active"))

    if st.session_state.get("role") == "admin":
        st.header(t("⚙️ Actions"))

        if token_ok:
            if st.button(t("🔄 FETCH NEW MATCHES"), use_container_width=True, type="primary"):
                with st.spinner(f"{datetime.now().year} {t('matches are being fetched...')}"):
                    try:
                        result = run_script("list_all_matches.py", [str(datetime.now().year)], 900)
                        if result is not None:
                            st.code(result.stdout[-2500:] if result.stdout else t("(no output)"))
                            if result.returncode == 0:
                                st.success(t("✅ Update completed!"))
                                refresh_cache()
                                st.rerun()
                            else:
                                st.error(t("❌ An error occurred"))
                                if result.stderr:
                                    st.code(result.stderr[-1000:])
                    except Exception as e:
                        st.error(f"{t('Error')}: {e}")
            st.divider()

        practice_tab.sidebar_button(token_ok, t)

        st.subheader(t("📥 Add Match by URL"))
        url_input = st.text_input(
            t("DartCounter match URL:"),
            placeholder="https://app.dartcounter.net/statistics/match/games/...",
            key="url_input"
        )
        if st.button(t("Add This Match"), use_container_width=True):
            if not token_ok:
                st.error(t("A token is required first."))
            elif url_input.strip():
                with st.spinner(t("Downloading...")):
                    try:
                        result = subprocess.run(
                            [sys.executable, "dartcounter_api.py", url_input.strip()],
                            capture_output=True, text=True, timeout=60
                        )
                        st.code(result.stdout or t("(no output)"))
                        if result.returncode == 0 and "✅" in result.stdout:
                            st.success(t("Match added!"))
                            refresh_cache()
                            st.rerun()
                        else:
                            st.error(t("An error occurred"))
                            if result.stderr:
                                st.code(result.stderr[-1500:])
                    except Exception as e:
                        st.error(f"{t('Error')}: {e}")
            else:
                st.warning(t("URL is empty."))

        st.divider()
        st.subheader(t("🔄 Fetch a Specific Year"))
        year = st.number_input(t("Year:"), min_value=2020, max_value=2030,
                               value=datetime.now().year, step=1)
        if st.button(t("Fetch This Year's Matches"), use_container_width=True):
            if not token_ok:
                st.error(t("A token is required first."))
            else:
                with st.spinner(f"{year} {t('matches are being fetched...')}"):
                    try:
                        result = run_script("list_all_matches.py", [str(year)], 900)
                        if result is not None:
                            st.code(result.stdout[-4000:] if result.stdout else t("(no output)"))
                            if result.returncode == 0:
                                st.success(t("Update completed!"))
                                refresh_cache()
                                st.rerun()
                            else:
                                st.error(t("Error"))
                                if result.stderr:
                                    st.code(result.stderr[-1500:])
                    except Exception as e:
                        st.error(f"{t('Error')}: {e}")

        st.divider()

    st.caption(f"{t('Player')}: **{PLAYER}**")
    st.caption(f"{t('Database')}: `{DB_PATH}`")
# ============================================================


matches, throws, legs = load_data()
if matches.empty:
    st.warning(t("No data yet. Press the 🔄 FETCH NEW MATCHES button in the sidebar."))
    st.stop()

efe_matches = matches[
    (matches['player1_name'] == PLAYER) | (matches['player2_name'] == PLAYER)
].copy()


def get_efe_result(row):
    return row['p1_result'] if row['player1_name'] == PLAYER else row['p2_result']


def get_opponent(row):
    return clean_name(row['player2_name'] if row['player1_name'] == PLAYER else row['player1_name'])


def get_opponent_avg(row):
    return row['p2_avg_3dart'] if row['player1_name'] == PLAYER else row['p1_avg_3dart']


efe_matches['result'] = efe_matches.apply(get_efe_result, axis=1)
efe_matches['opponent'] = efe_matches.apply(get_opponent, axis=1)
efe_matches['opp_avg'] = efe_matches.apply(get_opponent_avg, axis=1)

efe_throws = throws[throws['player_name'] == PLAYER].copy()

match_rows = []
for match_id in efe_matches['match_id']:
    mt = efe_throws[efe_throws['match_id'] == match_id]
    adj_avg, adj_darts, num_dbl, num_fail, normal_avg = adjusted_stats(mt)
    match_rows.append({
        'match_id': match_id,
        'calculated_avg': normal_avg,
        'adjusted_avg': adj_avg,
        'num_double_attempts': num_dbl,
        'num_failed_doubles': num_fail,
    })

match_stats_df = pd.DataFrame(match_rows)
efe_matches = efe_matches.merge(match_stats_df, on='match_id', how='left')
efe_matches['avg'] = efe_matches['calculated_avg'].fillna(0).round(2)
efe_matches['adjusted_avg'] = efe_matches['adjusted_avg'].fillna(0).round(2)
efe_matches['opp_avg'] = efe_matches['opp_avg'].fillna(0).round(2)
efe_complete = efe_matches[efe_matches['result'].notna()].copy()

wins = (efe_complete['result'] == 'won').sum()
losses = (efe_complete['result'] == 'lost').sum()
total_matches = len(efe_complete)
win_rate = (wins / total_matches * 100) if total_matches > 0 else 0

total_score = efe_throws['score_thrown'].sum()
total_darts = efe_throws['darts_thrown'].sum()
overall_avg = (total_score / total_darts * 3) if total_darts > 0 else 0
adj_avg_all, adj_darts_all, total_dbl, total_failed, _ = adjusted_stats(efe_throws)
efe_180s = len(efe_throws[efe_throws['score_thrown'] == 180])
efe_100s = len(efe_throws[efe_throws['score_thrown'] >= 100])

RESULT_TXT = {'won': t('✅ Won'), 'lost': t('❌ Lost')}
RESULT_ICON = {'won': '✅', 'lost': '❌'}
MAIN_COLS = [t('Date'), t('Opponent'), t('Result'), t('Raw Avg.'), t('Adjusted'), t('Opp. Avg.')]
RAW_COLS = ['date', 'opponent', 'result', 'avg', 'adjusted_avg', 'opp_avg']

ui_helpers.metric_grid([
    {"label": t("Total Matches"), "value": total_matches},
    {"label": t("Wins"), "value": wins},
    {"label": t("Losses"), "value": losses},
    {"label": t("Win %"), "value": f"{win_rate:.1f}%"},
    {"label": t("Raw Avg."), "value": f"{overall_avg:.2f}"},
    {"label": t("Adjusted"), "value": f"{adj_avg_all:.2f}",
     "delta": f"{adj_avg_all - overall_avg:+.2f}"},
    {"label": t("180s / 100+"), "value": f"{efe_180s} / {efe_100s}"},
], cols=7)

st.divider()

# ============================================================
# MAIN TABS
# ============================================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    t("🎯 Practice"), t("📊 Overview"), t("📈 Progress"),
    t("👥 Opponents"), t("🎯 Double Trouble"), t("🏆 Best / Worst"),
    t("📋 Match List"), t("🧠 Coaching & Analytics")
])

with tab1:
    practice_tab.render(PLAYER, DB_PATH, t)

with tab2:
    st.subheader(t("Last 10 Matches"))
    recent = efe_complete.head(10)[['date', 'opponent', 'result', 'avg', 'opp_avg']].copy()
    recent['result'] = recent['result'].map(RESULT_TXT)
    recent.columns = [t('Date'), t('Opponent'), t('Result'), t('Raw Avg.'), t('Opp. Avg.')]
    st.dataframe(recent, use_container_width=True, hide_index=True)
    st.subheader(t("Throw Score Distribution"))
    fig = px.histogram(efe_throws, x='score_thrown', nbins=30,
                       title=t("Score Distribution of All Throws"),
                       labels={'score_thrown': t('Score'), 'count': t('Frequency')},
                       color_discrete_sequence=['#ff6b35'])
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader(t("Average Over Time — Raw vs Adjusted"))
    efe_sorted = efe_complete.sort_values('date').copy()
    efe_sorted['label'] = efe_sorted.apply(
        lambda r: make_label(r['date'], r['opponent']), axis=1)
    if not efe_sorted.empty:
        fig = px.line(efe_sorted, x='label', y='avg', markers=True,
                      title=f"{PLAYER} — {t('Raw Average Progress')}",
                      labels={'label': t('Match'), 'avg': t('Average')})
        fig.update_traces(line_color='#ff6b35', marker=dict(size=10))
        fig.update_xaxes(tickangle=-90)
        st.plotly_chart(fig, use_container_width=True)
        fig2 = px.line(efe_sorted, x='label', y='adjusted_avg', markers=True,
                       title=f"{PLAYER} — {t('Adjusted Average Progress')}",
                       labels={'label': t('Match'), 'adjusted_avg': t('Adjusted Average')})
        fig2.update_traces(line_color='#4ecdc4', marker=dict(size=10))
        fig2.update_xaxes(tickangle=-90)
        st.plotly_chart(fig2, use_container_width=True)
    st.subheader(t("Average Performance by Turn"))
    turn_avg = efe_throws.groupby('turn')['score_thrown'].mean().reset_index()
    turn_avg['score_thrown'] = turn_avg['score_thrown'].round(2)
    fig3 = px.bar(turn_avg, x='turn', y='score_thrown',
                  title=t("Average Score by Turn Number"),
                  labels={'turn': t('Turn'), 'score_thrown': t('Average Score')},
                  color='score_thrown', color_continuous_scale='Oranges')
    st.plotly_chart(fig3, use_container_width=True)

with tab4:
    st.subheader(t("Stats by Opponent"))
    opp_stats = efe_complete.groupby('opponent').agg(
        Mac=('match_id', 'count'),
        Galibiyet=('result', lambda x: (x == 'won').sum()),
        Maglubiyet=('result', lambda x: (x == 'lost').sum()),
        Ham_Ort=('avg', 'mean'),
        Adjusted=('adjusted_avg', 'mean'),
        Rakip_Ort=('opp_avg', 'mean')
    ).reset_index()
    opp_stats['Kazanma_Yuzde'] = (opp_stats['Galibiyet'] / opp_stats['Mac'] * 100).round(1)
    opp_stats['Ham_Ort'] = opp_stats['Ham_Ort'].round(2)
    opp_stats['Adjusted'] = opp_stats['Adjusted'].round(2)
    opp_stats['Rakip_Ort'] = opp_stats['Rakip_Ort'].round(2)
    opp_stats = opp_stats.sort_values('Mac', ascending=False)
    opp_display = opp_stats.rename(columns={
        'opponent': t('Opponent'), 'Mac': t('Match'), 'Galibiyet': t('Wins'),
        'Maglubiyet': t('Losses'), 'Ham_Ort': t('Raw Avg.'),
        'Adjusted': t('Adjusted'), 'Rakip_Ort': t('Opp. Avg.'),
        'Kazanma_Yuzde': t('Win %')})
    st.dataframe(opp_display, use_container_width=True, hide_index=True)
    st.subheader(t("My Average by Opponent"))
    fig = px.bar(opp_stats, x='opponent', y='Ham_Ort',
                 color='Ham_Ort', color_continuous_scale='Oranges',
                 text='Ham_Ort', labels={'opponent': t('Opponent'), 'Ham_Ort': t('Average')})
    fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
    st.plotly_chart(fig, use_container_width=True)

with tab5:
    st.subheader(t("🎯 Double Attempt Analysis"))
    st.caption(t("Double attempt: Once remaining score first drops to ≤ 40 in a leg, all subsequent turns in that leg count as double attempts."))
    col1, col2, col3 = st.columns(3)
    col1.metric(t("Total Double Attempts"), int(total_dbl))
    col2.metric(t("Failed Doubles"), int(total_failed))
    success_rate = ((total_dbl - total_failed) / total_dbl * 100) if total_dbl > 0 else 0
    col3.metric(t("Double Success %"), f"{success_rate:.1f}%")
    st.subheader(t("Double Attempts by Match"))
    dbl_df = efe_complete[['date', 'opponent', 'avg', 'adjusted_avg',
                            'num_double_attempts', 'num_failed_doubles', 'result']].copy()
    dbl_df['fark'] = (dbl_df['adjusted_avg'] - dbl_df['avg']).round(2)
    dbl_df['result'] = dbl_df['result'].map(RESULT_ICON)
    dbl_df.columns = [t('Date'), t('Opponent'), t('Raw Avg.'), t('Adjusted'),
                      t('Double Attempts'), t('Failed'), t('Result'), t('Diff')]
    st.dataframe(dbl_df, use_container_width=True, hide_index=True)
    st.subheader(t("Raw vs Adjusted Comparison"))
    comp_df = efe_complete[['date', 'opponent', 'avg', 'adjusted_avg']].copy()
    comp_df['label'] = comp_df.apply(
        lambda r: make_label(r['date'], r['opponent']), axis=1)
    comp_df = comp_df.melt(id_vars=['label'], value_vars=['avg', 'adjusted_avg'],
                           var_name='Tip', value_name='Ortalama')
    comp_df['Tip'] = comp_df['Tip'].map({'avg': t('Raw'), 'adjusted_avg': t('Adjusted')})
    fig = px.bar(comp_df, x='label', y='Ortalama', color='Tip', barmode='group',
                 title=t("Raw vs Adjusted by Match"),
                 labels={'label': t('Match'), 'Ortalama': t('Average'), 'Tip': t('Type')})
    fig.update_xaxes(tickangle=-90)
    st.plotly_chart(fig, use_container_width=True)

with tab6:
    st.subheader(t("🏆 Top 5 Matches (by Raw Average)"))
    best = efe_complete.nlargest(5, 'avg')[RAW_COLS].copy()
    best['result'] = best['result'].map(RESULT_ICON)
    best.columns = MAIN_COLS
    st.dataframe(best, use_container_width=True, hide_index=True)
    st.subheader(t("💀 Bottom 5 Matches (by Raw Average)"))
    worst = efe_complete.nsmallest(5, 'avg')[RAW_COLS].copy()
    worst['result'] = worst['result'].map(RESULT_ICON)
    worst.columns = MAIN_COLS
    st.dataframe(worst, use_container_width=True, hide_index=True)
    st.subheader(t("🏆 Top 5 Matches (by Adjusted Average)"))
    best_adj = efe_complete.nlargest(5, 'adjusted_avg')[RAW_COLS].copy()
    best_adj['result'] = best_adj['result'].map(RESULT_ICON)
    best_adj.columns = MAIN_COLS
    st.dataframe(best_adj, use_container_width=True, hide_index=True)

with tab7:
    st.subheader(f"{t('All Matches')} ({len(efe_complete)})")
    col1, col2 = st.columns(2)
    with col1:
        result_filter = st.multiselect(t("Result:"), options=['won', 'lost'],
                                       default=['won', 'lost'],
                                       format_func=lambda x: RESULT_TXT[x])
    with col2:
        all_opponents = sorted(efe_complete['opponent'].unique())
        opponent_filter = st.multiselect(t("Opponent:"), all_opponents, default=all_opponents)
    filtered = efe_complete[
        (efe_complete['result'].isin(result_filter)) &
        (efe_complete['opponent'].isin(opponent_filter))
    ].copy()
    display_df = filtered[RAW_COLS].copy()
    display_df['result'] = display_df['result'].map(RESULT_TXT)
    display_df['avg'] = display_df['avg'].round(2)
    display_df['adjusted_avg'] = display_df['adjusted_avg'].round(2)
    display_df['opp_avg'] = display_df['opp_avg'].round(2)
    display_df.columns = MAIN_COLS
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    st.caption(f"{t('Showing')}: {len(filtered)} {t('matches')}")
    st.divider()
    st.subheader(t("🎯 Match Detail"))
    match_options = filtered.apply(lambda r: f"{r['date']} — vs {r['opponent']}", axis=1).tolist()
    if not match_options:
        st.info(t("No matches fit the filters."))
    else:
        selected = st.selectbox(t("Select match:"), match_options)
        idx = match_options.index(selected)
        selected_match_id = filtered.iloc[idx]['match_id']
        match_legs = legs[legs['match_id'] == selected_match_id].sort_values('leg_no')
        num_legs = len(match_legs)
        if num_legs == 0:
            st.warning(t("This match has no leg data."))
        else:
            st.caption(t("This match has **{n} legs**.").format(n=num_legs))
            for _, leg_row in match_legs.iterrows():
                leg_id = leg_row['leg_id']
                leg_no = leg_row['leg_no']
                winner = clean_name(leg_row['winner_name']) or "?"
                st.markdown(f"### Leg {leg_no} — {t('Winner')}: **{winner}**")
                leg_throws = throws[throws['leg_id'] == leg_id].copy()
                leg_throws = leg_throws.sort_values(['player_name', 'turn'])
                players_in_leg = [PLAYER] + [
                    p for p in leg_throws['player_name'].unique() if p != PLAYER][:2]
                if len(players_in_leg) == 2:
                    cols = st.columns(2)
                    for i, player in enumerate(players_in_leg):
                        p_throws = leg_throws[leg_throws['player_name'] == player].copy()
                        if p_throws.empty:
                            continue
                        with cols[i]:
                            st.write(t("**{p}** — {n} turns").format(p=clean_name(player), n=len(p_throws)))
                            p_marked = mark_double_attempts(p_throws)
                            p_marked['Dbl'] = p_marked['is_dbl'].apply(
                                lambda x: '🎯' if x else '')
                            p_display = p_marked[
                                ['turn', 'remaining_before', 'score_thrown', 'remaining_after', 'Dbl']].copy()
                            p_display.columns = [t('Turn'), t('Start'), t('Throw'), t('Remaining'), '🎯']
                            st.dataframe(p_display, use_container_width=True,
                                         hide_index=True, height=400)
                else:
                    p_display = leg_throws[
                        ['player_name', 'turn', 'remaining_before', 'score_thrown', 'remaining_after']].copy()
                    p_display.columns = [t('Player'), t('Turn'), t('Start'), t('Throw'), t('Remaining')]
                    st.dataframe(p_display, use_container_width=True, hide_index=True)

with tab8:
    coaching_page.render_coaching_page(PLAYER, t)
