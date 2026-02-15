#!/usr/bin/env python3
"""
Resident Risk Scoring Engine
=============================
Produces two scores per active resident:
  - churn_score:       0 (will not renew) → 1 (healthy, will stay)
  - delinquency_score: 0 (will owe money) → 1 (pays on time)

Data sources (all READ-ONLY from Snowflake DWH_V2):
  - BI.DIM_LEASE_CONTRACTS      — lease dates, rent, status
  - BI.DIM_USERS                — app adoption signals
  - BI.MOVE_OUTS                — scheduled / actual move-outs
  - BI.DIM_SERVICE_REQUESTS     — per-user ticket stats (open, escalated, resolution time)
  - DATA_SCIENCE.ENRICHED_USER_PROFILES — pre-aggregated engagement features
  - CHAT_INSIGHTS.INSIGHTS      — group-chat sentiment & negative category flags
"""

import os
import re
import sys
import numpy as np
import pandas as pd
import snowflake.connector
from datetime import date
from dotenv import load_dotenv

load_dotenv()

TODAY = date.today()

# ──────────────────────────────────────────────
# Inline Snowflake client (no external dependency)
# ──────────────────────────────────────────────
WRITE_KEYWORDS = [
    'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
    'TRUNCATE', 'REPLACE', 'MERGE', 'UPSERT', 'COPY', 'PUT',
    'GRANT', 'REVOKE', 'EXECUTE', 'CALL'
]

def _validate_read_only(query: str) -> None:
    normalized = query.strip().upper()
    for keyword in WRITE_KEYWORDS:
        if re.match(rf'^\s*{keyword}\b', normalized):
            raise ValueError(f"Write operations not allowed. Blocked keyword: {keyword}")

def _get_snowflake_connection():
    return snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        role=os.getenv('SNOWFLAKE_ROLE'),
    )

def query_db(query: str) -> pd.DataFrame:
    _validate_read_only(query)
    conn = _get_snowflake_connection()
    conn.cursor().execute("USE DATABASE DWH_V2")
    try:
        return pd.read_sql(query, conn)
    finally:
        conn.close()

# ──────────────────────────────────────────────
# 1. DATA EXTRACTION
# ──────────────────────────────────────────────

def fetch_active_leases() -> pd.DataFrame:
    """Current active primary leases."""
    return query_db(f"""
        SELECT
            l.USER_ID,
            l.LEASE_ID,
            l.BUILDING_ID,
            l.START_DATE,
            l.END_DATE,
            l.MOVE_IN_DATE,
            l.RENT,
            l.VENN_STATUS,
            l.PMS_STATUS
        FROM BI.DIM_LEASE_CONTRACTS l
        WHERE l.COMPUTED_TIMELINE = 'CURRENT'
          AND l.VENN_STATUS = 'ACTIVE'
          AND l.IS_PRIMARY = TRUE
    """)


def fetch_enriched_profiles() -> pd.DataFrame:
    """Pre-computed engagement features from the data-science team."""
    return query_db("""
        SELECT
            USER_ID,
            PAYMENT_RENT_COUNTS,
            PAYMENT_LATE_LEGAL_ISSUES_COUNTS,
            PAYMENT_INSURANCE_COUNTS,
            APP_EVENT_LAST_30D_HOMEPAGE,
            APP_EVENT_LAST_30D_INBOX,
            APP_EVENT_LAST_30D_CHANNEL,
            APP_EVENT_LAST_30D_DASHBOARD,
            APP_EVENT_LAST_180D_HOMEPAGE,
            APP_EVENT_LAST_180D_INBOX,
            APP_EVENT_LAST_180D_CHANNEL,
            APP_EVENT_LAST_180D_SERVICE_REQUEST,
            "APP_EVENT_LAST_180D_RENT PAYMENT" as APP_EVENT_LAST_180D_RENT_PAYMENT,
            SERVICE_REQUESTS_LAST_30D,
            SERVICE_REQUESTS_LAST_180D,
            MEDIAN_TIME_TO_RESOLVE_LAST_30D,
            MEDIAN_TIME_TO_RESOLVE_LAST_180D,
            LAST_YEAR_NUMBER_OF_AMENITY_RESERVATIONS,
            LAST_MONTH_NUMBER_OF_AMENITY_RESERVATIONS,
            INTEREST_GROUP_MESSAGES_COUNT,
            EVENTS_GOING_COUNT,
            EVENTS_CANCELLED_COUNT,
            MESSAGE_INTENT_COUNT_COMPLAINTS,
            MESSAGE_INTENT_COUNT_LOOKING_TO_SUBLEASE,
            VISITORS_LAST_MONTH,
            VISITORS_LAST_YEAR,
            LAST_YEAR_AMOUNT_OF_PACKAGES,
            LAST_MONTH_AMOUNT_OF_PACKAGES
        FROM DATA_SCIENCE.ENRICHED_USER_PROFILES
    """)


