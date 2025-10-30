@echo off
REM ========================================
REM  Configurar Banco de Dados - MODO LOCAL
REM ========================================

echo.
echo ========================================
echo  CONFIGURANDO BANCO DE DADOS - LOCAL
echo ========================================
echo.
echo Host: 192.168.100.202:1521
echo Service: XE
echo.

REM Definir variável de ambiente para a sessão atual
set DB_MODE=local

echo Modo LOCAL ativado!
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
