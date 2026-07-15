FROM python:3.11-slim

# Dependente sistem pentru OpenCV + MediaPipe
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    ffmpeg \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiaza requirements si instaleaza
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Descarca modelul MediaPipe automat la build
RUN wget -q \
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task" \
    -O pose_landmarker.task

# Copiaza codul
COPY pbrunner_api.py .
COPY pbrunner_coach.py .
COPY pbrunner_template.py .

# Creeaza directoare necesare
RUN mkdir -p jobs

# Port
EXPOSE 8000

# Variabile de mediu
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Start
CMD ["uvicorn", "pbrunner_api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