def fetch_scheduled_moveouts() -> pd.DataFrame:
    """Future scheduled move-outs for current leases."""
    return query_db("""
        SELECT DISTINCT
            m.LEASE_ID,
            m.MOVE_OUT_DATE
        FROM BI.MOVE_OUTS m
        WHERE m.TYPE = 'future'
    """)


def fetch_renewal_history() -> pd.DataFrame:
    """Users who have previously renewed at the same building."""
    return query_db("""
        SELECT DISTINCT l2.USER_ID, l2.BUILDING_ID
        FROM BI.DIM_LEASE_CONTRACTS l1
        JOIN BI.DIM_LEASE_CONTRACTS l2
            ON l1.USER_ID = l2.USER_ID
            AND l1.BUILDING_ID = l2.BUILDING_ID
        WHERE l1.COMPUTED_TIMELINE = 'PAST'
          AND l2.COMPUTED_TIMELINE = 'CURRENT'
          AND l2.VENN_STATUS = 'ACTIVE'
          AND l2.IS_PRIMARY = TRUE
    """)


def fetch_user_app_adoption() -> pd.DataFrame:
    """Mobile-app adoption signals from DIM_USERS."""
    return query_db("""
        SELECT
            ID as USER_ID,
            MOBILE_FIRST_LOGIN,
            COMPLETED_MOBILE_ONBOARDING
        FROM BI.DIM_USERS
        WHERE IS_TEST_USER = 0 AND VENN_TEST_USER = 0
    """)


def fetch_service_request_details() -> pd.DataFrame:
    """Per-user service request stats: open tickets, escalations, resolution quality."""
    return query_db("""
        SELECT
            USER_ID,
            COUNT(*) as sr_total_tickets,
            SUM(CASE WHEN STATUS IN ('OPEN','IN_PROGRESS','ESCALATED','ON_HOLD','PENDING')
                     THEN 1 ELSE 0 END) as sr_open_tickets,
            SUM(CASE WHEN STATUS = 'ESCALATED' THEN 1 ELSE 0 END) as sr_escalated,
            SUM(CASE WHEN TIME_TO_RESOLUTION_IN_MINUTES > 10080
                     THEN 1 ELSE 0 END) as sr_over_7days,
            AVG(TIME_TO_RESOLUTION_IN_MINUTES) as sr_avg_resolution_min,
            MAX(TIME_TO_RESOLUTION_IN_MINUTES) as sr_max_resolution_min
        FROM BI.DIM_SERVICE_REQUESTS
        WHERE USER_ID IS NOT NULL
        GROUP BY USER_ID
    """)


