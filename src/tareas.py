# ==========================================
# IMPORTACIONES Y CONFIGURACIÓN
# ==========================================

from flask import Blueprint, render_template_string, request, jsonify
import storage
from ui import render_layout

tareas_bp = Blueprint('tareas', __name__)

# ==========================================
# PLANTILLA HTML DE TAREAS
# ==========================================

TAREAS_HTML = """
<div class="tareas-page-container">
    <div class="section-card">
        <h2 class="tareas-section-title">Tareas de Hoy</h2>
        
        <div class="tareas-hoy-list" id="tareasHoyContainer">
            {% if tareas_hoy %}
                {% for tarea in tareas_hoy %}
                    <div class="tarea-row-item {% if tarea.completado %}is-completed{% endif %}">
                        <label class="tarea-checkbox-label">
                            <input type="checkbox" class="tarea-mini-checkbox" 
                                   data-index="{{ loop.index0 }}"
                                   {% if tarea.completado %}checked{% endif %}
                                   onchange="toggleCompletarTarea(this)">
                            <span class="tarea-text-name">{{ tarea.tarea }}</span>
                        </label>
                        <span class="tarea-time-badge">{{ tarea.hora_inicio }} - {{ tarea.hora_fin }}</span>
                    </div>
                {% endfor %}
            {% else %}
                <div class="evento-empty">No hay tareas programadas para hoy.</div>
            {% endif %}
        </div>
    </div>
</div>

<script>
    async function toggleCompletarTarea(checkbox) {
        const index = checkbox.dataset.index;
        const completado = checkbox.checked;
        const rowItem = checkbox.closest('.tarea-row-item');

        if (completado) {
            rowItem.classList.add('is-completed');
        } else {
            rowItem.classList.remove('is-completed');
        }

        try {
            const res = await fetch('/tareas/completar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ index: parseInt(index), completado: completado })
            });
            if (!res.ok) {
                console.error('Error al actualizar el estado de la tarea');
            }
        } catch (err) {
            console.error('Error de red:', err);
        }
    }
</script>
"""

# ==========================================
# RUTAS DE TAREAS DE HOY
# ==========================================

@tareas_bp.route('/tareas')
def vista_tareas():
    storage.verificar_cambio_de_dia()
    tareas_hoy = storage.TAREAS_HOY
    html = render_template_string(
        TAREAS_HTML,
        tareas_hoy=tareas_hoy
    )
    return render_layout(html, css_extra="tareas.css")


@tareas_bp.route('/tareas/completar', methods=['POST'])
def completar_tarea():
    data = request.get_json(silent=True) or {}
    idx = data.get('index')
    completado = bool(data.get('completado', False))

    if isinstance(idx, int) and 0 <= idx < len(storage.TAREAS_HOY):
        storage.TAREAS_HOY[idx]['completado'] = completado
        storage.recalcular_rendimiento()
        return jsonify({"status": "ok"})

    return jsonify({"error": "Índice inválido"}), 400