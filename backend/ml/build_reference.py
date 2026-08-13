"""
Builds the corpus reference profile used by the explainability layer.

Usage:
    python ml/build_reference.py --csv data/appeals_prediction_transformed.csv

The profile contains:
- median values for numeric features
- most common values for categorical features

It is generated from the supplied dataset rather than fabricated.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feature_schema import (  # noqa: E402
    CATEGORICAL,
    POLICY_FIT_FEATURES,
    derive_features,
)

MODELS_DIR = Path(__file__).resolve().parent / "models"
OUTPUT = MODELS_DIR / "reference_profile.json"


def clean_value(value):
    if pd.isna(value):
        return None

    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass

    if isinstance(value, float):
        return round(value, 6)

    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    args = parser.parse_args()

    csv_path = Path(args.csv)

    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    missing = [
        c for c in POLICY_FIT_FEATURES
        if c not in df.columns
    ]

    # Derived features are allowed to be absent from the CSV because they
    # can be deterministically reconstructed from the raw fields.
    if missing:
        for col in missing:
            if col in {
                "bmi_category",
                "age_group",
                "total_prior_events",
                "treatment_failure_ratio",
                "documentation_flag_sum",
                "documentation_score",
                "documentation_completeness_pct",
            }:
                continue

            raise SystemExit(
                f"CSV is missing required feature '{col}'"
            )

    # Build derived columns exactly as the serving layer does.
    derived_rows = [
        derive_features(row.to_dict())
        for _, row in df.iterrows()
    ]

    full = pd.DataFrame(derived_rows)

    profile = {}

    for column in POLICY_FIT_FEATURES:
        if column not in full.columns:
            continue

        series = full[column].dropna()

        if series.empty:
            profile[column] = None
            continue

        if column in CATEGORICAL:
            mode = series.mode(dropna=True)

            if len(mode):
                profile[column] = clean_value(mode.iloc[0])
            else:
                profile[column] = clean_value(series.iloc[0])

        else:
            numeric = pd.to_numeric(series, errors="coerce").dropna()

            if numeric.empty:
                profile[column] = clean_value(series.iloc[0])
            else:
                profile[column] = round(float(numeric.median()), 6)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        json.dumps(profile, indent=2),
        encoding="utf-8",
    )

    print(f"Loaded {len(df):,} rows")
    print(f"Built reference profile with {len(profile)} features")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()