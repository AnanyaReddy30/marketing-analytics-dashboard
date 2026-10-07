"""
sql_analysis.py
1. Cleans the CSV with pandas and loads it into a SQLite database.
2. Holds the SQL analysis queries (QUERIES) used by the dashboard and README.

The data is SIMULATED (see generate_data.py). Nothing here is a real ad account.

Run:  python sql_analysis.py     -> rebuilds data/marketing.db and prints every query result
"""
import sqlite3
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
CSV_FILE = DATA_DIR / "campaigns.csv"
DB_FILE = DATA_DIR / "marketing.db"


def load_and_clean() -> pd.DataFrame:
    """Read the CSV and apply the checks I would run on a real platform export."""
    df = pd.read_csv(CSV_FILE, parse_dates=["date"])
    df = df.drop_duplicates(subset=["date", "campaign"])
    df = df.dropna()

    numeric = ["impressions", "clicks", "spend", "conversions", "revenue"]
    df = df[(df[numeric] >= 0).all(axis=1)]           # no negative values
    df = df[df["clicks"] <= df["impressions"]]        # can't have more clicks than views

    # Monday of each row's week, so SQL can simply GROUP BY week_start
    df["week_start"] = (df["date"] - pd.to_timedelta(df["date"].dt.dayofweek, unit="D")).dt.date.astype(str)
    df["date"] = df["date"].dt.date.astype(str)       # SQLite stores dates as text
    return df


def build_database() -> None:
    df = load_and_clean()
    with sqlite3.connect(DB_FILE) as conn:
        df.to_sql("campaigns", conn, if_exists="replace", index=False)


def run_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    if not DB_FILE.exists():
        build_database()
    with sqlite3.connect(DB_FILE) as conn:
        return pd.read_sql_query(sql, conn, params=params)


# NULLIF(x, 0) turns a zero into NULL so a division by zero returns NULL instead of an error.
# "* 1.0" forces decimal division (SQLite does integer division on two integers).
QUERIES = {
    "1. ROAS and CPA by campaign": """
        SELECT campaign,
               channel,
               ROUND(SUM(spend))                                  AS spend,
               ROUND(SUM(revenue))                                AS revenue,
               ROUND(SUM(revenue) / NULLIF(SUM(spend), 0), 2)     AS roas,
               ROUND(SUM(spend) / NULLIF(SUM(conversions), 0))    AS cpa
        FROM campaigns
        GROUP BY campaign, channel
        ORDER BY roas DESC;
    """,
    "2. Weekly trend": """
        SELECT week_start,
               ROUND(SUM(spend))                              AS spend,
               ROUND(SUM(revenue))                            AS revenue,
               SUM(conversions)                               AS conversions,
               ROUND(SUM(revenue) / NULLIF(SUM(spend), 0), 2) AS roas
        FROM campaigns
        GROUP BY week_start
        ORDER BY week_start;
    """,
    "3. Channel share of spend": """
        SELECT channel,
               ROUND(SUM(spend))                                                  AS spend,
               ROUND(100.0 * SUM(spend) / (SELECT SUM(spend) FROM campaigns), 1)  AS spend_share_pct,
               ROUND(100.0 * SUM(revenue) / (SELECT SUM(revenue) FROM campaigns), 1) AS revenue_share_pct
        FROM campaigns
        GROUP BY channel
        ORDER BY spend DESC;
    """,
    "4. Week-over-week change": """
        WITH weekly AS (
            SELECT week_start,
                   SUM(spend)   AS spend,
                   SUM(revenue) AS revenue
            FROM campaigns
            GROUP BY week_start
        )
        SELECT week_start,
               ROUND(spend)   AS spend,
               ROUND(revenue) AS revenue,
               ROUND(100.0 * (spend - LAG(spend) OVER (ORDER BY week_start))
                     / LAG(spend) OVER (ORDER BY week_start), 1)     AS spend_wow_pct,
               ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY week_start))
                     / LAG(revenue) OVER (ORDER BY week_start), 1)   AS revenue_wow_pct
        FROM weekly
        ORDER BY week_start;
    """,
    "5. Worst campaigns by cost per conversion": """
        SELECT campaign,
               SUM(conversions)                                 AS conversions,
               ROUND(SUM(spend) / NULLIF(SUM(conversions), 0))  AS cpa,
               ROUND(SUM(revenue) / NULLIF(SUM(conversions), 0)) AS revenue_per_conversion,
               ROUND(SUM(spend) / NULLIF(SUM(clicks), 0), 2)    AS cpc
        FROM campaigns
        GROUP BY campaign
        ORDER BY cpa DESC
        LIMIT 3;
    """,
    "6. Funnel rates by channel": """
        SELECT channel,
               SUM(impressions)                                               AS impressions,
               SUM(clicks)                                                    AS clicks,
               SUM(conversions)                                               AS conversions,
               ROUND(100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0), 2)    AS ctr_pct,
               ROUND(100.0 * SUM(conversions) / NULLIF(SUM(clicks), 0), 2)    AS conversion_rate_pct
        FROM campaigns
        GROUP BY channel
        ORDER BY conversion_rate_pct DESC;
    """,
    "7. Weekday vs weekend by channel": """
        SELECT channel,
               CASE WHEN strftime('%w', date) IN ('0', '6') THEN 'Weekend' ELSE 'Weekday' END AS day_type,
               ROUND(SUM(spend) / COUNT(DISTINCT date))        AS avg_daily_spend,
               ROUND(SUM(revenue) / NULLIF(SUM(spend), 0), 2)  AS roas
        FROM campaigns
        GROUP BY channel, day_type
        ORDER BY channel, day_type;
    """,
}


if __name__ == "__main__":
    build_database()
    print(f"Loaded cleaned data into {DB_FILE} (simulated data)\n")
    for title, sql in QUERIES.items():
        print(f"--- {title} ---")
        print(run_query(sql).to_string(index=False), "\n")
