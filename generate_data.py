"""
generate_data.py
Creates a SIMULATED Google Ads / Meta Ads style dataset.

IMPORTANT: every number in this file is made up. It is not from a real ad
account. The "story" (which campaign is good or bad) is built in on purpose
through the settings below, so the analysis has something to find.

Run:  python generate_data.py
Output: data/campaigns.csv  (12 weeks x 7 days x 6 campaigns = 504 rows)
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42                      # fixed seed -> same data every run
START_DATE = "2026-07-06"      # a Monday, so weeks line up cleanly
DAYS = 12 * 7                  # 12 weeks
OUT_FILE = Path(__file__).parent / "data" / "campaigns.csv"

# One row of settings per campaign.
#   spend      = average daily budget in INR
#   cpc        = starting cost per click in INR
#   cpc_drift  = how much CPC grows by the last day (0.7 = +70%)
#   ctr        = click-through rate (clicks / impressions)
#   cvr        = conversion rate (conversions / clicks)
#   aov        = average revenue per conversion in INR
#   weekend    = multiplier on spend and conversion rate on Sat/Sun
CAMPAIGNS = [
    # Story 1: retargeting = small budget, strong returns.
    dict(channel="Meta Ads", campaign="Retargeting - Cart Abandoners",
         spend=2500, cpc=12, cpc_drift=0.0, ctr=0.030, cvr=0.050, aov=1600, weekend=1.20),
    dict(channel="Meta Ads", campaign="Prospecting - Lookalike",
         spend=7000, cpc=15, cpc_drift=0.05, ctr=0.012, cvr=0.022, aov=1400, weekend=1.20),
    dict(channel="Google Search", campaign="Brand Search",
         spend=4000, cpc=18, cpc_drift=0.0, ctr=0.080, cvr=0.050, aov=1500, weekend=0.90),
    dict(channel="Google Search", campaign="Generic Search",
         spend=9000, cpc=28, cpc_drift=0.10, ctr=0.035, cvr=0.032, aov=1700, weekend=0.90),
    # Story 2: biggest budget, weak returns, CPC rising week after week.
    dict(channel="YouTube", campaign="Video Awareness",
         spend=14000, cpc=20, cpc_drift=0.70, ctr=0.006, cvr=0.009, aov=1400, weekend=1.15),
    # Story 3: B2B audience is offline at weekends, so LinkedIn drops hard.
    dict(channel="LinkedIn", campaign="B2B Lead Gen",
         spend=6000, cpc=150, cpc_drift=0.05, ctr=0.005, cvr=0.040, aov=9000, weekend=0.55),
]


def generate() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    dates = pd.date_range(START_DATE, periods=DAYS, freq="D")
    rows = []

    for day_number, date in enumerate(dates):
        is_weekend = date.dayofweek >= 5          # 5 = Saturday, 6 = Sunday
        progress = day_number / (DAYS - 1)        # 0.0 on day 1 -> 1.0 on last day

        for c in CAMPAIGNS:
            weekend = c["weekend"] if is_weekend else 1.0

            # Daily spend: base budget x weekend effect x random noise (+/- ~10%)
            spend = c["spend"] * weekend * rng.normal(1.0, 0.10)

            # CPC drifts upward over the 12 weeks for some campaigns
            cpc = c["cpc"] * (1 + c["cpc_drift"] * progress) * rng.normal(1.0, 0.06)

            clicks = int(spend / cpc)
            impressions = int(clicks / (c["ctr"] * rng.normal(1.0, 0.08)))

            # Conversions are counts of rare events, so Poisson is a natural fit
            conversions = int(rng.poisson(clicks * c["cvr"] * weekend))
            revenue = conversions * c["aov"] * rng.normal(1.0, 0.10)

            rows.append(dict(
                date=date.date().isoformat(),
                channel=c["channel"],
                campaign=c["campaign"],
                impressions=impressions,
                clicks=clicks,
                spend=round(spend, 2),
                conversions=conversions,
                revenue=round(revenue, 2),
            ))

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate()
    OUT_FILE.parent.mkdir(exist_ok=True)
    df.to_csv(OUT_FILE, index=False)
    print(f"Wrote {len(df)} simulated rows to {OUT_FILE}")
    print(df.head())
