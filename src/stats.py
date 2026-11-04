# ==========================================
# IMPORTACIONES Y CONFIGURACIÓN
# ==========================================

import datetime
import json
from flask import Blueprint, render_template_string, request
import storage
from ui import render_layout

stats_bp = Blueprint('stats', __name__)

MAPA_TIPOS = {
    "carrera": "carrera",
    "estudio": "carrera",
    "trabajo": "carrera",
    "descanso": "descanso",
    "ocio": "descanso",
    "salud": "salud",
    "gym": "salud",
    "ejercicio": "salud",
    "propios": "propios",
    "personal": "propios",
}

NOMBRES_MESES = [
    "", "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"
]


# ==========================================
# CÁLCULO DE MÉTRICAS POR DÍA (SIN EVENTOS)
# ==========================================

def _duracion_minutos(hora_ini, hora_fin):
    try:
        h1, m1 = map(int, str(hora_ini).split(":"))
        h2, m2 = map(int, str(hora_fin).split(":"))
        diff = (h2 * 60 + m2) - (h1 * 60 + m1)
        return max(diff, 15)
    except Exception:
        return 30


def _calcular_detalle_dia(tareas_lista):
    tareas_validas = [
        t for t in tareas_lista
        if not t.get("es_evento") and t.get("tipo") != "evento"
    ]
    total_tareas = len(tareas_validas)
    if total_tareas == 0:
        return {
            "score": 0,
            "total_tareas": 0,
            "completadas": 0,
            "porcentajes": {"carrera": 0, "descanso": 0, "salud": 0, "propios": 0},
        }

    completadas_lista = [t for t in tareas_validas if t.get("completado")]
    completadas_count = len(completadas_lista)
    score_int = round((completadas_count / total_tareas) * 100)

    base_calculo = completadas_lista if completadas_lista else tareas_validas
    minutos_por_tipo = {"carrera": 0, "descanso": 0, "salud": 0, "propios": 0}

    for t in base_calculo:
        tipo_raw = str(t.get("tipo", "carrera")).lower().strip()
        tipo_norm = MAPA_TIPOS.get(tipo_raw, "carrera")
        minutos_por_tipo[tipo_norm] += _duracion_minutos(
            t.get("hora_inicio", "09:00"),
            t.get("hora_fin", "10:00")
        )

    total_min = sum(minutos_por_tipo.values())
    porcentajes = {"carrera": 0, "descanso": 0, "salud": 0, "propios": 0}

    if total_min > 0:
        acumulado = 0
        claves_activas = [k for k, v in minutos_por_tipo.items() if v > 0]
        for i, k in enumerate(claves_activas):
            if i == len(claves_activas) - 1:
                porcentajes[k] = max(0, 100 - acumulado)
            else:
                pct = round((minutos_por_tipo[k] / total_min) * 100)
                porcentajes[k] = pct
                acumulado += pct

    return {
        "score": score_int,
        "total_tareas": total_tareas,
        "completadas": completadas_count,
        "porcentajes": porcentajes,
    }


# ==========================================
# PLANTILLA HTML + CSS INCRUSTADO (ANTI-CACHÉ)
# ==========================================

