from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.models import AIReportSnapshot
from app.services.ai_report import build_ai_report
from app.services.ai_report_export import build_ai_report_markdown


DEFAULT_POSITIONS = [
    {"ticker": "SBER", "quantity": 10},
    {"ticker": "LKOH", "quantity": 1},
    {"ticker": "GAZP", "quantity": 50},
    {"ticker": "PLZL", "quantity": 1},
]


def _run_moex_ingest() -> dict[str, Any]:
    from datetime import date, timedelta

    backend_dir = Path(__file__).resolve().parents[2]

    tickers = [
        "SBER", "GAZP", "LKOH", "PLZL", "ROSN",
        "NVTK", "TATN", "VTBR", "CHMF", "ALRS",
        "GMKN", "MOEX",
    ]

    to_date = date.today()
    from_date = to_date - timedelta(days=220)

    results: list[dict[str, Any]] = []

    for ticker in tickers:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "app.tasks.ingest_moex",
                    ticker,
                    "--from-date",
                    from_date.isoformat(),
                    "--to-date",
                    to_date.isoformat(),
                    "--board",
                    "TQBR",
                ],
                cwd=backend_dir,
                capture_output=True,
                text=True,
                timeout=180,
            )

            results.append(
                {
                    "ticker": ticker,
                    "ok": result.returncode == 0,
                    "returncode": result.returncode,
                    "stdout": result.stdout[-1000:],
                    "stderr": result.stderr[-1000:],
                }
            )

        except Exception as error:
            results.append(
                {
                    "ticker": ticker,
                    "ok": False,
                    "error": str(error),
                }
            )

    failed = [row for row in results if not row.get("ok")]

    return {
        "ok": len(failed) == 0,
        "tickers_total": len(tickers),
        "tickers_ok": len(tickers) - len(failed),
        "tickers_failed": len(failed),
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "results": results,
    }

def _post_local_json(path: str, timeout: int = 90) -> dict[str, Any]:
    url = f"http://127.0.0.1:8000{path}"
    request = Request(url, data=b"", method="POST")

    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            try:
                return {
                    "ok": True,
                    "status": response.status,
                    "data": json.loads(raw),
                }
            except Exception:
                return {
                    "ok": True,
                    "status": response.status,
                    "raw": raw[-4000:],
                }

    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
        }


def _save_report_snapshot(
    db: Session,
    report: dict[str, Any],
    markdown: str,
    positions: list[dict[str, Any]],
) -> AIReportSnapshot:
    row = AIReportSnapshot(
        report_date=str(report.get("date") or ""),
        title=str(report.get("title") or "AI Report российского рынка"),
        portfolio_json=json.dumps({"positions": positions}, ensure_ascii=False),
        report_json=json.dumps(report, ensure_ascii=False, default=str),
        markdown=markdown,
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return row


def run_system_update_and_report(
    db: Session,
    positions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if positions is None:
        positions = DEFAULT_POSITIONS

    steps: list[dict[str, Any]] = []

    moex_result = _run_moex_ingest()
    steps.append({
        "step": "moex_ingest",
        **moex_result,
    })

    rss_result = _post_local_json("/ingest/rss/defaults?limit_per_source=5")
    steps.append({
        "step": "rss_ingest",
        **rss_result,
    })

    report = build_ai_report(
        db=db,
        positions=positions,
    )

    markdown = build_ai_report_markdown(report)

    snapshot = _save_report_snapshot(
        db=db,
        report=report,
        markdown=markdown,
        positions=positions,
    )

    return {
        "ok": True,
        "message": "Данные обновлены, AI Report собран и сохранён.",
        "steps": steps,
        "report": {
            "id": snapshot.id,
            "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
            "report_date": snapshot.report_date,
            "title": snapshot.title,
            "markdown_url": f"/ai/reports/{snapshot.id}.md",
            "detail_url": f"/ai/reports/{snapshot.id}",
        },
    }
