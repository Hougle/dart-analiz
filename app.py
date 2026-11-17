"""
🎯 Dart Analysis — Streamlit Main Application File
"""
import re
import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import streamlit_authenticator as stauth
from freshness import drop_stale_modules
drop_stale_modules()  # before the project imports: never mix new and old modules after a push
import practice_tab
import coaching_page
import ui_helpers
from match_stats import adjusted_stats, darts_stats, mark_double_attempts, per_match_stats
import doubles_section
import home_tab

st.set_page_config(page_title="DartAnaliz", page_icon=":material/target:", layout="wide")

ui_helpers.inject_theme_css()

DB_PATH = "dart.db"
ENV_FILE = ".env"
DEFAULT_PLAYER = "Efe"  # used until a DartCounter account is connected


@st.cache_data(ttl=60, show_spinner=False)
def get_connected_player():
    import dartcounter_api
    return dartcounter_api.connected_player()


# The dashboard shows whoever connected their DartCounter account.
PLAYER_ID, _connected_name = get_connected_player()
PLAYER = _connected_name or DEFAULT_PLAYER

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

def t(s):
    """UI text hook. All text is English for now; a translation table can plug in here."""
    return s




@st.cache_data(ttl=60, show_spinner=False)
def check_token():
    """Return (ok, source, updated_at). Source: 'connected', 'config' or None."""
    import dartcounter_api
    stored, updated = dartcounter_api.connected_token_info()
    if stored:
        return True, "connected", updated
    try:
        token = dartcounter_api.load_token()
        if token and len(token) > 20:
            return True, "config", None
    except Exception:
        pass
    return False, None, None


def connect_dartcounter_panel(token_ok, source, updated):
    """Sidebar panel: paste a token, check it against DartCounter, store it encrypted."""
    import dartcounter_api
    title = t("Connect DartCounter") + (" · connected" if token_ok else "")
    with st.expander(title, expanded=not token_ok):
        if token_ok and source == "connected":
            st.success(f"{t('Connected')} · {t('updated')} {updated}")
        elif token_ok:
            st.info(t("Using the token from the config file (.env / secrets). Connect here to replace it."))

        if not dartcounter_api.encryption_ready():
            st.warning(t("Add TOKEN_ENCRYPTION_KEY to secrets to store tokens from here. "
                         "Generate one with: python -c \"from cryptography.fernet import Fernet; "
                         "print(Fernet.generate_key().decode())\""))
            return

        with st.form("connect_dc", clear_on_submit=True):
            token_in = st.text_input(t("DartCounter token"), type="password",
                                     placeholder="12345678|AbCdEf...",
                                     help=t("Paste the value after 'Bearer ' (see the steps below)."))
            submitted = st.form_submit_button(t("Connect"), width="stretch", type="primary")
        if submitted:
            with st.spinner(t("Checking with DartCounter...")):
                ok, msg, ident = dartcounter_api.validate_token(token_in)
            if ok:
                try:
                    dartcounter_api.save_connected_token(token_in)
                    dartcounter_api.save_connected_player(*ident)
                    st.cache_data.clear()
                    st.session_state["sync_now"] = True  # import their history right away
                    st.success(t(msg))
                    st.rerun()
                except Exception as e:
                    st.error(f"{t('Error')}: {e}")
            else:
                st.error(t(msg))

        if source == "connected":
            if st.button(t("Disconnect"), width="stretch"):
                dartcounter_api.disconnect_token()
                st.cache_data.clear()
                st.rerun()

        with st.popover(t("How to get the token"), icon=":material/help:", width="stretch"):
            show_token_steps()


def show_token_steps():
    st.markdown(t("**1.** Log in to DartCounter in your browser: `https://app.dartcounter.net`"))
    st.markdown(t("**2.** Open any match page (Statistics → a match)"))
    st.markdown(t("**3.** Open Developer Tools with `F12` (Mac: `Cmd+Option+I`)"))
    st.markdown(t("**4.** Click the **Network** tab and select the **Fetch/XHR** filter"))
    st.markdown(t("**5.** Refresh the page"))
    st.markdown(t("**6.** Click a request to `api.dartcounter.net` → **Headers**"))
    st.markdown(t("**7.** Copy the `Authorization` value after `Bearer ` and paste it above"))
    st.caption(t("Your DartCounter password is never needed. The token is stored encrypted."))


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


