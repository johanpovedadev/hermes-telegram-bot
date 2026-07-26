$args = $args
if ($args.Count -eq 0) {
    Write-Host "Uso: oc 'tu prompt aqui'"
    exit 1
}

$prompt = $args -join " "
Write-Host "Ejecutando: $prompt"

& "$env:APPDATA\npm\opencode.cmd" run $prompt
$exitCode = $LASTEXITCODE

$chatId = if ($env:HERMES_CHAT_ID) { $env:HERMES_CHAT_ID } else { "5534032418" }
$token = $env:HERMES_BOT_TOKEN
if (-not $token) {
    Write-Host "Configura HERMES_BOT_TOKEN en tu entorno o .env."
    exit 1
}

if ($exitCode -eq 0) {
    $msg = "Tarea completada`nPrompt: $prompt"
} else {
    $msg = "Error en tarea (exit $exitCode)`nPrompt: $prompt"
}

$uri = "https://api.telegram.org/bot$token/sendMessage"
$body = @{ chat_id = $chatId; text = $msg } | ConvertTo-Json
Invoke-RestMethod -Uri $uri -Method Post -Body $body -ContentType "application/json"

Write-Host "Notificacion enviada a Telegram"
