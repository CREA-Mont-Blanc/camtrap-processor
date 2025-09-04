from lib import *
from display import *
from tqdm import tqdm
import numpy as np
import pandas as pd


def main(
    files_path,
    corresponding_dir,
    type_file,
    area2patch_g,
    query_condition_g,
    last_image_issue_g,
    correct_date_g,
):
    loader = TermLoading()

    try:
        loader.show(
            "1. Extracting metadata",
            finish_message="✅ Finished extracting metadata",
            failed_message="❌ Failed extracting metadata",
        )
        id_today = time.strftime("%Y%m%d%H%M%S")
        files_name = get_file_paths(files_path, save_path=None, type_file=type_file)
        structure = Parallel(n_jobs=-1)(
            delayed(get_metadata_structure)(f, corresponding_dir, type_file)
            for f in tqdm(files_name, desc="Extracting metadata")
        )
        structure = pd.DataFrame(structure)
        loader.finished = True
    except Exception as e:
        loader.failed = True
        print(f"Error: {e}")

    try:
        loader.show(
            "2. Creating cleaned arborescence",
            finish_message="✅ Finished creating cleaned arborescence",
            failed_message="❌ Failed creating cleaned arborescence",
        )
        cleaned_dir = prepare_cleaned_structure(files_path, structure, timelapse=True)
        os.makedirs(os.path.join(cleaned_dir, ".tmp"), exist_ok=True)
        structure["file_number"] = structure["file_path"].apply(
            lambda x: (
                int(os.path.basename(x)[4:8])
                if "RCNX" in x
                else np.random.randint(-9999, -1)
            )
        )
        loader.finished = True
    except Exception as e:
        loader.failed = True
        print(f"Error: {e}")

    try:
        loader.show(
            "3. Checking for duplicates",
            finish_message="✅ Finished checking for duplicates",
            failed_message="❌ Failed checking for duplicates",
        )
        structure, dropped = check_doublon(structure)
        dropped.to_csv(os.path.join(cleaned_dir, ".tmp", f"dropped_{id_today}.csv"))
        loader.finished = True
    except Exception as e:
        loader.failed = True
        print(f"Error: {e}")

    try:
        for area2patch, query_condition, last_image_issue, correct_date in zip(
            area2patch_g, query_condition_g, last_image_issue_g, correct_date_g
        ):
            if (area2patch is None) or (area2patch == ""):
                loader.show("4. No area to patch", finish_message="✅ No area to patch")
            loader.show(
                f"4. Correcting {area2patch} area",
                finish_message=f"✅ Finished correcting {area2patch} area",
                failed_message=f"❌ Failed correcting {area2patch} area",
            )
            structure = patch_area(
                structure, area2patch, last_image_issue, correct_date, query_condition
            )
            loader.finished = True
    except Exception as e:
        loader.failed = True
        print(f"Error: {e}")

    try:
        loader.show(
            "5. Adding new names",
            finish_message="✅ Finished adding new names",
            failed_message="❌ Failed adding new names",
        )
        # utiliser l'extension fournie par type_file (ajoute '.' si absent)
        ext = type_file if type_file.startswith(".") else f".{type_file}"
        structure["new_name"] = structure.apply(
            lambda x: (
                x.new_dir
                + "__"
                + x.date_acquisition.strftime("%Y-%m-%d__%H-%M-%S")
                + ext
                if ((x.date_acquisition is not None))
                else None
            ),
            axis=1,
        )
        loader.finished = True
    except Exception as e:
        loader.failed = True
        print(f"Error: {e}")

    try:
        loader.show(
            "6. Separating timelapse and camera images",
            finish_message="✅ Finished separating timelapse and camera images",
            failed_message="❌ Failed separating timelapse and camera images",
        )

        # Extract station from new_name column (split on '__' and take first part)
        structure["station"] = structure["new_name"].apply(
            lambda x: x.split("__")[0] if pd.notna(x) and "__" in x else None
        )

        # Check if timelapse column exists in corresponding_dir
        if "timelapse" in corresponding_dir.columns:
            # Merge structure with corresponding_dir to get timelapse info
            structure_with_timelapse = structure.merge(
                corresponding_dir[["station", "timelapse"]],
                on="station",
                how="left",
            )

            # Function to convert timelapse time format to hour (24h format)
            def convert_timelapse_to_hour(timelapse_val):
                if pd.isna(timelapse_val) or str(timelapse_val).lower() == "non":
                    return None

                timelapse_str = str(timelapse_val).lower()
                if "m" in timelapse_str:
                    # Split on 'm' and take the first part
                    time_part = timelapse_str.split("m")[0]
                    if "a" in time_part:
                        # AM time
                        hour_str = time_part.replace("a", "")
                        try:
                            hour = int(hour_str)
                            return hour if hour != 12 else 0  # 12am = 0h
                        except ValueError:
                            return None
                    elif "p" in time_part:
                        # PM time
                        hour_str = time_part.replace("p", "")
                        try:
                            hour = int(hour_str)
                            return (
                                hour + 12 if hour != 12 else 12
                            )  # 12pm = 12h, others +12
                        except ValueError:
                            return None
                return None

            # Function to check if a photo is timelapse based on date and timelapse schedule
            def is_timelapse_photo(row):
                if pd.isna(row["timelapse"]) or str(row["timelapse"]).lower() == "non":
                    return False

                timelapse_hour = convert_timelapse_to_hour(row["timelapse"])
                if timelapse_hour is None:
                    return False

                photo_datetime = row["date_acquisition"]
                if pd.isna(photo_datetime):
                    return False

                # Check if minute is 0 and hour matches timelapse schedule
                return (
                    photo_datetime.minute == 0 and photo_datetime.hour == timelapse_hour
                )

            structure_with_timelapse["is_timelapse"] = structure_with_timelapse.apply(
                is_timelapse_photo, axis=1
            )

            structure_timelapse = structure_with_timelapse[
                structure_with_timelapse["is_timelapse"] == True
            ].copy(deep=True)
            structure_camera = structure_with_timelapse[
                structure_with_timelapse["is_timelapse"] == False
            ].copy(deep=True)
        else:
            print(
                "Warning: 'timelapse' column not found in corresponding_dir. Using date-based separation."
            )
            # Use original logic based on date/time
            structure_timelapse = structure[
                structure.date_acquisition.apply(
                    lambda x: (True if (x.second == 0) and (x.minute == 0) else False)
                )
            ].copy(deep=True)
            structure_camera = structure[
                structure.date_acquisition.apply(
                    lambda x: (False if (x.second == 0) and (x.minute == 0) else True)
                )
            ].copy(deep=True)

        loader.finished = True
    except Exception as e:
        loader.failed = True
        print(f"Error: {e}")

    try:
        loader.show(
            "7. Saving timelapse filenames",
            finish_message="✅ Finished saving timelapse filenames",
            failed_message="❌ Failed saving timelapse filenames",
        )
        structure_timelapse.to_csv(
            os.path.join(cleaned_dir, ".tmp", "structure_timelapse.csv")
        )
        loader.finished = True
    except Exception as e:
        loader.failed = True
        print(f"Error: {e}")

    try:
        loader.show(
            "8. Moving timelapse files to new arborescence",
            finish_message="✅ Finished moving timelapse files to new arborescence",
            failed_message="❌ Failed moving timelapse files to new arborescence",
        )
        Parallel(n_jobs=-1)(
            delayed(process_files)(row, cleaned_dir, copy=True, timelapse=True)
            for _, row in tqdm(structure_timelapse.iterrows(), desc="Moving files")
        )
        loader.finished = True
    except Exception as e:
        loader.failed = True
        print(f"Error: {e}")

    try:
        loader.show(
            "9. Saving camera filenames",
            finish_message="✅ Finished saving camera filenames",
            failed_message="❌ Failed saving camera filenames",
        )
        for pp in tqdm(
            structure_camera.new_dir.unique(), desc="Saving camera filenames"
        ):
            strc_cam = structure_camera[structure_camera.new_dir == pp]
            strc_cam = add_sequence2name(strc_cam)
            strc_cam.to_csv(
                os.path.join(cleaned_dir, ".tmp", f"structure_camera_{pp}.csv")
            )
        loader.finished = True
    except Exception as e:
        loader.failed = True
        print(f"Error: {e}")

    try:
        for pp in tqdm(structure_camera.new_dir.unique(), desc="Moving camera files"):
            strc_cam = pd.read_csv(
                os.path.join(cleaned_dir, ".tmp", f"structure_camera_{pp}.csv")
            )
            loader.show(
                f"10. Moving camera files to new arborescence for {pp}",
                finish_message=f"✅ Finished moving camera files to new arborescence for {pp}",
                failed_message=f"❌ Failed moving camera files to new arborescence for {pp}",
            )
            Parallel(n_jobs=-1)(
                delayed(process_files)(row, cleaned_dir, copy=True, timelapse=False)
                for _, row in tqdm(strc_cam.iterrows(), desc="Moving files")
            )
            loader.finished = True
    except Exception as e:
        loader.failed = True
        print(f"Error: {e}")

    print("11. Terminated")


if __name__ == "__main__":

    files_path = "../cache_hdd_molosse/Herbiland_bauges"
    corresponding_dir = pd.read_csv(glob.glob("corresp*.csv")[0], sep=";")
    type_file = ".avi"
    area2patch_g = []  # ['bel18']
    query_condition_g = []  # [(
    #   "(file_path.str.contains('\\(2\\)') & (date_acquisition < '2024-06-20')) | "
    #   "(~file_path.str.contains('\\(2\\)') & (file_number < 142) & (file_number > 130)) | "
    #   "(file_number > 141)"
    # )]
    last_image_issue_g = []  # ['RCNX3502']
    correct_date_g = []  # ['2024-10-25 10:05:11']

    main(
        files_path,
        corresponding_dir,
        type_file,
        area2patch_g,
        query_condition_g,
        last_image_issue_g,
        correct_date_g,
    )
