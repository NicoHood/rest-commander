#!/usr/bin/env python3

import logging
import os
from fastapi import FastAPI, HTTPException, Request
import subprocess
import tomllib as toml
from pathlib import Path

__author__ = "NicoHood"
__version__ = "1.0.0"
__license__ = "MIT"

import sys

# Require minimum version
if not sys.version_info >= (3, 11):
    print('Minimum python version required: >=3.11', file=sys.stderr)
    sys.exit(1)

# Konfiguration des Loggings
logging.basicConfig(level=logging.DEBUG)  # Legen Sie das gewünschte Log-Level fest

app = FastAPI()

# Lade die Konfiguration aus einer TOML-Datei
def load_config(config_file):
    with open(config_file, 'rb') as f:
        # TODO check if flag and default are used at the same time -> should give an error
        return toml.load(f)

@app.get("/execute/{command_id}")
async def execute_command(
    command_id: str,
    request: Request
):
    logging.debug(f"Command ID: {command_id}")

    # Überprüfen, ob die Befehls-ID in der Konfiguration existiert
    command_data = config.get("commands", {}).get(command_id)
    if command_data is None:
        logging.error(f"Ungültige Befehls-ID: {command_id}")
        raise HTTPException(status_code=400, detail=f"Ungültige Befehls-ID: {command_id}")

    # Überprüfen, ob der Befehl einen absoluten Pfad hat
    command = command_data["command"]
    if not os.path.isabs(command):
        logging.error(f"Der Befehl '{command}' ist kein absoluter Pfad")
        raise HTTPException(status_code=400, detail=f"Der Befehl '{command}' ist kein absoluter Pfad")

    # Überprüfen, ob die übergebenen Parameter erlaubt und erforderlich sind
    allowed_params = command_data.get("params", [])
    param_list = []

    for param_name, param_value in request.query_params.items():
        param_config = next((param for param in allowed_params if param["name"] == param_name), None)
        if param_config:
            cmdline_arg = param_config.get('cmdline_arg')
            if cmdline_arg:
                param_list.append(cmdline_arg)
            # Do not append value if this is a flag parameter (e.g. ?help -> --help)
            if not param_config.get('flag', False):
                param_list.append(param_value)
        else:
            logging.error(f"Parameter '{param_name}' ist nicht erlaubt")
            raise HTTPException(status_code=400, detail=f"Parameter '{param_name}' ist nicht erlaubt")

    for param_config in allowed_params:
        param_name = param_config["name"]
        if param_config.get('required', False) and param_name not in request.query_params:
            logging.error(f"Erforderlicher Parameter '{param_name}' fehlt")
            raise HTTPException(status_code=400, detail=f"Erforderlicher Parameter '{param_name}' fehlt")

        default_value = param_config.get('default')
        if default_value and param_name not in request.query_params:
            logging.debug(f"Default Parameter '{param_name}' mit Wert '{param_config.get('default')}")

            cmdline_arg = param_config.get('cmdline_arg')
            if cmdline_arg:
                param_list.append(cmdline_arg)
            param_list.append(default_value)

    # Get fixed params that we always prepend
    fixed_params = command_data.get('fixed_params', [])

    command_to_execute = [command_data["command"]] + fixed_params + param_list
    logging.debug(f"Command to execute: {command_to_execute}")

    # Shell-Befehl ausführen (ohne shell)
    result = subprocess.run(
        command_to_execute,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Ergebnis zurückgeben
    logging.debug(f"Shell result: {result.stdout}, {result.stderr}")
    return {
        "command": command_to_execute,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode
    }

if __name__ == "__main__":
    """ This is executed when run from the command line """
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description='Rest Commander')

    parser.add_argument("-c", "--config", action="store", type=str, default=Path(__file__).with_name('config.toml').absolute(), help="Custom config file location")

    # Optional verbosity counter (eg. -v, -vv, -vvv, etc.)
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbosity (-v, -vv, etc)")

    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s (version {__version__})")
    args = parser.parse_args()

    if args.verbose == 1:
        logging.getLogger().setLevel(logging.INFO)
    elif args.verbose >=2:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.WARNING)

    config = load_config(args.config)

    # Starte die FastAPI-Anwendung
    uvicorn.run(app, host="127.0.0.1", port=8000)