def run_sync():
    """Import the connected player's DartCounter history, with live progress."""
    import dartcounter_api
    import sync
    with st.status(t("Syncing with DartCounter..."), expanded=True) as status:
        try:
            stats = sync.sync_all(dartcounter_api.load_token(), log=status.write)
        except PermissionError as e:
            status.update(label=t("Token rejected"), state="error")
            st.error(t(str(e)))
            return
        except Exception as e:
            status.update(label=t("Sync failed"), state="error")
            st.error(f"{t('Error')}: {e}")
            return
        new = (stats["matches"] + stats["score"] + stats["atc"] + stats["singles"]
               + stats.get("doubles", 0))
        status.update(label=f"{t('Sync done')}: {new} {t('new games')}", state="complete", expanded=False)
    try:
        dartcounter_api.mark_synced()
    except Exception:
        pass
    st.success(f"{stats['matches']} {t('matches')} · {stats['score']} Score Training · "
               f"{stats['atc']} Around the Clock · {stats['singles']} Singles · "
               f"{stats.get('doubles', 0)} Doubles Training"
               + (f" · {stats['errors']} {t('errors')}" if stats["errors"] else ""))
    st.cache_data.clear()  # also refreshes the "last synced" time
    if new:
        st.rerun()


@st.cache_data(ttl=60, show_spinner=False)
def last_sync_time():
    import dartcounter_api
    return dartcounter_api.get_setting("last_sync")


