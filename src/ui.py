# ==========================================
# IMPORTACIONES Y CONFIGURACIÓN
# ==========================================

import datetime
from flask import Blueprint, render_template_string, request, redirect, url_for
import storage
from gemini_service import generar_horario_diario

ui_bp = Blueprint('ui', __name__)


# ==========================================
# UTILIDADES Y LAYOUT BASE
# ==========================================

def obtener_saludo():
    hora = datetime.datetime.now().hour
    if 5 <= hora < 12:
        return "Buenos días, Brandon"
    elif 12 <= hora < 20:
        return "Buenas tardes, Brandon"
    else:
        return "Buenas noches, Brandon"


def _obtener_agenda_fija_local(fecha_iso):
    eventos_hoy = storage.obtener_eventos_del_dia(fecha_iso)
    if not eventos_hoy:
        return "No hay eventos fijos programados para hoy."

    lineas = [
        f"- {ev.get('hora_inicio', '09:00')} a {ev.get('hora_fin', '09:30')}: {ev.get('tarea', 'Evento fijo')}"
        for ev in eventos_hoy
    ]
    return "\n".join(lineas)


def render_layout(contenido_html, css_extra=None):
    link_extra = f'<link rel="stylesheet" href="/static/{css_extra}">' if css_extra else ''
    plantilla_base = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>AI Daily Planner</title>
        <link href="[https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Playfair+Display:ital,wght@1,700;1,800&display=swap](https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Playfair+Display:ital,wght@1,700;1,800&display=swap)" rel="stylesheet">
        <link rel="stylesheet" href="/static/ui.css">
        {link_extra}
    </head>
    <body>
        <header class="top-bar">
            <button class="hamburger-btn" onclick="toggleMenu()">☰</button>
            <div id="dropdownMenu" class="dropdown-menu">
                <a href="/">Inicio</a>
                <a href="/tareas">Tareas & Checkboxes</a>
                <a href="/calendario">Calendario</a>
                <a href="/stats">Stats</a>
                <a href="/contexto">Contexto Fijo</a>
            </div>
        </header>

        <main class="main-container">
            {contenido_html}
        </main>

        <script>
            function toggleMenu() {{
                const menu = document.getElementById('dropdownMenu');
                menu.classList.toggle('show');
            }}
            window.addEventListener('click', function(e) {{
                if (!e.target.matches('.hamburger-btn')) {{
                    const menu = document.getElementById('dropdownMenu');
                    if (menu && menu.classList.contains('show')) {{
                        menu.classList.remove('show');
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """
    return render_template_string(plantilla_base)


# ==========================================
# RUTAS DE INICIO Y PLANIFICACIÓN CON IA
# ==========================================

@ui_bp.route('/')
def home():
    storage.verificar_cambio_de_dia()
    saludo = obtener_saludo()
    contenido = f"""
    <div class="home-wrapper">
        <h1 class="iphone-greeting">{saludo}</h1>
        <form action="/planificar_hoy" method="POST" class="pill-form">
            <input type="text" name="input_hoy" class="pill-input" 
                   placeholder="¿Qué quieres lograr en el día de hoy?" required autocomplete="off">
            <button type="submit" class="pill-submit">→</button>
        </form>
    </div>
    """
    return render_layout(contenido)


@ui_bp.route('/planificar_hoy', methods=['POST'])
def planificar_hoy():
    from calendario.logic import reemplazar_rutina_dia_local

    storage.verificar_cambio_de_dia()
    input_hoy = request.form.get('input_hoy', '').strip()
    if input_hoy:
        storage.registrar_prompt_hoy(input_hoy)

    hoy_iso = datetime.date.today().isoformat()
    contexto_fijo = storage.cargar_contexto()
    agenda_local = _obtener_agenda_fija_local(hoy_iso)
    prompts_acumulados = storage.obtener_prompts_acumulados()
    tareas_previas = list(storage.TAREAS_HOY)

    horario = generar_horario_diario(
        contexto_fijo=contexto_fijo,
        prompts_hoy=prompts_acumulados,
        agenda_actual=agenda_local,
        tareas_actuales_hoy=tareas_previas
    )
    if horario:
        reemplazar_rutina_dia_local(hoy_iso, horario)

    return redirect(url_for('tareas.vista_tareas'))