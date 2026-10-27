import os
import json
import datetime

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data'))
HISTORY_FILE = os.path.join(DATA_DIR, 'history.json')
CONTEXT_FILE = os.path.join(DATA_DIR, 'context.json')

TAREAS_HOY = []

def asegurar_archivos():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    if not os.path.exists(CONTEXT_FILE):
        with open(CONTEXT_FILE, 'w', encoding='utf-8') as f:
            json.dump({"contexto": "Quiero estudiar programación, hacer ejercicio y mantener un balance adecuado."}, f)

asegurar_archivos()

def cargar_contexto():
    try:
        with open(CONTEXT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f).get("contexto", "")
    except:
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
    except:
        return {}

def guardar_historial(historial):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(historial, f, ensure_ascii=False, indent=4)

def recalcular_rendimiento():
    global TAREAS_HOY
    total = len(TAREAS_HOY)
    hoy_str = datetime.date.today().isoformat()
    historial = cargar_historial()
    
    if total > 0:
        completadas = sum(1 for t in TAREAS_HOY if t["completado"])
        porcentaje = completadas / total
        historial[hoy_str] = {
            "score": porcentaje,
            "tareas": TAREAS_HOY
        }
    else:
        if hoy_str in historial:
            del historial[hoy_str]
    guardar_historial(historial)