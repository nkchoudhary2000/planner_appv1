from flask import Blueprint

planner = Blueprint('planner', __name__)

from app.planner import routes
