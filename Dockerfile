FROM python:3.11-slim

# Install git, ffmpeg, nodejs (required for PO token provider)
RUN apt-get update && apt-get install -y git ffmpeg nodejs && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Start PO token provider in background, then run bot
CMD ["sh", "-c", "bgutil-ytdlp-pot-provider & sleep 5 && python main.py"]