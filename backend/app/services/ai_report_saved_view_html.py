from __future__ import annotations

import html
from typing import Any


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _text(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def _section(title: str, body: Any) -> str:
    return f"""
      <div class="section">
        <h3>{_e(title)}</h3>
        <p>{_e(_text(body))}</p>
      </div>
    """


def _fmt_rub(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.1f} руб.".replace(",", " ")
    except Exception:
        return f"{value} руб."


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f}%"
    except Exception:
        return f"{value}%"


def _pnl_class(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return ""
    if number > 0:
        return "good"
    if number < 0:
        return "bad"
    return ""


def _positions_table(portfolio: dict[str, Any]) -> str:
    rows = portfolio.get("positions") or []

    if not rows:
        return "<p class='muted'>Позиций в отчёте нет.</p>"

    body = []

    for item in rows:
        pnl_class = _pnl_class(item.get("daily_pnl_pct"))

        body.append(f"""
          <tr>
            <td><b>{_e(item.get("ticker"))}</b></td>
            <td>{_e(item.get("sector"))}</td>
            <td>{_e(item.get("quantity"))}</td>
            <td>{_fmt_rub(item.get("last_close"))}</td>
            <td>{_fmt_rub(item.get("current_value"))}</td>
            <td>{_fmt_pct(item.get("weight_pct"))}</td>
            <td class="{pnl_class}">{_fmt_pct(item.get("daily_pnl_pct"))}</td>
          </tr>
        """)

    return f"""
      <table>
        <thead>
          <tr>
            <th>Тикер</th>
            <th>Сектор</th>
            <th>Кол-во</th>
            <th>Цена</th>
            <th>Стоимость</th>
            <th>Доля</th>
            <th>День</th>
          </tr>
        </thead>
        <tbody>
          {''.join(body)}
        </tbody>
      </table>
    """


def _sectors_table(portfolio: dict[str, Any]) -> str:
    rows = portfolio.get("sector_allocation") or []

    if not rows:
        return "<p class='muted'>Секторной разбивки нет.</p>"

    body = []

    for item in rows:
        body.append(f"""
          <tr>
            <td><b>{_e(item.get("sector"))}</b></td>
            <td>{_fmt_rub(item.get("value"))}</td>
            <td>{_fmt_pct(item.get("weight_pct"))}</td>
          </tr>
        """)

    return f"""
      <table>
        <thead>
          <tr>
            <th>Сектор</th>
            <th>Стоимость</th>
            <th>Доля</th>
          </tr>
        </thead>
        <tbody>
          {''.join(body)}
        </tbody>
      </table>
    """


def _events_table(report: dict[str, Any]) -> str:
    events = ((report.get("events") or {}).get("top_events")) or []

    if not events:
        return "<p class='muted'>Событий в отчёте нет.</p>"

    body = []

    for item in events:
        url = item.get("url")
        title = _e(item.get("title"))
        title_html = f'<a href="{_e(url)}" target="_blank" rel="noopener">{title}</a>' if url else title

        body.append(f"""
          <tr>
            <td>{title_html}</td>
            <td>{_e(item.get("event_type"))}</td>
            <td>{_e(item.get("importance"))}/10</td>
            <td>{_e(item.get("impact"))}</td>
          </tr>
        """)

    return f"""
      <table>
        <thead>
          <tr>
            <th>Событие</th>
            <th>Тип</th>
            <th>Важность</th>
            <th>Влияние</th>
          </tr>
        </thead>
        <tbody>
          {''.join(body)}
        </tbody>
      </table>
    """


def build_ai_report_saved_view_html(snapshot: dict[str, Any]) -> str:
    report = snapshot.get("report") or {}
    markdown = snapshot.get("markdown") or ""
    sections = report.get("sections") or {}
    market = report.get("market") or {}
    portfolio = report.get("portfolio") or {}

    report_id = snapshot.get("id")
    title = report.get("title") or snapshot.get("title") or "AI Report российского рынка"
    date = report.get("date") or snapshot.get("report_date") or "—"

    market_mood = market.get("market_mood") or "—"
    total_value = portfolio.get("total_value")
    daily_abs = portfolio.get("daily_pnl_abs")
    daily_pct = portfolio.get("daily_pnl_pct")

    total_value_text = _fmt_rub(total_value)

    day_text = "—"
    if daily_abs is not None:
        day_text = _fmt_rub(daily_abs)
        if daily_pct is not None:
            day_text += f" / {_fmt_pct(daily_pct)}"

    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>{_e(title)}</title>
  <style>
    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      font-family: Inter, Arial, sans-serif;
      background: #eef0f3;
      color: #111827;
    }}

    header {{
      background: #111827;
      color: white;
      padding: 42px 32px;
    }}

    header h1 {{
      margin: 0 0 14px;
      font-size: 30px;
    }}

    a {{
      color: #2563eb;
      font-weight: 800;
      text-decoration: none;
    }}

    header a {{
      color: #93c5fd;
    }}

    main {{
      padding: 24px 32px 48px;
    }}

    .card {{
      background: white;
      border-radius: 18px;
      padding: 24px;
      margin-bottom: 20px;
      box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
    }}

    .muted {{
      color: #64748b;
    }}

    .metrics {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin-top: 18px;
    }}

    .metric {{
      background: #f8fafc;
      border-radius: 14px;
      padding: 16px;
    }}

    .metric .label {{
      color: #64748b;
      font-size: 13px;
      margin-bottom: 8px;
    }}

    .metric .value {{
      font-weight: 800;
      font-size: 22px;
    }}

    .section {{
      background: #f8fafc;
      border-left: 4px solid #2563eb;
      border-radius: 14px;
      padding: 16px;
      margin-top: 14px;
    }}

    .section h3 {{
      margin: 0 0 10px;
    }}

    .section p {{
      margin: 0;
      white-space: pre-line;
      line-height: 1.45;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
    }}

    th, td {{
      padding: 11px 10px;
      border-bottom: 1px solid #e5e7eb;
      text-align: left;
      vertical-align: top;
    }}

    th {{
      color: #64748b;
      font-size: 13px;
    }}

    .good {{
      color: #15803d;
      font-weight: 800;
    }}

    .bad {{
      color: #dc2626;
      font-weight: 800;
    }}

    pre {{
      background: #111827;
      color: #f8fafc;
      border-radius: 12px;
      padding: 18px;
      overflow: auto;
      white-space: pre-wrap;
      line-height: 1.45;
    }}

    details summary {{
      cursor: pointer;
      font-size: 18px;
      margin-bottom: 10px;
    }}

    .print-actions {{
      margin-top: 18px;
    }}

    .print-button {{
      display: inline-block;
      background: #2563eb;
      color: white;
      border: 0;
      border-radius: 10px;
      padding: 10px 14px;
      font-weight: 800;
      cursor: pointer;
    }}

    @media print {{
      body {{
        background: white;
      }}

      header {{
        padding: 24px 0;
        background: white;
        color: #111827;
      }}

      header a,
      .print-actions,
      details {{
        display: none !important;
      }}

      main {{
        padding: 0;
      }}

      .card {{
        box-shadow: none;
        border: 1px solid #e5e7eb;
        break-inside: avoid;
        page-break-inside: avoid;
      }}

      table {{
        font-size: 12px;
      }}
    }}

  </style>
