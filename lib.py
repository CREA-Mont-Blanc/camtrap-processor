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
    """
    Extract the creation date from a video file using ffprobe.

    Parameters
    ----------
    video_path : str
        Path to the video file.

    Returns
    -------
    str or None
        The creation time as a string in ISO format, or None if extraction fails.

    Notes
    -----
    This function uses ffprobe from the ffmpeg suite to extract metadata.
    """
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
    """
    Calculate the MD5 hash of a file.

    Parameters
    ----------
    file_path : str
        Path to the file for which to calculate the MD5 hash.

    Returns
    -------
    str
        The MD5 hash as a hexadecimal string.

    Notes
    -----
    The file is read in chunks of 4096 bytes to handle large files efficiently.
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def copy_file(src, dst):
    """
    Copy a file from source to destination with metadata preservation.

    Parameters
    ----------
    src : str
        Source file path.
    dst : str
        Destination file path.

    Notes
    -----
    This function uses shutil.copy2 to preserve file metadata including timestamps.
    """
    shutil.copy2(src, dst)


def verify_files(src, dst):
    """
    Verify that files in source and destination directories are identical by comparing MD5 hashes.

    Parameters
    ----------
    src : str
        Source directory path.
    dst : str
        Destination directory path.

    Returns
    -------
    bool
        True if all files are identical, False otherwise.

    Notes
    -----
    Compares file count and MD5 hashes of all files in both directories.
    """
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
    """
    Copy files from source to destination directory using parallel processing and verify the operation.

    Parameters
    ----------
    src_dir : str
        Source directory path.
    dst_dir : str
        Destination directory path.
    n_jobs : int, optional
        Number of parallel jobs for copying (default: 1).

    Notes
    -----
    Creates the destination directory if it doesn't exist and verifies all files after copying.
    Uses joblib for parallel file copying operations.
    """
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
    """
    Get all file paths of a specific type from a directory and its subdirectories.

    Parameters
    ----------
    directory : str
        Root directory to search for files.
    save_path : str, optional
        Path to save the list of files (default: None).
    type_file : str, optional
        File extension to search for (default: ".jpg").

    Returns
    -------
    list of str
        Sorted list of full file paths matching the specified extension.

    Raises
    ------
    ValueError
        If no files with the specified extension are found.

    Notes
    -----
    Recursively searches all subdirectories if no files are found in the root directory.
    """
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
    """
    Split a file path into its components.

    Parameters
    ----------
    file_path : str
        The file path to split.

    Returns
    -------
    list of str
        List of path components.

    Notes
    -----
    Normalizes the path before splitting using os.path.normpath.
    """
    # Normaliser le chemin
    normalized_path = os.path.normpath(file_path)
    # Diviser le chemin en composants
    components = normalized_path.split(os.path.sep)
    return components


def normalize_station_name(name):
    """
    Normalize a station name for comparison by removing spaces and hyphens and converting to lowercase.

    Parameters
    ----------
    name : str
        The station name to normalize.

    Returns
    -------
    str
        The normalized station name.

    Notes
    -----
    Removes all spaces and hyphens, then converts to lowercase for consistent matching.
    """
    return re.sub(r"[\s\-]", "", name.lower())


def get_new_dir(file_path, corresponding_dir=None):
    """
    Determine the new directory name for a file based on correspondence mapping.

    Parameters
    ----------
    file_path : str
        Path to the file to process.
    corresponding_dir : pandas.DataFrame, optional
        DataFrame containing station name mappings. Can have two structures:
        - Structure 1: columns 'current_name' and 'replacement_name'
        - Structure 2: columns 'station', 'running', 'move_to'

    Returns
    -------
    str
        The new directory name for the file.

    Raises
    ------
    ValueError
        If the correspondence DataFrame structure is not recognized.
    Warning
        If no correspondence is found for the file path.

    Notes
    -----
    Automatically detects the DataFrame structure and applies the appropriate mapping logic.
    For structure 1: directly maps current_name to replacement_name.
    For structure 2: considers running status and move_to fields.
    """
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

    # Si aucune correspondance trouvée, essayer de matcher sur replacement_name/station
    if (
        "current_name" in corresponding_dir.columns
        and "replacement_name" in corresponding_dir.columns
    ):
        # Chercher dans replacement_name
        for comp in components:
            normalized_comp = normalize_station_name(comp)
            match_row = corresponding_dir[
                corresponding_dir["replacement_name"].apply(normalize_station_name)
                == normalized_comp
            ]
            if not match_row.empty:
                match_row = match_row.iloc[0]
                return match_row["replacement_name"]

    elif "station" in corresponding_dir.columns:
        # Chercher dans station (déjà fait ci-dessus)
        pass

    # Si toujours aucune correspondance, prendre le nom du dossier au niveau 4
    # Exemple: /data/RAW/BELLEDONNE/bel02/100RECNX/ -> bel02
    try:
        # Chercher le niveau approprié dans les composants du chemin
        for i, comp in enumerate(components):
            if comp in ["RAW"]:
                # Le niveau 4 serait à l'index i+2 (RAW -> massif -> station)
                if i + 2 < len(components):
                    fallback_name = components[i + 2]
                    print(
                        f"Warning: Aucune correspondance trouvée pour {file_path}, utilisation du nom de dossier: {fallback_name}"
                    )
                    return fallback_name

        # Si pas de structure RAW trouvée, prendre l'avant-dernier composant
        if len(components) >= 2:
            fallback_name = components[-2]
            print(
                f"Warning: Aucune correspondance trouvée pour {file_path}, utilisation du nom de dossier: {fallback_name}"
            )
            return fallback_name
    except Exception as e:
        print(f"Error extracting folder name from path {file_path}: {e}")

    # En dernier recours, lever l'exception
    raise Warning(f"Aucune correspondance trouvée pour {file_path}")


def get_metadata_structure(file_path, corresponding_dir=None, type_file=".jpg"):
    """
    Extract metadata structure from image or video files.

    Parameters
    ----------
    file_path : str
        Path to the file to process.
    corresponding_dir : pandas.DataFrame, optional
        DataFrame containing station name mappings (default: None).
    type_file : str, optional
        File extension to process (default: ".jpg").

    Returns
    -------
    dict
        Dictionary containing:
        - 'file_path': original file path
        - 'date_acquisition': datetime of file creation/acquisition
        - 'new_dir': mapped directory name

    Notes
    -----
    Supports various image formats (jpg, png, tiff, bmp) and video formats (avi, mov, mp4).
    For images, extracts DateTimeOriginal from EXIF data.
    For videos, uses ffprobe to extract creation time.
    """
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
    """
    Create a cleaned directory structure for organizing processed files.

    Parameters
    ----------
    files_path : str
        Path to the original files directory.
    structure : pandas.DataFrame
        DataFrame containing file metadata with 'date_acquisition' column.
    timelapse : bool, optional
        Whether to create a timelapse subdirectory (default: True).

    Returns
    -------
    str
        Path to the created cleaned directory.

    Notes
    -----
    Creates a 'CLEANED' directory alongside the original directory.
    Creates year-based subdirectories based on acquisition dates.
    Sets directory permissions to 777 for full access.
    """
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
    """
    Add sequence numbers to consecutive images taken within 1-minute intervals.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing 'date_acquisition' column with datetime information.

    Returns
    -------
    pandas.DataFrame
        DataFrame with added 'sequence' column indicating consecutive image numbers.

    Notes
    -----
    Images taken within 1 minute of each other are considered part of the same sequence.
    Sequence counter resets when there's a gap longer than 1 minute between images.
    Modifies the input DataFrame in place and also returns it.
    """
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
    """
    Add sequence numbers to filenames by modifying the 'new_name' column.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing 'new_name' column with .jpg filenames.

    Returns
    -------
    pandas.DataFrame
        DataFrame with updated 'new_name' column including sequence numbers.

    Notes
    -----
    Replaces '.jpg' extension with '(sequence_number).jpg' format.
    Assumes the DataFrame already has a 'sequence' column.
    """
    df["new_name"] = df.apply(
        lambda x: x.new_name.replace(".jpg", f"({x.sequence}).jpg"), axis=1
    )
    return df


def calculate_hash_df(df):
    """
    Calculate MD5 hashes for all files in a DataFrame using parallel processing.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing a 'file_path' column.

    Returns
    -------
    pandas.DataFrame
        DataFrame with an added 'hash' column containing MD5 hashes.

    Notes
    -----
    Uses joblib for parallel hash calculation with all available cores (-1).
    """
    # Utiliser joblib pour paralléliser l'application de calculate_md5
    df["hash"] = Parallel(n_jobs=-1)(
        delayed(calculate_md5)(file_path) for file_path in df["file_path"]
    )
    return df


def check_doublon(df):
    """
    Identify and remove duplicate files based on MD5 hash comparison.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing file information with 'file_path' column.

    Returns
    -------
    tuple of (pandas.DataFrame, pandas.Series)
        - DataFrame with duplicates removed (keeping first occurrence)
        - Series containing file paths of dropped duplicates

    Notes
    -----
    Calculates MD5 hashes for all files and removes duplicates based on hash values.
    The first occurrence of each unique hash is kept.
    """
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
    """
    Extract indices of rows that match a query condition.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame to query.
    query_condition : str
        Pandas query string to filter rows.

    Returns
    -------
    pandas.Series
        Boolean series indicating which rows match the condition.

    Notes
    -----
    Uses pandas.DataFrame.query() method for filtering.
    """
    condition = df.query(query_condition)
    idx = df.index.isin(condition.index)
    return idx


def delta_enregistrement(df, last_image_issue, correct_date):
    """
    Calculate the time difference between a problematic image and the correct date.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing file information with 'file_path' and 'date_acquisition' columns.
    last_image_issue : str
        Identifier string to find the problematic image in file paths.
    correct_date : str
        The correct date in string format.

    Returns
    -------
    numpy.timedelta64
        Time difference in days between the correct date and the problematic image date.

    Notes
    -----
    Used for calculating date corrections when camera timestamps are incorrect.
    """
    last_image_issue_name = df[df.file_path.str.contains(last_image_issue)]
    diff_days = pd.to_datetime(correct_date) - pd.to_datetime(
        last_image_issue_name.date_acquisition
    )
    return diff_days.values.astype("timedelta64[D]")[0]


def patch_area(structure, area2patch, last_image_issue, correct_date, query_condition):
    """
    Correct timestamp issues for files in a specific area based on a reference image.

    Parameters
    ----------
    structure : pandas.DataFrame
        DataFrame containing file metadata with 'new_dir' and 'date_acquisition' columns.
    area2patch : str
        Name of the area/directory to patch.
    last_image_issue : str
        Identifier for the reference image with known correct timing.
    correct_date : str
        The correct date for the reference image.
    query_condition : str
        Pandas query string to select which files to patch.

    Returns
    -------
    pandas.DataFrame
        Updated DataFrame with corrected timestamps.

    Notes
    -----
    Calculates time offset from reference image and applies it to selected files.
    Used to fix systematic timestamp errors in camera trap data.
    """
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
    """
    Add sequence numbers to consecutive images taken within 1-minute intervals (improved version).

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing 'date_acquisition' column with datetime information.

    Returns
    -------
    pandas.DataFrame
        DataFrame with added 'sequence' column indicating consecutive image numbers.

    Notes
    -----
    Images taken within 1 minute of each other are considered part of the same sequence.
    Sequence counter resets when there's a gap longer than 1 minute between images.
    This version uses .copy() and .loc[] for safer DataFrame operations.
    """
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
    """
    Add sequence numbers to filenames by modifying the 'new_name' column (improved version).

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing 'new_name' column with .jpg filenames and 'date_acquisition' column.

    Returns
    -------
    pandas.DataFrame
        DataFrame with updated 'new_name' column including sequence numbers.

    Notes
    -----
    First calls add_sequence_column() to generate sequence numbers, then updates filenames.
    Replaces '.jpg' extension with '(sequence_number).jpg' format.
    Uses .loc[] for safer DataFrame operations.
    """
    df = add_sequence_column(df)
    df.loc[:, "new_name"] = df.apply(
        lambda x: x.new_name.replace(".jpg", f"({x.sequence}).jpg"), axis=1
    )
    return df


def process_files(row, cleaned_dir, copy=False, timelapse=False):
    """
    Process and organize individual files into the cleaned directory structure.

    Parameters
    ----------
    row : pandas.Series
        Row from DataFrame containing file metadata with columns:
        - 'date_acquisition': datetime of file creation
        - 'new_dir': target directory name
        - 'new_name': new filename
        - 'file_path': original file path
    cleaned_dir : str
        Path to the cleaned directory structure.
    copy : bool, optional
        If True, copy files; if False, move files (default: False).
    timelapse : bool, optional
        If True, organize as timelapse; if False, organize by year (default: False).

    Returns
    -------
    str
        Path to the cleaned directory.

    Notes
    -----
    Creates year-based subdirectories for regular files or timelapse subdirectory.
    Skips processing if target file already exists.
    Uses shutil.copy2() for copying or shutil.move() for moving files.
    """
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
