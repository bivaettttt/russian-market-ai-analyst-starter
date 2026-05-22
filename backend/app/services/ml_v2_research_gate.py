from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.adaptive_trade_calibration import compute_trade_setup
from app.services.ml_v2_dataset import DEFAULT_POLICY_ID, FEATURE_SET_VERSION, build_ml_v2_feature_row


ML_V2_RESEARCH_NOTE = (
    "ML v2 threshold 55% showed stable research edge in walk-forward validation; "
    "diagnostic-only by default."
)
DEFAULT_MODEL_VERSION = "ml_v2_trade_pnl_research_v1"


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 2) -> float | None:
    number = _to_float(value)
    if number is None:
        return None
    return round(number, digits)


def default_ml_v2_research_model_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "ml_v2_trade_pnl_model.joblib"


def _train_command() -> str:
    return (
        "cd backend && python3 -m app.tasks.train_ml_v2 "
        "--label positive_trade_return --max-tickers 120 --max-samples 10000 --horizon 30"
    )


def disabled_ml_v2_research_gate(threshold_pct: float = 55.0) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "disabled",
        "probability_pct": None,
        "threshold_pct": _round(threshold_pct, 1),
        "gate_passed": None,
        "label": "positive_trade_return",
        "model_version": None,
        "feature_set": FEATURE_SET_VERSION,
        "reason": "ML v2 research gate is disabled by default.",
        "research_note": ML_V2_RESEARCH_NOTE,
        "warnings": [],
    }


def classify_ml_v2_gate_probability(
    probability_pct: float | None,
    threshold_pct: float = 55.0,
) -> dict[str, Any]:
    probability = _to_float(probability_pct)
    threshold = _to_float(threshold_pct)
    if threshold is None:
        threshold = 55.0
    threshold = max(0.0, min(100.0, threshold))

    if probability is None:
        return {
            "status": "not_available",
            "gate_passed": None,
            "reason": "ML v2 probability is not available.",
        }

    if probability >= threshold:
        return {
            "status": "passed",
            "gate_passed": True,
            "reason": f"ML v2 probability {_round(probability, 1)}% is at or above threshold {_round(threshold, 1)}%.",
        }

    return {
        "status": "rejected",
        "gate_passed": False,
        "reason": f"ML v2 probability {_round(probability, 1)}% is below threshold {_round(threshold, 1)}%.",
    }


def load_ml_v2_research_model(model_path: str | None = None) -> dict[str, Any]:
    path = Path(model_path) if model_path else default_ml_v2_research_model_path()
    if not path.exists():
        return {
            "ok": False,
            "status": "not_available",
            "artifact_path": str(path),
            "reason": f"ML v2 artifact not found. Run: {_train_command()}",
            "warnings": [],
        }

    try:
        import joblib
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status": "error",
            "artifact_path": str(path),
            "reason": f"joblib is unavailable: {exc}",
            "warnings": ["Install/use the existing ML dependency environment before scoring ML v2."],
        }

    try:
        artifact = joblib.load(path)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status": "error",
            "artifact_path": str(path),
            "reason": f"Could not load ML v2 artifact: {exc}",
            "warnings": ["Retrain the ML v2 artifact if the file is corrupted or incompatible."],
        }

    model = artifact.get("model") if isinstance(artifact, dict) else None
    feature_names = artifact.get("feature_names") if isinstance(artifact, dict) else None
    metadata = artifact.get("metadata") if isinstance(artifact, dict) and isinstance(artifact.get("metadata"), dict) else {}

    if model is None or not isinstance(feature_names, list) or not feature_names:
        return {
            "ok": False,
            "status": "error",
            "artifact_path": str(path),
            "reason": "ML v2 artifact is missing model or feature_names.",
            "warnings": ["Retrain ML v2 with app.tasks.train_ml_v2."],
        }

    return {
        "ok": True,
        "status": "available",
        "artifact_path": str(path),
        "model": model,
        "feature_names": feature_names,
        "feature_set": metadata.get("feature_set") or artifact.get("feature_set") or FEATURE_SET_VERSION,
        "label": metadata.get("label") or "positive_trade_return",
        "policy_id": metadata.get("policy_id") or DEFAULT_POLICY_ID,
        "model_version": metadata.get("model_version") or DEFAULT_MODEL_VERSION,
        "metadata": metadata,
        "warnings": [],
    }


def _latest_close(candles: list[dict[str, Any]]) -> float | None:
    for row in reversed(candles):
        close = _to_float(row.get("close")) if isinstance(row, dict) else None
        if close is not None and close > 0:
            return close
    return None


def _policy_from_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    metadata = artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}
    policy = metadata.get("policy") if isinstance(metadata.get("policy"), dict) else None
    if policy:
        return policy
    return {
        "policy_type": "atr_multiple",
        "target_atr_mult": 1.5,
        "stop_atr_mult": 1.6,
        "horizon": 30,
        "min_rr": 0.8,
        "min_target_pct": 0.005,
        "max_target_pct": 0.25,
        "min_stop_pct": 0.005,
        "max_stop_pct": 0.20,
    }