def refresh_cache():
    st.cache_data.clear()


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    if st.session_state.get("role") == "visitor":
        with st.expander(t("Admin login"), icon=":material/lock:", expanded=False):
            authenticator.login(
                location="main",  # "main" draws the form where it's called, i.e. inside this expander
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
                st.error(t("Invalid username or password"))
    else:
        st.success(f"{t('Signed in as')} {st.session_state.get('name', '')}", icon=":material/person:")
        if st.button(t("Log out"), icon=":material/logout:", width="stretch"):
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

    token_ok, token_source, token_updated = check_token()
    if st.session_state.get("role") == "admin":
        connect_dartcounter_panel(token_ok, token_source, token_updated)
        st.divider()
    elif token_ok:
        st.success(t("DartCounter connected"), icon=":material/check_circle:")
    else:
        st.info(t("DartCounter is not connected yet. An admin can connect it from the sidebar."))

    if st.session_state.get("role") == "admin":
        st.header(t("Actions"))

        if token_ok:
            st.caption(t("Imports every match and practice session from DartCounter. "
                         "Already-stored games are skipped, so syncing again is quick."))
            if st.button(t("Sync DartCounter data"), icon=":material/sync:", width="stretch", type="primary") \
                    or st.session_state.pop("sync_now", False):
                run_sync()
            st.divider()

        st.subheader(t("Add a match by URL"))
        url_input = st.text_input(
            t("DartCounter match URL:"),
            placeholder="https://app.dartcounter.net/statistics/match/games/...",
            key="url_input"
        )
        if st.button(t("Add match"), icon=":material/add:", width="stretch"):
            if not token_ok:
                st.error(t("A token is required first."))
            elif url_input.strip():
                with st.spinner(t("Downloading...")):
                    try:
                        import dartcounter_api
                        data = dartcounter_api.fetch_match(
                            dartcounter_api.parse_match_id(url_input.strip()), dartcounter_api.load_token())
                        dartcounter_api.setup_database()
                        conn = None if dartcounter_api._turso_available() else dartcounter_api.get_db_connection()
                        try:
                            added = dartcounter_api.save_match(conn, data)
                        finally:
                            if conn is not None:
                                conn.close()
                        if added:
                            st.success(t("Match added!"))
                            refresh_cache()
                            st.rerun()
                        else:
                            st.info(t("This match is already stored (or has fewer than two players)."))
                    except Exception as e:
                        st.error(f"{t('Error')}: {e}")
            else:
                st.warning(t("URL is empty."))

        st.divider()

    st.caption(f"{t('Player')}: **{PLAYER}**")
    _synced = last_sync_time()
    st.caption(f"{t('Last synced')}: " + (_synced or t("not from the app yet")))
    import dartcounter_api as _dc
    st.caption(f"{t('Database')}: " + ("Turso" if _dc._turso_available() else f"`{DB_PATH}`"))
# ============================================================


# Page header and the period picker sit above every tab.
ui_helpers.page_header(PLAYER, last_sync_time())
ui_helpers.period_picker()

matches, throws, legs = load_data()
if matches.empty:
    st.warning(t("No data yet. Connect your DartCounter account in the sidebar, then press Sync DartCounter data."))
    st.stop()

def is_p1(row):
    # Match on DartCounter user id when known (survives name changes), else on name.
    if PLAYER_ID is not None and pd.notna(row.get('p1_user_id')):
        return int(row['p1_user_id']) == PLAYER_ID
    return row['player1_name'] == PLAYER


if PLAYER_ID is not None and {'p1_user_id', 'p2_user_id'}.issubset(matches.columns):
    efe_matches = matches[(matches['p1_user_id'] == PLAYER_ID) | (matches['p2_user_id'] == PLAYER_ID)].copy()
else:
    efe_matches = matches[
        (matches['player1_name'] == PLAYER) | (matches['player2_name'] == PLAYER)
    ].copy()


def get_efe_result(row):
    return row['p1_result'] if is_p1(row) else row['p2_result']


def get_opponent(row):
    return clean_name(row['player2_name'] if is_p1(row) else row['player1_name'])


def get_opponent_avg(row):
    return row['p2_avg_3dart'] if is_p1(row) else row['p1_avg_3dart']


efe_matches['result'] = efe_matches.apply(get_efe_result, axis=1)
efe_matches['opponent'] = efe_matches.apply(get_opponent, axis=1)
efe_matches['opp_avg'] = efe_matches.apply(get_opponent_avg, axis=1)

if PLAYER_ID is not None and 'player_user_id' in throws.columns:
    efe_throws = throws[throws['player_user_id'] == PLAYER_ID].copy()
else:
    efe_throws = throws[throws['player_name'] == PLAYER].copy()

efe_matches = efe_matches.merge(
    per_match_stats(mark_double_attempts(efe_throws) if not efe_throws.empty else efe_throws.assign(is_dbl=False)),
    on='match_id', how='left')
efe_matches['avg'] = efe_matches['calculated_avg'].fillna(0).round(2)
efe_matches['adjusted_avg'] = efe_matches['adjusted_avg'].fillna(0).round(2)
efe_matches['opp_avg'] = efe_matches['opp_avg'].fillna(0).round(2)
efe_complete_all = efe_matches[efe_matches['result'].notna()].copy()

# Everything below the Home tab follows the period picker.
efe_complete = ui_helpers.in_period(efe_complete_all, date_col='date').copy()
period_throws = efe_throws[efe_throws['match_id'].isin(ui_helpers.in_period(efe_matches, date_col='date')['match_id'])]
efe_marked = mark_double_attempts(period_throws) if not period_throws.empty else period_throws

wins = int((efe_complete['result'] == 'won').sum())
losses = int((efe_complete['result'] == 'lost').sum())
total_matches = len(efe_complete)
win_rate = (wins / total_matches * 100) if total_matches > 0 else 0

# Headline numbers use the same finished matches as the match and win counts.
complete_throws = period_throws[period_throws['match_id'].isin(efe_complete['match_id'])]
adj_avg_all, adj_darts_all, total_dbl, total_failed, overall_avg = adjusted_stats(complete_throws)
ds = darts_stats(complete_throws)

RESULT_TXT = {'won': t('Won'), 'lost': t('Lost')}
C = ui_helpers.colors()


def match_table(df, extra=None, key=None):
    """Matches as a table: readable sortable dates, plain column names, newest first."""
    cols = {'date': t('Date'), 'opponent': t('Opponent'), 'result': t('Result'),
            'avg': t('Average'), 'adjusted_avg': t('Adjusted'), 'opp_avg': t('Opponent avg')}
    cols.update(extra or {})
    d = df[list(cols)].copy()
    d['date'] = pd.to_datetime(d['date'], errors='coerce')
    d['result'] = d['result'].map(RESULT_TXT)
    d = d.rename(columns=cols)
    config = {t('Date'): ui_helpers.date_column(t('Date'))}
    for c in (t('Average'), t('Adjusted'), t('Opponent avg')):
        config[c] = st.column_config.NumberColumn(c, format="%.2f")
    st.dataframe(d, width="stretch", hide_index=True, column_config=config, key=key)


def no_matches_note():
    st.info(t("No matches in this period") + f" ({ui_helpers.period_label().lower()}). "
            + t("Pick a longer period at the top."))


# ============================================================
# MAIN TABS
# ============================================================
tab_home, tab_matches, tab_doubles, tab_practice, tab_coach = st.tabs([
    t(":material/home: Home"), t(":material/leaderboard: Matches"), t(":material/target: Doubles"),
    t(":material/fitness_center: Practice"), t(":material/psychology: Coaching")])

with tab_home:
    home_tab.render(efe_complete_all, PLAYER, PLAYER_ID, period_throws, last_sync_time(),
                    all_matches=efe_matches)

with tab_matches:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("Matches"), total_matches)
    c2.metric(t("Win %"), ui_helpers.pct(win_rate), help=f"{wins} {t('won')} · {losses} {t('lost')}")
    c3.metric(t("Average"), f"{overall_avg:.2f}", help=t("Raw 3-dart average: total score ÷ darts × 3."))
    c4.metric(t("Adjusted"), f"{adj_avg_all:.2f}",
              help=t("3-dart average without double-zone turns (remaining 40 or less, or 50). "
                     "It shows your scoring power.") + f" {adj_avg_all - overall_avg:+.2f}")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric(t("First 9 avg"), f"{ds['first9']:.2f}" if ds['first9'] is not None else "–",
              help=t("3-dart average over your first three turns of every leg."))
    d2.metric(t("Checkout %"), ui_helpers.pct(ds['checkout']) if ds['checkout'] is not None else "–",
              help=t("Legs you finished, divided by turns where you could finish: every turn once "
                     "you're on 40 or less (or 50), plus any finish from higher.")
              + f" {ds['checkouts']} / {ds['checkout_chances']}")
    d3.metric(t("Highest checkout"), ds['high_out'] or "–")
    d4.metric(t("Best leg"), f"{ds['best_leg']} {t('darts')}" if ds['best_leg'] else "–",
              help=t("Fewest darts you needed to win a 501 leg."))
    st.caption(f"{wins} {t('won')} · {losses} {t('lost')} · 180s: {ds['t180']} · 140+: {ds['t140']} · "
               f"100+: {ds['t100']} · {ui_helpers.period_label()}")

    m_over, m_prog, m_opp, m_best, m_list = st.tabs([
        t("Overview"), t("Progress"), t("Opponents"), t("Best & worst"), t("Match list")])

    with m_over:
        if efe_complete.empty:
            no_matches_note()
        else:
            st.markdown("##### " + t("Last 10 matches"))
            match_table(efe_complete.head(10), key="recent_matches")
        if not efe_marked.empty:
            dist = efe_marked.assign(
                band=ui_helpers.score_bands(efe_marked['score_thrown']),
                kind=efe_marked['is_dbl'].map({False: t('Scoring turns'), True: t('Double-zone turns')}))
            dist = (dist.groupby(['band', 'kind'], observed=False).size()
                    .reset_index(name='count'))
            fig = go.Figure()
            for kind, color in ((t('Scoring turns'), C['alt']), (t('Double-zone turns'), C['neutral'])):
                d = dist[dist['kind'] == kind]
                fig.add_trace(go.Bar(x=d['band'].astype(str), y=d['count'], name=kind,
                                     marker=dict(color=color, cornerradius=4),
                                     hovertemplate="%{x}: %{y} " + t("turns") + "<extra>" + kind + "</extra>"))
            fig.update_layout(barmode='stack', title=t("Score per turn (20-point bands)"),
                              xaxis_title=t('Score'), yaxis_title=t('Turns'))
            ui_helpers.chart(fig, key="overview_bands")
            st.caption(t("Double-zone turns (remaining ≤ 40) score low by nature, so they are shown "
                         "separately from your scoring turns."))

    with m_prog:
        efe_sorted = efe_complete.sort_values('date').copy()
        if efe_sorted.empty:
            no_matches_note()
        else:
            efe_sorted['when'] = pd.to_datetime(efe_sorted['date'], errors='coerce')
            ui_helpers.daily_trend(
                efe_sorted, 'when',
                [('adjusted_avg', t('Adjusted average'), 'you'), ('avg', t('Raw average'), 'alt')],
                t("Raw vs adjusted average per match day"),
                y_title=t('3-dart average'), unit=t("matches"), key="progress_avg", height=380, decimals=2)
            st.caption(t("Each dot is the average of that day's matches. "
                         "Adjusted leaves out double-zone turns."))

        if not efe_marked.empty:
            scoring = efe_marked[~efe_marked['is_dbl']]
            by_turn = scoring.groupby('turn')['score_thrown'].agg(['mean', 'count']).reset_index()
            by_turn = by_turn[by_turn['count'] >= 10]
            fig3 = go.Figure(go.Bar(
                x=by_turn['turn'], y=by_turn['mean'].round(1),
                marker=dict(color=C['alt'], cornerradius=4), customdata=by_turn['count'],
                hovertemplate=t("Turn") + " %{x}: %{y:.1f}<br>%{customdata} " + t("turns") + "<extra></extra>"))
            fig3.update_layout(title=t("Average score by turn number"),
                               xaxis=dict(title=t('Turn'), dtick=1), yaxis_title=t('Average score'))
            ui_helpers.chart(fig3, key="by_turn")
            st.caption(t("Only turns before the double zone, and only turn numbers with at least 10 samples."))

    with m_opp:
        if efe_complete.empty:
            no_matches_note()
        else:
            opp_stats = efe_complete.groupby('opponent').agg(
                matches=('match_id', 'count'),
                won=('result', lambda x: (x == 'won').sum()),
                lost=('result', lambda x: (x == 'lost').sum()),
                avg=('avg', 'mean'), adjusted=('adjusted_avg', 'mean'), opp_avg=('opp_avg', 'mean'),
            ).reset_index()
            opp_stats['win_pct'] = opp_stats['won'] / opp_stats['matches'] * 100
            opp_stats = opp_stats.sort_values('matches', ascending=False)
            st.dataframe(
                opp_stats.rename(columns={'opponent': t('Opponent'), 'matches': t('Matches'), 'won': t('Won'),
                                          'lost': t('Lost'), 'avg': t('Average'), 'adjusted': t('Adjusted'),
                                          'opp_avg': t('Opponent avg'), 'win_pct': t('Win %')}),
                width="stretch", hide_index=True,
                column_config={c: st.column_config.NumberColumn(c, format="%.2f")
                               for c in (t('Average'), t('Adjusted'), t('Opponent avg'))}
                | {t('Win %'): st.column_config.NumberColumn(t('Win %'), format="%.0f%%")})

            o = opp_stats.sort_values('avg')
            o['ylabel'] = o.apply(lambda r: f"{r['opponent']}  ({int(r['won'])}–{int(r['lost'])})", axis=1)
            fig = go.Figure()
            for _, r in o.iterrows():
                fig.add_trace(go.Scatter(x=[r['avg'], r['opp_avg']], y=[r['ylabel']] * 2, mode='lines',
                                         line=dict(color=C['grid'], width=6), showlegend=False, hoverinfo='skip'))
            hover = list(zip(o['matches'], o['won'], o['lost']))
            fig.add_trace(go.Scatter(x=o['opp_avg'], y=o['ylabel'], mode='markers', name=t('Opponent'),
                                     marker=dict(color=C['neutral'], size=12), customdata=hover,
                                     hovertemplate=t("Opponent") + ": %{x:.2f}<extra></extra>"))
            fig.add_trace(go.Scatter(x=o['avg'], y=o['ylabel'], mode='markers', name=PLAYER,
                                     marker=dict(color=C['you'], size=12), customdata=hover,
                                     hovertemplate=PLAYER + ": %{x:.2f}<br>%{customdata[0]} "
                                                   + t("matches") + " · %{customdata[1]}–%{customdata[2]}<extra></extra>"))
            fig.update_layout(title=t("You vs your opponents"),
                              xaxis_title=t('3-dart average'), yaxis_title="")
            ui_helpers.chart(fig, key="opp_dumbbell", height=max(300, 34 * len(o) + 120))
            st.caption(t("Each row is one opponent: your average and theirs. Wins–losses are in brackets."))

    with m_best:
        if efe_complete.empty:
            no_matches_note()
        else:
            st.markdown("##### " + t("Best 5 matches"))
            match_table(efe_complete.nlargest(5, 'avg'), key="best5")
            st.markdown("##### " + t("Worst 5 matches"))
            match_table(efe_complete.nsmallest(5, 'avg'), key="worst5")
            st.markdown("##### " + t("Best 5 by adjusted average"))
            match_table(efe_complete.nlargest(5, 'adjusted_avg'), key="best5adj")

    with m_list:
        col1, col2 = st.columns(2)
        with col1:
            result_filter = st.multiselect(t("Result"), options=['won', 'lost'], default=[],
                                           format_func=lambda x: RESULT_TXT[x], placeholder=t("Won and lost"))
        with col2:
            all_opponents = sorted(efe_complete['opponent'].dropna().unique())
            opponent_filter = st.multiselect(t("Opponent"), all_opponents, default=[],
                                             placeholder=t("All opponents (type to search)"))
        filtered = efe_complete.copy()
        if result_filter:
            filtered = filtered[filtered['result'].isin(result_filter)]
        if opponent_filter:
            filtered = filtered[filtered['opponent'].isin(opponent_filter)]
        if filtered.empty:
            st.info(t("No matches fit the filters."))
        else:
            match_table(filtered, key="all_matches")
            st.caption(f"{len(filtered)} {t('matches')}")

            st.markdown("##### " + t("Match detail"))
            labels = {
                r['match_id']: f"{pd.to_datetime(r['date']).strftime('%d %b %Y, %H:%M')} — vs {r['opponent']} "
                               f"({RESULT_TXT.get(r['result'], '?')}, {r['avg']:.1f})"
                for _, r in filtered.iterrows()}
            selected_match_id = st.selectbox(t("Match"), list(labels), format_func=labels.get)
            match_legs = legs[legs['match_id'] == selected_match_id].sort_values('leg_no')
            mthrows = throws[throws['match_id'] == selected_match_id]
            if match_legs.empty:
                st.warning(t("This match has no leg data."))
            else:
                me = PLAYER
                if PLAYER_ID is not None and 'player_user_id' in mthrows.columns:
                    mine = mthrows.loc[mthrows['player_user_id'] == PLAYER_ID, 'player_name'].unique()
                    if len(mine):
                        me = mine[0]

                # One line per leg, then a picker so only one leg is drawn at a time.
                leg_info = {}
                for _, leg_row in match_legs.iterrows():
                    lt = mthrows[(mthrows['leg_id'] == leg_row['leg_id']) & (mthrows['player_name'] == me)]
                    lt = lt.sort_values('turn')
                    won = clean_name(leg_row['winner_name']) == clean_name(me)
                    darts = int(pd.to_numeric(lt['darts_thrown'], errors='coerce').fillna(0).sum())
                    out = ""
                    if won and not lt.empty and pd.to_numeric(lt['remaining_after'], errors='coerce').iloc[-1] == 0:
                        out = f" · {t('out')} {int(lt['remaining_before'].iloc[-1])}"
                    leg_info[leg_row['leg_id']] = (f"{t('Leg')} {leg_row['leg_no']} · "
                                                   f"{t('Won') if won else t('Lost')} · {darts} {t('darts')}{out}")
                leg_id = st.radio(t("Leg"), list(leg_info), format_func=leg_info.get, horizontal=True,
                                  key=f"leg_pick_{selected_match_id}")

                leg_throws = mthrows[mthrows['leg_id'] == leg_id].sort_values(['player_name', 'turn'])
                players_in_leg = [me] + [p for p in leg_throws['player_name'].unique() if p != me][:2]

                # Leg replay: remaining score after each turn, both players.
                replay = go.Figure()
                for player in players_in_leg:
                    pt = leg_throws[leg_throws['player_name'] == player].sort_values('turn')
                    if pt.empty:
                        continue
                    is_me = player == me
                    replay.add_trace(go.Scatter(
                        x=[0] + pt['turn'].tolist(), y=[pt['remaining_before'].iloc[0]] + pt['remaining_after'].tolist(),
                        mode='lines+markers', name=clean_name(player),
                        line=dict(color=C['you'] if is_me else C['neutral'], width=2.5 if is_me else 2, shape='hv'),
                        marker=dict(size=8), customdata=[0] + pt['score_thrown'].tolist(),
                        hovertemplate="%{fullData.name} · " + t("Turn") + " %{x}<br>" + t("Throw")
                                      + ": %{customdata}<br>" + t("Remaining") + ": %{y}<extra></extra>"))
                replay.add_hrect(y0=0, y1=40, fillcolor=C['grid'], line_width=0,
                                 annotation_text=t("double zone"), annotation_position="top left",
                                 annotation_font_color=C['muted'])
                replay.update_layout(title=t("Remaining score after each turn"),
                                     xaxis=dict(title=t('Turn'), dtick=1),
                                     yaxis=dict(title=t('Remaining'), rangemode='tozero'))
                ui_helpers.chart(replay, key=f"replay_{leg_id}", height=300)

                cols = st.columns(max(1, len(players_in_leg)))
                for col, player in zip(cols, players_in_leg):
                    p_throws = leg_throws[leg_throws['player_name'] == player]
                    if p_throws.empty:
                        continue
                    with col:
                        st.write(f"**{clean_name(player)}** — {len(p_throws)} {t('turns')}")
                        p_marked = mark_double_attempts(p_throws)
                        p_marked['zone'] = p_marked['is_dbl'].map({True: 'Yes', False: ''})
                        p_display = p_marked[['turn', 'remaining_before', 'score_thrown', 'remaining_after', 'zone']]
                        p_display.columns = [t('Turn'), t('Start'), t('Throw'), t('Remaining'), t('Double zone')]
                        st.dataframe(p_display, width="stretch", hide_index=True)

