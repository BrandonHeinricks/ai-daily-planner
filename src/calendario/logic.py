# ==========================================
# IMPORTACIONES Y CONSTANTES
# ==========================================

import datetime
import uuid
import storage
from calendar_service import (
    sincronizar_tarea_creada_async,
    sincronizar_tarea_actualizada_async,
    eliminar_evento_calendario_async,
    sincronizar_evento_fijo_creado_async,
    reemplazar_dia_en_google_async,
)

MESES_CORTOS = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_LARGOS = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
NOMBRES_DIAS = ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"]
MAPA_REPITE = {
    "none": "Una vez",
    "daily": "Diario",
    "weekly": "Semanal",
    "monthly": "Mensual",
    "yearly": "Anual",
}


# ==========================================
# PREPARACIÓN DE DATOS Y VISTAS DEL CALENDARIO
# ==========================================

def obtener_nombre_mes(mes_num):
    return MESES_LARGOS[mes_num]


def obtener_etiquetas_horas():
    return [
        "12 AM" if h == 0 else f"{h} AM" if h < 12 else "12 PM" if h == 12 else f"{h-12} PM"
        for h in range(24)
    ]


def calcular_rango_semana(fecha_referencia):
    inicio = fecha_referencia - datetime.timedelta(days=fecha_referencia.weekday())
    fin = inicio + datetime.timedelta(days=6)
    return inicio, fin


def formatear_eventos_para_vista():
    eventos_crudos = storage.cargar_eventos()
    eventos_formateados = []

    for ev in eventos_crudos:
        fecha_mostrar = ev.get("proxima_fecha", ev.get("fecha", ""))
        repite = ev.get("repite", "none")
        repite_label = MAPA_REPITE.get(repite, "Una vez")
        try:
            dt = datetime.date.fromisoformat(fecha_mostrar)
            fecha_corta = f"{dt.day} {MESES_CORTOS[dt.month]}"
            fecha_larga = f"{dt.day} de {MESES_LARGOS[dt.month]} de {dt.year}"
        except Exception:
            fecha_corta = fecha_mostrar
            fecha_larga = fecha_mostrar

        if repite == "daily":
            etiqueta_lateral = f"Diario · {ev.get('hora_inicio', '09:00')}"
        else:
            etiqueta_lateral = f"{fecha_corta} · {ev.get('hora_inicio', '09:00')}"

        eventos_formateados.append({
            "id": ev.get("id"),
            "titulo": ev.get("titulo", "Evento"),
            "fecha": fecha_mostrar,
            "hora_inicio": ev.get("hora_inicio", "09:00"),
            "hora_fin": ev.get("hora_fin", "09:30"),
            "repite": repite,
            "repite_label": repite_label,
            "etiqueta_lateral": etiqueta_lateral,
            "fecha_corta": fecha_corta,
            "fecha_larga": fecha_larga,
        })

    return eventos_formateados


def construir_semana_datos(referencia_date=None, sincronizar=False):
    ahora = datetime.datetime.now()
    hoy_date = ahora.date()
    ref_date = referencia_date if referencia_date else hoy_date
    linea_roja_top = ahora.hour * 60 + ahora.minute if ref_date == hoy_date else 0

    inicio_semana = ref_date - datetime.timedelta(days=ref_date.weekday())
    historial = storage.cargar_historial()
    semana_datos = []

    for i in range(7):
        d_actual = inicio_semana + datetime.timedelta(days=i)
        d_iso = d_actual.isoformat()
        es_hoy = d_actual == hoy_date

        tareas_brutas = storage.TAREAS_HOY if es_hoy else historial.get(d_iso, {}).get("tareas", [])
        eventos_fijos_dia = storage.obtener_eventos_del_dia(d_iso)
        bloques_procesados = []

        for idx_real, t in enumerate(tareas_brutas):
            try:
                h_ini, m_ini = map(int, t["hora_inicio"].split(":"))
                h_fin, m_fin = map(int, t["hora_fin"].split(":"))
                top_px = h_ini * 60 + m_ini
                height_px = max((h_fin * 60 + m_fin) - top_px, 15)
                t_proc = t.copy()
                t_proc["top"] = top_px
                t_proc["height"] = height_px
                t_proc["es_evento"] = False
                t_proc["task_index"] = idx_real
                bloques_procesados.append(t_proc)
            except Exception:
                pass

        for ev in eventos_fijos_dia:
            try:
                h_ini, m_ini = map(int, ev["hora_inicio"].split(":"))
                h_fin, m_fin = map(int, ev["hora_fin"].split(":"))
                top_px = h_ini * 60 + m_ini
                height_px = max((h_fin * 60 + m_fin) - top_px, 15)
                ev_proc = ev.copy()
                ev_proc["top"] = top_px
                ev_proc["height"] = height_px
                ev_proc["es_evento"] = True
                ev_proc["task_index"] = -1
                bloques_procesados.append(ev_proc)
            except Exception:
                pass

        bloques_procesados.sort(key=lambda x: x["top"])
        semana_datos.append({
            "fecha_iso": d_iso,
            "nombre": NOMBRES_DIAS[d_actual.weekday()],
            "numero": d_actual.day,
            "es_hoy": es_hoy,
            "bloques": bloques_procesados,
        })

    mes_titulo = f"{MESES_LARGOS[ref_date.month]} {ref_date.year}"
    return semana_datos, linea_roja_top, mes_titulo


