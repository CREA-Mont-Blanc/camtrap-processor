# Camtrap Processor
This repository provides a set of tools to preprocess camera trap images, including duplicate detection and metadata extraction, folder structure management, and image renaming and NAS copying.
It is designed to work with a specific folder structure.

# Structure of the folder to process

```
data/
├── RAW/
│   ├── area1/
│   │   └── releve_august/
│   │       ├── image1.jpg
│   │       ├── image2.jpg
│   │       └── image3.jpg
│   ├── area2/
│   │   ├── releve_september/
│   │   |   └── image4.jpg
│   │   └── releve_october/
│   │       └── image5.jpg
│   │  
│   └── area3/
│       └── releve_september/
│           └── intermediate_folder/
│               └── image6.jpg
└── cameras_info.csv
```
The `cameras_info.csv` file contains metadata about the cameras, such as their name and optional area information. The name stored in the CSV file will be used to eventually correct the folder structure.

# Installation
1. Clone the repository
```bash
git clone <repository_url>
```
2. Navigate to the project directory
```bash
cd camtrap-processor
```
Be sure to have Docker installed on your system. If you don't have it, you can follow the [Docker installation guide](https://docs.docker.com/get-docker/).

3. Build the Docker image
```bash
sudo docker build -t camtrap-processor .
# or
sudo docker build -t camtrap-processor <path_to_dockerfile>
```
This command builds the Docker image using the Dockerfile in the current directory and tags it as `camtrap-processor`. Make sure to run this command in the directory where the Dockerfile is located.

# Usage
1. Prepare your data directory
Make sure your data is structured as shown above, with a `RAW` directory containing the images and a `cameras_info.csv` file in the root of your data directory.
The `cameras_info.csv` file contain either the correct name of the station and allow a correction of the name of the folder (for instance: "Blaitiere_1700" become "blaitiere1700") with a column `station`. Or two columns `current_name` and `replacement_name` two modify the current name of multiples folders.
 
A new folder `data/CLEANED` will be created to store the processed images and metadata with the following structure:
```
data/
├── CLEANED/
│   ├── year1/
│   │   ├── area1/
│   │   │   ├── area1__year1-month-day__HH-MM-SS(sequence).jpg
│   │   │   └── ...
│   │   ├── area2/
│   │   │   ├── area2__year1-month-day__HH-MM-SS(sequence).jpg
│   ├── year2/
│   │   ├── area1/
│   │   │   ├── area1__year2-month-day__HH-MM-SS(sequence).jpg
│   │   │   └── ...
│   │   ├── area3/
│   │   │   ├── area3__year2-month-day__HH-MM-SS(sequence).jpg
│   ├── timelapse/
│   │   ├── area1/
│   │   │   ├── area1__year1-month-day__HH-MM-SS(sequence).jpg
│   │   │   ├── ...
│   │   │   └── area1__year2-month-day__HH-MM-SS(sequence).jpg
│   │   ├── area2/
│   │   │   ├── area2__year1-month-day__HH-MM-SS(sequence).jpg
│   │   │   ├── ...
│   │   │   └── area2__year2-month-day__HH-MM-SS(sequence).jpg
│   └── .tmp/
│   └── hashes.csv
```

## What the pipeline does (high-level)

1. Interactive configuration
    - Ask for the root folder to process (default `/data/RAW`).
    - Ask for a CSV glob for camera correspondence (default `/data/*.csv`) and require exactly one match.
    - Ask for the file type/extension to process (e.g. `.jpg` or `.avi`).
    - Optionally accept multiple area/date correction patches (area name, filter condition, last bad image id, corrected date).

2. Processing (Python pipeline: `main_process_images.main`)
    - Extract metadata from all files under the chosen `FILES_PATH`.
    - Build a `CLEANED` arborescence and create a `.tmp` working folder in the cleaned output.
    - Detect obvious duplicates and save a `dropped_<timestamp>.csv` in `.tmp`.
    - Apply user-specified corrections (if any).
    - Compute new filenames based on acquisition date and the chosen extension.
    - Separate timelapse frames and camera-triggered images, write CSV manifests, and move/copy files into the `CLEANED` structure.

3. Post-processing placement
    - By default, the cleaned results are placed under `/data/CLEANED` (root of the mounted volume).
    - The script asks whether to place results into a subfolder under `/data/CLEANED`; if yes, it will move the cleaned output to `/data/CLEANED/<subfolder>`.

4. Hashing and duplicate detection
    - For non-`.avi` file types (e.g. `.jpg`) the script runs `run_hash.sh` to compute file hashes and `run_extract_duplicates.sh` to find duplicates. Hash output files like `hashes_output.csv` are saved in the cleaned output.
    - If the chosen extension is `.avi`, hashing and duplicate detection are skipped (video hashing is intentionally disabled by default).

5. Optional upload
    - The script can upload the cleaned folder to a remote NAS via SCP (interactive credentials and destination required).

## Key outputs

- `/data/CLEANED/` or `/data/CLEANED/<subfolder>` — organized and renamed images (timelapse / per-year / per-site structure).
- `/data/CLEANED/.tmp/` — intermediate manifests created during processing (e.g. `structure_timelapse.csv`, `structure_camera_*.csv`, `dropped_<timestamp>.csv`).
- `hashes_output.csv` (and other hash/duplicate reports) — when hashing runs (skipped for `.avi`).
- Duplicate report files produced by `run_extract_duplicates.sh`.
- The (sequence) in the name is produced in following manner: Images taken within 1 minute of each other are considered part of the same sequence.
    Sequence counter resets when there's a gap longer than 1 minute between images.

