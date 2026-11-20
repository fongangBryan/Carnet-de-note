#!/bin/sh
# Démarre un écran virtuel, le rend accessible dans le navigateur (noVNC), puis lance l'application.
set -e

# 1. Écran virtuel
Xvfb "$DISPLAY" -screen 0 "$SCREEN" -nolisten tcp &
for _ in $(seq 50); do
    [ -e "/tmp/.X11-unix/X${DISPLAY#:}" ] && break
    sleep 0.1
done

# 2. Gestionnaire de fenêtres (barres de titre, déplacement des boîtes de dialogue)
openbox >/dev/null 2>&1 &

# 3. Serveur VNC (accessible uniquement depuis le conteneur) + passerelle web noVNC
x11vnc -display "$DISPLAY" -localhost -forever -shared -nopw -quiet -bg -rfbport 5900
websockify --web /usr/share/novnc 6080 localhost:5900 >/dev/null 2>&1 &

echo "Carnet de notes disponible sur : http://localhost:6080/vnc.html?autoconnect=1&resize=scale"

# 4. Application (le conteneur s'arrête quand on la quitte)
exec python main.py
