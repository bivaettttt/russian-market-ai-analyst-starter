from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Instrument

from app.services.signals_data import list_market_signals
from app.services.signal_model_registry import normalize_signal_model_version


RISK_PROFILES = {
    "conservative": {
        "title": "Консервативный",
        "max_positions": 5,
        "cash_reserve_pct": 20.0,
        "max_position_pct": 25.0,
        "buy_score_multiplier": 0.85,
        "hold_score_multiplier": 0.45,
    },
    "balanced": {
        "title": "Сбалансированный",
        "max_positions": 7,
        "cash_reserve_pct": 10.0,
        "max_position_pct": 30.0,
        "buy_score_multiplier": 1.0,
        "hold_score_multiplier": 0.55,
    },
    "aggressive": {
        "title": "Агрессивный",
        "max_positions": 10,
        "cash_reserve_pct": 5.0,
        "max_position_pct": 40.0,
        "buy_score_multiplier": 1.25,
        "hold_score_multiplier": 0.7,
    },
}


HORIZONS = {
    "short": {
        "title": "Краткосрочный",
        "description": "примерно 1–4 недели",
        "buy_bonus": 1.1,
        "hold_bonus": 0.85,
    },
    "medium": {
        "title": "Среднесрочный",
        "description": "примерно 1–6 месяцев",
        "buy_bonus": 1.0,
        "hold_bonus": 1.0,
    },
    "long": {
        "title": "Долгосрочный",
        "description": "от 6 месяцев",
        "buy_bonus": 0.9,
        "hold_bonus": 1.15,
    },
}


QUALITY_MODES = {
    "loose": {
        "title": "Мягкий",
        "description": "Собирает портфель даже при средних условиях; больше подходит для обзора вариантов.",
    },
    "normal": {
        "title": "Обычный",
        "description": "Баланс между количеством позиций и качеством сигналов.",
    },
    "strict": {
        "title": "Строгий",
        "description": "Берёт только позиции с приемлемым соотношением потенциала и риска.",
    },
}


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


def _safe_int(value: Any, default: int = 1) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default

    return number if number > 0 else default


def _get_lot_sizes(db: Session, tickers: list[Any]) -> dict[str, int]:
    normalized = {
        str(ticker).upper().strip()
        for ticker in tickers
        if ticker
    }

    if not normalized:
        return {}

    result = {ticker: 1 for ticker in normalized}

    rows = db.execute(
        select(Instrument.ticker, Instrument.lot_size)
        .where(Instrument.ticker.in_(sorted(normalized)))
    ).all()

    for ticker, lot_size in rows:
        if ticker:
            result[str(ticker).upper()] = _safe_int(lot_size, default=1)

    return result


def _normalize_risk_profile(value: str | None) -> str:
    value = (value or "balanced").strip().lower()

    if value in RISK_PROFILES:
        return value

    return "balanced"


def _normalize_quality_mode(value: str | None) -> str:
    value = (value or "normal").strip().lower()

    if value in QUALITY_MODES:
        return value

    return "normal"


def _position_risk_reward_from_row(row: dict[str, Any]) -> tuple[float | None, str | None]:
    price = _to_float(row.get("price"))
    signal = row.get("signal") or {}
    target_price = _to_float(signal.get("target_price"))
    stop_loss = _to_float(signal.get("stop_loss"))

    if not price or price <= 0:
        return None, "нет корректной цены"

    if target_price is None or stop_loss is None:
        return None, "нет цели или стопа"

    upside_pct = (target_price - price) / price * 100
    downside_pct = (stop_loss - price) / price * 100
    abs_downside_pct = abs(downside_pct)

    if upside_pct <= 0:
        return None, "цель не выше текущей цены"

    if abs_downside_pct <= 0:
        return None, "стоп не даёт измеримого риска"

    return round(upside_pct / abs_downside_pct, 2), None


def _normalize_horizon(value: str | None) -> str:
    value = (value or "medium").strip().lower()

    if value in HORIZONS:
        return value

    return "medium"


