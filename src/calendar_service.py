# ==========================================
# IMPORTACIONES Y CONFIGURACIÓN
# ==========================================

import os
import datetime
import threading
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import storage

SCOPES = ['https://www.googleapis.com/auth/calendar']
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'token.json')

_google_lock = threading.Lock()


# ==========================================
# EJECUCIÓN EN SEGUNDO PLANO
# ==========================================

def _ejecutar_en_segundo_plano(func, *args, **kwargs):
    hilo = threading.Thread(target=func, args=args, kwargs=kwargs)
    hilo.daemon = True
    hilo.start()


# ==========================================
# AUTENTICACIÓN Y CLIENTE DE GOOGLE
# ==========================================

def obtener_servicio():
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"🔄 Token caducado ({e}). Solicitando nuevo inicio de sesión...")
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w', encoding='utf-8') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)


def _construir_fechas_rfc3339(fecha_iso, hora_inicio, hora_fin):
    tz_local = datetime.datetime.now().astimezone().tzinfo
    dt_ini = datetime.datetime.strptime(f"{fecha_iso} {hora_inicio}", "%Y-%m-%d %H:%M").replace(tzinfo=tz_local)
    dt_fin = datetime.datetime.strptime(f"{fecha_iso} {hora_fin}", "%Y-%m-%d %H:%M").replace(tzinfo=tz_local)
    if dt_fin <= dt_ini:
        dt_fin = dt_ini + datetime.timedelta(minutes=15)
    return dt_ini.isoformat(), dt_fin.isoformat()


def obtener_eventos_de_hoy():
    service = obtener_servicio()
    tz_local = datetime.datetime.now().astimezone().tzinfo
    hoy = datetime.date.today()
    inicio_dia = datetime.datetime.combine(hoy, datetime.time.min, tzinfo=tz_local).isoformat()
    fin_dia = datetime.datetime.combine(hoy, datetime.time.max, tzinfo=tz_local).isoformat()

    events_result = service.events().list(
        calendarId='primary', timeMin=inicio_dia, timeMax=fin_dia,
        singleEvents=True, orderBy='startTime'
    ).execute()
    eventos = events_result.get('items', [])

    if not eventos:
        return "No hay eventos programados para hoy."

    lineas = []
    for event in eventos:
        start = event['start'].get('dateTime', event['start'].get('date'))
        lineas.append(f"- {start}: {event.get('summary', 'Sin título')}")
    return "\n".join(lineas)


# ==========================================
# MANEJO DE TAREAS EN GOOGLE CALENDAR
# ==========================================

def agregar_eventos_al_calendario(lista_tareas, fecha_iso=None):
    service = obtener_servicio()
    if not fecha_iso:
        fecha_iso = datetime.date.today().isoformat()

    ids_creados = []
    for t in lista_tareas:
        ini_iso, fin_iso = _construir_fechas_rfc3339(fecha_iso, t['hora_inicio'], t['hora_fin'])
        evento = {
            'summary': t['tarea'],
            'colorId': '9',
            'start': {'dateTime': ini_iso},
            'end': {'dateTime': fin_iso},
            'extendedProperties': {
                'private': {'tipo_elemento': 'tarea'}
            }
        }
        creado = service.events().insert(calendarId='primary', body=evento).execute()
        ids_creados.append(creado.get('id'))
    return ids_creados


def actualizar_evento_calendario(event_id, tarea_dict, fecha_iso=None):
    if not fecha_iso:
        fecha_iso = datetime.date.today().isoformat()

    if not event_id or event_id == "PENDING":
        ids = agregar_eventos_al_calendario([tarea_dict], fecha_iso=fecha_iso)
        return ids[0] if ids else None

    service = obtener_servicio()
    ini_iso, fin_iso = _construir_fechas_rfc3339(fecha_iso, tarea_dict['hora_inicio'], tarea_dict['hora_fin'])
    cuerpo = {
        'summary': tarea_dict['tarea'],
        'colorId': '9',
        'start': {'dateTime': ini_iso},
        'end': {'dateTime': fin_iso},
    }
    service.events().patch(calendarId='primary', eventId=event_id, body=cuerpo).execute()
    return event_id


def eliminar_evento_calendario(event_id):
    if not event_id or event_id == "PENDING":
        return
    service = obtener_servicio()
    service.events().delete(calendarId='primary', eventId=event_id).execute()


def _guardar_google_id_en_storage(fecha_iso, tarea_ref, g_id):
    tarea_ref["google_event_id"] = g_id
    hoy_iso = datetime.date.today().isoformat()
    if fecha_iso == hoy_iso:
        storage.recalcular_rendimiento()
    else:
        historial = storage.cargar_historial()
        if fecha_iso in historial:
            tid = tarea_ref.get("id")
            for t in historial[fecha_iso].get("tareas", []):
                if (tid and t.get("id") == tid) or (
                    t.get("google_event_id") == "PENDING"
                    and t.get("tarea") == tarea_ref.get("tarea")
                ):
                    t["google_event_id"] = g_id
                    break
            storage.guardar_historial(historial)


