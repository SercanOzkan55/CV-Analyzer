#!/bin/bash
# Production Gunicorn + Uvicorn worker start script
export ENV="${ENV:-production}"
exec gunicorn main:app -c gunicorn_config.py
