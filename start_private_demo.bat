@echo off
title CV Analyzer - Private Local Demo
echo ====================================================
echo    CV ANALYZER - TAM GIZLILIK MODU (LOCAL DEMO)
echo ====================================================
echo.

:: 1. Gerekli klasoru olustur
if not exist "storage_data" (
    echo [1/3] Yerel depolama klasoru olusturuluyor...
    mkdir storage_data
) else (
    echo [1/3] Yerel depolama klasoru hazir.
)

:: 2. Gecici ayar dosyasini olustur
echo [2/3] Konfigurasyon hazirlaniyor...
echo STORAGE_BACKEND=local > .env.demo
echo LOCAL_STORAGE_PATH=./storage_data >> .env.demo
echo MOCK_SERVICES=true >> .env.demo
echo PRIVATE_MODE=true >> .env.demo
echo REGISTRATION_DISABLED=true >> .env.demo
echo ENV=development >> .env.demo

:: 3. Uygulamayi baslat
echo [3/3] Uygulama baslatiliyor...
echo.
echo ----------------------------------------------------
echo BILGI: Bu modda tum veriler 'storage_data' klasorunde 
echo saklanir. Internet (AWS/S3) kullanilmaz.
echo ----------------------------------------------------
echo.

:: Python'un yuklu oldugundan emin olalim ve baslatalim
set ENV_FILE=.env.demo
python -m uvicorn main:app --reload --port 8001

pause
