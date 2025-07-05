"""
student_lesson_analyzer.py  ·  v1.2
───────────────────────────────────────────────────────────────────────────────
✓ Normalises Accuracy (0–1, 0–100, "85 %", etc.)
✓ Drops rows without valid Accuracy before computing stats
✓ Generates table + key take-aways + CSV / MD downloads
"""

from __future__ import annotations
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
THRESHOLDS = {"too_hard": 80, "optimal_low": 80, "optimal_high": 90}
SUBJECTS = ["Language", "Math", "Reading"]      # Science is auto-excluded


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def clean_accuracy(val) -> Optional[float]:
    """
    Convert Accuracy to a 0-100 float or np.nan.
    Accepts 0-1 floats, 0-100 ints / floats, strings with '%', or blanks.
    """
    if pd.isna(val):
        return np.nan
    if isinstance(val, str):
        val = val.strip().replace("%", "")
    try:
        num = float(val)
    except Exception:
        return np.nan
    if 0 <= num <= 1:
        num *= 100
    return num


def classify_difficulty(acc: Optional[float]) -> Optional[str]:
    if pd.isna(acc):
        return None
    if acc < THRESHOLDS["too_hard"]:
        return "Too Hard"
    if THRESHOLDS["optimal_low"] <= acc <= THRESHOLDS["optimal_high"]:
        return "Optimal"
    return "Too Easy"


def avg_minutes(series: pd.Series) -> float:
    series = series.dropna()
    return round(series.mean(), 1) if not series.empty else np.nan


# ─────────────────────────────────────────────────────────────────────────────
# Core analysis
# ─────────────────────────────────────────────────────────────────────────────
def build_summary(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1. Strip Science rows
    df = df[~df["Subject"].str.contains("Science", na=False)]

    # 2. Clean & classify
    df["Accuracy"] = df["Accuracy"].apply(clean_accuracy)
    df["Difficulty"] = df["Accuracy"].apply(classify_difficulty)

    # 3. Drop rows without a Difficulty (i.e. missing / invalid Accuracy)
    df = df[df["Difficulty"].notna()]

    rows = []

    def collect(subset: pd.DataFrame, label: str):
        total = len(subset)
        counts = subset["Difficulty"].value_counts()

        hard, opt, easy = (
            counts.get("Too Hard", 0),
            counts.get("Optimal", 0),
            counts.get("Too Easy", 0),
        )

        hard_subset = subset[subset["Difficulty"] == "Too Hard"]
        abandoned_pct = (
            round(hard_subset["SmartScore"].lt(100).sum() / hard * 100, 1)
            if hard else 0.0
        )
        completed_hard = hard_subset["SmartScore"].eq(100).sum()

        rows.append(
            {
                "Subject": label,
                "Total Lessons": total,
                "% Too Hard": round(hard / total * 100, 1) if total else 0.0,
                "% Optimal": round(opt / total * 100, 1) if total else 0.0,
                "% Too Easy": round(easy / total * 100, 1) if total else 0.0,
                "% Too Hard Abandoned": abandoned_pct,
                "Too Hard Completed (#)": completed_hard,
                "Avg Min Too Hard": avg_minutes(hard_subset["Minutes Spent"]),
                "Avg Min Optimal": avg_minutes(
                    subset[subset["Difficulty"] == "Optimal"]["Minutes Spent"]
                ),
                "Avg Min Too Easy": avg_minutes(
                    subset[subset["Difficulty"] == "Too Easy"]["Minutes Spent"]
                ),
            }
        )

    # Per-subject rows
    for sub in SUBJECTS:
        sub_df = df[df["Subject"] == sub]
        if not sub_df.empty:
            collect(sub_df, sub)

    # Overall row
    collect(df, "Overall")

    col_order = [
        "Subject",
        "Total Lessons",
        "% Too Hard",
        "% Optimal",
        "% Too Easy",
        "% Too Hard Abandoned",
        "Too Hard Completed (#)",
        "Avg Min Too Hard",
        "Avg Min Optimal",
        "Avg Min Too Easy",
    ]
    return pd.DataFrame(rows)[col_order]


def generate_takeaways(summary: pd.DataFrame) -> str:
    overall = summary.loc[summary["Subject"] == "Overall"].iloc[0]
    bullets = [
        f"**Lesson mix:** {overall['% Too Easy']} % *too easy*, "
        f"{overall['% Optimal']} % in the *optimal* zone.",
        f"**Struggle:** {overall['% Too Hard']} % *too hard*; "
        f"{overall['% Too Hard Abandoned']} % of difficult lessons were abandoned.",
    ]
    return "\n".join(f"- {b}" for b in bullets)


def df_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def report_md(summary: pd.DataFrame, takeaways: str) -> bytes:
    md = "# Student Lesson Analysis Report\n\n"
    md += "## Summary Table\n\n" + summary.to_markdown(index=False)
    md += "\n\n## Key Take-Aways\n\n" + takeaways + "\n"
    return md.encode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit UI
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config("Student Lesson Analyzer", layout="wide")
st.title("📊 Student Lesson Analyzer")

uploaded = st.file_uploader(
    "Upload a single-student CSV (schema identical to Tegra_lesson_data.csv)",
    type=["csv"],
)

if uploaded:
    try:
        raw_df = pd.read_csv(uploaded)
    except Exception as err:
        st.error(f"Could not read CSV — {err}")
        st.stop()

    summary_df = build_summary(raw_df)
    takeaways_md = generate_takeaways(summary_df)

    st.subheader("Results Table")
    st.dataframe(summary_df, use_container_width=True)

    st.subheader("Key Take-Aways")
    st.markdown(takeaways_md)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "⬇️ Table (CSV)",
            data=df_to_csv(summary_df),
            file_name="lesson_summary.csv",
            mime="text/csv",
        )
    with col2:
        st.download_button(
            "⬇️ Full Report (Markdown)",
            data=report_md(summary_df, takeaways_md),
            file_name="lesson_report.md",
            mime="text/markdown",
        )
else:
    st.info("Awaiting CSV upload…")
