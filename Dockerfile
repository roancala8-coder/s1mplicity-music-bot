FROM python:3.11-slim

# Install git, ffmpeg, nodejs (required for PO token provider and git-based pip install)
RUN apt-get update && apt-get install -y git ffmpeg nodejs && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]