"""Time spent playing: every match and practice session at its real length, summed per week."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import ui_helpers
from dartcounter_api import only_player

# Fixed order: also the stacking order (bottom up) and the colour order.
ACTIVITIES = ["Matches", "Score Training", "Around the Clock", "Singles", "Doubles Training"]


def sessions(matches, player, player_id=None):
    """One row per game: activity, local start time, seconds played.

    matches: the player's matches with date and duration_sec.
    Practice lengths come from duration_sec in the practice tables (player's own rows only).
    """
    from practice_tab import load_all_practice_data
    from singles_tab import _load_singles
    from doubles_section import _load_doubles_training

    score, _, atc, _ = load_all_practice_data()
    singles, _ = _load_singles()
    doubles, _ = _load_doubles_training()

    parts = []
    if matches is not None and not matches.empty and "duration_sec" in matches.columns:
        parts.append(pd.DataFrame({"activity": "Matches", "when": ui_helpers.match_time(matches["date"]),
                                   "sec": pd.to_numeric(matches["duration_sec"], errors="coerce")}))
    for name, df in (("Score Training", score), ("Around the Clock", atc),
                     ("Singles", singles), ("Doubles Training", doubles)):
        df = only_player(df, player_id, player)
        if df is None or df.empty or not {"started_at", "duration_sec"}.issubset(df.columns):
            continue
        parts.append(pd.DataFrame({"activity": name, "when": ui_helpers.local_time(df["started_at"]),
                                   "sec": pd.to_numeric(df["duration_sec"], errors="coerce")}))
    if not parts:
        return pd.DataFrame(columns=["activity", "when", "sec"])
    out = pd.concat(parts, ignore_index=True)
    return out.dropna(subset=["when", "sec"])


def weekly(df):
    """Minutes per Monday-to-Sunday week (rows) and activity (columns), weeks without play included."""
    if df.empty:
        return pd.DataFrame(columns=ACTIVITIES)
    week = df["when"].dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time
    table = (df.assign(week=week, minutes=df["sec"] / 60)
             .pivot_table(index="week", columns="activity", values="minutes", aggfunc="sum", fill_value=0))
    weeks = pd.date_range(table.index.min(), table.index.max(), freq="7D")
    return table.reindex(index=weeks, columns=ACTIVITIES, fill_value=0)


def fmt_minutes(m):
    """95 -> '1 h 35 m', 12 -> '12 m'."""
    m = int(round(m))
    return f"{m // 60} h {m % 60:02d} m" if m >= 60 else f"{m} m"


def short_minutes(m):
    """Compact bar label: 95 -> '1h35', 12 -> '12m'."""
    m = int(round(m))
    return f"{m // 60}h{m % 60:02d}" if m >= 60 else f"{m}m"


def render(matches, player, player_id=None, key="time_played"):
    """Weekly time chart for the selected period, with a table of the same numbers."""
    df = sessions(matches, player, player_id)
    start = ui_helpers.period_start()
    if start is not None:
        df = df[df["when"] >= start]
    st.markdown(f"##### Time played · {ui_helpers.period_label().lower()}")
    table = weekly(df)
    if table.empty:
        st.info(f"No games in this period ({ui_helpers.period_label().lower()}).")
        return

    total = table.to_numpy().sum()
    weeks = len(table)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", fmt_minutes(total), help="Every match and practice session at its real length.")
    c2.metric("Per week", fmt_minutes(total / weeks),
              help=f"Average over {weeks} week{'s' if weeks != 1 else ''}, weeks without play included.")
    busiest = table.sum(axis=1).idxmax()
    c3.metric("Busiest week", fmt_minutes(table.sum(axis=1).max()),
              help=f"Week starting {busiest.strftime('%d %b')}.")

    c = ui_helpers.colors()
    palette = ui_helpers.categorical()
    x = table.index + pd.Timedelta(days=3, hours=12)  # centre each bar on its week
    fig = go.Figure()
    for name, color in zip(ACTIVITIES, palette):
        vals = table[name] / 60
        if not vals.any():
            continue
        fig.add_trace(go.Bar(
            x=x, y=vals, name=name, width=5 * 86_400_000,
            marker=dict(color=color, line=dict(color=c["card"], width=1.5)),
            customdata=list(zip(table.index.strftime("%d %b"), table[name].map(fmt_minutes))),
            hovertemplate="Week of %{customdata[0]}<br><b>" + name + ": %{customdata[1]}</b><extra></extra>",
            showlegend=False))
    totals = table.sum(axis=1)
    fig.add_trace(go.Scatter(
        x=x, y=totals / 60, mode="text", showlegend=False, hoverinfo="skip",
        text=[short_minutes(v) if v else "" for v in totals], textposition="top center",
        textfont=dict(color=c["text"], size=11), cliponaxis=False))
    fig.update_layout(barmode="stack", barcornerradius=4, title="Hours per week",
                      yaxis=dict(title="Hours", ticksuffix=" h", rangemode="tozero",
                                 range=[0, max(totals.max() / 60 * 1.18, 0.5)]),
                      xaxis=dict(title="", tickformat="%d %b", hoverformat="%d %b",
                                 tickvals=x, ticktext=table.index.strftime("%d %b")),
                      hovermode="closest")
    ui_helpers.chart(fig, key=key, height=320)
    ui_helpers.html_legend([(n, col) for n, col in zip(ACTIVITIES, palette) if table[n].any()])
    st.caption("Weeks run Monday to Sunday. Time is from the start to the end of each game.")

    with st.expander("Table"):
        show = table.copy()
        show["Total"] = show.sum(axis=1)
        show = show.loc[:, (show != 0).any()].sort_index(ascending=False)
        show.index = show.index.strftime("%d %b %Y")
        st.dataframe(show.map(lambda v: fmt_minutes(v) if v else "–").rename_axis("Week starting"),
                     width="stretch")