with tab_doubles:
    if total_dbl:
        col1, col2, col3 = st.columns(3)
        col1.metric(t("Double-zone turns"), int(total_dbl),
                    help=t("Turns from the moment the remaining score first reaches 40 or less (or 50)."))
        col2.metric(t("Turns without a checkout"), int(total_failed))
        col3.metric(t("Checkout %"), ui_helpers.pct(ds['checkout']) if ds['checkout'] is not None else "–",
                    help=t("Same as on the Matches tab: legs you finished ÷ turns where you could finish "
                           "(double-zone turns plus any finish from higher).")
                         + f" {ds['checkouts']} / {ds['checkout_chances']}. "
                         + t("The ring below counts single darts, so its hit rate is lower."))

    doubles_section.render(period_throws, PLAYER, t, player_id=PLAYER_ID)

    if not efe_complete.empty:
        st.divider()
        st.markdown("##### " + t("Doubles in each match"))
        dbl = efe_complete.copy()
        dbl['cost'] = (dbl['adjusted_avg'] - dbl['avg']).round(2)
        match_table(dbl, extra={'num_double_attempts': t('Double-zone turns'),
                                'num_failed_doubles': t('Without checkout'),
                                'cost': t('Average lost to doubles')}, key="dbl_matches")

        comp_df = efe_complete.copy()
        comp_df['when'] = pd.to_datetime(comp_df['date'], errors='coerce')
        comp_df['diff'] = comp_df['adjusted_avg'] - comp_df['avg']
        ui_helpers.daily_trend(comp_df, 'when', [('diff', t('Average lost to doubles'), 'you')],
                               t("Average lost to doubles per day"), y_title=t('Points of average'),
                               unit=t("matches"), key="dbl_cost", decimals=2)
        st.caption(t("Adjusted minus raw average: how much the double zone pulls your average down. "
                     "Each dot is the mean of that day's matches."))

with tab_practice:
    practice_tab.render(PLAYER, DB_PATH, t, player_id=PLAYER_ID)

with tab_coach:
    coaching_page.render_coaching_page(PLAYER, t, player_id=PLAYER_ID, matches=efe_complete,
                                       all_matches=efe_matches, throws=period_throws)
