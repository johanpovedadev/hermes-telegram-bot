@echo off
REM Reinicia la cola de Hermes (pm2 restart hermes). Resultado en reinicio_hermes.log.
cd /d "%~dp0"
echo ==== %date% %time% > reinicio_hermes.log
call pm2 restart hermes >> reinicio_hermes.log 2>&1
echo FIN >> reinicio_hermes.log
