# run.py
import argparse
import yaml
from gunicorn.app.base import BaseApplication
from app import app


class FlaskApp(BaseApplication):
    def __init__(self, app, config_path):
        self.application = app
        self.config_path = config_path
        self.options = self.load_config_from_yaml()
        super().__init__()

    def load_config_from_yaml(self):
        default_options = {
            "bind": "127.0.0.1:8000",
            "workers": 1,
        }
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                host = config.get('server', {}).get('host', '127.0.0.1')
                port = config.get('server', {}).get('port', 8000)
                default_options["bind"] = f"{host}:{port}"
        except Exception as e:
            print(f"Warning loading config: {e}")
        return default_options

    def load_config(self):
        for key, value in self.options.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", default="config/config.yaml", help="Path to config YAML")
    args = parser.parse_args()
    FlaskApp(app, config_path=args.config).run()
