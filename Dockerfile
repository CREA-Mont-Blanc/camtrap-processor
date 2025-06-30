# Utiliser une image Python officielle comme base
FROM python:3.10-slim

# Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Installer les dépendances système
# - ffmpeg: pour ffprobe (métadonnées vidéo)
# - imagemagick: pour la commande 'convert' (hash_V4.sh)
# - openssh-client: pour scp (téléversement)
# - procps: fournit xargs
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    openssh-client \
    procps \
    coreutils \
    && rm -rf /var/lib/apt/lists/*

# Copier le fichier des dépendances Python et les installer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier tous les scripts fournis dans le répertoire de travail du conteneur
COPY . .

# Rendre les scripts shell exécutables
RUN chmod +x *.sh

# Définir le point d'entrée du conteneur
ENTRYPOINT ["/bin/bash", "start.sh"]