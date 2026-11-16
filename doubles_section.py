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
import pandas as pd
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
    s = only_player(sessions, player_id, player)
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
    s = only_player(sessions, player_id, player)
    t = targets[targets["doubles_user_id"].isin(s["doubles_user_id"])].copy()
    if t.empty:
        return pd.DataFrame(columns=["target", "hits", "attempts"])
    t["hits"] = pd.to_numeric(t["hits"], errors="coerce").fillna(0)
    t["attempts"] = pd.to_numeric(t["darts_thrown"], errors="coerce").fillna(0)
    return t.groupby("target")[["hits", "attempts"]].sum().reset_index()


def _confidence(darts):
    if darts >= 500:
        return "High"
    if darts >= 150:
        return "Medium"
    return "Low"


def render(efe_throws, player, t, player_id=None):
    st.subheader(t("🎯 Double Ring Heatmap & Sector Reliability"))

    sources = {
        "Combined": t("Combined (all sources)"),
        "Training": t("Doubles Training"),
        "ATC": t("Around the Clock — Doubles mode"),
        "Match": t("Match checkouts (estimated)"),
    }
    choice = st.radio(t("Source"), list(sources), format_func=sources.get,
                      horizontal=True, key="double_source")

    match_df = _match_doubles(efe_throws)
    atc_df = _atc_doubles(player, player_id)
    training_df = _training_doubles(player, player_id)
    if choice == "Training":
        stats = training_df
    elif choice == "ATC":
        stats = atc_df
    elif choice == "Match":
        stats = match_df
    else:
        stats = (pd.concat([match_df, atc_df, training_df]).groupby("target")[["hits", "attempts"]]
                 .sum().reset_index())

    if stats.empty or stats["attempts"].sum() == 0:
        st.info(t("No double attempts recorded for this source yet."))
        return

    stats = stats.astype({"hits": float, "attempts": float})  # empty sources can leave object dtype
    stats = stats[stats["attempts"] > 0].copy()
    stats["target"] = stats["target"].astype(int)
    stats["value"] = stats["hits"] / stats["attempts"]
    hits, darts = int(stats["hits"].sum()), int(stats["attempts"].sum())
    rated = stats[stats["attempts"] >= MIN_N]

    def name(tg):
        return "DBull" if tg == 25 else f"D{tg}"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("Overall double hit rate"), ui_helpers.pct(hits / darts * 100),
              help=t("Hits divided by darts thrown at doubles.") + f" {hits} / {darts}")
    if not rated.empty:
        best = rated.loc[rated["value"].idxmax()]
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