STATS_HTML = """
<style>
    .main-container {
        max-width: 100% !important;
        width: 100% !important;
        padding: 20px 24px !important;
        box-sizing: border-box !important;
    }

    .stats-page-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 28px;
        width: 100%;
        max-width: 1240px;
        margin: 0 auto;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    .stats-heatmap-block {
        display: flex;
        flex-direction: column;
        gap: 12px;
        width: fit-content;
        max-width: 100%;
        margin: 0 auto;
    }

    .stats-header h2 {
        font-size: 20px;
        font-weight: 500;
        color: #24292e;
        margin: 0;
    }

    .stats-body-wrapper {
        display: flex;
        justify-content: center;
        align-items: flex-start;
        gap: 20px;
    }

    .stats-card {
        background-color: #ffffff;
        border: 1px solid #e1e4e8;
        border-radius: 10px;
        padding: 22px 28px;
        width: fit-content;
        max-width: 100%;
        box-sizing: border-box;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
        overflow-x: auto;
    }

    .stats-grid-container {
        display: flex;
        flex-direction: column;
        gap: 8px;
        width: fit-content;
    }

    /* Fila superior de meses alineada exactamente con las 53 columnas */
    .stats-months-row {
        display: grid;
        grid-template-columns: repeat(53, 15px);
        column-gap: 4px;
        padding-left: 40px;
        height: 18px;
        align-items: end;
    }

    .stats-month-cell {
        font-size: 12px;
        color: #586069;
        white-space: nowrap;
        line-height: 1;
    }

    .stats-grid-body {
        display: flex;
        gap: 10px;
        align-items: flex-start;
    }

    .stats-weekdays-col {
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 129px;
        font-size: 12px;
        color: #586069;
        width: 30px;
        flex-shrink: 0;
        padding: 0;
    }

    .stats-squares-grid {
        display: grid;
        grid-template-columns: repeat(53, 15px);
        column-gap: 4px;
    }

    .stats-column-week {
        display: flex;
        flex-direction: column;
        gap: 4px;
        width: 15px;
    }

    .stats-square {
        width: 15px;
        height: 15px;
        border-radius: 3px;
        background-color: #ebedf0;
        cursor: pointer;
        box-sizing: border-box;
        transition: transform 0.1s ease;
    }

    .stats-square:hover {
        transform: scale(1.18);
    }

    .stats-square.is-selected {
        outline: 2px solid #111111;
        outline-offset: 1px;
    }

    .stats-square.level-1 { background-color: #c6c6c6; }
    .stats-square.level-2 { background-color: #8c8c8c; }
    .stats-square.level-3 { background-color: #525252; }
    .stats-square.level-4 { background-color: #000000; }

    .stats-footer-legend {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 18px;
        font-size: 13px;
        color: #586069;
        border-top: 1px solid #eaecef;
        padding-top: 14px;
    }

    .legend-scale {
        display: flex;
        align-items: center;
        gap: 5px;
    }

    .legend-scale .stats-square {
        cursor: default;
    }

    .legend-scale .stats-square:hover {
        transform: none;
    }

    /* Tarjeta inferior del anillo independiente y centrada */
    .stats-donut-section {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 28px 24px 36px;
        background-color: #ffffff;
        border: 1px solid #e1e4e8;
        border-radius: 10px;
        width: 100%;
        max-width: 620px;
        margin: 0 auto;
        box-sizing: border-box;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
    }

    .stats-donut-date-badge {
        font-size: 13px;
        color: #6a737d;
        letter-spacing: 0.4px;
        margin-bottom: 4px;
    }

    .stats-donut-wrapper {
        width: 100%;
        max-width: 420px;
        display: flex;
        justify-content: center;
    }

    .stats-donut-svg {
        width: 100%;
        height: auto;
        overflow: visible;
    }

    .donut-center-subtitle {
        font-size: 15px;
        fill: #4a4a4a;
        font-weight: 400;
    }

    .donut-center-score {
        font-size: 46px;
        fill: #1f1f1f;
        font-weight: 400;
    }

    .donut-pct-label {
        font-size: 14px;
        fill: #24292e;
        font-weight: 400;
    }

    .stats-donut-legend {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 32px;
        margin-top: 10px;
    }

    .donut-legend-item {
        display: flex;
        align-items: center;
        gap: 9px;
        font-size: 15px;
        color: #24292e;
    }

    .donut-dot {
        width: 14px;
        height: 14px;
        border-radius: 50%;
        display: inline-block;
    }

    .dot-carrera  { background-color: #5B7D9A; }
    .dot-descanso { background-color: #C2746E; }
    .dot-salud    { background-color: #C7AC63; }
    .dot-propios  { background-color: #6D987A; }
</style>

<div class="stats-page-container">
    
    <div class="stats-heatmap-block">
        <div class="stats-header">
            <h2 class="stats-count-title">{{ total_contribuciones }} días planeados en {{ anio_seleccionado }}</h2>
        </div>

        <div class="stats-body-wrapper">
            <div class="stats-card">
                <div class="stats-grid-container">
                    <!-- Fila superior independiente con los meses alineados a su columna -->
                    <div class="stats-months-row">
                        {% for m in meses_labels %}
                            <span class="stats-month-cell" style="grid-column: {{ m.col }};">{{ m.nombre }}</span>
                        {% endfor %}
                    </div>

                    <div class="stats-grid-body">
                        <div class="stats-weekdays-col">
                            <span></span>
                            <span>Mon</span>
                            <span></span>
                            <span>Wed</span>
                            <span></span>
                            <span>Fri</span>
                            <span></span>
                        </div>

                        <div class="stats-squares-grid">
                            {% for semana in semanas %}
                                <div class="stats-column-week">
                                    {% for dia in semana %}
                                        <div class="stats-square level-{{ dia.nivel }} {% if dia.fecha == fecha_inicial %}is-selected{% endif %}"
                                             data-fecha="{{ dia.fecha }}"
                                             title="{{ dia.fecha }}: {{ dia.texto }}"
                                             onclick="seleccionarDiaStats(this, '{{ dia.fecha }}')"></div>
                                    {% endfor %}
                                </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>

                <div class="stats-footer-legend">
                    <span class="legend-text">Todo lo cumplido este año</span>
                    <div class="legend-scale">
                        <span>Less</span>
                        <div class="stats-square level-0"></div>
                        <div class="stats-square level-1"></div>
                        <div class="stats-square level-2"></div>
                        <div class="stats-square level-3"></div>
                        <div class="stats-square level-4"></div>
                        <span>More</span>
                    </div>
                </div>
            </div>

            {% if mostrar_selector_anios %}
                <div class="stats-years-sidebar">
                    {% for anio in anios_disponibles %}
                        <a href="/stats?anio={{ anio }}" class="year-btn {% if anio == anio_seleccionado %}active{% endif %}">
                            {{ anio }}
                        </a>
                    {% endfor %}
                </div>
            {% endif %}
        </div>
    </div>

    <!-- Sección inferior independiente y centrada: Gráfico de anillo -->
    <div class="stats-donut-section">
        <div class="stats-donut-date-badge" id="donutFechaLabel">{{ fecha_inicial }}</div>

        <div class="stats-donut-wrapper">
            <svg id="donutSvg" viewBox="0 0 420 340" class="stats-donut-svg">
                <g id="donutSegments"></g>
                <g id="donutLabels"></g>
                <text x="210" y="156" text-anchor="middle" class="donut-center-subtitle" id="donutCenterTitle">Día Completo</text>
                <text x="210" y="198" text-anchor="middle" class="donut-center-score" id="donutCenterScore">0</text>
            </svg>
        </div>

        <div class="stats-donut-legend">
            <div class="donut-legend-item">
                <span class="donut-dot dot-carrera"></span>
                <span>Carrera</span>
            </div>
            <div class="donut-legend-item">
                <span class="donut-dot dot-descanso"></span>
                <span>Descanso</span>
            </div>
            <div class="donut-legend-item">
                <span class="donut-dot dot-salud"></span>
                <span>Salud</span>
            </div>
            <div class="donut-legend-item">
                <span class="donut-dot dot-propios"></span>
                <span>Propios</span>
            </div>
        </div>
    </div>
</div>

<script>
    const DETALLE_DIAS = {{ detalle_dias_json | safe }};
    const COLORES_CATEGORIAS = {
        carrera: "#5B7D9A",
        descanso: "#C2746E",
        salud: "#C7AC63",
        propios: "#6D987A"
    };
    const ORDEN_CATEGORIAS = ["carrera", "descanso", "salud", "propios"];

    function seleccionarDiaStats(elemento, fechaIso) {
        document.querySelectorAll('.stats-squares-grid .stats-square.is-selected')
            .forEach(el => el.classList.remove('is-selected'));
        if (elemento) {
            elemento.classList.add('is-selected');
        }
        renderizarDonutDia(fechaIso);
    }

    function renderizarDonutDia(fechaIso) {
        const info = DETALLE_DIAS[fechaIso] || {
            score: 0,
            total_tareas: 0,
            completadas: 0,
            porcentajes: { carrera: 0, descanso: 0, salud: 0, propios: 0 }
        };

        document.getElementById('donutFechaLabel').textContent = fechaIso;
        document.getElementById('donutCenterScore').textContent = info.score;

        const subtituloEl = document.getElementById('donutCenterTitle');
        if (info.total_tareas === 0) {
            subtituloEl.textContent = "Sin Tareas";
        } else if (info.score === 100) {
            subtituloEl.textContent = "Día Completo";
        } else {
            subtituloEl.textContent = "Rendimiento";
        }

        const segGroup = document.getElementById('donutSegments');
        const lblGroup = document.getElementById('donutLabels');
        segGroup.innerHTML = "";
        lblGroup.innerHTML = "";

        const cx = 210, cy = 170, r = 96;
        const circunferencia = 2 * Math.PI * r;
        const activas = ORDEN_CATEGORIAS.filter(cat => (info.porcentajes[cat] || 0) > 0);

        if (activas.length === 0) {
            const baseCircle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            baseCircle.setAttribute("cx", cx);
            baseCircle.setAttribute("cy", cy);
            baseCircle.setAttribute("r", r);
            baseCircle.setAttribute("fill", "none");
            baseCircle.setAttribute("stroke", "#e6e8eb");
            baseCircle.setAttribute("stroke-width", "36");
            segGroup.appendChild(baseCircle);
            return;
        }

        let acumuladoPct = 0;
        const gapPx = activas.length > 1 ? 4 : 0;

        activas.forEach(cat => {
            const pct = info.porcentajes[cat];
            const frac = pct / 100;
            const arcoLen = Math.max(2, (frac * circunferencia) - gapPx);
            const offset = -(acumuladoPct / 100) * circunferencia;

            const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circle.setAttribute("cx", cx);
            circle.setAttribute("cy", cy);
            circle.setAttribute("r", r);
            circle.setAttribute("fill", "none");
            circle.setAttribute("stroke", COLORES_CATEGORIAS[cat]);
            circle.setAttribute("stroke-width", "36");
            circle.setAttribute("stroke-dasharray", `${arcoLen} ${circunferencia}`);
            circle.setAttribute("stroke-dashoffset", offset);
            circle.setAttribute("transform", `rotate(-90 ${cx} ${cy})`);
            segGroup.appendChild(circle);

            const midPct = acumuladoPct + (pct / 2);
            const anguloRad = (-Math.PI / 2) + (midPct / 100) * (2 * Math.PI);
            const labelRadius = 136;
            const lx = cx + labelRadius * Math.cos(anguloRad);
            const ly = cy + labelRadius * Math.sin(anguloRad) + 5;

            const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
            text.setAttribute("x", lx);
            text.setAttribute("y", ly);
            text.setAttribute("text-anchor", "middle");
            text.setAttribute("class", "donut-pct-label");
            text.textContent = `${pct}%`;
            lblGroup.appendChild(text);

            acumuladoPct += pct;
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        renderizarDonutDia("{{ fecha_inicial }}");
    });
</script>
"""


