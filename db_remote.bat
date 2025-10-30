@echo off
REM ========================================
REM  Configurar Banco de Dados - MODO REMOTO
REM ========================================

echo.
echo ========================================
echo  CONFIGURANDO BANCO DE DADOS - REMOTO
echo ========================================
echo.
echo Host: hfsemear.ddns.net:1521
echo Service: XE
echo.

REM Definir variável de ambiente para a sessão atual
set DB_MODE=remote

echo Modo REMOTO ativado!
echo.
echo Parando processos Python anteriores...
taskkill /F /IM python.exe 2>nul
timeout /t 3 /nobreak >nul
echo.
echo Iniciando servidor Django...
echo.

REM Iniciar servidor Django
py manage.py runserver 0.0.0.0:8000

pause
