# ==========================================
# IMPORTACIONES Y CONFIGURACIÓN
# ==========================================

import datetime
from flask import jsonify, render_template, request
from ui import render_layout
from . import calendario_bp
from .logic import (
    construir_semana_datos,
    formatear_eventos_para_vista,
    obtener_etiquetas_horas,
    obtener_nombre_mes,
    crear_tarea_local,
    mover_tarea_local,
    editar_tarea_local,
    eliminar_tarea_local,
    crear_evento_fijo_local,
    eliminar_evento_fijo_local,
)


# ==========================================
# VISTAS Y DATOS DEL CALENDARIO
# ==========================================

@calendario_bp.route("/calendario", methods=["GET"])
def vista_calendario():
    hoy_date = datetime.date.today()
    semana_datos, linea_roja_top, _ = construir_semana_datos(
        referencia_date=hoy_date, sincronizar=True
    )
    todos_eventos = formatear_eventos_para_vista()

    html = render_template(
        "calendario.html",
        semana_datos=semana_datos,
        horas_etiquetas=obtener_etiquetas_horas(),
        linea_roja_top=linea_roja_top,
        mes_actual=obtener_nombre_mes(hoy_date.month),
        mes_num=hoy_date.month,
        anio_actual=hoy_date.year,
        dia_hoy_num=hoy_date.day,
        hoy_iso=hoy_date.isoformat(),
        primeros_eventos=todos_eventos[:5],
        todos_eventos=todos_eventos,
        hay_mas_eventos=len(todos_eventos) > 5,
    )
    return render_layout(html, css_extra="calendario.css")


@calendario_bp.route("/calendario/datos_semana", methods=["GET"])
def datos_semana_json():
    fecha_str = request.args.get("fecha")
    ref_date = (
        datetime.date.fromisoformat(fecha_str)
        if fecha_str
        else datetime.date.today()
    )
    semana_datos, linea_roja_top, mes_titulo = construir_semana_datos(
        referencia_date=ref_date, sincronizar=(ref_date == datetime.date.today())
    )
    dias_dict = {dia["fecha_iso"]: dia["bloques"] for dia in semana_datos}
    todos_eventos = formatear_eventos_para_vista()

    return jsonify({
        "linea_roja_top": linea_roja_top,
        "mes_anio_titulo": mes_titulo,
        "dias": dias_dict,
        "semana_datos": semana_datos,
        "eventos_lista": todos_eventos,
    })


# ==========================================
# MANEJO DE TAREAS
# ==========================================

@calendario_bp.route("/calendario/crear_tarea", methods=["POST"])
def crear_tarea_calendario():
    data = request.get_json(silent=True) or {}
    crear_tarea_local(data)
    return jsonify({"status": "ok"})


@calendario_bp.route("/calendario/mover_tarea", methods=["POST"])
def mover_tarea_calendario():
    data = request.get_json(silent=True) or {}
    mover_tarea_local(data)
    return jsonify({"status": "ok"})


@calendario_bp.route("/calendario/editar_tarea", methods=["POST"])
@calendario_bp.route("/calendario/actualizar_tarea", methods=["POST"])
def editar_tarea_calendario():
    data = request.get_json(silent=True) or {}
    editar_tarea_local(data)
    return jsonify({"status": "ok"})


@calendario_bp.route("/calendario/eliminar_tarea", methods=["POST"])
def eliminar_tarea_calendario():
    data = request.get_json(silent=True) or {}
    eliminar_tarea_local(data)
    return jsonify({"status": "ok"})


# ==========================================
# MANEJO DE EVENTOS FIJOS
# ==========================================

@calendario_bp.route("/calendario/crear_evento", methods=["POST"])
def crear_evento_fijo():
    data = request.get_json(silent=True) or {}
    crear_evento_fijo_local(data)
    return jsonify({"status": "ok"})


@calendario_bp.route("/calendario/eliminar_evento", methods=["POST"])
def eliminar_evento_fijo_ruta():
    data = request.get_json(silent=True) or {}
    eliminar_evento_fijo_local(data.get("id"))
    return jsonify({"status": "ok"})