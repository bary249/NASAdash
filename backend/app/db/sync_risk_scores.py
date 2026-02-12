"""
Sync Risk Scores from Snowflake → unified.db

Reads per-resident churn & delinquency scores from the Snowflake scoring engine,
maps Snowflake BUILDING_ID → OwnerDashV2 unified_property_id,
and writes property-level aggregates to the unified_risk_scores table.

Usage:
    python -m app.db.sync_risk_scores          # from backend/
    python app/db/sync_risk_scores.py           # direct

READ-ONLY on Snowflake. Writes only to local unified.db.
"""

import sys
import sqlite3
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date, datetime

# ---------------------------------------------------------------------------
# Snowflake connection — reuse the existing client from the snowflake/ folder
# ---------------------------------------------------------------------------
SNOWFLAKE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "snowflake"
sys.path.insert(0, str(SNOWFLAKE_DIR))

from snowflake_client import query_db  # noqa: E402

UNIFIED_DB_PATH = Path(__file__).parent / "data" / "unified.db"
TODAY = date.today().isoformat()

# ---------------------------------------------------------------------------
# BUILDING_ID → unified_property_id mapping
#
# Built from: Snowflake BI.DIM_BUILDINGS matched against the OwnerDashV2
# property registry (sync_realpage_to_unified.py PROPERTY_MAPPING).
#
# Some properties have multiple sub-buildings (e.g. thePearl A-W).
# We map each BUILDING_ID to the parent unified_property_id.
# ---------------------------------------------------------------------------