# ==========================================
# MANEJO DE TAREAS (MANUAL Y POR LOTE DESDE INICIO)
# ==========================================

def obtener_lista_dia(fecha_iso, historial):
    hoy_iso = datetime.date.today().isoformat()
    if fecha_iso == hoy_iso:
        return storage.TAREAS_HOY
    if fecha_iso not in historial:
        historial[fecha_iso] = {"score": 0, "tareas": []}
    return historial[fecha_iso]["tareas"]


def crear_tarea_local(data):
    fecha_iso = data.get("fecha_iso")
    nueva_tarea = {
        "id": f"t_{uuid.uuid4().hex[:8]}",
        "hora_inicio": data.get("hora_inicio"),
        "hora_fin": data.get("hora_fin"),
        "tarea": data.get("tarea"),
        "tipo": data.get("tipo", "carrera"),
        "completado": False,
        "google_event_id": "PENDING",
    }

    hoy_iso = datetime.date.today().isoformat()
    if fecha_iso == hoy_iso:
        storage.TAREAS_HOY.append(nueva_tarea)
        storage.TAREAS_HOY.sort(key=lambda x: x["hora_inicio"])
        storage.recalcular_rendimiento()
    else:
        historial = storage.cargar_historial()
        lista = obtener_lista_dia(fecha_iso, historial)
        lista.append(nueva_tarea)
        lista.sort(key=lambda x: x["hora_inicio"])
        storage.recalcular_dia_historial(fecha_iso, historial)
        storage.guardar_historial(historial)

    sincronizar_tarea_creada_async(nueva_tarea, fecha_iso)


def mover_tarea_local(data):
    fecha_iso = data.get("fecha_iso")
    idx = int(data.get("index", -1))
    nueva_ini, nueva_fin = data.get("hora_inicio"), data.get("hora_fin")
    hoy_iso = datetime.date.today().isoformat()
    tarea_objetivo = None

    if fecha_iso == hoy_iso:
        if 0 <= idx < len(storage.TAREAS_HOY):
            tarea_objetivo = storage.TAREAS_HOY[idx]
            if not tarea_objetivo.get("id"):
                tarea_objetivo["id"] = f"t_{uuid.uuid4().hex[:8]}"
            tarea_objetivo["hora_inicio"], tarea_objetivo["hora_fin"] = nueva_ini, nueva_fin
            storage.recalcular_rendimiento()
    else:
        historial = storage.cargar_historial()
        lista = obtener_lista_dia(fecha_iso, historial)
        if 0 <= idx < len(lista):
            tarea_objetivo = lista[idx]
            if not tarea_objetivo.get("id"):
                tarea_objetivo["id"] = f"t_{uuid.uuid4().hex[:8]}"
            tarea_objetivo["hora_inicio"], tarea_objetivo["hora_fin"] = nueva_ini, nueva_fin
            storage.guardar_historial(historial)

    if tarea_objetivo:
        sincronizar_tarea_actualizada_async(tarea_objetivo, fecha_iso)


