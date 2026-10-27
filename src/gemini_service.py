import os
import json
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def generar_horario_diario(situacion_hoy: str, agenda_actual: str) -> list:
    """
    Le pide a Gemini que cree un horario respetando los eventos existentes.
    Si los servidores fallan por saturación, activa un horario de respaldo automático.
    """
    print("🧠 Gemini está pensando tu horario ideal...")
    
    prompt = f"""
    Eres un asistente experto en productividad. Crea un horario para hoy basándote en esta petición del usuario: '{situacion_hoy}'.
    
    REGLA VITAL: El usuario ya tiene estos eventos hoy y NO PUEDES programar nada que se solape con ellos:
    {agenda_actual}
    
    Genera un horario que encaje en los huecos libres. 
    Devuelve ÚNICAMENTE un arreglo JSON válido con esta estructura exacta, sin texto extra, sin markdown (```json):
    [
        {{
            "hora_inicio": "HH:MM",
            "hora_fin": "HH:MM",
            "tarea": "Nombre de la tarea",
            "tipo": "estudio/descanso/trabajo/ejercicio",
            "completado": false
        }}
    ]
    Usa formato de 24 horas (ej. 14:30).
    """
    
    intentos = 2
    for intento in range(intentos):
        try:
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt,
            )
            
            texto_limpio = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(texto_limpio)
            
        except Exception as e:
            print(f"⚠️ Intento {intento + 1} fallido por saturación. Reintentando...")
            time.sleep(2)
            
    # PLAN DE RESPALDO (Fallback) si Google sigue colapsado
    print("⚠️ Servidores de Gemini saturados. Activando plan de respaldo inteligente...")
    horario_emergencia = [
        {
            "hora_inicio": "16:00",
            "hora_fin": "17:30",
            "tarea": "Bloque de estudio intensivo (Modo Respaldo)",
            "tipo": "estudio",
            "completado": False
        },
        {
            "hora_inicio": "17:30",
            "hora_fin": "18:00",
            "tarea": "Descanso y estiramientos",
            "tipo": "descanso",
            "completado": False
        },
        {
            "hora_inicio": "18:00",
            "hora_fin": "19:30",
            "tarea": "Proyecto de programación / Práctica",
            "tipo": "trabajo",
            "completado": False
        }
    ]
    return horario_emergencia

if __name__ == "__main__":
    agenda_falsa = "- Algorítmica: 10:15 a 11:45\n- Comida: 14:00 a 15:00"
    resultado = generar_horario_diario("Quiero estudiar Python", agenda_falsa)
    print(json.dumps(resultado, indent=4, ensure_ascii=False))