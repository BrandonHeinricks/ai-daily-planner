from flask import Flask
import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from ui import ui_bp
from tareas import tareas_bp
from calendario import calendario_bp
from heatmap import heatmap_bp
from contexto import contexto_bp

app = Flask(__name__, static_folder='../static')

# Registramos cada módulo independiente
app.register_blueprint(ui_bp)
app.register_blueprint(tareas_bp)
app.register_blueprint(calendario_bp)
app.register_blueprint(heatmap_bp)
app.register_blueprint(contexto_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5000)