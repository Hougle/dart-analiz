"""
Double ring heatmap & sector reliability.

Combines three sources of double attempts into per-dart hit rates per double:
  - Doubles Training sessions: exact per-dart data. Each target is thrown at
    until it is hit; a hit is a dart in the double of the target number.
  - Around the Clock sessions played in Doubles mode: each target is hit once
    after `darts_needed` darts  ->  1 hit / darts_needed darts.
  - Match checkouts: a visit that starts on an even score <= 40 (or 50) is aimed
    at D(score/2) (or the bull). Darts in that visit count as attempts and a
    checkout counts as a hit. This is an estimate: a dart that lands in the
    single and leaves a new double is still counted against the first double.
"""
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import ui_helpers
from practice_tab import load_all_practice_data, read_table
from dartcounter_api import only_player

MIN_N = 5


def _match_doubles(efe_throws):
    if efe_throws.empty:
        return pd.DataFrame(columns=["target", "hits", "attempts"])
    df = efe_throws.copy()
    rb = pd.to_numeric(df["remaining_before"], errors="coerce")
    on_double = ((rb > 0) & (rb <= 40) & (rb % 2 == 0)) | (rb == 50)
    df = df[on_double].copy()
    df["target"] = (rb[on_double] / 2).astype(int).replace({25: 25})
    df["hits"] = (pd.to_numeric(df["remaining_after"], errors="coerce") == 0).astype(int)
    df["attempts"] = pd.to_numeric(df["darts_thrown"], errors="coerce").fillna(3).astype(int)
    return df.groupby("target")[["hits", "attempts"]].sum().reset_index()


def _atc_doubles(player, player_id=None):
    _, _, sessions, targets = load_all_practice_data()
    needed = {"atc_user_id", "target", "darts_needed"}
    if sessions.empty or targets.empty or not needed.issubset(targets.columns):
        return pd.DataFrame(columns=["target", "hits", "attempts"])
    s = ui_helpers.in_period(only_player(sessions, player_id, player))
    if "is_cpu" in s.columns:
        s = s[s["is_cpu"].fillna(0).astype(int) == 0]
    if "number_segment" in s.columns:
        s = s[s["number_segment"].astype(str).str.lower() == "double"]
    t = targets[targets["atc_user_id"].isin(s["atc_user_id"])].copy()
    if t.empty:
        return pd.DataFrame(columns=["target", "hits", "attempts"])
    t["hits"] = 1
    t["attempts"] = pd.to_numeric(t["darts_needed"], errors="coerce").fillna(0).astype(int)
    return t.groupby("target")[["hits", "attempts"]].sum().reset_index()


@st.cache_data(ttl=60)
def _load_doubles_training():
    return (read_table("SELECT * FROM doubles_sessions"),
            read_table("SELECT * FROM doubles_targets"))


def _training_doubles(player, player_id=None):
    sessions, targets = _load_doubles_training()
    needed = {"doubles_user_id", "target", "darts_thrown", "hits"}
    if sessions.empty or targets.empty or not needed.issubset(targets.columns):
        return pd.DataFrame(columns=["target", "hits", "attempts"])
    s = ui_helpers.in_period(only_player(sessions, player_id, player))
    t = targets[targets["doubles_user_id"].isin(s["doubles_user_id"])].copy()
    if t.empty:
        return pd.DataFrame(columns=["target", "hits", "attempts"])
    t["hits"] = pd.to_numeric(t["hits"], errors="coerce").fillna(0)
    t["attempts"] = pd.to_numeric(t["darts_thrown"], errors="coerce").fillna(0)
    return t.groupby("target")[["hits", "attempts"]].sum().reset_index()


def _wilson_low(hits, n, z=1.96):
    """Lower end of the 95% Wilson interval: a hit rate you can count on, not a lucky streak."""
    p = hits / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / (1 + z * z / n))


def double_name(tg):
    tg = int(tg)  # a row taken with .loc comes back as float
    return "DBull" if tg == 25 else f"D{tg}"


