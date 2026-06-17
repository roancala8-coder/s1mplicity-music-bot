FROM python:3.11-slim

# Install git, ffmpeg, nodejs (required for PO token provider and EJS)
RUN apt-get update && apt-get install -y git ffmpeg nodejs npm && rm -rf /var/lib/apt/lists/*

# Install yt-dlp-ejs for JavaScript challenge solving
RUN npm install -g yt-dlp-ejs

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Make entrypoint executable (this works on Linux, which Railway uses)
RUN chmod +x entrypoint.sh

# Use the entrypoint script
ENTRYPOINT ["./entrypoint.sh"]