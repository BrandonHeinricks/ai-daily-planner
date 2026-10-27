import datetime
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def obtener_servicio():
    creds = None
    token_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../token.json'))
    creds_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../credentials.json'))

    if os.path.exists(token_path) and os.path.getsize(token_path) > 0:
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def obtener_eventos_de_hoy():
    service = obtener_servicio()
    now = datetime.datetime.utcnow()
    inicio_dia = datetime.datetime(now.year, now.month, now.day, 0, 0, 0).isoformat() + 'Z'
    fin_dia = datetime.datetime(now.year, now.month, now.day, 23, 59, 59).isoformat() + 'Z'

    events_result = service.events().list(
        calendarId='primary', timeMin=inicio_dia, timeMax=fin_dia,
        singleEvents=True, orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])

    if not events:
        return "No hay eventos agendados para hoy."
    
    agenda_texto = ""
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        summary = event.get('summary', 'Sin título')
        agenda_texto += f"- {summary} ({start})\n"
    return agenda_texto

def agregar_eventos_al_calendario(horario):
    service = obtener_servicio()
    hoy = datetime.date.today().isoformat()
    ids_creados = []

    for tarea in horario:
        inicio = f"{hoy}T{tarea['hora_inicio']}:00"
        fin = f"{hoy}T{tarea['hora_fin']}:00"

        evento = {
            'summary': f"[{tarea['tipo'].upper()}] {tarea['tarea']}",
            'description': f"Creado por AI Daily Planner. Tipo: {tarea['tipo']}",
            'start': {'dateTime': inicio, 'timeZone': 'Europe/Madrid'},
            'end': {'dateTime': fin, 'timeZone': 'Europe/Madrid'},
        }

        evento_creado = service.events().insert(calendarId='primary', body=evento).execute()
        # Guardamos el ID que nos devuelve Google Calendar
        ids_creados.append(evento_creado.get('id'))
        print(f"✅ Evento creado en Google Calendar: {tarea['tarea']} (ID: {evento_creado.get('id')})")
        
    return ids_creados

def eliminar_evento_calendario(event_id):
    """Elimina un evento de Google Calendar usando su ID único"""
    if not event_id:
        return
    try:
        service = obtener_servicio()
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        print(f"🗑️ Evento con ID {event_id} eliminado de Google Calendar.")
    except Exception as e:
        print(f"⚠️ Error al eliminar evento de Google Calendar: {e}")