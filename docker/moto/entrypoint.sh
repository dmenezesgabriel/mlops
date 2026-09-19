#!/bin/sh
# Start moto_server with the Glue overlay applied (see glue_overlay.py).
# Keeps the official image unchanged: the compose volume mounts this directory
# at /docker/moto and PYTHONPATH exposes the patch to -c below; -H/-p flags
# coming from the compose `command` are forwarded to moto.server.main.
export PYTHONPATH=/docker/moto
exec python -c 'import glue_overlay; glue_overlay.apply_overlay(); from moto.server import main; main()' "$@"