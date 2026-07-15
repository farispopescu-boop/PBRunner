# PBRunner 

**PBRunner** is an automated video analysis software designed for the biomechanical evaluation of athletes during sprints. The system is split into a robust backend processing engine and a cross-platform client interface.

##  System Architecture
This repository is structured into two main components:
* **API Server (Python):** Handles routing, video processing jobs, and executes the biomechanical extraction algorithms locally.
* **Client App (Flutter):** Provides the frontend interface for interacting with the data, compatible across mobile and desktop platforms.

##  Key Features
* **Automated Job Handling:** Built to queue, route, and process local video files automatically.
* **Advanced Slow-Motion Processing:** Implements specific logic to accurately track fast movements and extract data from slow-motion sprint footage.
* **Biomechanical Data Extraction:** Utilizes AI pose landmarking to map and extract physical data points from runners without manual intervention.

##  Tech Stack
* **Backend:** Python, MediaPipe (Pose Landmarking API)
* **Frontend:** Flutter, Dart

##  Setup & Installation

###  Important Note on Machine Learning Models
To adhere to version control best practices and keep the repository lightweight, the compiled machine learning model (`pose_landmarker.task`) is not included in this repository. 

**Before running the server**, you must download the `pose_landmarker.task` file from the official Google MediaPipe documentation and place it directly in the server directory.

### Running the Python Server
1. Navigate to the API server directory.
2. Install the required dependencies: `pip install -r requirements.txt`
3. Ensure the `pose_landmarker.task` file is present in the directory.
4. Start the API: `python pbrunner_api.py`

### Running the Flutter Client
1. Navigate to the Flutter app directory.
2. Fetch the required packages: `flutter pub get`
3. Build and run the application: `flutter run`
