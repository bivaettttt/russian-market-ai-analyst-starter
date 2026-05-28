# Conservative Event Overlay Integration

The conservative event overlay is integrated as an opt-in paper-trading/report layer. It does not change production defaults.

## Why

Conservative calibration found the first practical event-aware risk-layer candidate:

- positive return folds: `4/4`;
- positive PF folds: `4/4`;
- positive stop-hit folds: `4/4`;
- avg PF delta: `+0.068`;
- avg return delta: `+0.187%`;
- stop-hit exposure delta: `-1.81 pp`;
- avg multiplier: `0.556`;
- exposure reduction: `44.388%`.

The selected config is:

`cons_t20_40_60_80_m95_e80_h65_x40_w100`

## How To Use

```bash
curl "http://127.0.0.1:8010/signals/consumer/SBER.json?use_conservative_event_overlay=true"

curl "http://127.0.0.1:8010/signals/consumer.json?limit=50&use_conservative_event_overlay=true"

curl "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-snapshot?limit=50"

curl "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-page"

curl -X POST "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-snapshots?name=daily-paper&limit=100&horizon_days=20"

curl "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-dashboard?limit=20"
```

Allowed shortcut modes:

- `soft_adjust`;
- `diagnostic_only`.

The conservative shortcut does not allow `experimental_downgrade`. Use the generic `use_event_risk_overlay=true` path explicitly if experimental action downgrades are needed for research.

## Fields

- `conservative_event_overlay_enabled`
- `conservative_event_overlay_config_id`
- `conservative_event_overlay_mode`
- `conservative_event_overlay_research_basis`
- `base_position_size_pct`
- `event_adjusted_position_size_pct`
- `event_position_multiplier`
- `event_position_delta_pct`
- `event_risk_score`
- `event_risk_level`
- `event_risk_position_multiplier`
- `event_risk_min_probability_addon_pct`
- `event_risk_min_rr_multiplier`
- `event_risk_reasons`
- `event_risk_matched_rule_ids`
- `event_risk_action_effect`

## Difference From Generic Overlay

- Generic overlay: manually choose `diagnostic_only`, `soft_adjust`, or `experimental_downgrade`.
- Conservative overlay shortcut: uses the calibrated config and only allows diagnostic/soft modes.
- Default production behavior: unchanged unless `use_conservative_event_overlay=true`.

## Paper Snapshot

`/signals/event-aware/conservative-overlay-paper-snapshot` compares the current baseline list vs conservative overlay:

- baseline exposure;
- overlay-adjusted exposure;
- exposure reduction;
- average multiplier;
- risk level counts;
- top risk rows.

This endpoint is read-only and writes no snapshots.

## Paper Tracking

Stored paper tracking is documented in `docs/conservative_event_overlay_paper_tracking.md`.

Key endpoints:

- `POST /signals/event-aware/conservative-overlay-paper-snapshots`
- `GET /signals/event-aware/conservative-overlay-paper-snapshots`
- `GET /signals/event-aware/conservative-overlay-paper-snapshots/{snapshot_id}`
- `POST /signals/event-aware/conservative-overlay-paper-snapshots/{snapshot_id}/evaluate`
- `GET /signals/event-aware/conservative-overlay-paper-dashboard`
- `/signals/event-aware/conservative-overlay-paper-tracking-page`

This layer writes only local paper snapshots. It does not place trades and does not change consumer defaults.

## Limitations

- Opt-in only.
- Research/paper-trading layer, not a default production control.
- No real trading operations.
- Historical calibration uses curated events and proxy backtest labels.
- No investment advice.
