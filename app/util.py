import base64
import json


def socket_send_file(sock, filepath, filename=None):
    """Send an encoded file via a flask_sock websocket.
    
    Args:
        sock: flask_sock websocket
        filepath: system path to file
        filename: filename to suggest to the recipient. The trailing part of
            'filepath' is used as a default filename.
    """
    if filename is None:
        filename = filepath.split("/")[-1]

    with open(filepath, "rb") as f:
        file_b64 = base64.b64encode(f.read()).decode()
    packet = { "type": "file", "filename": filename, "base64": file_b64 }
    sock.send(json.dumps(packet))


def socket_inform_error(sock, message):
    packet = { "type": "error", "value": message }
    sock.send(json.dumps(packet))


class SocketLogger():
    """Class which provides the basic logging interface (debug(), info, ...)
    and is used to redirect regular logging statements via a flask_sock
    websocket.
    
    We cannot use regular loggers from the logging library, as these modify
    global state and we'd need one logger per websocket (i.e. one per active
    user of the website).
    """
    def __init__(self, sock, outfile):
        self.sock = sock  # socket to send logs to
        self.outfile = outfile  # additional logfile; filehandle must be closed manually

    def encode_and_send_line(self, line):
        packet = { "type": "log", "value": line.replace(" ", "&nbsp;").rstrip() }
        self.sock.send(json.dumps(packet))

    def emit(self, prefix, message):
        self.outfile.write(f"[{prefix}] {message}\n")
        
        # Split the message into lines for simpler client code.
        lines = message.split("\n")
        self.encode_and_send_line(f"[{prefix}] {lines[0]}")
        for line in lines[1:]:
            self.encode_and_send_line(f"{(len(prefix)+2)*' '} {line}")

    def debug(self, message):
        self.emit("DEBU", message)

    def info(self, message):
        self.emit("INFO", message)

    def warning(self, message):
        self.emit("WARN", message)

    def error(self, message):
        self.emit("ERRO", message)

    def critical(self, message):
        self.emit("CRIT", message)


