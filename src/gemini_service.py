import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

def generar_horario_diario(contexto_fijo, input_hoy, agenda_actual):
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    prompt = f"""
    Eres un asistente de productividad personal.
    
    1. CONTEXTO FIJO DEL USUARIO (Reglas permanentes):
    {contexto_fijo}
    
    2. OBJETIVOS ESPECÍFICOS PARA HOY (Prioridad del día):
    {input_hoy}
    
    3. EVENTOS YA AGENDADOS EN GOOGLE CALENDAR HOY (No solapar):
    {agenda_actual}
    
    Genera un horario estructurado para hoy en formato JSON puro.
    Responde ÚNICAMENTE con una lista JSON válida con esta estructura exacta:
    [
        {{
            "hora_inicio": "09:00",
            "hora_fin": "10:30",
            "tarea": "Descripción de la tarea",
            "tipo": "estudio|trabajo|ejercicio|descanso",
            "completado": false
        }}
    ]
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        texto = response.text.strip()
        if texto.startswith("```json"):
            texto = texto[7:]
        if texto.startswith("```"):
            texto = texto[3:]
        if texto.endswith("```"):
            texto = texto[:-3]
        return json.loads(texto.strip())
    except Exception as e:
        print(f"⚠️ Error en la API de Gemini: {e}")
        return []