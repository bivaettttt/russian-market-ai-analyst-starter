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


def _rr_class(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""

    if number < 0.8:
        return "bad"
    if number < 1.2:
        return "warn"
    return "good"


def _rows_positions(positions: list[dict[str, Any]]) -> str:
    if not positions:
        return '<tr><td colspan="17" class="muted">Позиции отсутствуют.</td></tr>'

    rows = []
    for row in positions:
        reasons = row.get("reasons") or []
        reasons_html = "<br>".join(_e(item) for item in reasons[:3]) or "—"

        rows.append(
            f"""
            <tr>
              <td><a href="{_e(row.get('ticker_url') or '#')}"><b>{_e(row.get('ticker'))}</b></a></td>
              <td>{_e(row.get('name'))}</td>
              <td>{_e(row.get('action'))}</td>
              <td>{_e(row.get('label'))}</td>
              <td><b>{_money(row.get('price'))}</b></td>
              <td>{_e(row.get('lot_size'))}</td>
              <td>{_e(row.get('lots'))}</td>
              <td><b>{_e(row.get('quantity'))}</b></td>
              <td><b>{_money(row.get('value'))}</b></td>
              <td>{_pct(row.get('weight_pct'))}</td>
              <td>{_num(row.get('score'))}</td>
              <td>{_pct(row.get('confidence_pct'))}</td>
              <td>{_money(row.get('target_price'))}</td>
              <td class="good">{_pct(row.get('target_upside_pct'))}<br><span class="small">{_money(row.get('target_upside_rub'))}</span></td>
              <td>{_money(row.get('stop_loss'))}</td>
              <td class="bad">{_pct(row.get('stop_downside_pct'))}<br><span class="small">{_money(row.get('stop_downside_rub'))}</span></td>
              <td class="small">{reasons_html}</td>
            </tr>
            """
        )

    return "\n".join(rows)


def _rows_excluded(excluded: list[dict[str, Any]]) -> str:
    if not excluded:
        return '<tr><td colspan="7" class="muted">Исключённых бумаг нет.</td></tr>'

    rows = []
    for row in excluded:
        reasons = row.get("reasons") or []
        reasons_html = "<br>".join(_e(item) for item in reasons[:3]) or "—"

        rows.append(
            f"""
            <tr>
              <td><a href="{_e(row.get('ticker_url') or '#')}"><b>{_e(row.get('ticker'))}</b></a></td>
              <td>{_e(row.get('name'))}</td>
              <td>{_e(row.get('action'))}</td>
              <td>{_e(row.get('label'))}</td>
              <td>{_money(row.get('price'))}</td>
              <td>{_e(row.get('reason'))}</td>
              <td class="small">{reasons_html}</td>
            </tr>
            """
        )

    return "\n".join(rows)


def build_portfolio_construct_snapshot_detail_page_html(snapshot: dict[str, Any]) -> str:
    summary = snapshot.get("summary") or {}
    positions = snapshot.get("positions") or []
    excluded = snapshot.get("excluded") or []
    result = snapshot.get("result") or {}

    snapshot_id = snapshot.get("id")
    rr = summary.get("risk_reward_ratio")
    rr_label = summary.get("risk_reward_label") or "нет данных"
    rr_class = _rr_class(rr)

    conclusion = summary.get("portfolio_conclusion") or "Вывод не сформирован."

    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Snapshot портфеля #{_e(snapshot_id)}</title>
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
      --amber: #b45309;
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
      align-items: flex-start;
      gap: 16px;
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
    .warn {{ color: var(--amber); }}

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
      flex-wrap: wrap;
      gap: 10px;
      justify-content: flex-end;
    }}

    .button {{
      border: 0;
      border-radius: 12px;
      background: var(--blue);
      color: white;
      padding: 10px 14px;
      font-weight: 700;
      cursor: pointer;
      display: inline-block;
    }}

    .button.secondary {{
      background: #e5e7eb;
      color: #111827;
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

    .conclusion {{
      font-size: 16px;
      line-height: 1.55;
      margin: 0;
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
        <h1>Snapshot портфеля #{_e(snapshot_id)}</h1>
        <div class="muted">
          Создан: {_e(snapshot.get('created_at'))}
        </div>
      </div>

      <div class="nav">
        <a class="button secondary" href="/portfolio/construct/history">История</a>
        <a class="button secondary" href="/portfolio/construct/demo">Конструктор</a>
        <a class="button secondary" href="/portfolio/construct/snapshots/{_e(snapshot_id)}" target="_blank">JSON</a>
        <a class="button secondary" href="/dashboard">Рынок</a>
      </div>
    </div>

    <section class="card">
      <h2>Параметры и итог</h2>

      <div class="metrics">
        <div class="metric">
          <div class="label">Бюджет</div>
          <div class="value">{_money(snapshot.get('budget'))}</div>
        </div>

        <div class="metric">
          <div class="label">Инвестировано</div>
          <div class="value">{_money(summary.get('invested'))}</div>
        </div>

        <div class="metric">
          <div class="label">Кэш</div>
          <div class="value">{_money(summary.get('cash'))}</div>
          <div class="muted small">{_pct(summary.get('cash_pct'))}</div>
        </div>

        <div class="metric">
          <div class="label">Позиций</div>
          <div class="value">{_e(summary.get('positions_count') or snapshot.get('positions_count'))}</div>
        </div>

        <div class="metric">
          <div class="label">Risk/reward</div>
          <div class="value {rr_class}">{_num(rr)} · {_e(rr_label)}</div>
        </div>

        <div class="metric">
          <div class="label">Модель</div>
          <div class="value" style="font-size:16px;">{_e(snapshot.get('model_version'))}</div>
        </div>
      </div>

      <p class="muted small" style="margin-top:16px;">
        Риск-профиль: <b>{_e(snapshot.get('risk_profile'))}</b> ·
        Горизонт: <b>{_e(snapshot.get('horizon'))}</b> ·
        Качество отбора: <b>{_e(snapshot.get('quality_mode'))}</b>
      </p>
    </section>

    <section class="card">
      <h2>Вывод</h2>
      <p class="conclusion">{_e(conclusion)}</p>
    </section>

    <section class="card">
      <h2>Позиции</h2>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Тикер</th>
              <th>Название</th>
              <th>Action</th>
              <th>Сигнал</th>
              <th>Цена</th>
              <th>Лот</th>
              <th>Лоты</th>
              <th>Кол-во</th>
              <th>Сумма</th>
              <th>Вес</th>
              <th>Score</th>
              <th>Увер.</th>
              <th>Цель</th>
              <th>Потенциал</th>
              <th>Стоп</th>
              <th>Риск</th>
              <th>Причины</th>
            </tr>
          </thead>
          <tbody>
            {_rows_positions(positions)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <h2>Исключённые бумаги</h2>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Тикер</th>
              <th>Название</th>
              <th>Action</th>
              <th>Сигнал</th>
              <th>Цена</th>
              <th>Причина исключения</th>
              <th>Детали</th>
            </tr>
          </thead>
          <tbody>
            {_rows_excluded(excluded)}
          </tbody>
        </table>
      </div>
    </section>
  </div>
</body>
</html>"""
