import os
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import storage

SCOPES = ['https://www.googleapis.com/auth/calendar']
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'token.json')

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

def agregar_eventos_al_calendario(lista_tareas, fecha_iso=None):
    """Crea tareas normales en Google Calendar en color AZUL (colorId: '9')."""
    service = obtener_servicio()
    if not fecha_iso:
        fecha_iso = datetime.date.today().isoformat()

    ids_creados = []
    for t in lista_tareas:
        ini_iso, fin_iso = _construir_fechas_rfc3339(fecha_iso, t['hora_inicio'], t['hora_fin'])
        evento = {
            'summary': t['tarea'],
            'colorId': '9',  # Azul para tareas normales
            'start': {'dateTime': ini_iso},
            'end': {'dateTime': fin_iso},
            'extendedProperties': {
                'private': {'tipo_elemento': 'tarea'}
            }
        }
        creado = service.events().insert(calendarId='primary', body=evento).execute()
        nuevo_id = creado.get('id')
        ids_creados.append(nuevo_id)
    return ids_creados

def agregar_evento_fijo_calendario(evento_dict):
    """
    Crea un Evento Fijo ('Mis Eventos') en Google Calendar en color VERDE (colorId: '10')
    y con su regla de repetición (RRULE) si aplica.
    """
    service = obtener_servicio()
    fecha_iso = evento_dict.get('fecha', datetime.date.today().isoformat())
    ini_iso, fin_iso = _construir_fechas_rfc3339(
        fecha_iso,
        evento_dict.get('hora_inicio', '09:00'),
        evento_dict.get('hora_fin', '09:30')
    )

    # Obtener la zona horaria IANA del calendario del usuario (necesaria para eventos recurrentes en Google)
    try:
        cal_meta = service.calendars().get(calendarId='primary').execute()
        tz_iana = cal_meta.get('timeZone', 'Europe/Madrid')
    except Exception:
        tz_iana = 'Europe/Madrid'

    cuerpo = {
        'summary': evento_dict['titulo'],
        'colorId': '10',  # Verde (Albahaca) en Google Calendar para Eventos
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

def actualizar_evento_calendario(event_id, tarea_dict, fecha_iso=None):
    if not fecha_iso:
        fecha_iso = datetime.date.today().isoformat()

    if not event_id:
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
    if not event_id:
        return
    service = obtener_servicio()
    service.events().delete(calendarId='primary', eventId=event_id).execute()

def sincronizar_semana_con_google(inicio_semana_date):
    try:
        service = obtener_servicio()
    except Exception as e:
        print(f"⚠️ No se pudo conectar a Google Calendar para sincronizar: {e}")
        return

    tz_local = datetime.datetime.now().astimezone().tzinfo
    hoy_iso = datetime.date.today().isoformat()
    historial = storage.cargar_historial()

    # 0. Asegurar que todos los Eventos Fijos ('Mis Eventos') estén subidos a Google Calendar en verde
    eventos_fijos_raw = storage.cargar_eventos_raw()
    eventos_modificados = False
    ids_eventos_fijos = set()

    for ev_fijo in eventos_fijos_raw:
        if not ev_fijo.get("google_event_id"):
            try:
                g_id = agregar_evento_fijo_calendario(ev_fijo)
                if g_id:
                    ev_fijo["google_event_id"] = g_id
                    eventos_modificados = True
            except Exception as e:
                print(f"⚠️ Error subiendo evento fijo a Google: {e}")
        if ev_fijo.get("google_event_id"):
            ids_eventos_fijos.add(ev_fijo["google_event_id"])

    if eventos_modificados:
        storage.guardar_eventos_raw(eventos_fijos_raw)

    # 1. Subir cualquier tarea normal que no tenga google_event_id todavía
    for i in range(7):
        d_iso = (inicio_semana_date + datetime.timedelta(days=i)).isoformat()
        locales = storage.TAREAS_HOY if d_iso == hoy_iso else historial.get(d_iso, {}).get("tareas", [])
        for t in locales:
            if not t.get("google_event_id"):
                try:
                    ids = agregar_eventos_al_calendario([t], fecha_iso=d_iso)
                    if ids:
                        t["google_event_id"] = ids[0]
                except Exception as e:
                    print(f"⚠️ Error subiendo tarea local a Google: {e}")

    # 2. Descargar eventos de la semana desde Google Calendar
    fin_semana_date = inicio_semana_date + datetime.timedelta(days=7)
    time_min = datetime.datetime.combine(inicio_semana_date, datetime.time.min, tzinfo=tz_local).isoformat()
    time_max = datetime.datetime.combine(fin_semana_date, datetime.time.min, tzinfo=tz_local).isoformat()

    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        items = events_result.get('items', [])
    except Exception as e:
        print(f"⚠️ Error al leer eventos de Google Calendar: {e}")
        return

    eventos_google_por_dia = {
        (inicio_semana_date + datetime.timedelta(days=i)).isoformat(): []
        for i in range(7)
    }

    for ev in items:
        if ev.get('status') == 'cancelled':
            continue

        # Ignorar los Eventos Fijos para que no se conviertan en tareas móviles
        ev_id = ev.get('id', '')
        recurring_id = ev.get('recurringEventId', '')
        tipo_privado = ev.get('extendedProperties', {}).get('private', {}).get('tipo_elemento')
        if (
            tipo_privado == 'evento_fijo' or
            ev_id in ids_eventos_fijos or
            recurring_id in ids_eventos_fijos or
            ev.get('colorId') == '10'
        ):
            continue

        start_raw = ev.get('start', {}).get('dateTime')
        end_raw = ev.get('end', {}).get('dateTime')
        if not start_raw or not end_raw:
            continue

        if start_raw.endswith('Z'):
            start_raw = start_raw[:-1] + '+00:00'
        if end_raw.endswith('Z'):
            end_raw = end_raw[:-1] + '+00:00'

        dt_ini = datetime.datetime.fromisoformat(start_raw).astimezone(tz_local)
        dt_fin = datetime.datetime.fromisoformat(end_raw).astimezone(tz_local)
        d_iso = dt_ini.date().isoformat()

        if d_iso in eventos_google_por_dia:
            eventos_google_por_dia[d_iso].append({
                "google_event_id": ev_id,
                "tarea": ev.get('summary', 'Sin título'),
                "hora_inicio": dt_ini.strftime("%H:%M"),
                "hora_fin": dt_fin.strftime("%H:%M")
            })

    # 3. Fusionar tareas normales conservando 'tipo' y 'completado'
    for d_iso, lista_google in eventos_google_por_dia.items():
        locales = storage.TAREAS_HOY if d_iso == hoy_iso else historial.get(d_iso, {}).get("tareas", [])
        mapa_locales_id = {t.get("google_event_id"): t for t in locales if t.get("google_event_id")}

        nueva_lista_dia = []
        for g_ev in lista_google:
            g_id = g_ev["google_event_id"]
            if g_id in mapa_locales_id:
                tarea_existente = mapa_locales_id[g_id]
                tarea_existente["tarea"] = g_ev["tarea"]
                tarea_existente["hora_inicio"] = g_ev["hora_inicio"]
                tarea_existente["hora_fin"] = g_ev["hora_fin"]
                nueva_lista_dia.append(tarea_existente)
            else:
                nueva_lista_dia.append({
                    "hora_inicio": g_ev["hora_inicio"],
                    "hora_fin": g_ev["hora_fin"],
                    "tarea": g_ev["tarea"],
                    "tipo": "estudio",
                    "completado": False,
                    "google_event_id": g_id
                })

        nueva_lista_dia.sort(key=lambda x: x["hora_inicio"])

        if d_iso == hoy_iso:
            storage.TAREAS_HOY = nueva_lista_dia
            storage.recalcular_rendimiento()
        else:
            if nueva_lista_dia:
                completadas = sum(1 for t in nueva_lista_dia if t.get("completado"))
                historial[d_iso] = {
                    "score": completadas / len(nueva_lista_dia),
                    "tareas": nueva_lista_dia
                }
            elif d_iso in historial:
                del historial[d_iso]

    storage.guardar_historial(historial)