def double_stats(efe_throws, player, player_id=None, choice="Combined"):
    """Hits / darts / hit rate per double for one source (or all combined), in the selected period."""
    sources = {"Match": lambda: _match_doubles(efe_throws),
               "ATC": lambda: _atc_doubles(player, player_id),
               "Training": lambda: _training_doubles(player, player_id)}
    parts = [sources[choice]()] if choice in sources else [f() for f in sources.values()]
    stats = pd.concat(parts).groupby("target")[["hits", "attempts"]].sum().reset_index()
    if stats.empty:
        return pd.DataFrame(columns=["target", "hits", "attempts", "value"])
    stats = stats.astype({"hits": float, "attempts": float})  # empty sources can leave object dtype
    stats = stats[stats["attempts"] > 0].copy()
    stats["target"] = stats["target"].astype(int)
    stats["value"] = stats["hits"] / stats["attempts"]
    return stats


def ranked(stats, min_darts=20):
    """Doubles with at least min_darts, best first by confidence-adjusted hit rate."""
    r = stats[stats["attempts"] >= min_darts].copy()
    if r.empty:
        return r
    r["reliable"] = [_wilson_low(h, n) for h, n in zip(r["hits"], r["attempts"])]
    r = r.sort_values(["reliable", "value"], ascending=False).reset_index(drop=True)
    r["name"] = r["target"].apply(double_name)
    r["per_hit"] = r.apply(lambda x: x["attempts"] / x["hits"] if x["hits"] else None, axis=1)
    return r


def _reliable_doubles(stats, t):
    st.subheader(t("Most reliable doubles"))
    min_darts = st.slider(t("Minimum darts at a double to rank it"), 5, 100, 20, step=5,
                          key="reliable_min_darts",
                          help=t("Doubles with fewer darts are left out; a couple of lucky hits "
                                 "shouldn't put a double on top."))
    r = ranked(stats, min_darts)
    if r.empty:
        st.info(t("No double has that many darts yet. Lower the minimum or practise more doubles."))
        return

    top = r.head(3)
    cols = st.columns(len(top))
    for medal, (_, row), col in zip(("1st", "2nd", "3rd"), top.iterrows(), cols):
        col.metric(f"{medal} · {row['name']}", ui_helpers.pct(row["value"] * 100),
                   help=f"{int(row['hits'])} / {int(row['attempts'])} " + t("darts") + " · "
                        + (f"1 {t('in')} {row['per_hit']:.1f} {t('darts')}" if row["per_hit"] else t("no hits yet")))

    C = ui_helpers.colors()
    shown = r.iloc[::-1]  # best at the top of a horizontal bar chart
    fig = go.Figure(go.Bar(
        x=shown["value"], y=shown["name"], orientation="h",
        marker=dict(color=[C["you"] if i < 3 else C["alt"] for i in shown.index], cornerradius=4),
        text=[f"{ui_helpers.pct(v * 100)}  ·  " + (f"1 in {p:.1f}" if p else "–")
              for v, p in zip(shown["value"], shown["per_hit"])],
        textposition="outside", textfont=dict(color=C["text"], size=11), cliponaxis=False,
        customdata=list(zip(shown["hits"].astype(int), shown["attempts"].astype(int),
                            (shown["reliable"] * 100).round(1))),
        hovertemplate="<b>%{y}</b><br>" + t("Hit rate") + ": %{x:.1%}<br>%{customdata[0]} / "
                      "%{customdata[1]} " + t("darts") + "<br>" + t("Confidence-adjusted")
                      + ": %{customdata[2]}%<extra></extra>"))
    fig.update_layout(title=t("Doubles ranked by reliability (best at the top)"), showlegend=False,
                      xaxis=dict(title=t("Hit rate"), tickformat=".0%",
                                 range=[0, max(r["value"].max() * 1.35, 0.05)]),
                      yaxis=dict(title="", type="category"))
    ui_helpers.chart(fig, key="reliable_doubles", height=max(260, 30 * len(r) + 110),
                     margin=dict(t=56, b=40, l=64, r=20))
    st.caption(t("Ranked by a confidence-adjusted hit rate (the low end of a 95% range), so a double "
                 "you hit often over many darts beats one lucky streak. Orange = your top 3."))

    with st.expander(t("Full table")):
        table = pd.DataFrame({
            t("Rank"): range(1, len(r) + 1),
            t("Double"): r["name"],
            t("Hit rate"): r["value"] * 100,
            t("1 hit every … darts"): r["per_hit"].round(1),
            t("Hits"): r["hits"].astype(int),
            t("Darts"): r["attempts"].astype(int),
        })
        st.dataframe(table, hide_index=True, width="stretch",
                     column_config={t("Hit rate"): st.column_config.ProgressColumn(
                         t("Hit rate"), format="%.1f%%", min_value=0,
                         max_value=float(max(table[t("Hit rate")].max(), 1)))})


