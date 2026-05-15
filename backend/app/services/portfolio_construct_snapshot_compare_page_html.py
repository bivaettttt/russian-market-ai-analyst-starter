from __future__ import annotations

from html import escape
from typing import Any


def _e(value: Any) -> str:
    return escape(str(value if value is not None else "—"))


def _money(value: Any) -> str:
    try:
        return f"{float(value):,.2f} ₽".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "—"


def _num(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "—"


def _value_class(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""

    if number > 0:
        return "good"
    if number < 0:
        return "bad"
    return ""


def _status_class(status: str) -> str:
    if status == "added":
        return "good"
    if status == "removed":
        return "bad"
    return ""


def _rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<tr><td colspan="15" class="muted">Нет данных для сравнения.</td></tr>'

    html_rows = []

    for row in rows:
        html_rows.append(
            f"""
            <tr>
              <td><a href="{_e(row.get('ticker_url'))}"><b>{_e(row.get('ticker'))}</b></a></td>
              <td>{_e(row.get('name'))}</td>
              <td class="{_status_class(str(row.get('status')))}"><b>{_e(row.get('status_label'))}</b></td>
              <td>{_e(row.get('old_action'))}</td>
              <td>{_e(row.get('new_action'))}</td>
              <td>{_e(row.get('old_quantity'))}</td>
              <td>{_e(row.get('new_quantity'))}</td>
              <td class="{_value_class(row.get('delta_quantity'))}"><b>{_e(row.get('delta_quantity'))}</b></td>
              <td>{_money(row.get('old_value'))}</td>
              <td>{_money(row.get('new_value'))}</td>
              <td class="{_value_class(row.get('delta_value'))}"><b>{_money(row.get('delta_value'))}</b></td>
              <td>{_pct(row.get('old_weight_pct'))}</td>
              <td>{_pct(row.get('new_weight_pct'))}</td>
              <td class="{_value_class(row.get('delta_weight_pct'))}"><b>{_pct(row.get('delta_weight_pct'))}</b></td>
              <td class="{_value_class(row.get('delta_score'))}">{_num(row.get('delta_score'))}</td>
            </tr>
            """
        )

    return "\n".join(html_rows)


def build_portfolio_construct_snapshot_compare_page_html(data: dict[str, Any]) -> str:
    left = data.get("left") or {}
    right = data.get("right") or {}
    summary = data.get("summary") or {}
    rows = data.get("rows") or []

    left_summary = left.get("summary") or {}
    right_summary = right.get("summary") or {}

    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Сравнение snapshot-ов портфеля</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {{
      --bg: #f6f7fb;
      --card: #ffffff;
      --text: #111827;
      --muted: #6b7280;
      --border: #e5e7eb;
      --blue: #2563eb;
      --green: #15803d;
      --red: #b91c1c;
      --shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}

    .wrap {{
      max-width: 1480px;
      margin: 0 auto;
      padding: 28px;
    }}

    .top {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 18px;
    }}

    h1 {{
      margin: 0 0 8px;
      font-size: 30px;
      letter-spacing: -0.03em;
    }}

    h2 {{
      margin: 0 0 14px;
      font-size: 20px;
    }}

    a {{
      color: var(--blue);
      text-decoration: none;
    }}

    .muted {{ color: var(--muted); }}
    .small {{ font-size: 13px; }}
    .good {{ color: var(--green); }}
    .bad {{ color: var(--red); }}

    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: var(--shadow);
      padding: 20px;
      margin-bottom: 18px;
    }}

    .nav {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}

    .button {{
      border: 0;
      border-radius: 12px;
      background: #e5e7eb;
      color: #111827;
      padding: 10px 14px;
      font-weight: 700;
      display: inline-block;
    }}

    .metrics {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 12px;
    }}

    .metric {{
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px;
      background: #fafafa;
    }}

    .label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }}

    .value {{
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.02em;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}

    th, td {{
      padding: 10px 9px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
    }}

    th {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      background: #fafafa;
      position: sticky;
      top: 0;
      z-index: 1;
    }}

    .table-wrap {{
      overflow-x: auto;
    }}

    @media (max-width: 1000px) {{
      .top {{ display: block; }}
      .nav {{ justify-content: flex-start; margin-top: 12px; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <h1>Сравнение snapshot-ов портфеля</h1>
        <div class="muted">
          Старый: #{_e(left.get('id'))} · Новый: #{_e(right.get('id'))}
        </div>
      </div>

      <div class="nav">
        <a class="button" href="/portfolio/construct/history">История</a>
        <a class="button" href="/portfolio/construct/demo">Конструктор</a>
        <a class="button" href="/portfolio/construct/compare.json?left_id={_e(left.get('id'))}&right_id={_e(right.get('id'))}" target="_blank">JSON</a>
        <a class="button" href="/dashboard">Рынок</a>
      </div>
    </div>

    <section class="card">
      <h2>Итоги изменения</h2>

      <div class="metrics">
        <div class="metric">
          <div class="label">Добавлено</div>
          <div class="value good">{_e(summary.get('added'))}</div>
        </div>

        <div class="metric">
          <div class="label">Удалено</div>
          <div class="value bad">{_e(summary.get('removed'))}</div>
        </div>

        <div class="metric">
          <div class="label">Осталось</div>
          <div class="value">{_e(summary.get('kept'))}</div>
        </div>

        <div class="metric">
          <div class="label">Δ кэш</div>
          <div class="value {_value_class(summary.get('cash_delta'))}">{_money(summary.get('cash_delta'))}</div>
          <div class="muted small">Δ {_pct(summary.get('cash_pct_delta'))}</div>
        </div>

        <div class="metric">
          <div class="label">Δ risk/reward</div>
          <div class="value {_value_class(summary.get('risk_reward_delta'))}">{_num(summary.get('risk_reward_delta'))}</div>
          <div class="muted small">{_num(summary.get('old_risk_reward_ratio'))} → {_num(summary.get('new_risk_reward_ratio'))}</div>
        </div>

        <div class="metric">
          <div class="label">Δ инвестировано</div>
          <div class="value {_value_class(summary.get('invested_delta'))}">{_money(summary.get('invested_delta'))}</div>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>Старый vs новый</h2>

      <div class="metrics">
        <div class="metric">
          <div class="label">Старый snapshot</div>
          <div class="value">#{_e(left.get('id'))}</div>
          <div class="muted small">{_e(left.get('created_at'))}</div>
        </div>

        <div class="metric">
          <div class="label">Новый snapshot</div>
          <div class="value">#{_e(right.get('id'))}</div>
          <div class="muted small">{_e(right.get('created_at'))}</div>
        </div>

        <div class="metric">
          <div class="label">Позиции</div>
          <div class="value">{_e(left_summary.get('positions_count'))} → {_e(right_summary.get('positions_count'))}</div>
        </div>

        <div class="metric">
          <div class="label">Кэш</div>
          <div class="value">{_money(left_summary.get('cash'))} → {_money(right_summary.get('cash'))}</div>
        </div>

        <div class="metric">
          <div class="label">Risk/reward</div>
          <div class="value">{_num(left_summary.get('risk_reward_ratio'))} → {_num(right_summary.get('risk_reward_ratio'))}</div>
        </div>

        <div class="metric">
          <div class="label">Качество</div>
          <div class="value" style="font-size:16px;">{_e(left.get('quality_mode'))} → {_e(right.get('quality_mode'))}</div>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>Изменения по бумагам</h2>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Тикер</th>
              <th>Название</th>
              <th>Статус</th>
              <th>Action old</th>
              <th>Action new</th>
              <th>Кол-во old</th>
              <th>Кол-во new</th>
              <th>Δ кол-во</th>
              <th>Сумма old</th>
              <th>Сумма new</th>
              <th>Δ сумма</th>
              <th>Вес old</th>
              <th>Вес new</th>
              <th>Δ вес</th>
              <th>Δ score</th>
            </tr>
          </thead>
          <tbody>
            {_rows(rows)}
          </tbody>
        </table>
      </div>
    </section>
  </div>
</body>
</html>"""
