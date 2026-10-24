@echo off
title Launcher Hermes Desktop + OmniRoute
color 0A

echo ======================================================
echo       STARTING OMNIROUTE & HERMES DESKTOP
echo ======================================================
echo.

:: 1. Cek apakah OmniRoute sudah berjalan di port 20128
netstat -ano | findstr :20128 >nul 2>&1
if %errorlevel% equ 0 (
    echo [*] OmniRoute sudah aktif di port 20128.
) else (
    echo [*] Menjalankan OmniRoute di background...
    start "OmniRoute Service" /min cmd /k "omniroute"
    
    echo [*] Menunggu inisialisasi server OmniRoute...
    timeout /t 4 /nobreak >nul
)

:: 2. Set endpoint default ke OmniRoute (OpenAI-compatible)
set OPENAI_BASE_URL=http://localhost:20128/v1

echo.
echo [*] Endpoint aktif: %OPENAI_BASE_URL%
echo [*] Membuka Hermes Desktop...

:: 3. Deteksi dan Jalankan Hermes Desktop
set "HERMES_FOUND=0"

:: Cek lokasi 1: Local AppData Programs
if exist "%LOCALAPPDATA%\Programs\Hermes\Hermes.exe" (
    start "" "%LOCALAPPDATA%\Programs\Hermes\Hermes.exe"
    set "HERMES_FOUND=1"
    goto :SUCCESS
)

:: Cek lokasi 2: Local AppData Hermes Desktop
if exist "%LOCALAPPDATA%\hermes-desktop\Hermes Desktop.exe" (
    start "" "%LOCALAPPDATA%\hermes-desktop\Hermes Desktop.exe"
    set "HERMES_FOUND=1"
    goto :SUCCESS
)

:: Cek lokasi 3: Program Files
if exist "C:\Program Files\Hermes\Hermes.exe" (
    start "" "C:\Program Files\Hermes\Hermes.exe"
    set "HERMES_FOUND=1"
    goto :SUCCESS
)

:: Cek lokasi 4: Program Files (x86)
if exist "C:\Program Files (x86)\Hermes\Hermes.exe" (
    start "" "C:\Program Files (x86)\Hermes\Hermes.exe"
    set "HERMES_FOUND=1"
    goto :SUCCESS
)

:: Cek lokasi 5: Desktop Shortcut
if exist "%USERPROFILE%\Desktop\Hermes Desktop.lnk" (
    start "" "%USERPROFILE%\Desktop\Hermes Desktop.lnk"
    set "HERMES_FOUND=1"
    goto :SUCCESS
)
if exist "%USERPROFILE%\Desktop\Hermes.lnk" (
    start "" "%USERPROFILE%\Desktop\Hermes.lnk"
    set "HERMES_FOUND=1"
    goto :SUCCESS
)

:: Cek lokasi 6: Coba panggil via command sistem
where hermes >nul 2>&1
if %errorlevel% equ 0 (
    start "" hermes desktop >nul 2>&1 || start "" hermes
    set "HERMES_FOUND=1"
    goto :SUCCESS
)

:SUCCESS
if "%HERMES_FOUND%"=="1" (
    echo [OK] OmniRoute dan Hermes Desktop berhasil dijalankan!
    timeout /t 3 >nul
    exit
) else (
    echo.
    echo [!] PERINGATAN: File executable Hermes Desktop tidak ditemukan di lokasi standar.
    echo Silakan buka file ini dengan Notepad dan ubah baris path berikut sesuai lokasi file .exe Anda:
    echo     start "" "C:\Path\Ke\Hermes.exe"
    echo.
    pause
)
