$ErrorActionPreference = "Stop"
Start-Process powershell.exe -ArgumentList @("-NoExit","-ExecutionPolicy","Bypass","-File","E:\superagent-sentinel-v2\scripts\start-backend.ps1")
Start-Sleep -Seconds 2
Start-Process powershell.exe -ArgumentList @("-NoExit","-ExecutionPolicy","Bypass","-File","E:\superagent-sentinel-v2\scripts\start-frontend.ps1")
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5173"
Start-Process "http://127.0.0.1:8000/docs"
