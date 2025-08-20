#!/bin/bash

# --- Fonctions utilitaires ---
function print_header() {
    echo ""
    echo "======================================================"
    echo "$1"
    echo "======================================================"
}

function check_error() {
    if [ $? -ne 0 ]; then
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo "ERREUR lors de l'étape : $1"
        echo "Arrêt du script."
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        exit 1
    fi
}

# --- Script Principal ---
print_header "Pipeline de Traitement des Données de Pièges Photographiques"
echo "Ce script va vous guider pour traiter, organiser et téléverser vos données."
echo "Assurez-vous de lancer ce conteneur en montant un volume de données."
echo "Exemple : docker run -it -v /chemin/vers/vos/donnees:/data nom-image"

# --- 1. Collecte des informations utilisateur ---
print_header "Étape 1: Configuration"

read -e -p "Entrez le chemin du dossier principal des données (ex: /data/images_brutes) [défaut: /data/RAW]: " FILES_PATH

# Si vide, utiliser la valeur par défaut
FILES_PATH=${FILES_PATH:-/data/RAW}

# Vérification que le dossier existe
if [ ! -d "$FILES_PATH" ]; then
    echo "Erreur: Dossier '$FILES_PATH' non trouvé."
    exit 1
fi

read -e -p "Entrez le chemin de votre fichier de correspondance des caméras (ex: /data/camera-info.csv ou *.csv) [défaut: /data/*.csv]: " CORRESPONDING_DIR_GLOB

