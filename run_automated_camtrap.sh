#!/bin/bash

# Script automatisé pour traiter la structure CAMTRAP
# Utilise le fichier camtrap_config.json pour la configuration

set -e  # Arrêter en cas d'erreur

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/camtrap_config.json"

# Fonctions utilitaires
function print_header() {
    echo ""
    echo "======================================================"
    echo "$1"
    echo "======================================================"
}

function log_info() {
    echo "[INFO] $1"
}

function log_error() {
    echo "[ERROR] $1" >&2
}

# Vérifier que jq est installé pour parser JSON
if ! command -v jq &> /dev/null; then
    log_error "jq is required but not installed. Please install jq to parse JSON config."
    exit 1
fi

# Vérifier que le fichier config existe
if [ ! -f "$CONFIG_FILE" ]; then
    log_error "Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Lire la configuration
BASE_DATA_PATH=$(jq -r '.base_data_path' "$CONFIG_FILE")
OUTPUT_BASE=$(jq -r '.output_base' "$CONFIG_FILE")
DOCKER_IMAGE=$(jq -r '.docker_image' "$CONFIG_FILE")
VIDEO_SUBFOLDER=$(jq -r '.video_subfolder' "$CONFIG_FILE")

log_info "Base data path: $BASE_DATA_PATH"
log_info "Output base: $OUTPUT_BASE"
log_info "Docker image: $DOCKER_IMAGE"

# Créer le dossier de sortie principal
mkdir -p "$OUTPUT_BASE"

# Fonction pour traiter un dossier avec un type de fichier spécifique
process_folder() {
    local folder_name="$1"
    local input_path="$2"
    local csv_file="$3"
    local file_type="$4"
    local output_subfolder="$5"
    
    print_header "Processing $folder_name with $file_type files"
    
    # Déterminer le sous-dossier de sortie final
    local final_output_subfolder="$output_subfolder"
    if [[ "$file_type" == ".avi" ]]; then
        final_output_subfolder="${output_subfolder}/${VIDEO_SUBFOLDER}"
    fi
    
    log_info "Input path: $input_path"
    log_info "CSV file: $csv_file"
    log_info "File type: $file_type"
    log_info "Output subfolder: $final_output_subfolder"
    
    # Créer un script Python temporaire pour ce traitement
    cat > "/tmp/process_${folder_name}_${file_type//./}.py" << EOF
from main_process_images import main
import pandas as pd
import sys
import os

try:
    # Configuration pour $folder_name avec $file_type
    print("Loading CSV file: $csv_file")
    corresponding_dir = pd.read_csv("$csv_file", sep=None, engine='python')
    print(f"CSV columns: {corresponding_dir.columns.tolist()}")
    print(f"First few rows:")
    print(corresponding_dir.head())
    
    print("Starting main processing...")
    main(
        files_path="$input_path",
        corresponding_dir=corresponding_dir,
        type_file="$file_type",
        area2patch_g=[],
        query_condition_g=[],
        last_image_issue_g=[],
        correct_date_g=[]
    )
    print("Processing completed successfully")
except Exception as e:
    print(f"Error during processing: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

    # Lancer le container Docker avec le script automatisé
    if docker run --rm \
        --entrypoint="" \
        -v "$BASE_DATA_PATH:/data" \
        -v "/tmp/process_${folder_name}_${file_type//./}.py:/app/auto_process.py" \
        "$DOCKER_IMAGE" \
        /bin/bash -c "
            echo 'Running automated processing for $folder_name with $file_type files'
            python3 /app/auto_process.py
            
            # Déplacer le résultat vers le bon sous-dossier
            if [ -d '/data/RAW/CLEANED' ]; then
                mkdir -p '/data/CLEANED/$final_output_subfolder'
                cp -r /data/RAW/CLEANED/* '/data/CLEANED/$final_output_subfolder/'
                rm -rf /data/RAW/CLEANED
                chmod -R 777 '/data/CLEANED/$final_output_subfolder'
                echo 'Results moved to /data/CLEANED/$final_output_subfolder'
            else
                echo 'Warning: CLEANED folder not found in expected location'
                # Chercher le dossier CLEANED ailleurs
                find /data -name 'CLEANED' -type d 2>/dev/null | while read cleaned_path; do
                    if [ \"\$cleaned_path\" != \"/data/CLEANED\" ]; then
                        echo 'Found CLEANED at: \$cleaned_path'
                        mkdir -p '/data/CLEANED/$final_output_subfolder'
                        cp -r \"\$cleaned_path\"/* '/data/CLEANED/$final_output_subfolder/'
                        rm -rf \"\$cleaned_path\"
                        chmod -R 777 '/data/CLEANED/$final_output_subfolder'
                        echo 'Results moved from \$cleaned_path to /data/CLEANED/$final_output_subfolder'
                    fi
                done
            fi
        "; then
        log_info "Successfully completed processing $folder_name with $file_type files"
    else
        log_error "Failed processing $folder_name with $file_type files - continuing with next folder"
    fi
    
    # Nettoyer le script temporaire
    rm -f "/tmp/process_${folder_name}_${file_type//./}.py"
    
    log_info "Completed processing $folder_name with $file_type files"
}

# Traiter chaque dossier et type de fichier
jq -c '.folders_to_process[]' "$CONFIG_FILE" | while read -r folder_config; do
    folder_name=$(echo "$folder_config" | jq -r '.name')
    input_path=$(echo "$folder_config" | jq -r '.input_path')
    csv_file=$(echo "$folder_config" | jq -r '.csv_file')
    output_subfolder=$(echo "$folder_config" | jq -r '.output_subfolder')
    
    # Traiter chaque type de fichier pour ce dossier
    echo "$folder_config" | jq -r '.file_types[]' | while read -r file_type; do
        process_folder "$folder_name" "$input_path" "$csv_file" "$file_type" "$output_subfolder"
    done
done

print_header "All processing completed!"
log_info "Results are available in: $OUTPUT_BASE"
log_info "Structure:"
log_info "  - $OUTPUT_BASE/BAUGES/ (JPG files)"
log_info "  - $OUTPUT_BASE/BAUGES/$VIDEO_SUBFOLDER/ (AVI files)"
log_info "  - $OUTPUT_BASE/BELLEDONNE/ (JPG files)"
log_info "  - $OUTPUT_BASE/BELLEDONNE/$VIDEO_SUBFOLDER/ (AVI files)"
log_info "  - $OUTPUT_BASE/MB/ (JPG files)"
log_info "  - $OUTPUT_BASE/MB/$VIDEO_SUBFOLDER/ (AVI files)"