# ==========================================
# RUTA PRINCIPAL DE ESTADÍSTICAS
# ==========================================

@stats_bp.route('/stats')
def vista_stats():
    storage.verificar_cambio_de_dia()
    hoy_date = datetime.date.today()
    hoy_iso = hoy_date.isoformat()
    try:
        anio_req = int(request.args.get('anio', hoy_date.year))
    except Exception:
        anio_req = hoy_date.year

    datos = storage.obtener_datos_stats(anio_req)
    historial = storage.cargar_historial()

    detalle_dias = {}
    for fecha_iso, info_dia in historial.items():
        tareas_dia = info_dia.get("tareas", []) if isinstance(info_dia, dict) else []
        detalle_dias[fecha_iso] = _calcular_detalle_dia(tareas_dia)

    if storage.TAREAS_HOY:
        detalle_dias[hoy_iso] = _calcular_detalle_dia(storage.TAREAS_HOY)

    inicio_anio = datetime.date(anio_req, 1, 1)
    inicio_grid = inicio_anio - datetime.timedelta(days=(inicio_anio.weekday() + 1) % 7)

    semanas = []
    meses_labels = []
    current_date = inicio_grid
    mes_anterior = -1

    for idx_sem in range(53):
        semana_dias = []

        for _ in range(7):
            d_iso = current_date.isoformat()
            if current_date.year == anio_req and current_date.month != mes_anterior:
                meses_labels.append({
                    "nombre": NOMBRES_MESES[current_date.month],
                    "col": idx_sem + 1
                })
                mes_anterior = current_date.month

            val = datos["matriz_dias"].get(d_iso, 0)

            nivel = 0
            if val > 0:
                if val <= 0.25:
                    nivel = 1
                elif val <= 0.50:
                    nivel = 2
                elif val <= 0.75:
                    nivel = 3
                else:
                    nivel = 4

            semana_dias.append({
                "fecha": d_iso,
                "nivel": nivel,
                "texto": f"{round(val * 100)}% completado" if val > 0 else "Sin actividad"
            })
            current_date += datetime.timedelta(days=1)

        semanas.append(semana_dias)

    mostrar_selector = len(datos["anios_disponibles"]) > 1
    fecha_inicial = hoy_iso if anio_req == hoy_date.year else f"{anio_req}-01-01"

    html = render_template_string(
        STATS_HTML,
        total_contribuciones=datos["total"],
        anio_seleccionado=anio_req,
        anios_disponibles=datos["anios_disponibles"],
        mostrar_selector_anios=mostrar_selector,
        semanas=semanas,
        meses_labels=meses_labels,
        fecha_inicial=fecha_inicial,
        detalle_dias_json=json.dumps(detalle_dias)
    )
    return render_layout(html, css_extra="stats.css")