def _confidence(darts):
    if darts >= 500:
        return "High"
    if darts >= 150:
        return "Medium"
    return "Low"


def render(efe_throws, player, t, player_id=None):
    st.subheader(t("Double ring & reliability"))

    sources = {
        "Combined": t("All sources"),
        "Training": t("Doubles Training"),
        "ATC": t("Around the Clock (Doubles)"),
        "Match": t("Match checkouts (estimated)"),
    }
    choice = st.segmented_control(t("Source"), list(sources), format_func=sources.get,
                                  default="Combined", key="double_source") or "Combined"
    stats = double_stats(efe_throws, player, player_id, choice)
    if stats.empty or stats["attempts"].sum() == 0:
        st.info(t("No double attempts recorded for this source in this period."))
        return

    hits, darts = int(stats["hits"].sum()), int(stats["attempts"].sum())
    rated = stats[stats["attempts"] >= MIN_N]

    name = double_name

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("Overall double hit rate"), ui_helpers.pct(hits / darts * 100),
              help=t("Hits divided by darts thrown at doubles.") + f" {hits} / {darts}")
    if not rated.empty:
        # Same confidence-adjusted measure as the ranking below, so the two agree.
        reliable = [_wilson_low(h, n) for h, n in zip(rated["hits"], rated["attempts"])]
        best = rated.iloc[max(range(len(reliable)), key=reliable.__getitem__)]
        worst = rated.loc[rated["value"].idxmin()]
        c2.metric(t("Most reliable double"), name(best["target"]),
                  help=f"{ui_helpers.pct(best['value'] * 100)} · {int(best['hits'])}/{int(best['attempts'])}")
        c3.metric(t("Hardest double"), name(worst["target"]),
                  help=f"{ui_helpers.pct(worst['value'] * 100)} · {int(worst['hits'])}/{int(worst['attempts'])}")
    else:
        c2.metric(t("Most reliable double"), "–")
        c3.metric(t("Hardest double"), "–")
    c4.metric(t("Data confidence"), t(_confidence(darts)),
              help=t("High: 500+ darts, Medium: 150+, Low: fewer. "
                     "Doubles with fewer than 5 attempts are not rated."))
    st.caption(f"{hits} {t('hits')} / {darts} {t('darts')} · "
               f"{len(rated)} / 21 {t('doubles rated')}")

    left, right = st.columns(2)
    with left:
        ui_helpers.dartboard_ring(stats, t("Double ring"), prefix="D",
                                  value_label=t("Hit rate"), key="double_ring", min_n=MIN_N)
    with right:
        ui_helpers.segment_bars(stats, t("Hit rate per double"), prefix="D",
                                value_label=t("Hit rate"), key="double_bars", min_n=MIN_N)
    if choice in ("Combined", "Match"):
        st.caption(t("Match checkouts are estimated per visit: every dart in a visit that starts on a "
                     "finishable double counts as an attempt at that double."))

    st.divider()
    _reliable_doubles(stats, t)
