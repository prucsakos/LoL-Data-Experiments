# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file to the working directory
COPY ./requirements.txt .

# Install the required dependencies
RUN pip install -r requirements.txt

# Copy the rest of the application code to the working directory
COPY . .

# Create the template directory
RUN mkdir -p /app/data

# Specify the volume at WORKDIR/data/
VOLUME /app/data

# Specify the command to run when the container starts
CMD ["python", "./src/data-collector-2/main.py"]