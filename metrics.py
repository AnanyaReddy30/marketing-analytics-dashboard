"""
metrics.py
Every marketing metric formula lives here, so there is one place to check them.
(The data these run on is simulated - see generate_data.py.)

  CTR  (click-through rate)   = clicks / impressions      -> is the ad getting clicked?
  CPC  (cost per click)       = spend / clicks            -> what does one visit cost?
  CVR  (conversion rate)      = conversions / clicks      -> do visitors buy / sign up?
  CPA  (cost per acquisition) = spend / conversions       -> what does one customer cost?
  ROAS (return on ad spend)   = revenue / spend           -> rupees back per rupee spent
"""
import numpy as np
import pandas as pd

SUM_COLS = ["impressions", "clicks", "spend", "conversions", "revenue"]

# Status thresholds on ROAS. 1x = break-even on ad spend, 3x = a common rule-of-thumb target.
BREAK_EVEN_ROAS = 1.0
TARGET_ROAS = 3.0


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add ratio columns to a table that already has the five summed columns."""
    df = df.copy()
    # Replace 0 with NaN before dividing so we never divide by zero.
    impressions = df["impressions"].replace(0, np.nan)
    clicks = df["clicks"].replace(0, np.nan)
    conversions = df["conversions"].replace(0, np.nan)
    spend = df["spend"].replace(0, np.nan)

    df["ctr"] = df["clicks"] / impressions
    df["cpc"] = df["spend"] / clicks
    df["cvr"] = df["conversions"] / clicks
    df["cpa"] = df["spend"] / conversions
    df["roas"] = df["revenue"] / spend
    return df


def summarise(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Sum the raw columns per group, THEN compute ratios.
    (Averaging daily ratios would be wrong: big days must count for more.)"""
    return add_metrics(df.groupby(by, as_index=False)[SUM_COLS].sum())


def totals(df: pd.DataFrame) -> pd.Series:
    """One row of overall KPIs for the KPI cards."""
    return add_metrics(df[SUM_COLS].sum().to_frame().T).iloc[0]


def status(roas: float) -> str:
    """Scale = above target, Fix = losing money on ad spend, Watch = in between."""
    if roas >= TARGET_ROAS:
        return "Scale"
    if roas < BREAK_EVEN_ROAS:
        return "Fix"
    return "Watch"


def campaign_table(df: pd.DataFrame) -> pd.DataFrame:
    table = summarise(df, ["channel", "campaign"])
    table["spend_share"] = table["spend"] / table["spend"].sum()
    table["status"] = table["roas"].apply(status)
    return table.sort_values("roas", ascending=False).reset_index(drop=True)