def _score_signal(row: dict[str, Any], risk_profile: str, horizon: str, quality_mode: str = "normal") -> tuple[float, list[str]]:
    signal = row.get("signal") or {}
    technical = row.get("technical") or {}

    action = signal.get("action")
    confidence = _to_float(signal.get("confidence_pct")) or 0.0
    volatility = _to_float(technical.get("volatility_20d_pct")) or 0.0
    return_5d = _to_float(technical.get("return_5d_pct")) or 0.0
    volume_ratio = _to_float(technical.get("volume_ratio")) or 0.0
    position_rr, position_rr_error = _position_risk_reward_from_row(row)

    profile = RISK_PROFILES[risk_profile]
    horizon_cfg = HORIZONS[horizon]

    reasons: list[str] = []

    if action == "buy_watch":
        score = confidence * profile["buy_score_multiplier"] * horizon_cfg["buy_bonus"]
        reasons.append("Есть позитивный технический сценарий покупки.")
    elif action == "hold_watch":
        if quality_mode != "loose":
            if risk_profile in {"conservative", "balanced"} and return_5d <= 0:
                return 0.0, ["Исключено: нейтральный сигнал без положительного импульса."]

            if risk_profile in {"conservative", "balanced"} and volume_ratio < 0.1:
                return 0.0, ["Исключено: слишком низкий объём для нейтральной позиции."]

        if quality_mode == "strict":
            if return_5d < 1.0:
                return 0.0, ["Исключено strict-режимом: слабый импульс для нейтральной позиции."]

            if volume_ratio < 0.5:
                return 0.0, ["Исключено strict-режимом: недостаточный объём для нейтральной позиции."]

        score = confidence * profile["hold_score_multiplier"] * horizon_cfg["hold_bonus"]
        reasons.append("Нейтральный сигнал: можно включать только как диверсификацию.")
    else:
        return 0.0, ["Исключено: сигнал риска снижения или нет подходящего сценария."]

    if quality_mode == "strict":
        if position_rr is None:
            return 0.0, [f"Исключено strict-режимом: {position_rr_error or 'не удалось оценить risk/reward позиции'}."]

        if position_rr < 1.0:
            return 0.0, [f"Исключено strict-режимом: слабый risk/reward позиции ({position_rr})."]

        reasons.append(f"Strict-фильтр пройден: risk/reward позиции {position_rr}.")
        score *= min(1.0 + position_rr / 10.0, 1.25)

    if return_5d > 0:
        score += min(return_5d * 2.0, 12.0)
        reasons.append(f"Положительная динамика за 5 свечей: {round(return_5d, 2)}%.")

    if volume_ratio >= 1.2:
        score += 5.0
        reasons.append(f"Объём выше среднего: {round(volume_ratio, 2)}x.")

    if volatility > 2.0 and risk_profile == "conservative":
        score *= 0.75
        reasons.append("Снижена доля из-за повышенной волатильности для консервативного профиля.")

    if volatility > 3.0:
        score *= 0.85
        reasons.append("Снижена доля из-за высокой волатильности.")

    return round(max(score, 0.0), 2), reasons