def sincronizar_tarea_creada_async(tarea_ref, fecha_iso):
    def _worker():
        with _google_lock:
            try:
                ids = agregar_eventos_al_calendario([tarea_ref], fecha_iso=fecha_iso)
                g_id = ids[0] if ids else None
                _guardar_google_id_en_storage(fecha_iso, tarea_ref, g_id)
            except Exception as e:
                tarea_ref["google_event_id"] = None
                print(f"⚠️ Error creando tarea en Google: {e}")

    _ejecutar_en_segundo_plano(_worker)


def sincronizar_tarea_actualizada_async(tarea_ref, fecha_iso):
    def _worker():
        with _google_lock:
            try:
                ev_id = tarea_ref.get("google_event_id")
                if not ev_id or ev_id == "PENDING":
                    hoy_iso = datetime.date.today().isoformat()
                    if fecha_iso != hoy_iso:
                        historial = storage.cargar_historial()
                        tid = tarea_ref.get("id")
                        for t in historial.get(fecha_iso, {}).get("tareas", []):
                            if tid and t.get("id") == tid:
                                ev_id = t.get("google_event_id")
                                break

                nuevo_id = actualizar_evento_calendario(ev_id, tarea_ref, fecha_iso=fecha_iso)
                if nuevo_id and nuevo_id != ev_id:
                    _guardar_google_id_en_storage(fecha_iso, tarea_ref, nuevo_id)
            except Exception as e:
                print(f"⚠️ Error actualizando tarea en Google: {e}")

    _ejecutar_en_segundo_plano(_worker)


def eliminar_evento_calendario_async(event_id):
    if not event_id or event_id == "PENDING":
        return

    def _worker():
        with _google_lock:
            try:
                eliminar_evento_calendario(event_id)
            except Exception as e:
                print(f"⚠️ Error eliminando en Google: {e}")

    _ejecutar_en_segundo_plano(_worker)


# ==========================================
# MANEJO DE EVENTOS FIJOS EN GOOGLE CALENDAR
# ==========================================

def agregar_evento_fijo_calendario(evento_dict):
    service = obtener_servicio()
    fecha_iso = evento_dict.get('fecha', datetime.date.today().isoformat())
    ini_iso, fin_iso = _construir_fechas_rfc3339(
        fecha_iso,
        evento_dict.get('hora_inicio', '09:00'),
        evento_dict.get('hora_fin', '09:30')
    )

    try:
        cal_meta = service.calendars().get(calendarId='primary').execute()
        tz_iana = cal_meta.get('timeZone', 'Europe/Madrid')
    except Exception:
        tz_iana = 'Europe/Madrid'

    cuerpo = {
        'summary': evento_dict['titulo'],
        'colorId': '10',
        'start': {'dateTime': ini_iso, 'timeZone': tz_iana},
        'end': {'dateTime': fin_iso, 'timeZone': tz_iana},
        'extendedProperties': {
            'private': {'tipo_elemento': 'evento_fijo'}
        }
    }

    mapa_rrule = {
        'daily': 'RRULE:FREQ=DAILY',
        'weekly': 'RRULE:FREQ=WEEKLY',
        'monthly': 'RRULE:FREQ=MONTHLY',
        'yearly': 'RRULE:FREQ=YEARLY'
    }
    repite = evento_dict.get('repite', 'none')
    if repite in mapa_rrule:
        cuerpo['recurrence'] = [mapa_rrule[repite]]

    creado = service.events().insert(calendarId='primary', body=cuerpo).execute()
    return creado.get('id')


def sincronizar_evento_fijo_creado_async(evento_dict):
    def _worker():
        with _google_lock:
            try:
                g_id = agregar_evento_fijo_calendario(evento_dict)
                if not g_id:
                    return
                eventos = storage.cargar_eventos_raw()
                for ev in eventos:
                    if ev.get("id") == evento_dict.get("id"):
                        ev["google_event_id"] = g_id
                        break
                storage.guardar_eventos_raw(eventos)
            except Exception as e:
                print(f"⚠️ Error sincronizando evento fijo con Google: {e}")

    _ejecutar_en_segundo_plano(_worker)



# ==========================================
# ESPEJO DE DÍA COMPLETO (PARA PESTAÑA INICIO)
# ==========================================

def reemplazar_dia_en_google_async(fecha_iso, ids_anteriores, nuevas_tareas_ref):
    def _worker():
        with _google_lock:
            for old_id in ids_anteriores:
                if old_id and old_id != "PENDING":
                    try:
                        eliminar_evento_calendario(old_id)
                    except Exception:
                        pass

            for tarea in nuevas_tareas_ref:
                try:
                    ids = agregar_eventos_al_calendario([tarea], fecha_iso=fecha_iso)
                    g_id = ids[0] if ids else None
                    _guardar_google_id_en_storage(fecha_iso, tarea, g_id)
                except Exception as e:
                    tarea["google_event_id"] = None
                    print(f"⚠️ Error subiendo tarea de rutina a Google: {e}")

    _ejecutar_en_segundo_plano(_worker)


def sincronizar_semana_con_google(inicio_semana_date):
    pass
