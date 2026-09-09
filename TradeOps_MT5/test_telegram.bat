@echo off
chcp 65001 > nul
title TradeOps Telegram - Teste de Envio
echo ========================================================
echo         TradeOps - Teste de Conexao com Telegram        
echo ========================================================
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0tradeops_telegram.ps1" -Test

echo.
echo ========================================================
echo Teste finalizado. Verifique se recebeu a mensagem no celular!
echo ========================================================
pause
