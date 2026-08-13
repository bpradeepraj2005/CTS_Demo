"""
Trains the two models the platform serves, and writes an honest metrics card.

    python ml/train.py --csv /path/to/appeals_prediction_transformed.csv

Outputs to ml/models/:
    policy_fit.joblib          HistGradientBoostingRegressor
    appeal_propensity.joblib   HistGradientBoostingClassifier
    metrics.json               held-out metrics, surfaced in the UI

Nothing here is fabricated. Whatever the held-out numbers are, they are what
metrics.json reports and what the app displays on the model card.
"""
import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    mean_absolute_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent))
from feature_schema import (  # noqa: E402
    APPEAL_CLASSES,
    APPEAL_FEATURES,
    CATEGORICAL,
    POLICY_FIT_FEATURES,
)

MODELS_DIR = Path(__file__).resolve().parent / "models"


def as_frame(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    X = df[columns].copy()
    for c in columns:
        if c in CATEGORICAL:
            X[c] = X[c].astype("category")
    return X


def train_policy_fit(df: pd.DataFrame) -> dict:
    X = as_frame(df, POLICY_FIT_FEATURES)
    y = df["policy_fit_score"].astype(float)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)

    model = HistGradientBoostingRegressor(
        categorical_features="from_dtype",
        max_iter=400,
        learning_rate=0.08,
        max_leaf_nodes=31,
        l2_regularization=0.1,
        early_stopping=True,
        random_state=42,
    ).fit(Xtr, ytr)

    pred = model.predict(Xte)
    joblib.dump(
        {"model": model, "features": POLICY_FIT_FEATURES, "categorical": CATEGORICAL},
        MODELS_DIR / "policy_fit.joblib",
    )
    return {
        "task": "regression",
        "target": "policy_fit_score",
        "r2": round(float(r2_score(yte, pred)), 4),
        "mae": round(float(mean_absolute_error(yte, pred)), 4),
        "target_std": round(float(y.std()), 4),
        "n_train": int(len(Xtr)),
        "n_test": int(len(Xte)),
    }


def train_appeal(df: pd.DataFrame) -> dict:
    X = as_frame(df, APPEAL_FEATURES)
    y = df["appeal_status"].astype(str)
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = HistGradientBoostingClassifier(
        categorical_features="from_dtype",
        max_iter=300,
        learning_rate=0.06,
        l2_regularization=0.5,
        early_stopping=True,
        random_state=42,
    ).fit(Xtr, ytr)

    pred = model.predict(Xte)
    proba = model.predict_proba(Xte)
    majority = float(pd.Series(yte).value_counts(normalize=True).max())

    try:
        auc = round(
            float(roc_auc_score(yte, proba, multi_class="ovr", average="macro")), 4
        )
    except ValueError:
        auc = None

    joblib.dump(
        {
            "model": model,
            "features": APPEAL_FEATURES,
            "categorical": CATEGORICAL,
            "classes": list(model.classes_),
        },
        MODELS_DIR / "appeal_propensity.joblib",
    )
    return {
        "task": "multiclass",
        "target": "appeal_status",
        "classes": list(model.classes_),
        "accuracy": round(float(accuracy_score(yte, pred)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(yte, pred)), 4),
        "macro_f1": round(float(f1_score(yte, pred, average="macro")), 4),
        "macro_auc_ovr": auc,
        "majority_class_baseline": round(majority, 4),
        "n_train": int(len(Xtr)),
        "n_test": int(len(Xte)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    args = ap.parse_args()

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.csv)
    print(f"Loaded {len(df):,} rows x {df.shape[1]} columns")

    missing = [c for c in set(APPEAL_FEATURES) | {"policy_fit_score", "appeal_status"}
               if c not in df.columns]
    if missing:
        raise SystemExit(f"CSV is missing required columns: {missing}")

    print("\nTraining policy-fit regressor...")
    pf = train_policy_fit(df)
    print(json.dumps(pf, indent=2))

    print("\nTraining appeal-propensity classifier...")
    ap_metrics = train_appeal(df)
    print(json.dumps(ap_metrics, indent=2))

    lift = None
    if ap_metrics["macro_auc_ovr"] is not None:
        lift = round(ap_metrics["accuracy"] - ap_metrics["majority_class_baseline"], 4)

    card = {
        "dataset_rows": int(len(df)),
        "source_csv": Path(args.csv).name,
        "policy_fit": pf,
        "appeal_propensity": ap_metrics,
        "appeal_accuracy_lift_over_baseline": lift,
        "notes": [
            "Metrics are computed on a held-out 20% split and are reported verbatim.",
            "The decision engine is a deterministic rules engine, not a classifier: "
            "the training data contains denied cases only, so an approve/deny "
            "boundary cannot be learned from it.",
        ],
    }
    (MODELS_DIR / "metrics.json").write_text(json.dumps(card, indent=2))
    print(f"\nWrote {MODELS_DIR/'metrics.json'}")


if __name__ == "__main__":
    main()