"""Pure match calculations (no Streamlit), so they can be tested on their own.

All functions take a throws table: one row per turn with leg_id, turn,
remaining_before, score_thrown, remaining_after and darts_thrown.
"""
import pandas as pd


def is_double_attempt(remaining_before):
    if remaining_before is None:
        return False
    try:
        rb = int(remaining_before)
    except (ValueError, TypeError):
        return False
    if 0 < rb <= 40 and rb % 2 == 0:
        return True
    return rb == 50


def mark_double_attempts(throws_df):
    """Add is_dbl: True from the turn a leg first reaches ≤ 40 (or exactly 50) to the end of the leg."""
    if throws_df.empty or "leg_id" not in throws_df.columns:
        df = throws_df.copy()
        df["is_dbl"] = df["remaining_before"].apply(is_double_attempt)
        return df

    df = throws_df.sort_values(["leg_id", "turn"]).reset_index(drop=True).copy()
    rb = pd.to_numeric(df["remaining_before"], errors="coerce")
    trigger = ((rb > 0) & (rb <= 40)) | (rb == 50)
    df["is_dbl"] = trigger.groupby(df["leg_id"]).cumsum() > 0
    return df


def adjusted_stats(throws_df):
    """(adjusted avg, scoring darts, double-zone turns, failed double-zone turns, raw avg)."""
    if throws_df.empty:
        return 0, 0, 0, 0, 0

    total_score = throws_df["score_thrown"].sum()
    total_darts = throws_df["darts_thrown"].sum()
    normal_avg = (total_score / total_darts * 3) if total_darts > 0 else 0

    tdf = mark_double_attempts(throws_df)
    num_dbl = int(tdf["is_dbl"].sum())
    # A double attempt only succeeds when it checks out (remaining hits 0);
    # setup shots like 32 -> 16 are not successes.
    checked_out = pd.to_numeric(tdf["remaining_after"], errors="coerce") == 0
    num_failed = int((tdf["is_dbl"] & ~checked_out).sum())

    filtered = tdf[~tdf["is_dbl"]]
    if filtered.empty or filtered["darts_thrown"].sum() == 0:
        return normal_avg, 0, num_dbl, num_failed, normal_avg

    adj_avg = (filtered["score_thrown"].sum() / filtered["darts_thrown"].sum()) * 3
    return adj_avg, int(filtered["darts_thrown"].sum()), num_dbl, num_failed, normal_avg


def per_match_stats(marked):
    """Raw/adjusted average and double counts for every match in one pass."""
    cols = ["match_id", "calculated_avg", "adjusted_avg", "num_double_attempts", "num_failed_doubles"]
    if marked.empty:
        return pd.DataFrame(columns=cols)
    df = marked.assign(
        score=pd.to_numeric(marked["score_thrown"], errors="coerce").fillna(0),
        darts=pd.to_numeric(marked["darts_thrown"], errors="coerce").fillna(0),
        checked_out=pd.to_numeric(marked["remaining_after"], errors="coerce") == 0)
    df["scoring"] = ~df["is_dbl"]
    df["adj_score"] = df["score"].where(df["scoring"], 0)
    df["adj_darts"] = df["darts"].where(df["scoring"], 0)
    df["failed"] = df["is_dbl"] & ~df["checked_out"]
    g = df.groupby("match_id").agg(score=("score", "sum"), darts=("darts", "sum"),
                                   adj_score=("adj_score", "sum"), adj_darts=("adj_darts", "sum"),
                                   num_double_attempts=("is_dbl", "sum"),
                                   num_failed_doubles=("failed", "sum")).reset_index()
    g["calculated_avg"] = (g["score"] / g["darts"].where(g["darts"] > 0) * 3).fillna(0)
    # A match with no scoring turns falls back to the raw average (same as adjusted_stats).
    g["adjusted_avg"] = (g["adj_score"] / g["adj_darts"].where(g["adj_darts"] > 0) * 3) \
        .fillna(g["calculated_avg"])
    return g[cols]


def darts_stats(throws_df):
    """The standard darts numbers for one player's turns.

    first9      3-dart average over the first three turns of every leg
    checkout    checkouts ÷ turns with a chance to finish (double-zone turns plus
                any turn that finished from higher), as a percentage
    checkouts / checkout_chances   the two counts behind it
    high_out    highest finish
    best_leg    fewest darts to win a 501 leg
    t180 / t140 / t100   turns of 180, 140+ and 100+
    Values are None when there's nothing to measure.
    """
    out = dict(first9=None, checkout=None, checkouts=0, checkout_chances=0,
               high_out=None, best_leg=None, t180=0, t140=0, t100=0)
    if throws_df is None or throws_df.empty:
        return out

    df = mark_double_attempts(throws_df)
    score = pd.to_numeric(df["score_thrown"], errors="coerce").fillna(0)
    darts = pd.to_numeric(df["darts_thrown"], errors="coerce").fillna(0)
    finished = pd.to_numeric(df["remaining_after"], errors="coerce") == 0

    out["t180"] = int((score == 180).sum())
    out["t140"] = int((score >= 140).sum())
    out["t100"] = int((score >= 100).sum())

    # Turn numbers count each player's own turns, so the first three per leg are that player's first 9 darts.
    first = df.assign(score=score, darts=darts).groupby("leg_id", sort=False).head(3)
    if first["darts"].sum() > 0:
        out["first9"] = float(first["score"].sum() / first["darts"].sum() * 3)

    chances = df["is_dbl"] | finished
    out["checkouts"] = int(finished.sum())
    out["checkout_chances"] = int(chances.sum())
    if out["checkout_chances"]:
        out["checkout"] = out["checkouts"] / out["checkout_chances"] * 100
    if finished.any():
        out["high_out"] = int(score[finished].max())

    # Best leg: legs that started at 501 and that this player finished.
    start = pd.to_numeric(df.groupby("leg_id")["remaining_before"].transform("first"), errors="coerce")
    won = finished.groupby(df["leg_id"]).transform("any")
    legs = darts[(start == 501) & won].groupby(df["leg_id"]).sum()
    if not legs.empty:
        out["best_leg"] = int(legs.min())
    return out
