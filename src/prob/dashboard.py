from pathlib import Path
from datetime import datetime, date, timedelta
import csv
import json

from flask import Flask, request, render_template_string, jsonify

app = Flask(__name__)

DATA_DIR = Path("/home/pi/microbit_data")


HTML = """
<!doctype html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>micro:bit logger</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="{{ refresh_seconds }}">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            background: #0b0b0b;
            color: #eeeeee;
            margin: 0;
            padding: 24px;
        }
        h1 {
            font-size: 24px;
            margin-bottom: 4px;
        }
        .muted {
            color: #999;
            font-size: 14px;
        }
        .topbar {
            display: flex;
            justify-content: space-between;
            gap: 16px;
            flex-wrap: wrap;
            align-items: flex-end;
            margin-top: 18px;
        }
        form {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: flex-end;
            background: #151515;
            border: 1px solid #2a2a2a;
            border-radius: 14px;
            padding: 12px;
        }
        label {
            display: flex;
            flex-direction: column;
            gap: 4px;
            color: #aaa;
            font-size: 12px;
        }
        input, select, button {
            background: #0f0f0f;
            color: #eee;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 8px 10px;
            font-size: 14px;
        }
        button {
            cursor: pointer;
            font-weight: 700;
        }
        a.pill {
            color: #eee;
            text-decoration: none;
            border: 1px solid #333;
            border-radius: 999px;
            padding: 8px 10px;
            background: #151515;
            font-size: 14px;
        }
        .quick {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 12px;
            margin-top: 24px;
        }
        .card {
            background: #151515;
            border: 1px solid #2a2a2a;
            border-radius: 14px;
            padding: 16px;
        }
        .label {
            color: #aaa;
            font-size: 13px;
            margin-bottom: 6px;
        }
        .value {
            font-size: 28px;
            font-weight: 700;
        }
        .ok { color: #8fff8f; }
        .warn { color: #ffd166; }
        .bad { color: #ff6b6b; }
        .chart-card {
            background: #151515;
            border: 1px solid #2a2a2a;
            border-radius: 14px;
            padding: 16px;
            margin-top: 24px;
        }
        .chart-wrap {
            height: 320px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 24px;
            background: #151515;
            border-radius: 14px;
            overflow: hidden;
        }
        th, td {
            padding: 10px;
            border-bottom: 1px solid #2a2a2a;
            text-align: left;
            font-size: 14px;
        }
        th {
            color: #aaa;
            font-weight: 600;
            background: #1d1d1d;
        }
        tr:last-child td {
            border-bottom: none;
        }
        .footer {
            margin-top: 24px;
            color: #777;
            font-size: 13px;
        }
        @media (max-width: 700px) {
            body { padding: 14px; }
            .chart-wrap { height: 260px; }
            table { display: block; overflow-x: auto; white-space: nowrap; }
        }
    </style>
</head>
<body>
    <h1>micro:bit logger</h1>
    <div class="muted">Dashboard local Raspberry Pi — rafraîchissement toutes les {{ refresh_seconds }} secondes</div>

    <div class="topbar">
        <form method="get" action="/">
            <label>
                Début
                <input type="date" name="start" value="{{ start_date }}">
            </label>
            <label>
                Fin
                <input type="date" name="end" value="{{ end_date }}">
            </label>
            <label>
                Métrique
                <select name="metric">
                    <option value="temperature_c" {% if metric == "temperature_c" %}selected{% endif %}>Température</option>
                    <option value="light_level" {% if metric == "light_level" %}selected{% endif %}>Luminosité</option>
                    <option value="sound_level" {% if metric == "sound_level" %}selected{% endif %}>Son</option>
                </select>
            </label>
            <label>
                Points
                <select name="limit">
                    <option value="50" {% if limit == 50 %}selected{% endif %}>50</option>
                    <option value="100" {% if limit == 100 %}selected{% endif %}>100</option>
                    <option value="250" {% if limit == 250 %}selected{% endif %}>250</option>
                    <option value="500" {% if limit == 500 %}selected{% endif %}>500</option>
                </select>
            </label>
            <button type="submit">Afficher</button>
        </form>

        <div class="quick">
            <a class="pill" href="/?period=today&metric={{ metric }}&limit={{ limit }}">Aujourd'hui</a>
            <a class="pill" href="/?period=7d&metric={{ metric }}&limit={{ limit }}">7 jours</a>
            <a class="pill" href="/?period=30d&metric={{ metric }}&limit={{ limit }}">30 jours</a>
        </div>
    </div>

    {% if not latest %}
        <div class="card" style="margin-top:24px;">
            <div class="value warn">Aucune donnée</div>
            <p class="muted">Aucune donnée trouvée dans {{ data_dir }} pour la période sélectionnée.</p>
        </div>
    {% else %}
        <div class="grid">
            <div class="card">
                <div class="label">État</div>
                <div class="value {{ status_class }}">{{ status }}</div>
            </div>
            <div class="card">
                <div class="label">Capteur</div>
                <div class="value">{{ latest.device_id }}</div>
            </div>
            <div class="card">
                <div class="label">Température</div>
                <div class="value">{{ latest.temperature_c }} °C</div>
            </div>
            <div class="card">
                <div class="label">Luminosité</div>
                <div class="value">{{ latest.light_level }}</div>
            </div>
            <div class="card">
                <div class="label">Son</div>
                <div class="value">{{ latest.sound_level }}</div>
            </div>
            <div class="card">
                <div class="label">Dernière mesure</div>
                <div class="value" style="font-size:18px;">{{ latest.raspberry_timestamp }}</div>
            </div>
        </div>

        <div class="chart-card">
            <div class="label">Graphique — {{ metric_label }}</div>
            <div class="chart-wrap">
                <canvas id="sensorChart"></canvas>
            </div>
            <noscript>
                <p class="muted">JavaScript est nécessaire pour afficher le graphique.</p>
            </noscript>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Heure Raspberry</th>
                    <th>ID</th>
                    <th>Seq</th>
                    <th>Uptime ms</th>
                    <th>Temp °C</th>
                    <th>Lumière</th>
                    <th>Son</th>
                </tr>
            </thead>
            <tbody>
                {% for row in table_rows %}
                <tr>
                    <td>{{ row.raspberry_timestamp }}</td>
                    <td>{{ row.device_id }}</td>
                    <td>{{ row.seq }}</td>
                    <td>{{ row.microbit_uptime_ms }}</td>
                    <td>{{ row.temperature_c }}</td>
                    <td>{{ row.light_level }}</td>
                    <td>{{ row.sound_level }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <div class="footer">
            Période : {{ start_date }} → {{ end_date }} —
            fichiers lus : {{ csv_count }} —
            points affichés : {{ chart_points|length }} —
            dernière actualisation serveur : {{ server_time }}
        </div>

        <script>
            const chartPoints = {{ chart_points_json | safe }};
            const labels = chartPoints.map(p => p.label);
            const values = chartPoints.map(p => p.value);

            const ctx = document.getElementById("sensorChart");

            new Chart(ctx, {
                type: "line",
                data: {
                    labels,
                    datasets: [{
                        label: "{{ metric_label }}",
                        data: values,
                        tension: 0.25,
                        pointRadius: 2,
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    scales: {
                        x: {
                            ticks: {
                                maxTicksLimit: 8,
                                color: "#999"
                            },
                            grid: {
                                color: "#222"
                            }
                        },
                        y: {
                            ticks: {
                                color: "#999"
                            },
                            grid: {
                                color: "#222"
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            labels: {
                                color: "#eee"
                            }
                        },
                        tooltip: {
                            mode: "index",
                            intersect: false
                        }
                    }
                }
            });
        </script>
    {% endif %}
</body>
</html>
"""


