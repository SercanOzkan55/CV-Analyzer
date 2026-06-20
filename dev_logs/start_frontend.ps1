$ErrorActionPreference = 'Continue'
$env:Path = 'C:\Users\ASUS\Desktop\cv-analyzer\tools\node-v24.14.0-win-x64;' + $env:Path
$env:VITE_API_BASE = 'http://127.0.0.1:8001'
Set-Location 'C:\Users\ASUS\Desktop\cv-analyzer\frontend'
& 'C:\Users\ASUS\Desktop\cv-analyzer\tools\node-v24.14.0-win-x64\npm.cmd' run dev -- --host 127.0.0.1 --port 5173 *> 'C:\Users\ASUS\Desktop\cv-analyzer\dev_logs\frontend.log'
