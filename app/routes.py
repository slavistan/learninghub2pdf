import shutil
import json
import tempfile
import shutil
import traceback
from datetime import datetime

from flask import render_template

from app import app, sock, logger, util, mock

from learninghub import ebook2pdf_userpass


@app.route("/")
@app.route("/index.html")
def index():
    logger.debug("Serve '/index.html'.")
    template_params = {
        "indexhtml_default": app.config.get("indexhtml", ""),
        "username_default": app.config.get("username", ""),
        "password_default": app.config.get("password", "")
    }
    return render_template("index.html", **template_params)


@sock.route("/websocket")
def websocket(sock):
    while True:
        # Wait for client to send the login credentials and the ebook's url.
        message = sock.receive()
        creds = json.loads(message)

        # Set up tempdir and logging.
        tmpdir = tempfile.mkdtemp(prefix=f"learninghub2pdf-{datetime.now().isoformat()}-", dir=app.config.get("tmpdir", "/tmp"))
        logfile = open(f"{tmpdir}/log", "w")
        socket_logger = util.SocketLogger(sock, logfile)

        # Use path segment prior to /index.html as filename.
        output_filename = creds["indexhtml"].split("/")[-2] + ".pdf"

        try:
            args = {
                "indexhtml": creds["indexhtml"],
                "username": creds["username"],
                "password": creds["password"],
                "output_filename": output_filename,
                "output_dir": tmpdir,
                "temp_dir": tmpdir,
                "max_pages": app.config.get("debug_max_pages", 1e6),
                "logger": socket_logger
            }
            if app.config.get("debug_learninghub_noop"):
                mock.ebook2pdf_userpass_learninghub_noop(**args)
            else:
                ebook2pdf_userpass(**args)
            util.socket_send_file(sock, f"{tmpdir}/{output_filename}")
            logfile.close()
            if not app.config.get("debug_no_cleanup"):
                shutil.rmtree(tmpdir)
        except Exception as e:
            # Uncaught exceptions indicate a critical error (most likely the website layout changed).
            socket_logger.critical(f"Uncaught exception: {traceback.format_exc()}")
            logfile.close()
            util.socket_inform_error(sock, "An error occurred. Please reload the page and try again.")
