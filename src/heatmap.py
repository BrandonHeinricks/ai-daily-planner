from flask import Blueprint, render_template_string
import storage
from ui import render_layout

heatmap_bp = Blueprint('heatmap', __name__)

HEATMAP_HTML = """
<div class="section-card">
    <h2 class="section-title">Mapa de Rendimiento Histórico</h2>
    <p style="font-size: 13px; color: #666; margin-bottom: 15px;">Haz clic en cualquier día para auditar las tareas de esa fecha.</p>
    
    <div class="heatmap-grid">
        {% for dia, info in historial.items() %}
        <div class="heatmap-cell" 
             style="background-color: rgba(0, 0, 0, {{ info.score * 0.85 + 0.1 }}); color: {% if info.score > 0.4 %}#fff{% else %}#000{% endif %};"
             onclick='abrirModal("{{ dia }}", {{ (info.score * 100)|int }}, {{ info.tareas | tojson }})'>
            <span style="font-size: 9px;">{{ dia[5:] }}</span>
            <b>{{ (info.score * 100)|int }}%</b>
        </div>
        {% endfor %}
    </div>
    {% if not historial %}
        <p style="color: #777; font-size: 14px;">Aún no hay registros históricos.</p>
    {% endif %}
</div>

<div id="modalDetalle" class="modal-overlay" onclick="cerrarModalFuera(event)">
    <div class="modal-card">
        <div class="modal-header">
            <h3 id="modalFecha">Fecha</h3>
            <button class="modal-close" onclick="cerrarModal()">✕</button>
        </div>
        <p id="modalScore" style="font-size: 13px; color: #555; margin-bottom: 15px;"></p>
        <div id="modalListaTareas"></div>
    </div>
</div>

<script>
    function abrirModal(fecha, score, tareas) {
        document.getElementById("modalFecha").innerText = "Auditoría del " + fecha;
        document.getElementById("modalScore").innerText = "Cumplimiento: " + score + "%";
        let cont = document.getElementById("modalListaTareas");
        cont.innerHTML = "";
        if (!tareas || tareas.length === 0) {
            cont.innerHTML = "<p>Sin tareas registradas.</p>";
        } else {
            tareas.forEach(t => {
                let d = document.createElement("div");
                d.className = "audit-item";
                let estado = t.completado ? "✓ Hecha" : "✗ Pendiente";
                d.innerHTML = `<span><b>[${t.hora_inicio}-${t.hora_fin}]</b> ${t.tarea}</span> <strong>${estado}</strong>`;
                cont.appendChild(d);
            });
        }
        document.getElementById("modalDetalle").style.display = "flex";
    }
    function cerrarModal() {
        document.getElementById("modalDetalle").style.display = "none";
    }
    function cerrarModalFuera(e) {
        if (e.target.id === "modalDetalle") cerrarModal();
    }
</script>
"""

@heatmap_bp.route('/heatmap')
def vista_heatmap():
    historial = storage.cargar_historial()
    html = render_template_string(HEATMAP_HTML, historial=historial)
    return render_layout(html, css_extra="heatmap.css")