def score_ml_v2_research_gate(
    *,
    candles: list[dict[str, Any]],
    instrument: dict[str, Any] | None = None,
    market_regime: dict[str, Any] | None = None,
    threshold_pct: float = 55.0,
    model_path: str | None = None,
) -> dict[str, Any]:
    loaded = load_ml_v2_research_model(model_path=model_path)
    threshold = _round(max(0.0, min(100.0, _to_float(threshold_pct) or 55.0)), 1)

    if not loaded.get("ok"):
        return {
            "ok": False,
            "status": loaded.get("status") or "not_available",
            "probability_pct": None,
            "threshold_pct": threshold,
            "gate_passed": None,
            "label": "positive_trade_return",
            "model_version": None,
            "feature_set": FEATURE_SET_VERSION,
            "reason": loaded.get("reason") or f"ML v2 artifact not found. Run: {_train_command()}",
            "research_note": ML_V2_RESEARCH_NOTE,
            "warnings": loaded.get("warnings") or [],
        }

    warnings = list(loaded.get("warnings") or [])
    close = _latest_close(candles)
    if close is None:
        return {
            "ok": False,
            "status": "error",
            "probability_pct": None,
            "threshold_pct": threshold,
            "gate_passed": None,
            "label": loaded.get("label") or "positive_trade_return",
            "model_version": loaded.get("model_version"),
            "feature_set": loaded.get("feature_set") or FEATURE_SET_VERSION,
            "reason": "ML v2 feature extraction failed: current close price is unavailable.",
            "research_note": ML_V2_RESEARCH_NOTE,
            "warnings": warnings + ["No valid close price in candle history."],
        }

    try:
        setup = compute_trade_setup(
            close=close,
            candles=candles,
            policy=_policy_from_artifact(loaded),
            instrument=instrument,
            market_regime=market_regime,
        )
        sample = {
            "history": candles,
            "volatility_bucket": setup.get("volatility_bucket"),
            "liquidity_bucket": setup.get("liquidity_bucket"),
            "market_regime": market_regime or {},
            "market_regime_name": (market_regime or {}).get("regime"),
            "market_regime_score": (market_regime or {}).get("regime_score"),
            "atr_pct": setup.get("atr_pct"),
            "target_return_pct": setup.get("target_pct"),
            "stop_return_pct": setup.get("stop_pct"),
            "risk_reward_ratio": setup.get("risk_reward_ratio"),
            "sector": (instrument or {}).get("sector"),
            "asset_type": (instrument or {}).get("asset_type"),
        }
        features = build_ml_v2_feature_row(sample)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status": "error",
            "probability_pct": None,
            "threshold_pct": threshold,
            "gate_passed": None,
            "label": loaded.get("label") or "positive_trade_return",
            "model_version": loaded.get("model_version"),
            "feature_set": loaded.get("feature_set") or FEATURE_SET_VERSION,
            "reason": f"ML v2 feature extraction failed: {exc}",
            "research_note": ML_V2_RESEARCH_NOTE,
            "warnings": warnings,
        }

    feature_names = loaded.get("feature_names") or []
    if len(features) != len(feature_names):
        return {
            "ok": False,
            "status": "error",
            "probability_pct": None,
            "threshold_pct": threshold,
            "gate_passed": None,
            "label": loaded.get("label") or "positive_trade_return",
            "model_version": loaded.get("model_version"),
            "feature_set": loaded.get("feature_set") or FEATURE_SET_VERSION,
            "reason": f"ML v2 feature mismatch: expected {len(feature_names)}, got {len(features)}.",
            "research_note": ML_V2_RESEARCH_NOTE,
            "warnings": warnings + ["Retrain artifact if feature_set changed."],
        }

    try:
        probability = float(loaded["model"].predict_proba([features])[0][1]) * 100.0
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status": "error",
            "probability_pct": None,
            "threshold_pct": threshold,
            "gate_passed": None,
            "label": loaded.get("label") or "positive_trade_return",
            "model_version": loaded.get("model_version"),
            "feature_set": loaded.get("feature_set") or FEATURE_SET_VERSION,
            "reason": f"ML v2 prediction failed: {exc}",
            "research_note": ML_V2_RESEARCH_NOTE,
            "warnings": warnings,
        }

    decision = classify_ml_v2_gate_probability(probability, threshold)
    return {
        "ok": True,
        "status": decision["status"],
        "probability_pct": _round(probability, 2),
        "threshold_pct": threshold,
        "gate_passed": decision["gate_passed"],
        "label": loaded.get("label") or "positive_trade_return",
        "model_version": loaded.get("model_version"),
        "feature_set": loaded.get("feature_set") or FEATURE_SET_VERSION,
        "reason": decision["reason"],
        "research_note": ML_V2_RESEARCH_NOTE,
        "warnings": warnings + list(setup.get("warnings") or []),
    }
