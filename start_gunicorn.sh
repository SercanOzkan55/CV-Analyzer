#!/bin/bash
# Production Gunicorn + Uvicorn worker start script
export ENV=production
exec gunicorn main:app -k uvicorn.workers.UvicornWorker -w 4 --timeout 120 --log-level info --bind 0.0.0.0:8000
