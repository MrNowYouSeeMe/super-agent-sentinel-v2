$ErrorActionPreference = "Stop"
Set-Location "E:\superagent-sentinel-v2\backend"
& "E:\superagent-sentinel-v2\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
