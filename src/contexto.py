from flask import Blueprint, request, redirect, url_for, render_template_string
import storage
from ui import render_layout

contexto_bp = Blueprint('contexto', __name__)

CONTEXTO_HTML = """
<div class="section-card">
    <h2 class="section-title">Contexto Fijo de Brandon</h2>
    <p style="font-size: 13px; color: #666; margin-bottom: 15px;">
        Aquí van tus horarios fijos, hábitos y reglas permanentes. La IA combinará esto con lo que le pidas cada mañana en la pantalla de inicio.
    </p>
    <form action="/contexto/guardar" method="POST">
        <textarea name="nuevo_contexto" class="context-area">{{ contexto }}</textarea>
        <button type="submit" class="btn-save-ctx">Guardar Reglas Fijas</button>
    </form>
</div>
"""

@contexto_bp.route('/contexto')
def vista_contexto():
    ctx = storage.cargar_contexto()
    html = render_template_string(CONTEXTO_HTML, contexto=ctx)
    return render_layout(html, css_extra="contexto.css")

@contexto_bp.route('/contexto/guardar', methods=['POST'])
def guardar_contexto():
    nuevo = request.form.get('nuevo_contexto', '')
    storage.guardar_contexto_txt(nuevo)
    return redirect(url_for('contexto.vista_contexto'))