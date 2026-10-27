from flask import Blueprint, request, redirect, url_for, render_template_string
import storage
from ui import render_layout
from calendar_service import agregar_eventos_al_calendario, eliminar_evento_calendario

tareas_bp = Blueprint('tareas', __name__)

TAREAS_HTML = """
<div class="section-card">
    <h2 class="section-title">Añadir Tarea Manualmente</h2>
    <form action="/tareas/agregar" method="POST" class="manual-form">
        <div class="row-inputs">
            <input type="time" name="hora_inicio" required>
            <input type="time" name="hora_fin" required>
            <select name="tipo">
                <option value="estudio">Estudio</option>
                <option value="trabajo">Trabajo</option>
                <option value="ejercicio">Ejercicio</option>
                <option value="descanso">Descanso</option>
            </select>
        </div>
        <div class="row-inputs">
            <input type="text" name="tarea" placeholder="Descripción de la tarea..." required>
            <button type="submit" class="btn-black">Añadir</button>
        </div>
    </form>
</div>

<div class="section-card">
    <h2 class="section-title">Tareas de Hoy</h2>
    {% if tareas %}
        {% for tarea in tareas %}
        <div class="task-row">
            <div class="task-left">
                <form action="/tareas/toggle" method="POST">
                    <input type="hidden" name="index" value="{{ loop.index0 }}">
                    <input type="checkbox" class="task-check" {% if tarea.completado %}checked{% endif %} onchange="this.form.submit()">
                </form>
                <span class="{% if tarea.completado %}task-done{% endif %}">
                    <strong>[{{ tarea.hora_inicio }} - {{ tarea.hora_fin }}]</strong> {{ tarea.tarea }} <small>({{ tarea.tipo }})</small>
                </span>
            </div>
            <form action="/tareas/eliminar" method="POST">
                <input type="hidden" name="index" value="{{ loop.index0 }}">
                <button type="submit" class="btn-outline-del">Eliminar</button>
            </form>
        </div>
        {% endfor %}
    {% else %}
        <p class="empty-msg">No hay tareas programadas todavía.</p>
    {% endif %}
</div>
"""

@tareas_bp.route('/tareas')
def vista_tareas():
    html = render_template_string(TAREAS_HTML, tareas=storage.TAREAS_HOY)
    return render_layout(html, css_extra="tareas.css")

@tareas_bp.route('/tareas/agregar', methods=['POST'])
def agregar_manual():
    nueva_tarea = {
        "hora_inicio": request.form.get('hora_inicio'),
        "hora_fin": request.form.get('hora_fin'),
        "tarea": request.form.get('tarea'),
        "tipo": request.form.get('tipo'),
        "completado": False,
        "google_event_id": None
    }
    try:
        ids = agregar_eventos_al_calendario([nueva_tarea])
        if ids:
            nueva_tarea["google_event_id"] = ids[0]
    except Exception as e:
        print(f"⚠️ Error al sincronizar con Google Calendar: {e}")

    storage.TAREAS_HOY.append(nueva_tarea)
    storage.TAREAS_HOY.sort(key=lambda x: x['hora_inicio'])
    storage.recalcular_rendimiento()
    return redirect(url_for('tareas.vista_tareas'))

@tareas_bp.route('/tareas/toggle', methods=['POST'])
def toggle_tarea():
    idx = int(request.form.get('index'))
    if 0 <= idx < len(storage.TAREAS_HOY):
        storage.TAREAS_HOY[idx]["completado"] = not storage.TAREAS_HOY[idx]["completado"]
        storage.recalcular_rendimiento()
    return redirect(url_for('tareas.vista_tareas'))

@tareas_bp.route('/tareas/eliminar', methods=['POST'])
def eliminar_tarea():
    idx = int(request.form.get('index'))
    if 0 <= idx < len(storage.TAREAS_HOY):
        tarea_a_borrar = storage.TAREAS_HOY[idx]
        if tarea_a_borrar.get("google_event_id"):
            eliminar_evento_calendario(tarea_a_borrar["google_event_id"])
        storage.TAREAS_HOY.pop(idx)
        storage.recalcular_rendimiento()
    return redirect(url_for('tareas.vista_tareas'))