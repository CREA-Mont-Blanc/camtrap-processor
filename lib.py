import os, sys, shutil, re, time, glob
import pandas as pd
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from joblib import Parallel, delayed
import shutil, hashlib
from datetime import datetime
import subprocess
import json


def get_video_creation_date(video_path):
    # Run ffprobe command to get video metadata
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "format_tags=creation_time",
        "-of",
        "json",
        video_path,
    ]

    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    if result.returncode != 0:
        print("Error:", result.stderr)
        return None

    # Parse the JSON output
    metadata = json.loads(result.stdout)
    creation_time = metadata.get("format", {}).get("tags", {}).get("creation_time")

    return creation_time


def calculate_md5(file_path):
    """Calcule le hash MD5 d'un fichier."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def copy_file(src, dst):
    """Copie un fichier de src à dst."""
    shutil.copy2(src, dst)


def verify_files(src, dst):
    """Vérifie que les fichiers dans src et dst sont identiques en comparant leurs hash MD5."""
    src_files = sorted(
        [
            os.path.join(src, f)
            for f in os.listdir(src)
            if os.path.isfile(os.path.join(src, f))
        ]
    )
    dst_files = sorted(
        [
            os.path.join(dst, f)
            for f in os.listdir(dst)
            if os.path.isfile(os.path.join(dst, f))
        ]
    )

    if len(src_files) != len(dst_files):
        return False

    for src_file, dst_file in zip(src_files, dst_files):
        if calculate_md5(src_file) != calculate_md5(dst_file):
            return False

    return True


def copy_files_with_verification(src_dir, dst_dir, n_jobs=1):
    """Copie les fichiers de src_dir à dst_dir en utilisant joblib et vérifie la copie."""
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)

    src_files = [
        os.path.join(src_dir, f)
        for f in os.listdir(src_dir)
        if os.path.isfile(os.path.join(src_dir, f))
    ]
    dst_files = [os.path.join(dst_dir, os.path.basename(f)) for f in src_files]

    Parallel(n_jobs=n_jobs)(
        delayed(copy_file)(src, dst) for src, dst in zip(src_files, dst_files)
    )

    if verify_files(src_dir, dst_dir):
        print("Tous les fichiers ont été copiés et vérifiés avec succès.")
    else:
        print("Erreur lors de la vérification des fichiers copiés.")


def get_file_paths(directory, save_path=None, type_file=".jpg"):
    lst_img = os.walk(directory).__next__()[2]
    full_name = [
        os.path.join(directory, l) for l in lst_img if l.lower().endswith((type_file))
    ]
    if full_name == []:
        for dirpath, _, filenames in os.walk(directory):
            # Filtrer les fichiers jpg et construire leur chemin absolu
            # print(dirpath)
            for f in filenames:
                if f.lower().endswith(type_file):
                    full_name.append(os.path.join(dirpath, f))
    full_name.sort()
    if full_name == []:
        raise ValueError(f"No jpg files found in {directory} or subdirectories")
    if save_path is not None:
        with open(save_path, "w") as f:
            for item in full_name:
                f.write(item + "\n")
    return full_name


def split_path(file_path):
    # Normaliser le chemin
    normalized_path = os.path.normpath(file_path)
    # Diviser le chemin en composants
    components = normalized_path.split(os.path.sep)
    return components


def normalize_station_name(name):
    """Normalise un nom de station pour comparaison."""
    return re.sub(r"[\s\-]", "", name.lower())


def get_new_dir(file_path, corresponding_dir=None):
    components = split_path(os.path.abspath(file_path))
    if corresponding_dir is None:
        return components[-2]

    # Préparer DataFrame
    corresponding_dir = corresponding_dir.copy()

    # Détecter automatiquement la structure du DataFrame
    if (
        "current_name" in corresponding_dir.columns
        and "replacement_name" in corresponding_dir.columns
    ):
        # Structure avec current_name et replacement_name
        corresponding_dir["normalized_current"] = corresponding_dir[
            "current_name"
        ].apply(normalize_station_name)

        # Essayer de trouver une correspondance pour chaque composant du chemin
        for comp in components:
            normalized_comp = normalize_station_name(comp)
            match_row = corresponding_dir[
                corresponding_dir["normalized_current"] == normalized_comp
            ]

            if not match_row.empty:
                match_row = match_row.iloc[0]
                return match_row["replacement_name"]

    elif "station" in corresponding_dir.columns:
        # Structure avec station, running, move_to
        corresponding_dir["normalized_station"] = corresponding_dir["station"].apply(
            normalize_station_name
        )

        # Essayer de trouver une correspondance pour chaque composant du chemin
        for comp in components:
            normalized_comp = normalize_station_name(comp)
            match_row = corresponding_dir[
                corresponding_dir["normalized_station"] == normalized_comp
            ]

            if not match_row.empty:
                match_row = match_row.iloc[0]
                if match_row.get("running", "N") != "Y" and pd.notna(
                    match_row.get("move_to", None)
                ):
                    return match_row["move_to"]
                else:
                    return match_row["station"]
    else:
        raise ValueError(
            "Structure de correspondance non reconnue. Colonnes attendues: ('current_name', 'replacement_name') ou ('station')"
        )

    # Si aucune correspondance trouvée
    raise Warning(f"Aucune correspondance trouvée pour {file_path}")


def get_metadata_structure(file_path, corresponding_dir=None, type_file=".jpg"):
    if file_path.lower().endswith(type_file):
        new_dir = get_new_dir(file_path, corresponding_dir)

        # Lire les métadonnées de l'image
        if type_file in [
            ".jpg",
            ".jpeg",
            ".JPG",
            ".JPEG",
            ".png",
            ".PNG",
            ".tiff",
            ".TIFF",
            ".bmp",
            ".BMP",
        ]:
            try:
                image = Image.open(file_path)
                exif_data = image._getexif()

                # Extraire la date d'acquisition
                if exif_data is not None:
                    for tag_id, value in exif_data.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if tag == "DateTimeOriginal":
                            date_acquisition = datetime.strptime(
                                value, "%Y:%m:%d %H:%M:%S"
                            )
                            break

                    else:
                        date_acquisition = None
                else:
                    date_acquisition = None

            except Exception as e:
                print(f"Erreur lors de la lecture des métadonnées de {file_path}: {e}")
                date_acquisition = None
        elif type_file in [".AVI", ".avi", ".MOV", ".mov", ".MP4", ".mp4"]:
            try:
                value = get_video_creation_date(file_path)
                date_acquisition = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except Exception as e:
                print(f"Erreur lors de la lecture des métadonnées de {file_path}: {e}")
                date_acquisition = None
        else:
            date_acquisition = None
            print(f"Type file {type_file} not supported")
    return {
        "file_path": file_path,
        "date_acquisition": date_acquisition,
        "new_dir": new_dir,
    }


def prepare_cleaned_structure(files_path, structure, timelapse=True):
    abs_dir, dir = os.path.split(os.path.abspath(files_path))
    cleaned_dir = os.path.join(abs_dir, f"CLEANED")
    os.makedirs(cleaned_dir, exist_ok=True)
    os.chmod(cleaned_dir, 0o777)  # Lecture/écriture/exécution pour tous

    for years in structure["date_acquisition"].dt.year.unique():
        os.makedirs(os.path.join(cleaned_dir, str(years)), exist_ok=True)
    if timelapse:
        os.makedirs(os.path.join(cleaned_dir, "timelapse"), exist_ok=True)
    return cleaned_dir


def add_sequence_column(df):
    # Trier les données par date d'acquisition
    df.sort_values("date_acquisition", inplace=True)

    # Convertir la colonne 'date_acquisition' en datetime
    df["date_acquisition"] = pd.to_datetime(df["date_acquisition"])

    # Initialiser la colonne 'sequence'
    df["sequence"] = 1

    # Initialiser le compteur de séquence
    sequence_counter = 1

    # Parcourir les lignes pour attribuer les numéros de séquence
    time_ref = df.loc[0, "date_acquisition"]
    for i in range(1, len(df)):
        current_time = pd.to_datetime(df.loc[i, "date_acquisition"])
        if current_time <= time_ref + pd.Timedelta(minutes=1):
            sequence_counter += 1
            df.loc[i, "sequence"] = sequence_counter
        else:
            time_ref = pd.to_datetime(df.loc[i, "date_acquisition"])
            sequence_counter = 1
            df.loc[i, "sequence"] = sequence_counter
    return df


def add_sequence2name(df):
    df["new_name"] = df.apply(
        lambda x: x.new_name.replace(".jpg", f"({x.sequence}).jpg"), axis=1
    )
    return df


def calculate_hash_df(df):
    # Utiliser joblib pour paralléliser l'application de calculate_md5
    df["hash"] = Parallel(n_jobs=-1)(
        delayed(calculate_md5)(file_path) for file_path in df["file_path"]
    )
    return df


def check_doublon(df):
    # Calculer les hash pour le DataFrame
    df_hash = calculate_hash_df(df).copy(deep=True)

    # Identifier les doublons
    duplicated = df_hash[df_hash.duplicated(subset="hash", keep="first")]

    # Supprimer les doublons basés sur la colonne 'hash'
    df_unique = df_hash.drop_duplicates(subset="hash", keep="first")

    # Obtenir la liste des fichiers supprimés
    dropped_files = duplicated["file_path"]

    return df_unique, dropped_files


def extract_indice_to_rename(df, query_condition):
    condition = df.query(query_condition)
    idx = df.index.isin(condition.index)
    return idx


def delta_enregistrement(df, last_image_issue, correct_date):
    last_image_issue_name = df[df.file_path.str.contains(last_image_issue)]
    diff_days = pd.to_datetime(correct_date) - pd.to_datetime(
        last_image_issue_name.date_acquisition
    )
    return diff_days.values.astype("timedelta64[D]")[0]


def patch_area(structure, area2patch, last_image_issue, correct_date, query_condition):
    sub_df = structure.loc[structure.new_dir == area2patch, :]
    idx = extract_indice_to_rename(sub_df, query_condition)
    sub_df = sub_df.loc[idx]
    delta = delta_enregistrement(sub_df, last_image_issue, correct_date)
    sub_df.date_acquisition = sub_df.date_acquisition.apply(
        lambda x: pd.to_datetime(x) + delta
    )
    # convert to datetime64
    sub_df.date_acquisition = pd.to_datetime(sub_df.date_acquisition)
    idx_structure = structure.index[structure.new_dir == area2patch][idx]
    structure.loc[idx_structure, "date_acquisition"] = sub_df.date_acquisition
    return structure


def add_sequence_column(df):
    # Trier les données par date d'acquisition
    df = df.sort_values("date_acquisition").copy()

    # Convertir la colonne 'date_acquisition' en datetime
    df.loc[:, "date_acquisition"] = pd.to_datetime(df["date_acquisition"])

    # Initialiser la colonne 'sequence'
    df.loc[:, "sequence"] = 1

    # Initialiser le compteur de séquence
    sequence_counter = 1

    # Parcourir les lignes pour attribuer les numéros de séquence
    time_ref = df.loc[df.index[0], "date_acquisition"]
    for i in df.index[1:]:
        current_time = pd.to_datetime(df.loc[i, "date_acquisition"])
        if current_time <= time_ref + pd.Timedelta(minutes=1):
            sequence_counter += 1
            df.loc[i, "sequence"] = sequence_counter
        else:
            time_ref = pd.to_datetime(df.loc[i, "date_acquisition"])
            sequence_counter = 1
            df.loc[i, "sequence"] = sequence_counter
    return df


def add_sequence2name(df):
    df = add_sequence_column(df)
    df.loc[:, "new_name"] = df.apply(
        lambda x: x.new_name.replace(".jpg", f"({x.sequence}).jpg"), axis=1
    )
    return df


def process_files(row, cleaned_dir, copy=False, timelapse=False):
    if row.date_acquisition is not None:
        if not timelapse:
            try:
                year = row.date_acquisition.year
            except:
                year = pd.to_datetime(row.date_acquisition).year

            new_dir = os.path.join(os.path.abspath(cleaned_dir), str(year), row.new_dir)
        else:
            new_dir = os.path.join(
                os.path.abspath(cleaned_dir), "timelapse", row.new_dir
            )
        os.makedirs(new_dir, exist_ok=True)
        new_file = os.path.join(new_dir, row.new_name)
        if os.path.exists(new_file):
            print(f"File {new_file} already exists")
            return cleaned_dir
        else:
            if copy:
                shutil.copy2(row.file_path, new_file)
            else:
                shutil.move(row.file_path, new_file)
    return cleaned_dir