## Interactive prompts you will see

- Path to the root folder containing raw data (default `/data/RAW`).
- CSV glob for camera correspondence (default `/data/*.csv`).
- File type to process (e.g. `.jpg`, `.avi`).
- Optionally, repeated blocks to add area/date corrections (area name, query, last image id, corrected date).
- After processing: whether to move results into a subfolder under `/data/CLEANED` and the subfolder name.
- Optionally: whether to upload results to a NAS and the remote connection details.

## Points of vigilance

- Permissions: the script sets wide permissions (chmod -R 777) on output folders. Ensure the mounted host folder can accept these changes and that you are comfortable with those permissions.
- CSV globbing: the script requires exactly one CSV match for the correspondence file. If the glob matches zero or multiple files the script will exit.
- Large datasets: processing uses joblib parallelism; monitor memory and CPU usage inside the container for large inputs. Consider limiting parallel workers if needed.
- `.avi` behaviour: By design the pipeline skips hashing and duplicate detection for `.avi` files — this is intentional because hashing video content may be expensive or not required.
- Interactivity: `start.sh` is interactive. For automation you will need to change it to accept arguments or provide non-interactive defaults.
- Backups: the script may copy/move many files — keep a backup of your raw data if you need to preserve original paths.

## Quick start
If any corrections are made on the original code, please re-build the Docker image. Else, you can run the following command:
```bash
sudo docker run -it --rm \
    -v /path/to/your/data:/data \  # Mount your data directory
    camtrap-processor
```
Replace `/path/to/your/data` with the actual path to your data directory. This command mounts your data directory to the `/data` directory inside the Docker container, allowing the container to access your images and metadata.

# Notes
- The csv file `hashes_output_duplicates_sha256.csv` and `hashes_output_duplicates_pixels_md5.csv` will be generated in the `CLEANED` directory, containing the SHA256 and MD5 hashes of the images, with and without tags, respectively. These files can be used to identify duplicate images

## Where to look for logs and intermediate files

- Processing manifests and intermediate CSVs: `/data/CLEANED/.tmp/` after processing.
- Hash and duplicate reports: `/data/CLEANED/` (or chosen subfolder) as `hashes_output.csv` and files produced by `run_extract_duplicates.sh`.

## Automated processing for multiple mountain ranges

For large-scale processing of multiple mountain ranges (massifs) containing mixed video and image datasets, an automated solution is available. This is particularly useful when you have:

- Multiple distinct geographical areas (e.g., Bauges, Belledonne, Mont-Blanc)
- Mixed file types (.jpg images and .avi videos) that need different processing workflows
- Different camera correspondence CSV files for each region
- Need to process everything without manual intervention

### Automated workflow features

The automated script (`run_automated_camtrap.sh`) processes multiple folders sequentially using a JSON configuration file (`camtrap_config.json`). It:

- Handles different mountain ranges with their specific camera correspondence files
- Automatically separates image and video processing (videos go to a `video/` subfolder)
- Skips hashing for video files (which is expensive and often unnecessary)
- Organizes results by geographical area and file type
- Requires no user interaction once configured

### Example structure processed

```
CAMTRAP/
├── RAW/
│   ├── BAUGES/          # Uses BA_BEL_renaming_PP_*.csv
│   │   ├── ba01/
│   │   ├── ba02/
│   │   └── ...
│   ├── BELLEDONNE/      # Uses BA_BEL_renaming_PP_*.csv  
│   │   ├── bel01/
│   │   ├── bel02/
│   │   └── ...
│   └── MB/              # Uses MB_camerainfo_*.csv
│       ├── loriaz1700/
│       ├── para2100/
│       └── ...
└── CLEANED/             # Automated output
    ├── BAUGES/
    │   ├── [organized .jpg files]
    │   └── video/
    │       └── [organized .avi files]
    ├── BELLEDONNE/
    │   ├── [organized .jpg files] 
    │   └── video/
    │       └── [organized .avi files]
    └── MB/
        ├── [organized .jpg files]
        └── video/
            └── [organized .avi files]
```

### Prerequisites for automated processing


1. Docker installed and running
2. The CAMTRAP dataset mounted at `/media/XXX/Creator Pro/CAMTRAP` (replace `XXX` with your username)
3. CSV correspondence files copied to the CAMTRAP root folder
4. Built Docker image: `camtrap-processor`
5. `jq` installed for JSON parsing (`sudo apt install jq`)

### Quick Start

1. Configure your datasets in `camtrap_config.json`
2. Ensure CSV correspondence files are in place
3. Run: `./run_automated_camtrap.sh`

```bash
cd /path/to/the/dock
./run_automated_camtrap.sh
```

#### Troubleshooting

- Ensure `jq` is installed: `sudo apt install jq`
- If Docker permissions issues occur, try running with `sudo`
- Ensure the CAMTRAP folder path is correct in `camtrap_config.json`
- Check that CSV files are present in the CAMTRAP root folder
- Monitor disk space as processing creates copies of all files

This automated approach is ideal for research projects spanning multiple mountain ranges where consistent processing of large mixed datasets is required.

If you want, I can also add a short example showing a full interactive session and expected folder changes on the host after running the pipeline.
