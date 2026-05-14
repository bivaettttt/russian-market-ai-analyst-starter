from __future__ import annotations

from html import escape
from typing import Any


def _fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "—"

    if isinstance(value, float):
        text = f"{value:,.2f}".replace(",", " ")
    else:
        text = str(value)

    return escape(text + suffix)


def _status_label(status: str) -> str:
    if status == "added":
        return "Добавлена"
    if status == "removed":
        return "Удалена"
    return "Была / осталась"


def build_ai_report_compare_html(data: dict[str, Any]) -> str:
    left = data["left"]
    right = data["right"]
    summary = data["summary"]
    positions = data.get("positions") or []

    rows = []

    for item in positions:
        rows.append(
            "<tr>"
            f"<td><b>{escape(str(item.get('ticker', '—')))}</b></td>"
            f"<td>{escape(_status_label(str(item.get('status'))))}</td>"
            f"<td>{_fmt(item.get('old_value'), ' руб.')}</td>"
            f"<td>{_fmt(item.get('new_value'), ' руб.')}</td>"
            f"<td>{_fmt(item.get('value_delta'), ' руб.')}</td>"
            f"<td>{_fmt(item.get('old_weight_pct'), '%')}</td>"
            f"<td>{_fmt(item.get('new_weight_pct'), '%')}</td>"
            f"<td>{_fmt(item.get('weight_delta'), ' п.п.')}</td>"
            "</tr>"
        )

    position_rows = "\n".join(rows) or '<tr><td colspan="8">Нет данных по позициям</td></tr>'

    style = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Сравнение AI Report</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #eef0f3;
      color: #111827;
    }
    header {
      background: #111827;
      color: white;
      padding: 44px 32px;
    }
    header h1 {
      margin: 0 0 14px;
      font-size: 32px;
    }
    header a {
      color: #93c5fd;
      font-weight: 700;
      text-decoration: none;
    }
    main {
      padding: 28px 32px 60px;
    }
    .card {
      background: white;
      border-radius: 18px;
      padding: 24px;
      margin-bottom: 22px;
      box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }
    .metric {
      background: #f8fafc;
      border-radius: 14px;
      padding: 16px;
    }
    .metric small {
      display: block;
      color: #64748b;
      margin-bottom: 8px;
      font-weight: 700;
    }
    .metric b {
      font-size: 22px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th, td {
      padding: 12px 10px;
      border-bottom: 1px solid #e5e7eb;
      text-align: left;
      vertical-align: top;
    }
    th {
      color: #64748b;
      font-size: 13px;
    }
    .links a {
      color: #2563eb;
      font-weight: 700;
      text-decoration: none;
      margin-right: 10px;
    }
    .muted {
      color: #64748b;
    }
    .print-button {
      border: 0;
      border-radius: 10px;
      background: #2563eb;
      color: white;
      padding: 10px 14px;
      font-weight: 800;
      cursor: pointer;
    }
    @media print {
      header, .print-button { display: none; }
      body { background: white; }
      main { padding: 0; }
      .card {
        box-shadow: none;
        border: 1px solid #e5e7eb;
        break-inside: avoid;
      }
    }
  </style>
</head>
<body>
"""

    html = f"""
<header>
  <h1>Сравнение AI Report</h1>
  <div>
    <a href="/ai/reports/dashboard">← История отчётов</a>
    · <a href="{escape(left['view_url'])}">Отчёт #{escape(str(left['id']))}</a>
    · <a href="{escape(right['view_url'])}">Отчёт #{escape(str(right['id']))}</a>
  </div>
</header>

<main>
  <section class="card">
    <button class="print-button" onclick="window.print()">Печать / сохранить PDF</button>
    <h2>Отчёт #{escape(str(left['id']))} → отчёт #{escape(str(right['id']))}</h2>
    <p class="muted">
      Старый: {escape(str(left.get('created_at') or '—'))}
      · Новый: {escape(str(right.get('created_at') or '—'))}
    </p>
    <p class="links">
      <a href="{escape(left['markdown_url'])}">Markdown старого</a>
      <a href="{escape(right['markdown_url'])}">Markdown нового</a>
      <a href="/ai/report/compare.json?left_id={escape(str(left['id']))}&right_id={escape(str(right['id']))}">JSON сравнения</a>
    </p>
  </section>

  <section class="card">
    <h2>Ключевые изменения</h2>
    <div class="grid">
      <div class="metric">
        <small>Рынок</small>
        <b>{escape(str(summary.get('market_mood_old') or '—'))} → {escape(str(summary.get('market_mood_new') or '—'))}</b>
      </div>
      <div class="metric">
        <small>Стоимость портфеля</small>
        <b>{_fmt(summary.get('portfolio_value_old'), ' руб.')} → {_fmt(summary.get('portfolio_value_new'), ' руб.')}</b>
        <div class="muted">Δ {_fmt(summary.get('portfolio_value_delta'), ' руб.')}</div>
      </div>
      <div class="metric">
        <small>Дневной PnL</small>
        <b>{_fmt(summary.get('daily_pnl_abs_old'), ' руб.')} → {_fmt(summary.get('daily_pnl_abs_new'), ' руб.')}</b>
        <div class="muted">Δ {_fmt(summary.get('daily_pnl_abs_delta'), ' руб.')}</div>
      </div>
    </div>
  </section>

  <section class="card">
    <h2>Позиции</h2>
    <table>
      <thead>
        <tr>
          <th>Тикер</th>
          <th>Статус</th>
          <th>Старая стоимость</th>
          <th>Новая стоимость</th>
          <th>Δ стоимость</th>
          <th>Старый вес</th>
          <th>Новый вес</th>
          <th>Δ вес</th>
        </tr>
      </thead>
      <tbody>
        {position_rows}
      </tbody>
    </table>
  </section>
</main>
</body>
</html>
"""

    return style + html
