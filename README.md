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


2. Run the Docker container
```bash
sudo docker run -it --rm \
    -v /path/to/your/data:/data \  # Mount your data directory
    camtrap-processor
```
Replace `/path/to/your/data` with the actual path to your data directory. This command mounts your data directory to the `/data` directory inside the Docker container, allowing the container to access your images and metadata.

# Notes
- The csv file `hashes_output_duplicates_sha256.csv` and `hashes_output_duplicates_pixels_md5.csv` will be generated in the `CLEANED` directory, containing the SHA256 and MD5 hashes of the images, with and without tags, respectively. These files can be used to identify duplicate images