def editar_tarea_local(data):
    fecha_iso = data.get("fecha_iso")
    idx = int(data.get("index", -1))
    hoy_iso = datetime.date.today().isoformat()
    tarea_objetivo = None

    if fecha_iso == hoy_iso:
        if 0 <= idx < len(storage.TAREAS_HOY):
            t = storage.TAREAS_HOY[idx]
            if not t.get("id"):
                t["id"] = f"t_{uuid.uuid4().hex[:8]}"
            t["tarea"] = data.get("tarea", t["tarea"])
            t["tipo"] = data.get("tipo", t.get("tipo", "estudio"))
            t["hora_inicio"] = data.get("hora_inicio", t["hora_inicio"])
            t["hora_fin"] = data.get("hora_fin", t["hora_fin"])
            t["completado"] = bool(data.get("completado", t.get("completado", False)))
            tarea_objetivo = t
            storage.TAREAS_HOY.sort(key=lambda x: x["hora_inicio"])
            storage.recalcular_rendimiento()
    else:
        historial = storage.cargar_historial()
        lista = obtener_lista_dia(fecha_iso, historial)
        if 0 <= idx < len(lista):
            t = lista[idx]
            if not t.get("id"):
                t["id"] = f"t_{uuid.uuid4().hex[:8]}"
            t["tarea"] = data.get("tarea", t["tarea"])
            t["tipo"] = data.get("tipo", t.get("tipo", "estudio"))
            t["hora_inicio"] = data.get("hora_inicio", t["hora_inicio"])
            t["hora_fin"] = data.get("hora_fin", t["hora_fin"])
            t["completado"] = bool(data.get("completado", t.get("completado", False)))
            tarea_objetivo = t
            lista.sort(key=lambda x: x["hora_inicio"])
            storage.recalcular_dia_historial(fecha_iso, historial)
            storage.guardar_historial(historial)

    if tarea_objetivo:
        sincronizar_tarea_actualizada_async(tarea_objetivo, fecha_iso)


def eliminar_tarea_local(data):
    fecha_iso = data.get("fecha_iso")
    idx = int(data.get("index", -1))
    hoy_iso = datetime.date.today().isoformat()
    tarea_a_borrar = None

    if fecha_iso == hoy_iso:
        if 0 <= idx < len(storage.TAREAS_HOY):
            tarea_a_borrar = storage.TAREAS_HOY.pop(idx)
            storage.recalcular_rendimiento()
    else:
        historial = storage.cargar_historial()
        lista = obtener_lista_dia(fecha_iso, historial)
        if 0 <= idx < len(lista):
            tarea_a_borrar = lista.pop(idx)
            storage.recalcular_dia_historial(fecha_iso, historial)
            storage.guardar_historial(historial)

    if tarea_a_borrar and tarea_a_borrar.get("google_event_id"):
        eliminar_evento_calendario_async(tarea_a_borrar["google_event_id"])


def reemplazar_rutina_dia_local(fecha_iso, lista_tareas_nuevas):
    hoy_iso = datetime.date.today().isoformat()
    tareas_preparadas = []
    for t in lista_tareas_nuevas:
        tareas_preparadas.append({
            "id": f"t_{uuid.uuid4().hex[:8]}",
            "hora_inicio": t.get("hora_inicio", "09:00"),
            "hora_fin": t.get("hora_fin", "10:00"),
            "tarea": t.get("tarea", "Tarea"),
            "tipo": t.get("tipo", "estudio"),
            "completado": bool(t.get("completado", False)),
            "google_event_id": "PENDING",
        })
    tareas_preparadas.sort(key=lambda x: x["hora_inicio"])

    if fecha_iso == hoy_iso:
        ids_anteriores = [t.get("google_event_id") for t in storage.TAREAS_HOY if t.get("google_event_id")]
        storage.TAREAS_HOY[:] = tareas_preparadas
        storage.recalcular_rendimiento()
    else:
        historial = storage.cargar_historial()
        lista_actual = obtener_lista_dia(fecha_iso, historial)
        ids_anteriores = [t.get("google_event_id") for t in lista_actual if t.get("google_event_id")]
        historial[fecha_iso] = {"score": 0, "tareas": tareas_preparadas}
        storage.recalcular_dia_historial(fecha_iso, historial)
        storage.guardar_historial(historial)

    reemplazar_dia_en_google_async(fecha_iso, ids_anteriores, tareas_preparadas)


# ==========================================
# MANEJO DE EVENTOS FIJOS
# ==========================================

def crear_evento_fijo_local(data):
    nuevo_evento = {
        "id": f"ev_{uuid.uuid4().hex[:8]}",
        "titulo": data.get("titulo", "Evento"),
        "fecha": data.get("fecha", datetime.date.today().isoformat()),
        "hora_inicio": data.get("hora_inicio", "09:00"),
        "hora_fin": data.get("hora_fin", "09:30"),
        "repite": data.get("repite", "none"),
        "google_event_id": "PENDING",
    }

    eventos = storage.cargar_eventos_raw()
    eventos.append(nuevo_evento)
    storage.guardar_eventos_raw(eventos)

    sincronizar_evento_fijo_creado_async(dict(nuevo_evento))


def eliminar_evento_fijo_local(ev_id):
    eventos = storage.cargar_eventos_raw()
    restantes, evento_borrado = [], None

    for ev in eventos:
        if ev.get("id") == ev_id:
            evento_borrado = ev
        else:
            restantes.append(ev)

    storage.guardar_eventos_raw(restantes)

    if evento_borrado and evento_borrado.get("google_event_id"):
        eliminar_evento_calendario_async(evento_borrado["google_event_id"])