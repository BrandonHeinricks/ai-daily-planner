import os
import json
import uuid
import calendar
import datetime

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data'))
HISTORY_FILE = os.path.join(DATA_DIR, 'history.json')
CONTEXT_FILE = os.path.join(DATA_DIR, 'context.json')
EVENTS_FILE = os.path.join(DATA_DIR, 'events.json')

TAREAS_HOY = []

EVENTOS_INICIALES = [
    {
        "id": "ev_init_1",
        "titulo": "Ir a la cama",
        "fecha": "2026-11-01",
        "hora_inicio": "23:00",
        "hora_fin": "23:45",
        "repite": "daily",
        "google_event_id": None
    },
    {
        "id": "ev_init_2",
        "titulo": "Cita médico general",
        "fecha": "2026-11-04",
        "hora_inicio": "10:00",
        "hora_fin": "11:00",
        "repite": "none",
        "google_event_id": None
    },
    {
        "id": "ev_init_3",
        "titulo": "Cumpleaños de mamá",
        "fecha": "2026-11-09",
        "hora_inicio": "09:00",
        "hora_fin": "09:30",
        "repite": "yearly",
        "google_event_id": None
    }
]

def asegurar_archivos():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    if not os.path.exists(CONTEXT_FILE):
        with open(CONTEXT_FILE, 'w', encoding='utf-8') as f:
            json.dump({"contexto": "Quiero estudiar programación, hacer ejercicio y mantener un balance adecuado."}, f)
    if not os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(EVENTOS_INICIALES, f, ensure_ascii=False, indent=4)

asegurar_archivos()

def cargar_contexto():
    try:
        with open(CONTEXT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f).get("contexto", "")
    except Exception:
        return ""

def guardar_contexto_txt(texto):
    with open(CONTEXT_FILE, 'w', encoding='utf-8') as f:
        json.dump({"contexto": texto}, f, ensure_ascii=False, indent=4)

def cargar_historial():
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for k, v in data.items():
                if isinstance(v, (int, float)):
                    data[k] = {"score": v, "tareas": []}
            return data
    except Exception:
        return {}

def guardar_historial(historial):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(historial, f, ensure_ascii=False, indent=4)

def cargar_eventos_raw():
    """Carga la lista de eventos asegurando que todos tengan los campos necesarios."""
    try:
        with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
            eventos = json.load(f)
    except Exception:
        eventos = []

    modificado = False
    for ev in eventos:
        if "id" not in ev:
            ev["id"] = f"ev_{uuid.uuid4().hex[:8]}"
            modificado = True
        if "hora_inicio" not in ev:
            ev["hora_inicio"] = "09:00"
            modificado = True
        if "hora_fin" not in ev:
            ev["hora_fin"] = "09:30"
            modificado = True
        if "repite" not in ev:
            ev["repite"] = "none"
            modificado = True
        if "google_event_id" not in ev:
            ev["google_event_id"] = None
            modificado = True

    if modificado:
        guardar_eventos_raw(eventos)
    return eventos

