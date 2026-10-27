import os
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Este es el permiso estricto solo para leer y editar tus eventos
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def obtener_servicio_calendario():
    """Autentica al usuario y devuelve el servicio de Google Calendar."""
    creds = None
    
    # El archivo token.json almacena tus tokens de acceso y actualización
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Si no hay credenciales válidas disponibles, pide iniciar sesión
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            # Esto abrirá el navegador para que aceptes
            creds = flow.run_local_server(port=0)
        
        # Guarda las credenciales para la próxima ejecución
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)

def agregar_eventos_al_calendario(horario_json):
    """Recibe la lista de tareas en JSON y las inyecta en el calendario de hoy."""
    servicio = obtener_servicio_calendario()
    hoy = datetime.date.today().isoformat()
    
    print("Conectando con Google Calendar...")
    
    for bloque in horario_json:
        # Formateamos las horas para cumplir con el estándar ISO que pide Google
        inicio = f"{hoy}T{bloque['hora_inicio']}:00"
        fin = f"{hoy}T{bloque['hora_fin']}:00"
        
        evento = {
            'summary': bloque['tarea'],
            'description': f"Tipo de bloque: {bloque['tipo']}",
            'start': {
                'dateTime': inicio,
                'timeZone': 'Europe/Madrid',
            },
            'end': {
                'dateTime': fin,
                'timeZone': 'Europe/Madrid',
            },
        }

        # Insertar el evento en tu calendario principal
        servicio.events().insert(calendarId='primary', body=evento).execute()
        print(f"✅ Evento agendado: {bloque['tarea']} ({bloque['hora_inicio']} - {bloque['hora_fin']})")

def obtener_eventos_de_hoy():
    """Lee tus eventos actuales para pasárselos a Gemini y evitar solapamientos."""
    servicio = obtener_servicio_calendario()
    
    # Calculamos el inicio y fin del día actual para buscar eventos (versión moderna)
    ahora = datetime.datetime.now(datetime.UTC).isoformat().replace('+00:00', 'Z')
    fin_dia = (datetime.datetime.now(datetime.UTC).replace(hour=23, minute=59, second=59)).isoformat().replace('+00:00', 'Z')
    
    print("Revisando tu agenda actual...")
    
    # Pedimos a Google los eventos desde este momento hasta la medianoche
    eventos_result = servicio.events().list(
        calendarId='primary', 
        timeMin=ahora,
        timeMax=fin_dia,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    eventos = eventos_result.get('items', [])
    
    if not eventos:
        return "No hay eventos programados para el resto del día."
    
    agenda = []
    for evento in eventos:
        inicio = evento['start'].get('dateTime', evento['start'].get('date'))
        fin = evento['end'].get('dateTime', evento['end'].get('date'))
        resumen = evento.get('summary', 'Ocupado')
        
        # Limpiamos un poco el formato de la hora para que la IA lo entienda fácil
        inicio_hora = inicio.split('T')[1][:5] if 'T' in inicio else "Todo el día"
        fin_hora = fin.split('T')[1][:5] if 'T' in fin else ""
        
        agenda.append(f"- {resumen}: {inicio_hora} a {fin_hora}")
        
    return "\n".join(agenda)

# --- ZONA DE PRUEBAS ---
if __name__ == '__main__':
    # Probamos leer los eventos de hoy
    mi_agenda = obtener_eventos_de_hoy()
    print("\n--- LO QUE VE LA IA EN TU CALENDARIO ---")
    print(mi_agenda)