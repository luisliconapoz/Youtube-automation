#!/usr/bin/env bash
# Conecta OneDrive a Pilo Studio desde un Codespace (pensado para iPad, sin PC).
# Solo hace falta hacerlo UNA vez: al final imprime el valor del secreto RCLONE_CONF_B64.
set -euo pipefail
CONF="$HOME/.config/rclone/rclone.conf"

cat <<'TXT'
════════════════════════════════════════════════════════════════════
  CONECTAR ONEDRIVE: sigue estos pasos (unos 3 minutos)
════════════════════════════════════════════════════════════════════
 1. A continuación rclone hará preguntas. Responde:
      name>                     onedrive
      Storage>                  onedrive
      client_id> / client_secret>   (Enter, en blanco)
      region>                   1  (Microsoft Cloud Global)
      Edit advanced config?     n
      Use web browser...?       y
 2. rclone mostrará un enlace http://127.0.0.1:53682/auth?state=...
    Ábrelo (el Codespace lo redirige solo). Inicia sesión en Microsoft.
 3. Al terminar, Safari mostrará un ERROR en una página "localhost:53682".
    ¡Es normal! Copia la URL COMPLETA de esa página de error.
 4. Abre una SEGUNDA terminal (botón + de la terminal) y ejecuta:
        curl "PEGA_AQUÍ_LA_URL"
    Vuelve a la primera terminal: rclone ya habrá recibido el permiso.
 5. Elige "OneDrive Personal or Business" (normalmente opción 1),
    confirma la unidad (y) y termina (y, luego q).
════════════════════════════════════════════════════════════════════
TXT
read -rp "Pulsa Enter para empezar…" _
rclone config

if ! rclone listremotes | grep -q '^onedrive:$'; then
  echo "⚠️  No se encontró el remoto 'onedrive'. Si le diste otro nombre, ajusta salida.nube.destino en config/settings.yaml."
fi
echo
echo "Probando acceso…"
rclone mkdir onedrive:PiloStudio/Videos && rclone lsd onedrive:PiloStudio && echo "✅ OneDrive conectado."
echo
echo "Para que funcione en futuros Codespaces y en GitHub Actions, guarda este valor como secreto RCLONE_CONF_B64:"
echo "  • Codespaces: github.com/settings/codespaces → New secret (dale acceso a este repositorio)"
echo "  • Actions:    repositorio → Settings → Secrets and variables → Actions → New repository secret"
echo "────────────────────────── copiar desde aquí ──────────────────────────"
base64 -w0 "$CONF"; echo
echo "────────────────────────── hasta aquí ─────────────────────────────────"
