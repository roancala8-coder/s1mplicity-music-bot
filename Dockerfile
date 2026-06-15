FROM python:3.11-slim

# Install git, ffmpeg, nodejs (required for PO token provider)
RUN apt-get update && apt-get install -y git ffmpeg nodejs npm && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the POT provider server (Node.js version)
RUN git clone --single-branch --branch 1.3.1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /pot-provider && \
    cd /pot-provider/server && \
    npm ci && \
    npx tsc

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Start POT provider in background, then your bot
CMD cd /pot-provider/server && node build/main.js & \
    sleep 5 && \
    python main.py