from flask import Blueprint

calendario_bp = Blueprint('calendario', __name__, template_folder='templates')

from . import routes