CORRESPONDING_DIR_GLOB=${CORRESPONDING_DIR_GLOB:-/data/*.csv}

# Vérifie si l'utilisateur a entré quelque chose
if [ -z "$CORRESPONDING_DIR_GLOB" ]; then
    echo "Erreur: Aucun chemin ou motif n'a été saisi."
    exit 1
fi

# Expansion manuelle du motif avec globbing activé
shopt -s nullglob
FILES_MATCH=( $CORRESPONDING_DIR_GLOB )
shopt -u nullglob

if [ "${#FILES_MATCH[@]}" -eq 0 ]; then
    echo "Erreur: Aucun fichier ne correspond au motif '$CORRESPONDING_DIR_GLOB'."
    exit 1
elif [ "${#FILES_MATCH[@]}" -gt 1 ]; then
    echo "Erreur: Plusieurs fichiers correspondent au motif '$CORRESPONDING_DIR_GLOB':"
    printf ' - %s\n' "${FILES_MATCH[@]}"
    exit 1
fi

CORRESPONDING_DIR_CSV="${FILES_MATCH[0]}"

read -e -p "Entrez le type de fichier à traiter (ex: .jpg, .avi) [défaut: .jpg]: " TYPE_FILE
TYPE_FILE=${TYPE_FILE:-.jpg}

AREA2PATCH_G=()
QUERY_CONDITION_G=()
LAST_IMAGE_ISSUE_G=()
CORRECT_DATE_G=()

while true; do
    read -p "Voulez-vous corriger la date pour une zone spécifique ? (o/n): " yn
    case $yn in
        [Oo]* ) 
            read -p " -> Nom de la zone à corriger (ex: bel18): " area2patch
            read -p " -> Condition de requête pour identifier les fichiers: " query_condition
            read -p " -> Nom de la dernière image incorrecte (ex: RCNX3502): " last_image
            read -p " -> Date correcte pour cette image (YYYY-MM-DD HH:MM:SS): " correct_date
            
            AREA2PATCH_G+=("$area2patch")
            QUERY_CONDITION_G+=("$query_condition")
            LAST_IMAGE_ISSUE_G+=("$last_image")
            CORRECT_DATE_G+=("$correct_date")
            ;;
        [Nn]* ) break;;
        * ) echo "Répondez par 'o' ou 'n'.";;
    esac
done

# --- 2. Exécution du script de traitement principal ---

print_header "Étape 2: Réorganisation et renommage des fichiers"

py_list_area2patch=$(printf "'%s'," "${AREA2PATCH_G[@]}")
py_list_query=$(printf "'%s'," "${QUERY_CONDITION_G[@]}")
py_list_last_image=$(printf "'%s'," "${LAST_IMAGE_ISSUE_G[@]}")
py_list_correct_date=$(printf "'%s'," "${CORRECT_DATE_G[@]}")

# Création d'un script python temporaire pour appeler votre fonction main
echo "from main_process_images import main
import pandas as pd
main(
    files_path=\"$FILES_PATH\",
    corresponding_dir=pd.read_csv(\"$CORRESPONDING_DIR_CSV\", sep=None, engine='python'),
    type_file=\"$TYPE_FILE\",
    area2patch_g=[${py_list_area2patch%,}],
    query_condition_g=[${py_list_query%,}],
    last_image_issue_g=[${py_list_last_image%,}],
    correct_date_g=[${py_list_correct_date%,}]
)
" > run_main.py


python3 run_main.py
check_error "Réorganisation des fichiers (main_process_images.py)"

# Nouvelle logique pour déplacer CLEANED à la racine du volume monté
if [[ "$FILES_PATH" == /data/RAW* ]]; then
    CLEANED_DIR="/data/RAW/CLEANED"
    ROOT_DIR="/data"
else
    BASE_PATH="${FILES_PATH/RAW/}"
    CLEANED_DIR="${BASE_PATH%/}/CLEANED"
    ROOT_DIR="$(dirname "$FILES_PATH")"
fi

# Vérifier si le dossier CLEANED existe
if [ ! -d "$CLEANED_DIR" ]; then
    echo "Erreur: Le dossier CLEANED '$CLEANED_DIR' n'a pas été trouvé."
    exit 1
fi

# Demander à l'utilisateur s'il veut un sous-dossier
read -e -p "Voulez-vous mettre les résultats dans un sous-dossier de CLEANED ? (o/n) [défaut: n]: " SOUSDOSSIER_REP
SOUSDOSSIER_REP=${SOUSDOSSIER_REP:-n}
if [[ "$SOUSDOSSIER_REP" =~ ^[Oo]$ ]]; then
    read -e -p "Nom du sous-dossier : " SOUSDOSSIER_NOM
    DEST_CLEANED="/data/CLEANED/$SOUSDOSSIER_NOM"
else
    DEST_CLEANED="/data/CLEANED"
fi

# Créer le dossier destination si besoin
mkdir -p "$DEST_CLEANED"

# Déplacer le contenu de CLEANED dans la destination
cp -r "$CLEANED_DIR"/* "$DEST_CLEANED"/
check_error "Déplacement du dossier CLEANED"

# Nettoyer l'ancien dossier CLEANED
rm -rf "$CLEANED_DIR"

chmod -R 777 "$DEST_CLEANED"
echo "Les fichiers traités sont dans le dossier: $DEST_CLEANED"

ROOT_DIR="$DEST_CLEANED"

# --- 3. Exécution du hachage ---
print_header "Étape 3: Calcul des hashes des fichiers"


if [ ! -d "$ROOT_DIR" ]; then
    echo "Erreur: Le dossier de sortie '$ROOT_DIR' n'a pas été trouvé."
    exit 1
fi

# Fichier de sortie dans le dossier destination
HASH_OUTPUT_FILE="${ROOT_DIR}/hashes_output.csv"
./run_hash.sh "$ROOT_DIR" "$HASH_OUTPUT_FILE"
check_error "Hachage des fichiers (run_hash.sh)"



# --- 4. Recherche de doublons ---
print_header "Étape 4: Recherche des doublons"
if [ ! -f "$HASH_OUTPUT_FILE" ]; then
    echo "Erreur: Le fichier de hashes '$HASH_OUTPUT_FILE' n'a pas été trouvé."
    exit 1
fi

./run_extract_duplicates.sh "$HASH_OUTPUT_FILE"
check_error "Détection des doublons (run_extract_duplicates.sh)"
echo "Les rapports sur les doublons ont été enregistrés dans le dossier '$ROOT_DIR'."


# --- 5. Téléversement sur le NAS ---
print_header "Étape 5: Téléversement sur le NAS"

while true; do
    read -p "Voulez-vous téléverser les résultats sur un NAS distant via SCP ? (o/n): " yn
    case $yn in
        [Oo]* ) 
            read -p " -> Nom d'utilisateur du NAS: " NAS_USER
            read -p " -> Adresse IP ou nom d'hôte du NAS: " NAS_HOST
            read -p " -> Chemin absolu du dossier de destination sur le NAS: " NAS_DEST_PATH
            read -p " -> Port SSH (laissez vide pour le port 22 par défaut): " NAS_PORT
            
            PORT_OPTION=""
            if [[ ! -z "$NAS_PORT" ]]; then
                PORT_OPTION="-P $NAS_PORT"
            fi
            
            echo "Tentative de téléversement de '$CLEANED_DIR' vers '${NAS_USER}@${NAS_HOST}:${NAS_DEST_PATH}'"
            echo "Un mot de passe ou une phrase de passe pour votre clé SSH peut vous être demandé."
            
            scp -O -r $PORT_OPTION "$CLEANED_DIR" "${NAS_USER}@${NAS_HOST}:${NAS_DEST_PATH}"
            check_error "Téléversement SCP"
            
            echo "Téléversement terminé avec succès."
            break
            ;;
        [Nn]* ) 
            echo "Étape de téléversement ignorée."
            break
            ;;
        * ) echo "Répondez par 'o' ou 'n'.";;
    esac
done

chmod -R 777 "$ROOT_DIR"

print_header "Pipeline Terminé !"
echo "Les fichiers traités se trouvent dans: $CLEANED_DIR"
echo "Les rapports de hash et de doublons sont également dans ce dossier."