#!/bin/bash

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <hashes_csv_file>"
    exit 1
fi

CSV_FILE="$1"
BASE_NAME=$(basename "$CSV_FILE" .csv)
CLEANED_DIR="$(dirname "$CSV_FILE")"
OUTPUT_FILE_ALL="${CLEANED_DIR}/${BASE_NAME}_duplicates_sha256.csv"
OUTPUT_FILE_NOTAG="${CLEANED_DIR}/${BASE_NAME}_duplicates_pixels_md5.csv"

if [[ ! -f "$CSV_FILE" ]]; then
    echo "Erreur : Fichier $CSV_FILE non trouvé."
    exit 1
fi

echo "Analyse des doublons par hash SHA256 (colonne 2)..."
echo "Occurrences,Hash,Fichiers" > "$OUTPUT_FILE_ALL"
awk -F',' 'NR>1 {hash[$2] = (hash[$2] ? hash[$2] " | " $1 : $1); count[$2]++} 
    END {for (h in count) if (count[h] > 1) print count[h] "," h "," hash[h]}' "$CSV_FILE" | sort -nr >> "$OUTPUT_FILE_ALL"
echo "Résultats enregistrés dans $OUTPUT_FILE_ALL"

echo "Analyse des doublons par hash MD5 des pixels (colonne 3)..."
echo "Occurrences,Hash,Fichiers" > "$OUTPUT_FILE_NOTAG"
awk -F',' 'NR>1 && $3 !~ /^ERROR:/ {hash[$3] = (hash[$3] ? hash[$3] " | " $1 : $1); count[$3]++} 
    END {for (h in count) if (count[h] > 1) print count[h] "," h "," hash[h]}' "$CSV_FILE" | sort -nr >> "$OUTPUT_FILE_NOTAG"
echo "Résultats enregistrés dans $OUTPUT_FILE_NOTAG"

echo "Analyse des doublons terminée."