BUILDING_TO_PROPERTY = {
    # -- Direct 1:1 matches (building = property) --
    "c1052eff-237d-4c85-b6c7-f14195162b17": "7_east",
    "25d6c684-2864-4d35-8f6c-716f358cbed6": "aspire_7th_grant",
    "cloedt1k8002x01vx5rml8qkz":             "aspire_7th_grant",   # "Aspire" alias
    "30135dec-07a3-4a01-b55e-6f74ee51e572": "block_44",
    "b2cfe835-96dc-40d1-be8e-2f5a41c98d24": "broadleaf",
    "a2d58f6f-e870-4ad2-a3d2-20035e047c43": "confluence",
    "f7a6c27c-599f-4568-b76f-150a16e77e19": "discovery_kingwood",
    "5b44a8f2-983d-4ba5-8b3e-4a77ea78aa25": "eden_keller_ranch",
    "509f90ed-e6d4-48d6-a0fb-803ff02036d9": "edison_rino",
    "85e53e7e-492f-4586-9c87-996e57bcad2e": "harvest",
    "607b39d2-712e-49b1-9f13-663e182a8573": "heights_interlocken",
    "6430d240-92ac-42bd-9c54-71ce9723c101": "izzy",
    "a341beae-abd7-4f26-aaaa-48200ade90ec": "kalaco",
    "ce608304-ad6d-4850-81cc-1c1ef244352b": "links_plum_creek",
    "7a2ec430-0d14-4b28-bacf-6cbc1d8ca0ae": "luna",
    "bd606148-364a-4ac1-a4fa-f37e01412ba0": "nexus_east",
    "339657e1-e993-48ef-b10b-7208849c51e3": "park_17",
    "83e166b1-9991-4877-91df-2628d92b55c3": "parkside",
    "083eabb9-42c9-4a99-acae-2cd91a1d63af": "pearl_lantana",
    "e2746fcc-548e-4767-96f8-652f9c1afac9": "ridian",
    "c7a3bb17-a626-4a9d-a9a1-3a4409631336": "slate",
    "6d402bf0-2b91-4e04-af8e-b46ea35ac1af": "slate",
    "fef7faf0-8343-458c-b79d-82d919155f3d": "slate",
    "ed77d5c3-e4dc-407d-86df-1510346201c6": "sloane",
    "f3785376-96a7-4d9b-b465-944b89a25658": "station_riverfront",
    "579155b7-de13-42be-9baa-aafa632ecab4": "stonewood",
    "3ddb776e-910b-4a54-bfd0-3b969b9c3f0b": "ten50",
    "60461902-2e2b-4ae9-b05d-cc906e63a50c": "the_alcott",
    "e857f841-afe7-4a5e-8123-1516e01b43ab": "the_alcott",
    "e4c94ebd-ecc5-4e88-9161-6dd745ccea63": "the_avant",
    "0d19c0f8-a837-4840-b3a5-375693f3db91": "the_hunter",
    "d42481fe-4707-4284-85ab-276750a66436": "the_northern",
    "7913ea6b-c24e-42d4-bc28-e60fd90da779": "thequinci",

    # -- Curate sub-buildings → single property --
    "57c1890c-3bca-4d0c-b681-e2d340ab0c6f": "curate",  # A-North
    "c404fe62-0f79-445e-b442-4e4210e3098f": "curate",  # A-South
    "92144f44-cdf2-4c90-b5a8-5c895efb8c42": "curate",  # B
    "492cc618-db8b-4989-854a-978bec3187d2": "curate",  # C
    "2e70a758-c4f1-4860-9e95-7dfc21ad6b08": "curate",  # N/A

    # -- thePearl sub-buildings → single property --
    "229d367a-f22e-4045-9a8d-ab287f78bd9b": "thepearl",  # 1
    "5e202b46-6348-4441-883a-9bfd3c8a6f89": "thepearl",  # 2
    "02600049-6346-4cf2-b424-a3fb321ad29d": "thepearl",  # 3
    "6a07ad13-9fdf-4b1c-828b-375e52eb8d86": "thepearl",  # A
    "a9593737-c569-4ce1-a7e2-1d51f5c1e5b4": "thepearl",  # B
    "f27cf209-f5fe-4743-8a71-0dece102e082": "thepearl",  # C
    "eb044407-fa0e-4d78-a6af-0681b5c89731": "thepearl",  # D
    "2a161304-7d78-4d60-986b-884c6494d85d": "thepearl",  # E
    "fb067995-69b6-4b06-8971-5bbb79313ea5": "thepearl",  # F
    "d3f70451-0966-4b5a-8378-65e4acecef80": "thepearl",  # G
    "a8fc7b97-46e5-4098-93ad-48c39b6f6164": "thepearl",  # H
    "fe4d6a6d-0e29-4282-ace5-d41ed1b7f525": "thepearl",  # J
    "9dbe9ab3-6284-46f6-95ad-1e13816498ba": "thepearl",  # K
    "101001f5-51f9-4aea-9f34-ff22f2e2c014": "thepearl",  # L
    "ce6e59a6-c62b-4bbd-9b01-b42694a4c1a4": "thepearl",  # M
    "ae57fec3-41dc-4549-a38f-96f3b7d7f218": "thepearl",  # N
    "4097f888-c239-4a6c-89ff-cab2a5fdd1ed": "thepearl",  # P
    "84696e1c-d1bb-4247-a275-2cc0858fa1f0": "thepearl",  # Q
    "4dae7f11-27e8-452b-bd92-62d84406432a": "thepearl",  # R
    "7babbd6a-7f9a-4e6e-b61e-cc785948d659": "thepearl",  # S
    "1ce019b4-8c48-4c44-a820-b33aaccecb0d": "thepearl",  # T
    "bce4e26f-e9b9-4b56-8bf0-5aa73f15751e": "thepearl",  # U
    "0b1d8222-b43f-43b7-99c2-861375577510": "thepearl",  # V
    "8c16e11a-1375-42a1-a04d-189a390d7d1c": "thepearl",  # W
}


def load_risk_scores() -> pd.DataFrame:
    """Load the pre-computed risk scores CSV from the snowflake directory."""
    csv_path = SNOWFLAKE_DIR / "resident_risk_scores.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Risk scores CSV not found at {csv_path}. "
            "Run resident_risk_scores.py first."
        )
    df = pd.read_csv(csv_path)
    print(f"  Loaded {len(df):,} resident scores from {csv_path.name}")
    return df


def map_to_properties(df: pd.DataFrame) -> pd.DataFrame:
    """Map BUILDING_ID → unified_property_id using the hardcoded mapping."""
    df["unified_property_id"] = (
        df["BUILDING_ID"].astype(str).map(BUILDING_TO_PROPERTY)
    )
    mapped = df.dropna(subset=["unified_property_id"])
    unmapped_count = len(df) - len(mapped)
    mapped_props = mapped["unified_property_id"].nunique()
    print(f"  Mapped {len(mapped):,} residents to {mapped_props} properties")
    if unmapped_count > 0:
        print(f"  ({unmapped_count:,} residents in non-Kairoi buildings skipped)")
    return mapped


