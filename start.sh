#!/bin/sh

# Start the Python program with different arguments
nohup python ./src/data-collector-2/main.py americas &
nohup python ./src/data-collector-2/main.py europe &
nohup python ./src/data-collector-2/main.py asia &
nohup python ./src/data-collector-2/main.py sea &

# Wait indefinitely to keep the container running
tail -f /dev/null