FROM python:3.11-slim

WORKDIR /app

# Install ffmpeg, libopus, and build dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus0 \
    libopus-dev \
    && rm -rf /var/lib/apt/lists/*

# Install davey separately first
RUN pip install davey==0.1.0

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]