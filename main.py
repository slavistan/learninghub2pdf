import yaml

from app import app

if __name__ == "__main__":
    app.config = app.config | yaml.safe_load(open("./config.yml"))
    app.run("0.0.0.0", app.config["port"])