def guardar_eventos_raw(eventos):
    with open(EVENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(eventos, f, ensure_ascii=False, indent=4)

def evento_ocurre_en_fecha(ev, target_date):
    """Determina si un evento (según su regla de repetición) ocurre en target_date."""
    try:
        ev_date = datetime.date.fromisoformat(ev.get("fecha", ""))
    except Exception:
        return False

    repite = ev.get("repite", "none")

    if repite == "none":
        return target_date == ev_date
    elif repite == "daily":
        return target_date >= ev_date
    elif repite == "weekly":
        return target_date >= ev_date and target_date.weekday() == ev_date.weekday()
    elif repite == "monthly":
        return target_date >= ev_date and target_date.day == ev_date.day
    elif repite == "yearly":
        return target_date >= ev_date and (target_date.month == ev_date.month and target_date.day == ev_date.day)
    return False

def _proxima_ocurrencia(ev, hoy_date):
    """Calcula la fecha más próxima en la que ocurrirá el evento a partir de hoy."""
    try:
        ev_date = datetime.date.fromisoformat(ev.get("fecha", ""))
    except Exception:
        return None

    repite = ev.get("repite", "none")

    if repite == "none":
        return ev_date if ev_date >= hoy_date else None
    elif repite == "daily":
        return max(hoy_date, ev_date)
    elif repite == "weekly":
        base = max(hoy_date, ev_date)
        dias_faltantes = (ev_date.weekday() - base.weekday()) % 7
        return base + datetime.timedelta(days=dias_faltantes)
    elif repite == "monthly":
        base = max(hoy_date, ev_date)
        y, m = base.year, base.month
        for _ in range(24):
            max_d = calendar.monthrange(y, m)[1]
            d = min(ev_date.day, max_d)
            cand = datetime.date(y, m, d)
            if cand >= base:
                return cand
            m += 1
            if m > 12:
                m = 1
                y += 1
        return base
    elif repite == "yearly":
        base = max(hoy_date, ev_date)
        for y in range(base.year, base.year + 5):
            max_d = calendar.monthrange(y, ev_date.month)[1]
            d = min(ev_date.day, max_d)
            cand = datetime.date(y, ev_date.month, d)
            if cand >= base:
                return cand
    return None

def cargar_eventos():
    """Devuelve los eventos activos ordenados por su próxima aparición."""
    eventos = cargar_eventos_raw()
    hoy_date = datetime.date.today()
    resultado = []

    for ev in eventos:
        prox = _proxima_ocurrencia(ev, hoy_date)
        if prox is not None:
            copia = ev.copy()
            copia["proxima_fecha"] = prox.isoformat()
            resultado.append(copia)

    resultado.sort(key=lambda x: (x["proxima_fecha"], x.get("hora_inicio", "00:00")))
    return resultado

def obtener_eventos_del_dia(fecha_iso):
    """Devuelve todos los eventos fijos/repetitivos que caen en una fecha concreta (YYYY-MM-DD)."""
    try:
        target_date = datetime.date.fromisoformat(fecha_iso)
    except Exception:
        return []

    eventos = cargar_eventos_raw()
    del_dia = []
    for ev in eventos:
        if evento_ocurre_en_fecha(ev, target_date):
            del_dia.append({
                "id": ev["id"],
                "hora_inicio": ev.get("hora_inicio", "09:00"),
                "hora_fin": ev.get("hora_fin", "09:30"),
                "tarea": ev.get("titulo", "Evento"),
                "tipo": "evento",
                "repite": ev.get("repite", "none"),
                "completado": False,
                "es_evento": True,
                "google_event_id": ev.get("google_event_id")
            })
    del_dia.sort(key=lambda x: x["hora_inicio"])
    return del_dia

def obtener_contexto_eventos_ia(fecha_iso=None):
    """
    Texto estructurado para inyectar en el prompt de Gemini:
    Informa de los eventos inmutables del día (citas, cumpleaños, hora de dormir)
    para que la IA no asigne tareas en esas horas ni después de la hora de dormir.
    """
    if not fecha_iso:
        fecha_iso = datetime.date.today().isoformat()
    eventos_hoy = obtener_eventos_del_dia(fecha_iso)
    if not eventos_hoy:
        return "No hay eventos fijos ni bloqueos de horario para este día."

    lineas = ["EVENTOS FIJOS E INMUTABLES DEL DÍA (NO asignar tareas en estos bloques ni después de la hora de dormir):"]
    for ev in eventos_hoy:
        lineas.append(f"- {ev['hora_inicio']} a {ev['hora_fin']}: {ev['tarea']} (Inmutable)")
    return "\n".join(lineas)

def recalcular_rendimiento():
    global TAREAS_HOY
    total = len(TAREAS_HOY)
    hoy_str = datetime.date.today().isoformat()
    historial = cargar_historial()
    
    if total > 0:
        completadas = sum(1 for t in TAREAS_HOY if t.get("completado"))
        porcentaje = completadas / total
        historial[hoy_str] = {
            "score": porcentaje,
            "tareas": TAREAS_HOY
        }
    else:
        if hoy_str in historial:
            del historial[hoy_str]
    guardar_historial(historial)

def inicializar_tareas_hoy():
    global TAREAS_HOY
    hoy_str = datetime.date.today().isoformat()
    historial = cargar_historial()
    if hoy_str in historial and "tareas" in historial[hoy_str]:
        TAREAS_HOY = historial[hoy_str]["tareas"]

inicializar_tareas_hoy()