def aggregate_per_property(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate risk scores to property level.
    
    Risk tiers use portfolio-wide percentile thresholds computed on the
    at-risk group (residents WITHOUT scheduled move-out / notice).
    HIGH = bottom 25%, MEDIUM = 25-75%, LOW = top 25%.
    """
    # Compute portfolio-wide percentile thresholds on the at-risk group
    at_risk_all = df[df["has_scheduled_moveout"] == 0]
    if len(at_risk_all) > 0:
        churn_p25 = float(at_risk_all["churn_score"].quantile(0.25))
        churn_p75 = float(at_risk_all["churn_score"].quantile(0.75))
        delinq_p25 = float(at_risk_all["delinquency_score"].quantile(0.25))
        delinq_p75 = float(at_risk_all["delinquency_score"].quantile(0.75))
    else:
        churn_p25 = churn_p75 = delinq_p25 = delinq_p75 = 0.5

    print(f"  Portfolio churn thresholds (at-risk only): HIGH < {churn_p25:.3f}, LOW >= {churn_p75:.3f}")
    print(f"  Portfolio delinq thresholds (at-risk only): HIGH < {delinq_p25:.3f}, LOW >= {delinq_p75:.3f}")
    print(f"  At-risk residents (no notice): {len(at_risk_all)}, Notice givers: {len(df) - len(at_risk_all)}")

    records = []
    for prop_id, group in df.groupby("unified_property_id"):
        n = len(group)
        notice = group[group["has_scheduled_moveout"] == 1]
        at_risk = group[group["has_scheduled_moveout"] == 0]
        notice_count = len(notice)
        at_risk_total = len(at_risk)

        # Churn score distribution — on AT-RISK group only, using portfolio percentile thresholds
        if at_risk_total > 0:
            ar_churn = at_risk["churn_score"]
            churn_high = int((ar_churn < churn_p25).sum())
            churn_medium = int(((ar_churn >= churn_p25) & (ar_churn < churn_p75)).sum())
            churn_low = int((ar_churn >= churn_p75).sum())
        else:
            churn_high = churn_medium = churn_low = 0

        # Delinquency score distribution — on AT-RISK group only
        if at_risk_total > 0:
            ar_delinq = at_risk["delinquency_score"]
            delinq_high = int((ar_delinq < delinq_p25).sum())
            delinq_medium = int(((ar_delinq >= delinq_p25) & (ar_delinq < delinq_p75)).sum())
            delinq_low = int((ar_delinq >= delinq_p75).sum())
        else:
            delinq_high = delinq_medium = delinq_low = 0

        # Avg/median computed on ALL scored residents (for overall health)
        churn_all = group["churn_score"]
        delinq_all = group["delinquency_score"]

        records.append({
            "unified_property_id": prop_id,
            "snapshot_date": TODAY,
            "total_scored": n,
            "notice_count": notice_count,
            "at_risk_total": at_risk_total,
            "avg_churn_score": round(float(churn_all.mean()), 3),
            "median_churn_score": round(float(churn_all.median()), 3),
            "avg_delinquency_score": round(float(delinq_all.mean()), 3),
            "median_delinquency_score": round(float(delinq_all.median()), 3),
            "churn_high_count": churn_high,
            "churn_medium_count": churn_medium,
            "churn_low_count": churn_low,
            "delinq_high_count": delinq_high,
            "delinq_medium_count": delinq_medium,
            "delinq_low_count": delinq_low,
            "pct_scheduled_moveout": round(
                float(group["has_scheduled_moveout"].mean()) * 100, 1
            ),
            "pct_with_app": round(
                float(group["has_app"].mean()) * 100, 1
            ),
            "avg_tenure_months": round(float(group["tenure_months"].mean()), 1),
            "avg_rent": round(float(group["RENT"].mean()), 0),
            "avg_open_tickets": round(
                float(group["sr_open_tickets"].mean()), 1
            ),
            "churn_threshold_high": round(churn_p25, 3),
            "churn_threshold_low": round(churn_p75, 3),
        })

    result = pd.DataFrame(records)
    print(f"  Aggregated to {len(result)} property-level records")
    return result


def write_to_unified_db(agg: pd.DataFrame):
    """Write property aggregates to unified.db, replacing today's snapshot."""
    conn = sqlite3.connect(UNIFIED_DB_PATH)
    cursor = conn.cursor()

    # Recreate table with latest schema
    cursor.execute("DROP TABLE IF EXISTS unified_risk_scores")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS unified_risk_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unified_property_id TEXT NOT NULL,
            snapshot_date TEXT NOT NULL,
            total_scored INTEGER DEFAULT 0,
            notice_count INTEGER DEFAULT 0,
            at_risk_total INTEGER DEFAULT 0,
            avg_churn_score REAL DEFAULT 0,
            median_churn_score REAL DEFAULT 0,
            avg_delinquency_score REAL DEFAULT 0,
            median_delinquency_score REAL DEFAULT 0,
            churn_high_count INTEGER DEFAULT 0,
            churn_medium_count INTEGER DEFAULT 0,
            churn_low_count INTEGER DEFAULT 0,
            delinq_high_count INTEGER DEFAULT 0,
            delinq_medium_count INTEGER DEFAULT 0,
            delinq_low_count INTEGER DEFAULT 0,
            pct_scheduled_moveout REAL DEFAULT 0,
            pct_with_app REAL DEFAULT 0,
            avg_tenure_months REAL DEFAULT 0,
            avg_rent REAL DEFAULT 0,
            avg_open_tickets REAL DEFAULT 0,
            churn_threshold_high REAL DEFAULT 0,
            churn_threshold_low REAL DEFAULT 0,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(unified_property_id, snapshot_date)
        )
    """)

    # Delete today's records (idempotent re-run)
    cursor.execute(
        "DELETE FROM unified_risk_scores WHERE snapshot_date = ?", (TODAY,)
    )

    # Insert new records
    for _, row in agg.iterrows():
        cursor.execute("""
            INSERT INTO unified_risk_scores (
                unified_property_id, snapshot_date, total_scored,
                notice_count, at_risk_total,
                avg_churn_score, median_churn_score,
                avg_delinquency_score, median_delinquency_score,
                churn_high_count, churn_medium_count, churn_low_count,
                delinq_high_count, delinq_medium_count, delinq_low_count,
                pct_scheduled_moveout, pct_with_app,
                avg_tenure_months, avg_rent, avg_open_tickets,
                churn_threshold_high, churn_threshold_low,
                synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["unified_property_id"], row["snapshot_date"],
            row["total_scored"], row["notice_count"], row["at_risk_total"],
            row["avg_churn_score"], row["median_churn_score"],
            row["avg_delinquency_score"], row["median_delinquency_score"],
            row["churn_high_count"], row["churn_medium_count"],
            row["churn_low_count"],
            row["delinq_high_count"], row["delinq_medium_count"],
            row["delinq_low_count"],
            row["pct_scheduled_moveout"], row["pct_with_app"],
            row["avg_tenure_months"], row["avg_rent"],
            row["avg_open_tickets"],
            row["churn_threshold_high"], row["churn_threshold_low"],
            datetime.now().isoformat(),
        ))

    conn.commit()
    conn.close()
    print(f"  Wrote {len(agg)} records to unified_risk_scores (date={TODAY})")


