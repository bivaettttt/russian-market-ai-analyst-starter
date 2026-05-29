# Official Live Validation Hygiene

Official paper validation now separates local snapshots into operational classes so legacy/test data does not pollute the official quality report.

## Snapshot Types

- `official`: snapshot name starts with `official-` or `official-daily` and exposure is positive.
- `test`: snapshot name/source contains test markers such as `manual-test`, `exposure-fix-test`, or `cli-daily-test`.
- `manual`: positive-exposure local snapshot that is not official or test.
- `legacy`: zero/missing exposure or missing post-fix position sizing metadata.

Current official example: `official-daily-2026-05-29`.

## Official-Only Views

Use official-only filters for live validation decisions:

```text
GET /signals/event-aware/conservative-overlay-quality-report?official_only=true
GET /signals/event-aware/conservative-overlay-paper-snapshots?official_only=true
GET /signals/live-paper-validation/official-summary
```

The quality report page defaults to official validation view. Test and legacy snapshots remain inspectable with filters, but are excluded from the official summary.

## Cleanup

Cleanup is explicit and dry-run by default:

```bash
curl -X POST "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-cleanup?dry_run=true&delete_legacy_zero_exposure=true&delete_test_snapshots=true"

cd backend
python3 -m app.tasks.event_overlay_paper_tracking cleanup --legacy-zero-exposure --test-snapshots
```

Actual delete requires `dry_run=false` or CLI `--delete`. Official snapshots are kept by default.

## Recommended Workflow

1. Refresh candles and verify market freshness.
2. Start an official daily snapshot.
3. Keep manual/test snapshots separate.
4. Review official-only quality reports.
5. Dry-run cleanup before deleting legacy zero-exposure snapshots.

This is paper validation only. It creates no real orders and does not change production recommendations.
