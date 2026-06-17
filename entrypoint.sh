#!/bin/bash

# Start the PO Token Provider in the background
echo "Starting PO Token Provider..."
bgutil-ytdlp-pot-provider &

# Wait for the provider to fully start
sleep 5

# Now start the bot
echo "Starting bot..."
python main.py