def main():
    print("=" * 60)
    print("  RISK SCORE SYNC → unified.db")
    print(f"  Date: {TODAY}")
    print("=" * 60)

    print("\n[1/4] Loading risk scores CSV …")
    df = load_risk_scores()

    print("[2/4] Mapping buildings → properties …")
    mapped = map_to_properties(df)

    print("[3/4] Aggregating per property …")
    agg = aggregate_per_property(mapped)

    print("[4/4] Writing to unified.db …")
    write_to_unified_db(agg)

    # Summary
    print("\n" + "=" * 60)
    print("  SYNC COMPLETE")
    print("=" * 60)
    print(f"\n  {'Property':<25s} {'Total':>6s} {'Notice':>7s} {'At Risk':>8s} {'HIGH':>6s} {'MED':>6s} {'LOW':>6s}")
    print(f"  {'─' * 25} {'─' * 6} {'─' * 7} {'─' * 8} {'─' * 6} {'─' * 6} {'─' * 6}")
    for _, row in agg.sort_values("churn_high_count", ascending=False).iterrows():
        print(
            f"  {row['unified_property_id']:<25s} "
            f"{row['total_scored']:>6d} "
            f"{row['notice_count']:>7d} "
            f"{row['at_risk_total']:>8d} "
            f"{row['churn_high_count']:>6d} "
            f"{row['churn_medium_count']:>6d} "
            f"{row['churn_low_count']:>6d}"
        )

    return agg


if __name__ == "__main__":
    main()
