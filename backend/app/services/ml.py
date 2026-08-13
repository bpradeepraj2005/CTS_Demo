"""
Production serving layer for the prior-authorization ML models.
"""

import json
import sys
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

from ..config import MODELS_DIR

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2] / "ml"),
)

from feature_schema import (  # noqa: E402
    APPEAL_LABELS,
    CATEGORICAL,
    derive_features,
)


class ModelUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _policy_fit_bundle():

    path = MODELS_DIR / "policy_fit.joblib"

    if not path.exists():
        raise ModelUnavailable(
            "Policy-fit model is missing. "
            "Run: python ml/train.py --csv data/appeals_prediction_transformed.csv"
        )

    try:
        return joblib.load(path)
    except Exception as exc:
        raise ModelUnavailable(
            f"Could not load policy-fit model: {exc}"
        ) from exc


@lru_cache(maxsize=1)
def _appeal_bundle():

    path = MODELS_DIR / "appeal_propensity.joblib"

    if not path.exists():
        raise ModelUnavailable(
            "Appeal model is missing. "
            "Run: python ml/train.py --csv data/appeals_prediction_transformed.csv"
        )

    try:
        return joblib.load(path)
    except Exception as exc:
        raise ModelUnavailable(
            f"Could not load appeal model: {exc}"
        ) from exc


@lru_cache(maxsize=1)
def metrics_card():

    path = MODELS_DIR / "metrics.json"

    if not path.exists():
        return {
            "available": False
        }

    try:
        card = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        card["available"] = True

        return card

    except Exception:
        return {
            "available": False
        }


def models_ready():

    return {
        "policy_fit": (
            MODELS_DIR / "policy_fit.joblib"
        ).exists(),

        "appeal_propensity": (
            MODELS_DIR / "appeal_propensity.joblib"
        ).exists(),
    }


def build_frame(
    features: dict,
    columns: list,
) -> pd.DataFrame:

    full = derive_features(features)

    row = {
        column: full.get(column)
        for column in columns
    }

    frame = pd.DataFrame(
        [row],
        columns=columns,
    )

    for column in columns:

        if column in CATEGORICAL:
            frame[column] = (
                frame[column]
                .fillna("Unknown")
                .astype("category")
            )
        else:
            frame[column] = pd.to_numeric(
                frame[column],
                errors="coerce",
            )

    return frame


def predict_policy_fit(
    features: dict,
) -> float:

    bundle = _policy_fit_bundle()

    frame = build_frame(
        features,
        bundle["features"],
    )

    try:
        score = bundle["model"].predict(frame)[0]
    except Exception as exc:
        raise ModelUnavailable(
            f"Policy-fit prediction failed: {exc}"
        ) from exc

    return float(
        max(
            0.0,
            min(
                1.0,
                score,
            ),
        )
    )


def predict_appeal(
    features: dict,
    policy_fit: float,
    clinical_evidence: float | None = None,
) -> dict:

    bundle = _appeal_bundle()

    enriched = dict(features)

    enriched["policy_fit_score"] = policy_fit

    enriched.setdefault(
        "clinical_evidence_score",
        clinical_evidence
        if clinical_evidence is not None
        else 0.35,
    )

    frame = build_frame(
        enriched,
        bundle["features"],
    )

    try:
        probabilities = (
            bundle["model"]
            .predict_proba(frame)[0]
        )
    except Exception as exc:
        raise ModelUnavailable(
            f"Appeal prediction failed: {exc}"
        ) from exc

    classes = list(
        bundle["model"].classes_
    )

    ranked = sorted(
        zip(classes, probabilities),
        key=lambda item: -item[1],
    )

    appealed_probability = float(
        sum(
            probability
            for class_name, probability
            in zip(classes, probabilities)
            if class_name != "NEVER_APPLIED"
        )
    )

    metrics = metrics_card().get(
        "appeal_propensity",
        {},
    )

    return {
        "top_class": ranked[0][0],

        "top_label": APPEAL_LABELS.get(
            ranked[0][0],
            ranked[0][0],
        ),

        "top_probability": round(
            float(ranked[0][1]),
            4,
        ),

        "any_appeal_probability": round(
            appealed_probability,
            4,
        ),

        "distribution": [
            {
                "outcome": class_name,
                "label": APPEAL_LABELS.get(
                    class_name,
                    class_name,
                ),
                "probability": round(
                    float(probability),
                    4,
                ),
            }
            for class_name, probability
            in ranked
        ],

        "model_macro_auc": metrics.get(
            "macro_auc_ovr"
        ),

        "model_accuracy": metrics.get(
            "accuracy"
        ),

        "baseline_accuracy": metrics.get(
            "majority_class_baseline"
        ),
    }