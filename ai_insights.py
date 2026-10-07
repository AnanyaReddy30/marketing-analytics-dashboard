"""
ai_insights.py
Turns the filtered dashboard data into plain-language insights with an LLM.

How it works:
  1. build_context() converts the numbers into a small text table.
  2. That text + an instruction is sent to the LLM (Claude or OpenAI).
  3. The system prompt tells the model to answer ONLY from that table.

API key: read from an environment variable, never written in the code.
  ANTHROPIC_API_KEY  -> uses Claude
  OPENAI_API_KEY     -> uses OpenAI (only if no Anthropic key is set)
  neither            -> free rule-based fallback (plain Python, no AI, no cost)

The data is SIMULATED, and the prompt tells the model so.
"""
import os

import pandas as pd

import metrics

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """You are a marketing analyst helping a junior marketer.
The data you receive is SIMULATED ad campaign data in Indian Rupees (INR). It is not a real account.
Rules:
- Use ONLY the numbers in the data provided. Do not use outside benchmarks or invent figures.
- If the data cannot answer the question, say so plainly.
- Quote the specific numbers you rely on.
- Plain language, short sentences, no jargon without a brief explanation.
Status rule used in the dashboard: ROAS >= 3 is Scale, ROAS < 1 is Fix, otherwise Watch."""


def provider() -> str:
    """Which backend will be used: 'claude', 'openai' or 'rules'."""
    if os.getenv("ANTHROPIC_API_KEY"):
        return "claude"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "rules"


def build_context(df: pd.DataFrame) -> str:
    """Summarise the filtered rows as text. This is ALL the model gets to see."""
    camp = metrics.campaign_table(df)
    weekly = metrics.summarise(df, ["week_start"])
    weekly_cpc = metrics.summarise(df, ["campaign", "week_start"])
    first_last = weekly_cpc.groupby("campaign")["cpc"].agg(["first", "last"])

    dates = pd.to_datetime(df["date"])
    day_type = dates.dt.dayofweek.map(lambda d: "Weekend" if d >= 5 else "Weekday")
    weekend = metrics.summarise(df.assign(day_type=day_type), ["channel", "day_type"])
    weekend["avg_daily_spend"] = weekend["spend"] / weekend["day_type"].map(
        dates.groupby(day_type).nunique())

    lines = [f"Period: {df['date'].min()} to {df['date'].max()}", "", "CAMPAIGNS:"]
    for r in camp.itertuples():
        lines.append(
            f"- {r.campaign} ({r.channel}): spend {r.spend:,.0f} ({r.spend_share:.0%} of total), "
            f"revenue {r.revenue:,.0f}, ROAS {r.roas:.2f}, conversions {r.conversions:,.0f}, "
            f"CPA {r.cpa:,.0f}, CPC {r.cpc:.1f}, CTR {r.ctr:.2%}, conversion rate {r.cvr:.2%}, "
            f"CPC first week {first_last.loc[r.campaign, 'first']:.1f} -> last week "
            f"{first_last.loc[r.campaign, 'last']:.1f}, status {r.status}")
    lines += ["", "WEEKLY TOTALS:"]
    for r in weekly.itertuples():
        lines.append(f"- week of {r.week_start}: spend {r.spend:,.0f}, revenue {r.revenue:,.0f}, ROAS {r.roas:.2f}")
    lines += ["", "WEEKDAY VS WEEKEND:"]
    for r in weekend.itertuples():
        lines.append(f"- {r.channel} {r.day_type}: avg daily spend {r.avg_daily_spend:,.0f}, ROAS {r.roas:.2f}")
    return "\n".join(lines)


def ask_llm(user_message: str) -> str:
    """Send one message to whichever LLM has a key set."""
    if provider() == "claude":
        import anthropic
        client = anthropic.Anthropic()                 # reads ANTHROPIC_API_KEY
        reply = client.messages.create(
            model=CLAUDE_MODEL, max_tokens=500, system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}])
        return reply.content[0].text

    from openai import OpenAI
    client = OpenAI()                                  # reads OPENAI_API_KEY
    reply = client.chat.completions.create(
        model=OPENAI_MODEL, max_tokens=500,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": user_message}])
    return reply.choices[0].message.content


def generate_summary(df: pd.DataFrame) -> str:
    if provider() == "rules":
        return rule_based_summary(df)
    return ask_llm(
        f"DATA:\n{build_context(df)}\n\n"
        "Write a summary of at most 120 words: what is working, what is not, "
        "and one specific budget recommendation (which campaign to move money from and to).")


def answer_question(df: pd.DataFrame, question: str) -> str:
    if provider() == "rules":
        return rule_based_answer(df, question)
    return ask_llm(f"DATA:\n{build_context(df)}\n\nQUESTION: {question}\n\nAnswer in under 100 words.")


# ---------- Free fallback: plain Python rules, no AI involved ----------

def rule_based_summary(df: pd.DataFrame) -> str:
    camp = metrics.campaign_table(df)          # already sorted best ROAS first
    total = metrics.totals(df)
    best, worst = camp.iloc[0], camp.iloc[-1]
    text = (
        f"Overall ROAS is {total.roas:.2f}x on ₹{total.spend:,.0f} of spend. "
        f"Best: **{best.campaign}** at {best.roas:.2f}x ROAS with only {best.spend_share:.0%} of spend. "
        f"Weakest: **{worst.campaign}** at {worst.roas:.2f}x ROAS while taking {worst.spend_share:.0%} of spend.")
    if len(camp) > 1 and worst.roas < metrics.BREAK_EVEN_ROAS:
        text += (f" Recommendation: test moving part of the {worst.campaign} budget to {best.campaign} "
                 "in small steps, and check that ROAS holds as spend grows.")
    return text


def rule_based_answer(df: pd.DataFrame, question: str) -> str:
    camp = metrics.campaign_table(df)
    best, worst = camp.iloc[0], camp.iloc[-1]
    q = question.lower()
    if any(word in q for word in ["cut", "worst", "pause", "stop", "fix", "reduce"]):
        return (f"Lowest ROAS is **{worst.campaign}**: {worst.roas:.2f}x on ₹{worst.spend:,.0f} "
                f"({worst.spend_share:.0%} of spend), CPA ₹{worst.cpa:,.0f}.")
    if any(word in q for word in ["scale", "best", "increase", "more", "grow"]):
        return (f"Highest ROAS is **{best.campaign}**: {best.roas:.2f}x on ₹{best.spend:,.0f} "
                f"({best.spend_share:.0%} of spend), CPA ₹{best.cpa:,.0f}.")
    return ("Without an API key I can only answer simple best / worst questions "
            "(try \"which campaign should I cut?\"). Set ANTHROPIC_API_KEY or OPENAI_API_KEY for free-form questions.")
