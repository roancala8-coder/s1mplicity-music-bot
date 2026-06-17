FROM python:3.11-slim

# Install git, ffmpeg, nodejs (required for PO token provider and git-based pip install)
RUN apt-get update && apt-get install -y git ffmpeg nodejs npm && rm -rf /var/lib/apt/lists/*

# Install the PO token provider globally (Node.js version for better compatibility)
RUN npm install -g bgutil-ytdlp-pot-provider

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Start PO token provider in background, then run bot
CMD ["sh", "-c", "bgutil-ytdlp-pot-provider & sleep 5 && python main.py"]