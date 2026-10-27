from flask import Blueprint, request, render_template_string
import datetime
import calendar
from ui import render_layout
from calendar_service import obtener_eventos_de_hoy

calendario_bp = Blueprint('calendario', __name__)

CALENDARIO_HTML = """
<div class="section-card">
    <div class="cal-header">
        <h2 class="section-title" style="margin:0;">{{ nombre_mes_actual }}</h2>
        <div class="cal-nav">
            <a href="/calendario?mes={{ mes_ant }}&anio={{ anio_ant }}" class="cal-arrow">&lt;</a>
            <a href="/calendario?mes={{ mes_sig }}&anio={{ anio_sig }}" class="cal-arrow">&gt;</a>
        </div>
    </div>

    <div class="cal-grid">
        <div class="cal-dow">D</div><div class="cal-dow">L</div><div class="cal-dow">M</div>
        <div class="cal-dow">X</div><div class="cal-dow">J</div><div class="cal-dow">V</div><div class="cal-dow">S</div>
        
        {% for semana in mes_matriz %}
            {% for dia in semana %}
                {% if dia == 0 %}
                    <div class="cal-day empty"></div>
                {% else %}
                    {% set es_hoy = (dia == hoy_dia and mes_actual == hoy_mes and anio_actual == hoy_anio) %}
                    <div class="cal-day {% if es_hoy %}today{% endif %}">{{ dia }}</div>
                {% endif %}
            {% endfor %}
        {% endfor %}
    </div>

    <div class="agenda-box">
        <h3>Eventos en Google Calendar para Hoy</h3>
        <pre class="agenda-pre">{{ agenda_real }}</pre>
    </div>
</div>
"""

@calendario_bp.route('/calendario')
def vista_calendario():
    hoy_date = datetime.date.today()
    anio = request.args.get('anio', default=hoy_date.year, type=int)
    mes = request.args.get('mes', default=hoy_date.month, type=int)

    mes_ant, anio_ant = (12, anio - 1) if mes == 1 else (mes - 1, anio)
    mes_sig, anio_sig = (1, anio + 1) if mes == 12 else (mes + 1, anio)

    cal = calendar.Calendar(firstweekday=6)
    mes_matriz = cal.monthdayscalendar(anio, mes)

    nombres = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    nombre_mes_actual = f"{nombres[mes]} de {anio}"

    try:
        agenda_real = obtener_eventos_de_hoy()
    except Exception as e:
        agenda_real = f"No se pudo conectar con Google Calendar: {e}"

    html = render_template_string(
        CALENDARIO_HTML,
        mes_matriz=mes_matriz,
        nombre_mes_actual=nombre_mes_actual,
        mes_ant=mes_ant, anio_ant=anio_ant,
        mes_sig=mes_sig, anio_sig=anio_sig,
        hoy_dia=hoy_date.day, hoy_mes=hoy_date.month, hoy_anio=hoy_date.year,
        mes_actual=mes, anio_actual=anio,
        agenda_real=agenda_real
    )
    return render_layout(html, css_extra="calendario.css")