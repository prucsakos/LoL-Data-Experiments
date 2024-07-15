#!/bin/sh

# Start the Python program with different arguments in the background
python ./src/data-collector-2/main.py americas &
python ./src/data-collector-2/main.py europe &
python ./src/data-collector-2/main.py asia &
python ./src/data-collector-2/main.py sea &

# Wait for all background processes to finish
wait