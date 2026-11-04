# ==========================================
# IMPORTACIONES Y CONFIGURACIÓN
# ==========================================

import os
import json
import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

TIPOS_VALIDOS = {"carrera", "propios", "salud", "descanso"}
MAPA_TIPOS_IA = {
    "estudio": "carrera",
    "trabajo": "carrera",
    "gym": "salud",
    "ejercicio": "salud",
    "ocio": "descanso",
    "personal": "propios",
}


# ==========================================
# UTILIDADES DE FILTRADO DE HORA
# ==========================================

def _a_minutos(hhmm):
    try:
        h, m = map(int, str(hhmm).strip().split(":"))
        return h * 60 + m
    except Exception:
        return 0


def _filtrar_y_combinar_por_hora(tareas_nuevas, tareas_previas, hora_actual_str):
    min_actual = _a_minutos(hora_actual_str)
    resultado = []

    # 1. Conservar tareas de hoy que ya fueron completadas o que ya terminaron antes de esta hora
    if tareas_previas:
        for t_prev in tareas_previas:
            fin_prev = _a_minutos(t_prev.get("hora_fin", "00:00"))
            if t_prev.get("completado") or fin_prev <= min_actual:
                resultado.append(t_prev)

    # 2. Filtrar las tareas generadas por la IA para que ninguna empiece en el pasado
    for item in tareas_nuevas:
        ini_min = _a_minutos(item.get("hora_inicio", "00:00"))
        fin_min = _a_minutos(item.get("hora_fin", "00:00"))

        # Si la tarea entera termina antes o justo en la hora actual, se descarta
        if fin_min <= min_actual:
            continue

        # Si empezaba un poco antes de la hora actual pero termina después, recortamos su inicio a la hora actual
        if ini_min < min_actual:
            item["hora_inicio"] = hora_actual_str

        tipo_raw = str(item.get("tipo", "carrera")).lower().strip()
        if tipo_raw in MAPA_TIPOS_IA:
            tipo_raw = MAPA_TIPOS_IA[tipo_raw]
        if tipo_raw not in TIPOS_VALIDOS:
            tipo_raw = "carrera"

        item["tipo"] = tipo_raw
        item["completado"] = bool(item.get("completado", False))
        resultado.append(item)

    resultado.sort(key=lambda x: x.get("hora_inicio", "00:00"))
    return resultado


# ==========================================
# GENERACIÓN DE HORARIO CON GEMINI
# ==========================================

def generar_horario_diario(contexto_fijo, prompts_hoy, agenda_actual, tareas_actuales_hoy=None):
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    hora_actual_str = datetime.datetime.now().strftime("%H:%M")

    if isinstance(prompts_hoy, list):
        texto_prompts = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(prompts_hoy))
    else:
        texto_prompts = f"  1. {prompts_hoy}"

    if tareas_actuales_hoy:
        lineas_previas = [
            f"  - {t.get('hora_inicio')} a {t.get('hora_fin')}: {t.get('tarea')} ({t.get('tipo', 'carrera')})"
            for t in tareas_actuales_hoy
            if _a_minutos(t.get("hora_fin", "00:00")) > _a_minutos(hora_actual_str)
        ]
        bloque_horario_previo = "\n".join(lineas_previas) if lineas_previas else "Ninguna tarea futura programada aún."
    else:
        bloque_horario_previo = "Primera planificación del día (sin tareas previas)."

    prompt = f"""
Eres un asistente de productividad personal.

REGLA ESTRICTA DE HORA ACTUAL:
- La hora actual del usuario es EXACTAMENTE las {hora_actual_str}.
- PROHIBIDO programar cualquier bloque o tarea antes de las {hora_actual_str} (aunque el contexto fijo mencione actividades matutinas anteriores a las {hora_actual_str}, esas horas YA PASARON hoy).
- Todas las tareas que devuelvas deben tener "hora_inicio" igual o posterior a "{hora_actual_str}".

1. CONTEXTO FIJO DEL USUARIO (Reglas permanentes, aplica solo a las horas posteriores a las {hora_actual_str}):
{contexto_fijo}

2. HISTORIAL DE PROMPTS DE HOY (El usuario ha pedido esto hoy en orden cronológico; debes cumplir TODOS los prompts acumulados e integrar las modificaciones del último prompt sobre los anteriores):
{texto_prompts}

3. HORARIO QUE EL USUARIO TENÍA ARMADO HASTA AHORA PARA EL RESTO DE HOY (Úsalo como referencia si el nuevo prompt pide añadir algo antes/después de una tarea existente):
{bloque_horario_previo}

4. EVENTOS FIJOS YA AGENDADOS HOY (No solapar con estos horarios):
{agenda_actual}

Genera el horario actualizado desde las {hora_actual_str} en adelante en formato JSON puro.
Usa formato militar 24h (HH:MM) y asigna 'tipo' únicamente como 'carrera', 'propios', 'salud' o 'descanso'.
Responde ÚNICAMENTE con una lista JSON válida con esta estructura exacta, sin texto extra:
[
    {{
        "hora_inicio": "{hora_actual_str}",
        "hora_fin": "11:30",
        "tarea": "Descripción de la tarea",
        "tipo": "carrera",
        "completado": false
    }}
]
"""

    modelos_disponibles = [
        'gemini-3.8-flash',
        'gemini-3.6-flash',
        'gemini-3.5-flash',
        'gemini-3.5-flash-lite'
    ]

    for modelo in modelos_disponibles:
        print(f"🔄 Intentando generar rutina desde las {hora_actual_str} con: {modelo}...")
        try:
            response = client.models.generate_content(
                model=modelo,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )

            texto = response.text.strip()
            if texto.startswith("```json"):
                texto = texto[7:]
            elif texto.startswith("```"):
                texto = texto[3:]
            if texto.endswith("```"):
                texto = texto[:-3]

            datos = json.loads(texto.strip())

            if isinstance(datos, list):
                horario_filtrado = _filtrar_y_combinar_por_hora(
                    datos,
                    tareas_actuales_hoy or [],
                    hora_actual_str
                )
                print(f"✅ ¡Éxito con {modelo}! ({len(horario_filtrado)} tareas activas)")
                return horario_filtrado

        except Exception as e:
            print(f"⚠️ El modelo {modelo} falló ({e}). Pasando al siguiente...")
            continue

    print("❌ Todos los modelos fallaron o la cuota está saturada.")
    return []