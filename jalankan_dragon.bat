@echo off
setlocal
title Launcher - 9Router + Hermes Desktop

rem ===== PENGATURAN (ubah di sini kalau perlu) =====
set "PROJECT_DIR=D:\Fauzih\Kuliah\SEMESTER V\Proyek Multimedia dan Game\AR Dragon"
set "ROUTER_PORT=20128"
set "ROUTER_CMD=9router"
set "MAX_WAIT=60"
rem =================================================

echo [1/3] Mengecek 9Router di port %ROUTER_PORT% ...
netstat -ano | findstr /R /C:":%ROUTER_PORT% .*LISTENING" >nul
if %errorlevel%==0 (
    echo       9Router sudah berjalan, dilewati.
    goto start_hermes
)

echo [2/3] Menjalankan 9Router ...
start "9Router" cmd /k %ROUTER_CMD%

set /a waited=0
:wait_loop
timeout /t 2 /nobreak >nul
set /a waited+=2
netstat -ano | findstr /R /C:":%ROUTER_PORT% .*LISTENING" >nul
if %errorlevel%==0 goto router_ready
if %waited% GEQ %MAX_WAIT% (
    echo.
    echo [!] 9Router tidak aktif setelah %MAX_WAIT% detik.
    echo     Cek jendela "9Router" untuk melihat error.
    echo     Pastikan nilai ROUTER_CMD di file ini benar.
    pause
    exit /b 1
)
goto wait_loop

:router_ready
echo       9Router siap di http://localhost:%ROUTER_PORT%

:start_hermes
echo [3/3] Menjalankan Hermes Desktop ...
cd /d "%PROJECT_DIR%"
start "Hermes Desktop" cmd /k hermes desktop --cwd "%PROJECT_DIR%"

echo.
echo Selesai. Jendela ini akan menutup dalam 5 detik.
timeout /t 5 >nul
endlocal
