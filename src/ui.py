from flask import Blueprint, render_template_string, request, redirect, url_for
import datetime
import storage
from calendar_service import obtener_eventos_de_hoy, agregar_eventos_al_calendario
from gemini_service import generar_horario_diario

ui_bp = Blueprint('ui', __name__)

def obtener_saludo():
    hora = datetime.datetime.now().hour
    if 5 <= hora < 12:
        return "Buenos días, Brandon"
    elif 12 <= hora < 20:
        return "Buenas tardes, Brandon"
    else:
        return "Buenas noches, Brandon"

def render_layout(contenido_html, css_extra=None):
    link_extra = f'<link rel="stylesheet" href="/static/{css_extra}">' if css_extra else ''
    plantilla_base = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>AI Daily Planner</title>
        <!-- Fuente serif cursiva gruesa estilo iPhone -->
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
                <a href="/heatmap">Mapa de Calor</a>
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

@ui_bp.route('/')
def home():
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
    input_hoy = request.form.get('input_hoy', '')
    contexto_fijo = storage.cargar_contexto()
    try:
        agenda = obtener_eventos_de_hoy()
    except Exception as e:
        agenda = f"Sin conexión al calendario: {e}"

    horario = generar_horario_diario(contexto_fijo, input_hoy, agenda)
    if horario:
        try:
            ids = agregar_eventos_al_calendario(horario)
        except Exception:
            ids = []
        for i, tarea in enumerate(horario):
            tarea["google_event_id"] = ids[i] if i < len(ids) else None
        storage.TAREAS_HOY = horario
        storage.recalcular_rendimiento()

    return redirect(url_for('tareas.vista_tareas'))