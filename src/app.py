from flask import Flask, render_template_string, request, redirect, url_for
import sys
import os
import json
import datetime

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from calendar_service import obtener_eventos_de_hoy, agregar_eventos_al_calendario
from gemini_service import generar_horario_diario

app = Flask(__name__)

# Rutas de almacenamiento local
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data'))
HISTORY_FILE = os.path.join(DATA_DIR, 'history.json')
CONTEXT_FILE = os.path.join(DATA_DIR, 'context.json')

def asegurar_archivos():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    if not os.path.exists(CONTEXT_FILE):
        with open(CONTEXT_FILE, 'w', encoding='utf-8') as f:
            json.dump({"contexto": "Quiero estudiar programación, hacer ejercicio y mantener un balance adecuado."}, f)

asegurar_archivos()

def cargar_contexto():
    try:
        with open(CONTEXT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f).get("contexto", "")
    except:
        return ""

def guardar_contexto_txt(texto):
    with open(CONTEXT_FILE, 'w', encoding='utf-8') as f:
        json.dump({"contexto": texto}, f, ensure_ascii=False, indent=4)

def cargar_historial():
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def guardar_historial(historial):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(historial, f, ensure_ascii=False, indent=4)

# Memoria temporal para las tareas de hoy
TAREAS_HOY = []

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>AI Daily Planner</title>
    <style>
        :root {
            --bg-color: #ffffff;
            --text-color: #37352f;
            --border-color: #e6e6e6;
            --hover-color: #f7f6f3;
            --active-tab: #000000;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        h1 { font-weight: 600; font-size: 24px; margin-bottom: 20px; }
        
        .tabs {
            display: flex;
            gap: 10px;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 30px;
            padding-bottom: 10px;
        }
        .tab-btn {
            background: transparent;
            border: none;
            padding: 8px 16px;
            font-size: 14px;
            font-weight: 500;
            color: #777;
            cursor: pointer;
            border-radius: 6px;
            transition: all 0.2s;
        }
        .tab-btn.active, .tab-btn:hover {
            background: var(--hover-color);
            color: var(--active-tab);
        }

        .tab-content { display: none; }
        .tab-content.active { display: block; }

        .card {
            background: #fff;
            padding: 24px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            margin-bottom: 20px;
        }
        input[type="text"], textarea {
            width: 100%;
            padding: 12px;
            margin-top: 10px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            box-sizing: border-box;
            font-size: 14px;
            font-family: inherit;
        }
        textarea { height: 120px; resize: vertical; }
        button {
            background: var(--active-tab);
            color: #fff;
            border: none;
            padding: 10px 18px;
            border-radius: 6px;
            margin-top: 12px;
            cursor: pointer;
            font-weight: 500;
            font-size: 14px;
        }
        button:hover { opacity: 0.85; }

        .task-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px 0;
            border-bottom: 1px solid #f0f0f0;
        }
        .task-item span { font-size: 14px; }
        .completed { text-decoration: line-through; color: #999; }

        /* Mapa de calor real estilo GitHub (últimos 90 días aprox o vista de lista) */
        .heatmap-grid {
            display: grid;
            grid-template-columns: repeat(10, 40px);
            gap: 8px;
            margin-top: 15px;
        }
        .heatmap-cell {
            width: 40px;
            height: 40px;
            background: #ebedf0;
            border-radius: 6px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            color: #333;
            border: 1px solid #d1d5db;
        }
    </style>
</head>
<body>

    <h1>Daily Planner</h1>

    <div class="tabs">
        <button class="tab-btn active" onclick="switchTab(event, 'tab-hoy')">Hoy & Tareas</button>
        <button class="tab-btn" onclick="switchTab(event, 'tab-heatmap')">Mapa de Calor</button>
        <button class="tab-btn" onclick="switchTab(event, 'tab-calendar')">Calendario</button>
        <button class="tab-btn" onclick="switchTab(event, 'tab-contexto')">Contexto IA</button>
    </div>

    <!-- PESTAÑA 1: HOY Y TAREAS -->
    <div id="tab-hoy" class="tab-content active">
        <div class="card">
            <h3>Generar Rutina de Hoy</h3>
            <form action="/generar" method="POST">
                <p style="font-size: 13px; color: #666; margin-top: 5px;">Se usará tu contexto actual para armar el día esquivando tus eventos.</p>
                <button type="submit">Generar Horario e Inyectar en Google Calendar</button>
            </form>
        </div>

        <div class="card">
            <h3>Tareas de Hoy</h3>
            {% if tareas %}
                <form action="/toggle_tarea" method="POST">
                    {% for tarea in tareas %}
                    <div class="task-item">
                        <input type="checkbox" name="index" value="{{ loop.index0 }}" {% if tarea.completado %}checked{% endif %} onchange="this.form.submit()">
                        <span class="{% if tarea.completado %}completed{% endif %}"><b>[{{ tarea.hora_inicio }} - {{ tarea.hora_fin }}]</b> {{ tarea.tarea }} <i>({{ tarea.tipo }})</i></span>
                    </div>
                    {% endfor %}
                </form>
            {% else %}
                <p style="color: #888; font-size: 14px;">No hay tareas generadas para hoy todavía. ¡Dale al botón de arriba!</p>
            {% endif %}
        </div>
    </div>

    <!-- PESTAÑA 2: MAPA DE CALOR -->
    <div id="tab-heatmap" class="tab-content">
        <div class="card">
            <h3>Mapa de Rendimiento</h3>
            <p style="font-size: 13px; color: #666;">Porcentaje de cumplimiento diario guardado en tu historial.</p>
            <div class="heatmap-grid">
                {% for dia, score in historial.items() %}
                <div class="heatmap-cell" style="background-color: rgba(40, 167, 69, {{ score }}); {% if score > 0.5 %}color: white;{% endif %}" title="{{ dia }}: {{ (score * 100)|int }}%">
                    <span style="font-size: 9px;">{{ dia[5:] }}</span>
                    <b>{{ (score * 100)|int }}%</b>
                </div>
                {% endfor %}
            </div>
            {% if not historial %}
                <p style="color: #888; font-size: 14px; margin-top: 15px;">Aún no hay registros de rendimiento. ¡Completa tareas hoy para empezar a llenar tu mapa!</p>
            {% endif %}
        </div>
    </div>

    <!-- PESTAÑA 3: CALENDAR -->
    <div id="tab-calendar" class="tab-content">
        <div class="card">
            <h3>Sincronización con Google Calendar</h3>
            <p style="font-size: 14px; color: #555;">Tus eventos activos se leen y escriben directamente en tu cuenta principal.</p>
        </div>
    </div>

    <!-- PESTAÑA 4: CONTEXTO -->
    <div id="tab-contexto" class="tab-content">
        <div class="card">
            <h3>Contexto Personal para la IA</h3>
            <p style="font-size: 13px; color: #666;">Modifica las reglas fijas o preferencias que lee Gemini al planificar.</p>
            <form action="/guardar_contexto" method="POST">
                <textarea name="nuevo_contexto">{{ contexto }}</textarea>
                <button type="submit">Guardar Contexto</button>
            </form>
        </div>
    </div>

    <script>
        function switchTab(evt, tabName) {
            let contents = document.getElementsByClassName("tab-content");
            for (let c of contents) c.classList.remove("active");
            
            let buttons = document.getElementsByClassName("tab-btn");
            for (let b of buttons) b.classList.remove("active");
            
            document.getElementById(tabName).classList.add("active");
            evt.currentTarget.classList.add("active");
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    historial = cargar_historial()
    contexto = cargar_contexto()
    return render_template_string(
        HTML_TEMPLATE, 
        contexto=contexto, 
        tareas=TAREAS_HOY,
        historial=historial
    )

@app.route('/generar', methods=['POST'])
def generar():
    global TAREAS_HOY
    contexto = cargar_contexto()
    agenda = obtener_eventos_de_hoy()
    horario = generar_horario_diario(contexto, agenda)
    if horario:
        agregar_eventos_al_calendario(horario)
        TAREAS_HOY = horario
    return redirect(url_for('index'))

@app.route('/toggle_tarea', methods=['POST'])
def toggle_tarea():
    global TAREAS_HOY
    try:
        idx = int(request.form.get('index'))
        # Cambiamos el estado de completado de la tarea seleccionada
        TAREAS_HOY[idx]["completado"] = not TAREAS_HOY[idx]["completado"]
        
        # Calculamos el porcentaje de rendimiento del día actual
        total = len(TAREAS_HOY)
        if total > 0:
            completadas = sum(1 for t in TAREAS_HOY if t["completado"])
            porcentaje = completadas / total # Valor entre 0.0 y 1.0
            
            # Guardamos en el historial con la fecha de hoy (YYYY-MM-DD)
            hoy_str = datetime.date.today().isoformat()
            historial = cargar_historial()
            historial[hoy_str] = porcentaje
            guardar_historial(historial)
    except Exception as e:
        print(f"Error al actualizar tarea: {e}")
        
    return redirect(url_for('index'))

@app.route('/guardar_contexto', methods=['POST'])
def guardar_contexto():
    nuevo = request.form.get('nuevo_contexto')
    guardar_contexto_txt(nuevo)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)