METRICS = {
    "temperature_c": "Température °C",
    "light_level": "Luminosité",
    "sound_level": "Son",
}


def parse_date_or_default(value, default_value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return default_value


def selected_period():
    today = date.today()
    period = request.args.get("period", "")

    if period == "today":
        return today, today
    if period == "7d":
        return today - timedelta(days=6), today
    if period == "30d":
        return today - timedelta(days=29), today

    start = parse_date_or_default(request.args.get("start", ""), today)
    end = parse_date_or_default(request.args.get("end", ""), today)

    if start > end:
        start, end = end, start

    return start, end


def csv_paths_between(start, end):
    paths = []
    current = start
    while current <= end:
        path = DATA_DIR / f"microbit_{current.strftime('%Y-%m-%d')}.csv"
        if path.exists():
            paths.append(path)
        current += timedelta(days=1)
    return paths


def safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def row_datetime(row):
    try:
        return datetime.fromisoformat(row.get("raspberry_timestamp", ""))
    except Exception:
        return None


def read_rows(start, end):
    paths = csv_paths_between(start, end)
    rows = []

    for path in paths:
        with path.open("r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

    # Tri chronologique
    rows.sort(key=lambda r: row_datetime(r) or datetime.min)

    # Déduplication : garde la première ligne pour chaque device_id + seq
    seen = set()
    deduped = []
    for row in rows:
        key = (row.get("device_id"), row.get("seq"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return paths, deduped


def compute_status(latest):
    if latest is None:
        return "OFF", "bad"

    dt = row_datetime(latest)
    if dt is None:
        return "INCONNU", "warn"

    age_seconds = (datetime.now() - dt).total_seconds()

    if age_seconds < 8 * 60:
        return "OK", "ok"
    if age_seconds < 20 * 60:
        return "RETARD", "warn"
    return "OFF", "bad"


def chart_points_from_rows(rows, metric, limit):
    chart_rows = []
    for row in rows:
        dt = row_datetime(row)
        value = safe_float(row.get(metric))
        if dt is None or value is None:
            continue

        chart_rows.append({
            "label": dt.strftime("%d/%m %H:%M"),
            "value": value,
        })

    return chart_rows[-limit:]


@app.route("/")
def index():
    start, end = selected_period()

    metric = request.args.get("metric", "temperature_c")
    if metric not in METRICS:
        metric = "temperature_c"

    try:
        limit = int(request.args.get("limit", "100"))
    except Exception:
        limit = 100

    if limit not in (50, 100, 250, 500):
        limit = 100

    paths, rows = read_rows(start, end)

    latest = rows[-1] if rows else None
    status, status_class = compute_status(latest)

    chart_points = chart_points_from_rows(rows, metric, limit)
    table_rows = rows[-30:][::-1]

    return render_template_string(
        HTML,
        data_dir=DATA_DIR,
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
        metric=metric,
        metric_label=METRICS[metric],
        limit=limit,
        refresh_seconds=30,
        csv_count=len(paths),
        latest=latest,
        rows=rows,
        table_rows=table_rows,
        chart_points=chart_points,
        chart_points_json=json.dumps(chart_points),
        status=status,
        status_class=status_class,
        server_time=datetime.now().isoformat(timespec="seconds"),
    )


@app.route("/api/latest")
def api_latest():
    today = date.today()
    paths, rows = read_rows(today, today)
    latest = rows[-1] if rows else None
    status, status_class = compute_status(latest)

    return jsonify({
        "status": status,
        "status_class": status_class,
        "latest": latest,
        "csv_count": len(paths),
    })


@app.route("/api/data")
def api_data():
    start, end = selected_period()
    metric = request.args.get("metric", "temperature_c")
    if metric not in METRICS:
        metric = "temperature_c"

    try:
        limit = int(request.args.get("limit", "500"))
    except Exception:
        limit = 500

    paths, rows = read_rows(start, end)

    return jsonify({
        "start": start.strftime("%Y-%m-%d"),
        "end": end.strftime("%Y-%m-%d"),
        "metric": metric,
        "metric_label": METRICS[metric],
        "csv_count": len(paths),
        "points": chart_points_from_rows(rows, metric, limit),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

