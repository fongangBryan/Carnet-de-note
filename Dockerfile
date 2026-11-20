# syntax=docker/dockerfile:1
#
# Carnet de notes - Master 1 DAT (application Tkinter) en conteneur.
#
# Stages :
#   base  : Python + Tkinter + code de l'application
#   test  : lance verification.py sur un écran virtuel (le build échoue si un test échoue)
#   x11   : affiche l'application sur le serveur X de la machine hôte
#   web   : (cible par défaut) affiche l'application dans le navigateur via noVNC
#
# Build :
#   docker build -t carnet-notes .                    -> stage web (par défaut)
#   docker build --target x11 -t carnet-notes:x11 .   -> stage x11
#   docker build --target test .                      -> uniquement les tests

ARG PYTHON_VERSION=3.14

# ---------------------------------------------------------------------------- base
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CARNET_DATA_DIR=/data \
    LANG=C.UTF-8

# Police lisible pour Tk (l'image slim n'en contient aucune)
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

# Vérifie dès maintenant que Tkinter est disponible dans l'image Python
RUN python -c "import tkinter, sqlite3; print('Tk', tkinter.TkVersion)"

# Utilisateur non root + dossier des données (base SQLite et exports)
RUN useradd --create-home --uid 1000 app \
 && mkdir -p /data /tmp/.X11-unix \
 && chmod 1777 /tmp/.X11-unix \
 && chown app:app /data

WORKDIR /app
COPY *.py ./

# ---------------------------------------------------------------------------- test
FROM base AS test

RUN apt-get update \
 && apt-get install -y --no-install-recommends xvfb xauth \
 && rm -rf /var/lib/apt/lists/*

USER app
# verification.py utilise une base temporaire et renvoie le code 1 en cas d'échec
RUN xvfb-run -a python verification.py \
 && touch /tmp/tests-ok

# ---------------------------------------------------------------------------- x11
FROM base AS x11

# Dépendance vers le stage test : sans elle, BuildKit ne lancerait pas les tests
COPY --from=test /tmp/tests-ok /tmp/tests-ok

USER app
VOLUME ["/data"]
CMD ["python", "main.py"]

# ---------------------------------------------------------------------------- web
FROM base AS web

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        xvfb x11vnc openbox novnc websockify \
 && rm -rf /var/lib/apt/lists/*

COPY --from=test /tmp/tests-ok /tmp/tests-ok

COPY docker/entrypoint-web.sh /usr/local/bin/entrypoint-web.sh
# Supprime les fins de ligne Windows (CRLF) éventuelles, sinon le script ne s'exécute pas
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint-web.sh \
 && chmod +x /usr/local/bin/entrypoint-web.sh

ENV DISPLAY=:99 \
    SCREEN=1280x800x24

USER app
VOLUME ["/data"]
EXPOSE 6080
ENTRYPOINT ["/usr/local/bin/entrypoint-web.sh"]
