// Hermes en PM2 (REGLAS_ECOSISTEMA regla 7: nada corre a mano en PM2).
// Arrancar desde esta carpeta:  pm2 start ecosystem.config.js && pm2 save
// Hermes no escucha en ningún puerto (usa polling de Telegram), así que no necesita registro en ports.json.
module.exports = {
  apps: [
    {
      name: 'hermes',
      script: 'bot.py',
      interpreter: process.platform === 'win32' ? 'python' : 'python3',
      cwd: __dirname,
      autorestart: true,
      min_uptime: '30s',
      max_restarts: 10,
      restart_delay: 5000,
      stop_exit_codes: [78], // falta configuración: no reiniciar en bucle
      max_memory_restart: '400M',
      time: true,
    },
  ],
};
