#!/bin/bash

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <directory_to_scan> <output_csv_file>"
    exit 1
fi

DIR="$1"
OUTPUT_FILE="$2"

if [ ! -d "$DIR" ]; then
    echo "Error: Directory '$DIR' not found."
    exit 1
fi

start_time=$(date +%s)

echo "Localisation des fichiers JPG/JPEG dans $DIR..."
FILE_LIST=$(mktemp)
find "$DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" \) ! -path "*/@eaDir/*" > "$FILE_LIST"
TOTAL_FILES=$(wc -l < "$FILE_LIST")

if [ "$TOTAL_FILES" -eq 0 ]; then
    echo "Aucun fichier JPG/JPEG trouvé. Arrêt."
    rm -f "$FILE_LIST"
    # Créer un fichier de sortie vide avec en-têtes pour ne pas causer d'erreur à l'étape suivante
    echo "file_path,hash_sha256,hash_md5_no_metadata" > "$OUTPUT_FILE"
    exit 0
fi

echo "Calcul des hashes pour $TOTAL_FILES fichiers..."
TMP_FILE=$(mktemp)
export TMP_FILE

cat "$FILE_LIST" | tqdm --total "$TOTAL_FILES" --unit "file" | xargs -I{} -P $(nproc) bash -c '
    file="{}"
    hash_sha256=$(sha256sum "$file" | cut -d" " -f1)
    error_msg=$(mktemp)
    hash_md5_no_metadata=$(convert "$file" rgb:- 2> "$error_msg" | md5sum | awk "{ print \$1 }")

    if [ -s "$error_msg" ]; then
        error_message=$(head -n 1 "$error_msg" | tr "," ";")
        echo "$file,$hash_sha256,ERROR: $error_message" >> "$TMP_FILE"
    else
        echo "$file,$hash_sha256,$hash_md5_no_metadata" >> "$TMP_FILE"
    fi
    rm -f "$error_msg"
'

echo "file_path,hash_sha256,hash_md5_no_metadata" > "$OUTPUT_FILE"
cat "$TMP_FILE" >> "$OUTPUT_FILE"
rm -f "$TMP_FILE" "$FILE_LIST"

end_time=$(date +%s)
elapsed_time=$((end_time - start_time))

echo -e "\nCalcul des hashes terminé en $elapsed_time secondes. Résultats dans $OUTPUT_FILE"