def construct_portfolio(
    db: Session,
    budget: float,
    risk_profile: str = "balanced",
    horizon: str = "medium",
    quality_mode: str = "normal",
    model_version: str | None = None,
    tickers: str | None = None,
    candles_limit: int = 120,
) -> dict[str, Any]:
    budget = float(budget or 0)

    if budget <= 0:
        return {
            "ok": False,
            "error": "budget должен быть больше 0",
        }

    risk_profile = _normalize_risk_profile(risk_profile)
    horizon = _normalize_horizon(horizon)
    quality_mode = _normalize_quality_mode(quality_mode)
    selected_model_version = normalize_signal_model_version(model_version)

    profile = RISK_PROFILES[risk_profile]
    horizon_cfg = HORIZONS[horizon]
    quality_cfg = QUALITY_MODES[quality_mode]

    limit = 120
    signals_data = list_market_signals(
        db=db,
        limit=limit,
        candles_limit=candles_limit,
        model_version=selected_model_version,
    )

    rows = signals_data.get("rows") or []

    if tickers:
        allowed = {
            item.strip().upper()
            for item in tickers.split(",")
            if item.strip()
        }
        rows = [
            row for row in rows
            if str(row.get("ticker") or "").upper() in allowed
        ]

    lot_sizes = _get_lot_sizes(
        db=db,
        tickers=[row.get("ticker") for row in rows],
    )

    candidates = []
    excluded = []

    for row in rows:
        price = _to_float(row.get("price"))

        if not price or price <= 0:
            excluded.append({
                "ticker": row.get("ticker"),
                "name": row.get("name") or row.get("ticker"),
                "action": (row.get("signal") or {}).get("action"),
                "label": (row.get("signal") or {}).get("label"),
                "price": row.get("price"),
                "reason": "Исключено: нет корректной цены.",
                "ticker_url": row.get("ticker_url"),
            })
            continue

        ticker_key = str(row.get("ticker") or "").upper()
        lot_size = _safe_int(lot_sizes.get(ticker_key), default=1)

        score, reasons = _score_signal(
            row=row,
            risk_profile=risk_profile,
            horizon=horizon,
            quality_mode=quality_mode,
        )

        if score <= 0:
            excluded.append({
                "ticker": row.get("ticker"),
                "name": row.get("name") or row.get("ticker"),
                "action": (row.get("signal") or {}).get("action"),
                "label": (row.get("signal") or {}).get("label"),
                "price": row.get("price"),
                "score": score,
                "reason": reasons[0] if reasons else "Исключено: недостаточный скоринг.",
                "reasons": reasons,
                "ticker_url": row.get("ticker_url"),
            })
            continue

        candidates.append({
            "ticker": row.get("ticker"),
            "name": row.get("name") or row.get("ticker"),
            "sector": row.get("sector"),
            "price": price,
            "lot_size": lot_size,
            "change_pct": row.get("change_pct"),
            "trade_date": row.get("trade_date"),
            "score": score,
            "signal": row.get("signal") or {},
            "technical": row.get("technical") or {},
            "reasons": reasons,
            "ticker_url": row.get("ticker_url"),
        })

    candidates.sort(key=lambda item: item["score"], reverse=True)

    max_positions = int(profile["max_positions"])
    selected_candidates = candidates[:max_positions]

    for item in candidates[max_positions:]:
        excluded.append({
            "ticker": item.get("ticker"),
            "name": item.get("name") or item.get("ticker"),
            "action": (item.get("signal") or {}).get("action"),
            "label": (item.get("signal") or {}).get("label"),
            "price": item.get("price"),
            "score": item.get("score"),
            "reason": "Не вошло: ниже рейтинг относительно выбранных позиций.",
            "reasons": item.get("reasons") or [],
            "ticker_url": item.get("ticker_url"),
        })

    candidates = selected_candidates

    investable_budget = budget * (1.0 - profile["cash_reserve_pct"] / 100.0)

    if not candidates:
        return {
            "ok": True,
            "model_version": selected_model_version,
            "risk_profile": risk_profile,
            "risk_profile_title": profile["title"],
            "horizon": horizon,
            "horizon_title": horizon_cfg["title"],
            "quality_mode": quality_mode,
            "quality_mode_title": quality_cfg["title"],
            "budget": round(budget, 2),
            "investable_budget": round(investable_budget, 2),
            "cash_reserve_target": round(budget - investable_budget, 2),
            "positions": [],
            "excluded_count": len(excluded),
            "excluded": excluded,
            "summary": {
                "positions_count": 0,
                "invested": 0.0,
                "cash": round(budget, 2),
                "cash_pct": 100.0,
                "portfolio_risk_level": "нет портфеля",
            },
            "notes": [
                "Не найдено подходящих кандидатов по текущим сигналам.",
                "Можно увеличить список тикеров, сменить профиль риска или дождаться новых сигналов.",
            ],
        }

    total_score = sum(item["score"] for item in candidates) or 1.0
    max_position_value = investable_budget * profile["max_position_pct"] / 100.0

    positions = []
    invested = 0.0

    for item in candidates:
        raw_weight = item["score"] / total_score
        target_value = investable_budget * raw_weight
        target_value = min(target_value, max_position_value)

        lot_size = _safe_int(item.get("lot_size"), default=1)
        lot_price = item["price"] * lot_size
        lots = int(target_value // lot_price)
        quantity = lots * lot_size

        if lots <= 0 or quantity <= 0:
            excluded.append({
                "ticker": item.get("ticker"),
                "name": item.get("name") or item.get("ticker"),
                "action": (item.get("signal") or {}).get("action"),
                "label": (item.get("signal") or {}).get("label"),
                "price": item.get("price"),
                "lot_size": lot_size,
                "lot_price": _round(lot_price),
                "score": item.get("score"),
                "reason": "Не вошло: цена одного лота выше доступной целевой суммы.",
                "reasons": item.get("reasons") or [],
                "ticker_url": item.get("ticker_url"),
            })
            continue

        value = lots * lot_price
        invested += value

        signal = item.get("signal") or {}
        technical = item.get("technical") or {}

        price = item["price"]
        target_price = _to_float(signal.get("target_price"))
        stop_loss = _to_float(signal.get("stop_loss"))

        target_upside_pct = None
        target_upside_rub = None
        stop_downside_pct = None
        stop_downside_rub = None

        if target_price is not None and price > 0:
            target_upside_pct = _round((target_price - price) / price * 100)
            target_upside_rub = _round((target_price - price) * quantity)

        if stop_loss is not None and price > 0:
            stop_downside_pct = _round((stop_loss - price) / price * 100)
            stop_downside_rub = _round((stop_loss - price) * quantity)

        positions.append({
            "ticker": item["ticker"],
            "name": item["name"],
            "sector": item["sector"],
            "price": _round(price),
            "lot_size": lot_size,
            "lots": lots,
            "quantity": quantity,
            "value": _round(value),
            "weight_pct": None,
            "score": item["score"],
            "action": signal.get("action"),
            "label": signal.get("label"),
            "confidence_pct": signal.get("confidence_pct"),
            "risk_level": signal.get("risk_level"),
            "entry_price": signal.get("entry_price"),
            "target_price": signal.get("target_price"),
            "stop_loss": signal.get("stop_loss"),
            "target_upside_pct": target_upside_pct,
            "target_upside_rub": target_upside_rub,
            "stop_downside_pct": stop_downside_pct,
            "stop_downside_rub": stop_downside_rub,
            "horizon": signal.get("horizon"),
            "trend": technical.get("trend"),
            "return_5d_pct": technical.get("return_5d_pct"),
            "volatility_20d_pct": technical.get("volatility_20d_pct"),
            "volume_ratio": technical.get("volume_ratio"),
            "reasons": item["reasons"],
            "ticker_url": item.get("ticker_url"),
        })

    for position in positions:
        value = _to_float(position.get("value")) or 0.0
        position["weight_pct"] = round(value / invested * 100, 2) if invested > 0 else 0.0

    cash = budget - invested
    cash_pct = round(cash / budget * 100, 2) if budget > 0 else None

    avg_confidence_values = [
        _to_float(position.get("confidence_pct"))
        for position in positions
        if _to_float(position.get("confidence_pct")) is not None
    ]

    avg_confidence = (
        round(sum(avg_confidence_values) / len(avg_confidence_values), 2)
        if avg_confidence_values
        else None
    )

    risk_sell_count = sum(1 for row in rows if (row.get("signal") or {}).get("action") == "risk_sell_watch")
    buy_count = sum(1 for position in positions if position.get("action") == "buy_watch")
    hold_count = sum(1 for position in positions if position.get("action") == "hold_watch")

    target_upside_rub = sum(
        _to_float(position.get("target_upside_rub")) or 0.0
        for position in positions
    )
    stop_downside_rub = sum(
        _to_float(position.get("stop_downside_rub")) or 0.0
        for position in positions
    )

    target_upside_pct = round(target_upside_rub / invested * 100, 2) if invested > 0 else None
    stop_downside_pct = round(stop_downside_rub / invested * 100, 2) if invested > 0 else None

    absolute_risk_rub = abs(stop_downside_rub)

    risk_reward_ratio = None
    risk_reward_label = "нет данных"

    if absolute_risk_rub > 0 and target_upside_rub > 0:
        risk_reward_ratio = round(target_upside_rub / absolute_risk_rub, 2)

        if risk_reward_ratio < 0.8:
            risk_reward_label = "слабое"
        elif risk_reward_ratio < 1.2:
            risk_reward_label = "пограничное"
        elif risk_reward_ratio < 1.8:
            risk_reward_label = "хорошее"
        else:
            risk_reward_label = "сильное"

    portfolio_conclusion_level = "neutral"
    portfolio_conclusion = "Портфель собран по текущим сигналам."

    if not positions:
        portfolio_conclusion_level = "warning"
        portfolio_conclusion = "Подходящих позиций по текущим условиям не найдено. Лучше сохранить кэш и дождаться более сильных сигналов."
    elif risk_reward_ratio is None:
        portfolio_conclusion_level = "warning"
        portfolio_conclusion = "Недостаточно данных для оценки risk/reward. Проверьте цели и стопы по выбранным бумагам."
    elif risk_reward_ratio < 0.8:
        portfolio_conclusion_level = "warning"
        portfolio_conclusion = "Risk/reward слабое: потенциальная прибыль ниже риска до стопов. Портфель можно рассматривать только осторожно, без агрессивного добора."
    elif risk_reward_ratio < 1.2:
        portfolio_conclusion_level = "review"
        portfolio_conclusion = "Risk/reward пограничное: портфель допустим, но запас качества небольшой. Лучше проверить точки входа и долю кэша."
    elif risk_reward_ratio < 1.8:
        portfolio_conclusion_level = "good"
        portfolio_conclusion = "Risk/reward хорошее: потенциал выше риска, портфель выглядит приемлемо по текущим техническим сигналам."
    else:
        portfolio_conclusion_level = "strong"
        portfolio_conclusion = "Risk/reward сильное: потенциал заметно выше риска. Всё равно проверьте новости, ликвидность и общий рыночный фон."

    if quality_mode == "strict" and positions and (summary_positions_count := len(positions)) <= 2:
        portfolio_conclusion += " Строгий режим оставил мало позиций — это сигнал, что качественных входов сейчас немного."

    if risk_profile == "conservative":
        portfolio_risk_level = "умеренный" if buy_count else "низкий/умеренный"
    elif risk_profile == "aggressive":
        portfolio_risk_level = "повышенный"
    else:
        portfolio_risk_level = "средний"

    notes = [
        "MVP-конструктор использует текущие технические сигналы и rule-based скоринг.",
        "Количество считается через lot_size инструмента; для старых инструментов без данных используется lot_size = 1.",
        "Это аналитический сценарий, не индивидуальная инвестиционная рекомендация.",
    ]

    return {
        "ok": True,
        "model_version": selected_model_version,
        "risk_profile": risk_profile,
        "risk_profile_title": profile["title"],
        "horizon": horizon,
        "horizon_title": horizon_cfg["title"],
        "horizon_description": horizon_cfg["description"],
        "quality_mode": quality_mode,
        "quality_mode_title": quality_cfg["title"],
        "quality_mode_description": quality_cfg["description"],
        "budget": round(budget, 2),
        "investable_budget": round(investable_budget, 2),
        "cash_reserve_target": round(budget - investable_budget, 2),
        "positions": positions,
        "excluded_count": len(excluded),
        "excluded": excluded,
        "candidates_count": len(candidates),
        "source_rows_count": len(rows),
        "summary": {
            "positions_count": len(positions),
            "invested": _round(invested),
            "cash": _round(cash),
            "cash_pct": cash_pct,
            "avg_confidence_pct": avg_confidence,
            "portfolio_risk_level": portfolio_risk_level,
            "target_upside_rub": _round(target_upside_rub),
            "target_upside_pct": target_upside_pct,
            "stop_downside_rub": _round(stop_downside_rub),
            "stop_downside_pct": stop_downside_pct,
            "risk_reward_ratio": risk_reward_ratio,
            "risk_reward_label": risk_reward_label,
            "portfolio_conclusion_level": portfolio_conclusion_level,
            "portfolio_conclusion": portfolio_conclusion,
            "buy_positions": buy_count,
            "hold_positions": hold_count,
            "risk_signals_in_market": risk_sell_count,
        },
        "notes": notes,
    }
