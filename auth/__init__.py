from flask import Blueprint
from flask_login import login_required

auth = Blueprint('auth', __name__)

from . import routes