</head>
<body>
  <header>
    <h1>{_e(title)}</h1>
    <div>
      <a href="/dashboard">← Рынок</a> ·
      <a href="/ai/reports/dashboard">История отчётов</a> ·
      <a href="/ai/reports/{_e(report_id)}.md">Markdown</a> ·
      <a href="/ai/reports/{_e(report_id)}">JSON</a>
    </div>
  </header>

  <main>
    <section class="card">
      <h2>Отчёт #{_e(report_id)}</h2>
      <p class="muted">Дата отчёта: {_e(date)} · Создан: {_e(snapshot.get("created_at"))}</p>

      <div class="print-actions">
        <button class="print-button" onclick="window.print()">Печать / сохранить PDF</button>
      </div>

      <div class="metrics">
        <div class="metric">
          <div class="label">Рынок</div>
          <div class="value">{_e(market_mood)}</div>
        </div>
        <div class="metric">
          <div class="label">Стоимость портфеля</div>
          <div class="value">{_e(total_value_text)}</div>
        </div>
        <div class="metric">
          <div class="label">День</div>
          <div class="value">{_e(day_text)}</div>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>Позиции портфеля</h2>
      {_positions_table(portfolio)}
    </section>

    <section class="card">
      <h2>Сектора</h2>
      {_sectors_table(portfolio)}
    </section>

    <section class="card">
      <h2>Главные события</h2>
      {_events_table(report)}
    </section>

    <section class="card">
      <h2>Структура отчёта</h2>
      {_section("1. Рыночный фон", sections.get("market_context"))}
      {_section("2. Главные события", sections.get("important_events"))}
      {_section("3. Рыночные сигналы", sections.get("market_signals"))}
      {_section("4. Портфель", sections.get("portfolio_context"))}
      {_section("5. Риски", sections.get("risk_review"))}
      {_section("6. Watchlist", sections.get("watchlist"))}
      {_section("7. Вывод дня", sections.get("conclusion"))}
    </section>

    <section class="card">
      <details>
        <summary><b>Полный Markdown</b></summary>
        <pre>{_e(markdown)}</pre>
      </details>
    </section>
  </main>
</body>
</html>
"""