def fetch_chat_sentiment() -> pd.DataFrame:
    """Per-user chat sentiment from group-chat insights."""
    return query_db("""
        SELECT
            USER_ID,
            COUNT(*) as chat_total_insights,
            AVG(TRY_CAST(SENTIMENT_SCORE AS FLOAT)) as chat_avg_sentiment,
            MIN(TRY_CAST(SENTIMENT_SCORE AS FLOAT)) as chat_min_sentiment,
            SUM(CASE WHEN TRY_CAST(SENTIMENT_SCORE AS FLOAT) <= 4 THEN 1 ELSE 0 END)
                as chat_negative_count,
            SUM(CASE WHEN CATEGORY_ID IN (
                    'Noise Complaints',
                    'Billing And Financial Concerns',
                    'Neighbor Conflicts',
                    'Security And Safety Concerns',
                    'Urgent Maintenance Issues'
                ) THEN 1 ELSE 0 END) as chat_angry_category_count
        FROM CHAT_INSIGHTS.INSIGHTS
        WHERE USER_ID IS NOT NULL
        GROUP BY USER_ID
    """)


# ──────────────────────────────────────────────
# 2. FEATURE ENGINEERING
# ──────────────────────────────────────────────

def build_features(
    leases: pd.DataFrame,
    enriched: pd.DataFrame,
    moveouts: pd.DataFrame,
    renewals: pd.DataFrame,
    app_adoption: pd.DataFrame,
    sr_details: pd.DataFrame,
    chat_sentiment: pd.DataFrame,
) -> pd.DataFrame:
    """Merge all sources and compute derived features."""

    df = leases.copy()

    # --- Lease-derived features ---
    df["days_until_lease_end"] = (
        pd.to_datetime(df["END_DATE"]) - pd.Timestamp(TODAY)
    ).dt.days.clip(lower=0)

    df["tenure_days"] = (
        pd.Timestamp(TODAY) - pd.to_datetime(df["MOVE_IN_DATE"])
    ).dt.days.clip(lower=1)

    df["tenure_months"] = (df["tenure_days"] / 30.44).round(1)

    # --- Scheduled move-out flag ---
    df = df.merge(
        moveouts.rename(columns={"MOVE_OUT_DATE": "SCHEDULED_MOVEOUT_DATE"}),
        on="LEASE_ID",
        how="left",
    )
    df["has_scheduled_moveout"] = df["SCHEDULED_MOVEOUT_DATE"].notna().astype(int)

    # --- Renewal history ---
    renewals["has_prior_renewal"] = 1
    df = df.merge(
        renewals[["USER_ID", "BUILDING_ID", "has_prior_renewal"]],
        on=["USER_ID", "BUILDING_ID"],
        how="left",
    )
    df["has_prior_renewal"] = df["has_prior_renewal"].fillna(0).astype(int)

    # --- App adoption ---
    app_adoption["has_app"] = app_adoption["MOBILE_FIRST_LOGIN"].notna().astype(int)
    app_adoption["completed_onboarding"] = (
        app_adoption["COMPLETED_MOBILE_ONBOARDING"].fillna(False).astype(int)
    )
    df = df.merge(
        app_adoption[["USER_ID", "has_app", "completed_onboarding"]],
        on="USER_ID",
        how="left",
    )
    df["has_app"] = df["has_app"].fillna(0).astype(int)
    df["completed_onboarding"] = df["completed_onboarding"].fillna(0).astype(int)

    # --- Enriched profile features ---
    df = df.merge(enriched, on="USER_ID", how="left")

    # Fill NaN engagement columns with 0
    engagement_cols = [c for c in enriched.columns if c != "USER_ID"]
    for col in engagement_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # --- Per-user service request details ---
    sr_details.columns = [c.lower() for c in sr_details.columns]
    sr_details.rename(columns={"user_id": "USER_ID"}, inplace=True)
    df = df.merge(sr_details, on="USER_ID", how="left")
    for col in sr_details.columns:
        if col != "USER_ID":
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Open ticket ratio (open / total)
    df["sr_open_ratio"] = (
        df["sr_open_tickets"] / df["sr_total_tickets"].replace(0, np.nan)
    ).fillna(0).clip(0, 1)

    # Tickets stuck > 7 days ratio
    df["sr_stuck_ratio"] = (
        df["sr_over_7days"] / df["sr_total_tickets"].replace(0, np.nan)
    ).fillna(0).clip(0, 1)

    # --- Chat sentiment ---
    chat_sentiment.columns = [c.lower() for c in chat_sentiment.columns]
    chat_sentiment.rename(columns={"user_id": "USER_ID"}, inplace=True)
    df = df.merge(chat_sentiment, on="USER_ID", how="left")
    for col in chat_sentiment.columns:
        if col != "USER_ID":
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Normalized sentiment (0=angry, 1=happy; scale is 1-10, default 5 if no data)
    df["chat_sentiment_norm"] = (
        df["chat_avg_sentiment"].replace(0, np.nan).fillna(5.0) / 10.0
    ).clip(0, 1)

    # Has angry chat categories flag
    df["has_angry_chats"] = (df["chat_angry_category_count"] > 0).astype(int)

    # Has negative sentiment flag
    df["has_negative_sentiment"] = (df["chat_negative_count"] > 0).astype(int)

    # --- Composite engagement metrics ---
    df["app_engagement_30d"] = (
        df.get("APP_EVENT_LAST_30D_HOMEPAGE", 0)
        + df.get("APP_EVENT_LAST_30D_INBOX", 0)
        + df.get("APP_EVENT_LAST_30D_CHANNEL", 0)
        + df.get("APP_EVENT_LAST_30D_DASHBOARD", 0)
    )
    df["app_engagement_180d"] = (
        df.get("APP_EVENT_LAST_180D_HOMEPAGE", 0)
        + df.get("APP_EVENT_LAST_180D_INBOX", 0)
        + df.get("APP_EVENT_LAST_180D_CHANNEL", 0)
    )

    df["community_score"] = (
        df["EVENTS_GOING_COUNT"]
        + df["INTEREST_GROUP_MESSAGES_COUNT"]
        + df["VISITORS_LAST_YEAR"]
    )

    # Rent payment ratio: actual rent payments / expected months
    df["expected_payments"] = df["tenure_months"].clip(lower=1)
    df["payment_ratio"] = (
        df["PAYMENT_RENT_COUNTS"] / df["expected_payments"]
    ).clip(0, 2)

    # Late-payment ratio
    df["late_ratio"] = (
        df["PAYMENT_LATE_LEGAL_ISSUES_COUNTS"]
        / df["PAYMENT_RENT_COUNTS"].replace(0, np.nan)
    ).fillna(0).clip(0, 1)

    return df


