@echo off
chcp 65001 > nul
title TradeOps Telegram Monitor
echo ========================================================
echo             TradeOps Telegram Monitor (VPS)             
echo ========================================================
echo.
echo [*] Iniciando monitoramento em segundo plano...
echo [*] Para fechar, pressione Ctrl+C ou feche esta janela.
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0tradeops_telegram.ps1"

echo.
echo [!] O monitor foi finalizado.
pause
