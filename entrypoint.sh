#!/bin/bash

# Start the PO Token Provider in the background
echo "Starting PO Token Provider..."
bgutil-ytdlp-pot-provider &

# Wait a moment for the provider to initialize
sleep 3

# Start the bot
echo "Starting bot..."
python main.py