# ──────────────────────────────────────────────
# 3. SCORING MODELS
# ──────────────────────────────────────────────

def _percentile_norm(series: pd.Series) -> pd.Series:
    """Normalize using rank-based percentile (robust to outliers)."""
    return series.rank(pct=True, method="average").fillna(0.5)


def _minmax(series: pd.Series) -> pd.Series:
    """Simple 0-1 min-max normalization."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(0.5, index=series.index)
    return ((series - mn) / (mx - mn)).clip(0, 1)


def score_churn(df: pd.DataFrame) -> pd.Series:
    """
    Churn score: 1 = healthy (will stay), 0 = high churn risk.

    Weighted feature model:
      POSITIVE signals  (push score toward 1):
        - Days until lease end (far out = healthy)
        - App engagement 30d / 180d
        - Community participation
        - Amenity usage
        - Prior renewal
        - Has app & completed onboarding
        - Package usage (convenience stickiness)
      NEGATIVE signals  (push score toward 0):
        - Scheduled move-out
        - Complaint messages
        - Sublease intent messages
        - High cancelled events ratio
        - Poor service-request resolution time
    """

    scores = pd.DataFrame(index=df.index)

    # -- Positive signals --
    # Lease end proximity: >180d = 1.0, 0d = 0.0
    scores["lease_runway"] = (df["days_until_lease_end"] / 365).clip(0, 1)

    # App engagement
    scores["app_30d"] = _percentile_norm(df["app_engagement_30d"])
    scores["app_180d"] = _percentile_norm(df["app_engagement_180d"])

    # Community stickiness
    scores["community"] = _percentile_norm(df["community_score"])

    # Amenity usage
    scores["amenity"] = _percentile_norm(
        df["LAST_YEAR_NUMBER_OF_AMENITY_RESERVATIONS"]
    )

    # Renewal history (binary)
    scores["prior_renewal"] = df["has_prior_renewal"].astype(float)

    # App adoption
    scores["app_adoption"] = (df["has_app"] * 0.5 + df["completed_onboarding"] * 0.5)

    # Package convenience
    scores["packages"] = _percentile_norm(df["LAST_YEAR_AMOUNT_OF_PACKAGES"])

    # Tenure (longer = stickier, up to 3 years)
    scores["tenure"] = (df["tenure_days"] / (365 * 3)).clip(0, 1)

    # -- Negative signals (inverted: 1 = good, 0 = bad) --
    # Scheduled move-out is the strongest churn signal
    scores["no_moveout"] = 1.0 - df["has_scheduled_moveout"].astype(float)

    # Complaints (inverted percentile)
    scores["no_complaints"] = 1.0 - _percentile_norm(
        df["MESSAGE_INTENT_COUNT_COMPLAINTS"]
    )

    # Sublease intent (binary-ish, very strong signal)
    scores["no_sublease"] = (
        1.0 - (df["MESSAGE_INTENT_COUNT_LOOKING_TO_SUBLEASE"] > 0).astype(float)
    )

    # Service resolution satisfaction (lower median = better)
    median_resolve = df["MEDIAN_TIME_TO_RESOLVE_LAST_180D"].replace(0, np.nan)
    scores["sr_satisfaction"] = 1.0 - _percentile_norm(median_resolve.fillna(0))

    # Open tickets frustration (more unresolved = more frustrated)
    scores["low_open_tickets"] = 1.0 - _percentile_norm(df["sr_open_tickets"])

    # Stuck tickets (>7 days unresolved)
    scores["low_stuck_tickets"] = 1.0 - df["sr_stuck_ratio"]

    # Chat sentiment (higher = happier = less churn)
    scores["chat_sentiment"] = df["chat_sentiment_norm"]

    # No angry chat categories
    scores["no_angry_chats"] = 1.0 - df["has_angry_chats"].astype(float)

    # -- Weighted combination --
    weights = {
        "no_moveout":       0.22,   # strongest direct signal
        "lease_runway":     0.10,
        "app_30d":          0.08,
        "app_180d":         0.04,
        "community":        0.07,
        "amenity":          0.05,
        "prior_renewal":    0.07,
        "app_adoption":     0.03,
        "packages":         0.02,
        "tenure":           0.03,
        "no_complaints":    0.05,
        "no_sublease":      0.04,
        "sr_satisfaction":  0.04,
        "low_open_tickets": 0.05,  # NEW: unresolved ticket frustration
        "low_stuck_tickets":0.03,  # NEW: long-stuck tickets
        "chat_sentiment":   0.05,  # NEW: group-chat mood
        "no_angry_chats":   0.03,  # NEW: noise/billing/neighbor complaints in chat
    }

    churn = sum(scores[feat] * w for feat, w in weights.items())
    return churn.clip(0, 1).round(3)


def score_delinquency(df: pd.DataFrame) -> pd.Series:
    """
    Delinquency score: 1 = pays on time, 0 = high risk of owing money.

    Weighted feature model:
      POSITIVE signals  (push toward 1 = reliable payer):
        - High rent-payment ratio (pays consistently)
        - App engagement with rent-payment screen
        - Longer tenure
        - Insurance payments (responsible behavior)
        - Has app (engaged resident)
      NEGATIVE signals  (push toward 0 = will owe):
        - Late/legal payment counts
        - High late-to-rent ratio
        - Complaint messages
        - High rent amount (affordability stress)
    """

    scores = pd.DataFrame(index=df.index)

    # -- Positive signals --
    # Payment consistency (rent count / expected months)
    scores["payment_ratio"] = df["payment_ratio"].clip(0, 1)

    # Rent payment app engagement
    scores["rent_app_usage"] = _percentile_norm(
        df.get("APP_EVENT_LAST_180D_RENT_PAYMENT", pd.Series(0, index=df.index))
    )

    # Tenure reliability (longer = more track record)
    scores["tenure"] = (df["tenure_days"] / (365 * 3)).clip(0, 1)

    # Insurance (responsible behavior proxy)
    scores["has_insurance"] = (df["PAYMENT_INSURANCE_COUNTS"] > 0).astype(float)

    # App adoption
    scores["app_adoption"] = (df["has_app"] * 0.5 + df["completed_onboarding"] * 0.5)

    # General engagement (engaged residents tend to pay)
    scores["engagement"] = _percentile_norm(df["app_engagement_180d"])

    # -- Negative signals (inverted) --
    # Late/legal ratio
    scores["no_late_issues"] = 1.0 - df["late_ratio"]

    # Absolute late counts (inverted percentile)
    scores["low_late_count"] = 1.0 - _percentile_norm(
        df["PAYMENT_LATE_LEGAL_ISSUES_COUNTS"]
    )

    # Complaints (dissatisfied residents may withhold)
    scores["no_complaints"] = 1.0 - _percentile_norm(
        df["MESSAGE_INTENT_COUNT_COMPLAINTS"]
    )

    # Rent affordability (higher rent = more stress, inverted percentile)
    scores["rent_affordable"] = 1.0 - _percentile_norm(
        df["RENT"].fillna(0).astype(float)
    )

    # Open tickets frustration (unhappy residents may withhold payment)
    scores["low_open_tickets"] = 1.0 - _percentile_norm(df["sr_open_tickets"])

    # Chat sentiment (angry residents less likely to pay)
    scores["chat_sentiment"] = df["chat_sentiment_norm"]

    # Billing complaints in chat (direct signal)
    scores["no_billing_chats"] = 1.0 - df["has_angry_chats"].astype(float)

    # -- Weighted combination --
    weights = {
        "no_late_issues":    0.22,   # strongest direct signal
        "low_late_count":    0.13,
        "payment_ratio":     0.13,
        "rent_app_usage":    0.07,
        "tenure":            0.06,
        "has_insurance":     0.03,
        "app_adoption":      0.03,
        "engagement":        0.05,
        "no_complaints":     0.06,
        "rent_affordable":   0.09,
        "low_open_tickets":  0.04,  # NEW: unresolved tickets → frustration → withhold
        "chat_sentiment":    0.05,  # NEW: angry in group chats
        "no_billing_chats":  0.04,  # NEW: billing complaints in chats
    }

    delinq = sum(scores[feat] * w for feat, w in weights.items())
    return delinq.clip(0, 1).round(3)


# ──────────────────────────────────────────────
# 4. MAIN
# ──────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  RESIDENT RISK SCORING ENGINE")
    print(f"  Run date: {TODAY}")
    print("=" * 60)

    # --- Fetch data ---
    print("\n[1/8] Fetching active leases …")
    leases = fetch_active_leases()
    print(f"       {len(leases):,} active primary leases")

    print("[2/8] Fetching enriched profiles …")
    enriched = fetch_enriched_profiles()
    print(f"       {len(enriched):,} enriched profiles")

    print("[3/8] Fetching scheduled move-outs …")
    moveouts = fetch_scheduled_moveouts()
    print(f"       {len(moveouts):,} scheduled move-outs")

    print("[4/8] Fetching renewal history …")
    renewals = fetch_renewal_history()
    print(f"       {len(renewals):,} prior renewals")

    print("[5/8] Fetching app adoption …")
    app_adoption = fetch_user_app_adoption()
    print(f"       {len(app_adoption):,} user records")

    print("[6/8] Fetching service request details …")
    sr_details = fetch_service_request_details()
    print(f"       {len(sr_details):,} users with tickets")

    print("[7/8] Fetching chat sentiment …")
    chat_sentiment = fetch_chat_sentiment()
    print(f"       {len(chat_sentiment):,} users with chat insights")

    # --- Build features ---
    print("[8/8] Building features & scoring …")
    df = build_features(leases, enriched, moveouts, renewals, app_adoption,
                        sr_details, chat_sentiment)

    # --- Score ---
    df["churn_score"] = score_churn(df)
    df["delinquency_score"] = score_delinquency(df)

    # --- Output summary ---
    output_cols = [
        "USER_ID", "LEASE_ID", "BUILDING_ID",
        "RENT", "MOVE_IN_DATE", "END_DATE",
        "has_scheduled_moveout", "has_prior_renewal",
        "has_app", "tenure_months",
        "sr_open_tickets", "sr_total_tickets",
        "chat_avg_sentiment", "has_angry_chats",
        "churn_score", "delinquency_score",
    ]
    result = df[output_cols].copy()

    # Risk buckets
    result["churn_risk"] = pd.cut(
        result["churn_score"],
        bins=[0, 0.3, 0.6, 1.0],
        labels=["HIGH", "MEDIUM", "LOW"],
        include_lowest=True,
    )
    result["delinquency_risk"] = pd.cut(
        result["delinquency_score"],
        bins=[0, 0.3, 0.6, 1.0],
        labels=["HIGH", "MEDIUM", "LOW"],
        include_lowest=True,
    )

    # --- Print summary stats ---
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    print(f"\n  Total scored residents: {len(result):,}")

    print("\n  ── Churn Score ──")
    print(f"  Mean:   {result['churn_score'].mean():.3f}")
    print(f"  Median: {result['churn_score'].median():.3f}")
    print(f"  Std:    {result['churn_score'].std():.3f}")
    print(f"\n  Risk distribution:")
    for risk, cnt in result["churn_risk"].value_counts().sort_index().items():
        pct = cnt / len(result) * 100
        print(f"    {risk:8s}  {cnt:>6,}  ({pct:.1f}%)")

    print("\n  ── Delinquency Score ──")
    print(f"  Mean:   {result['delinquency_score'].mean():.3f}")
    print(f"  Median: {result['delinquency_score'].median():.3f}")
    print(f"  Std:    {result['delinquency_score'].std():.3f}")
    print(f"\n  Risk distribution:")
    for risk, cnt in result["delinquency_risk"].value_counts().sort_index().items():
        pct = cnt / len(result) * 100
        print(f"    {risk:8s}  {cnt:>6,}  ({pct:.1f}%)")

    # --- Top 20 highest churn risk ---
    print("\n  ── Top 20 Highest Churn Risk ──")
    top_churn = result.nsmallest(20, "churn_score")[
        ["BUILDING_ID", "RENT", "tenure_months", "has_scheduled_moveout",
         "churn_score", "delinquency_score"]
    ]
    print(top_churn.to_string(index=False))

    # --- Top 20 highest delinquency risk ---
    print("\n  ── Top 20 Highest Delinquency Risk ──")
    top_delinq = result.nsmallest(20, "delinquency_score")[
        ["BUILDING_ID", "RENT", "tenure_months",
         "delinquency_score", "churn_score"]
    ]
    print(top_delinq.to_string(index=False))

    # --- Save to CSV ---
    out_path = "resident_risk_scores.csv"
    result.to_csv(out_path, index=False)
    print(f"\n  ✓ Full results saved to {out_path}")
    print(f"    Columns: {', '.join(result.columns)}")

    return result


if __name__ == "__main__":
    result = main()
