import logging

from flask import Flask
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

from app import routes