# Dockerfile

# Use the official Python image as a base
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install ffmpeg and other necessary packages
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Flask, CORS, Gunicorn
RUN pip install --no-cache-dir flask flask_cors gunicorn

# Copy the entire application into the container
COPY . .

# Ensure the Rhubarb executable is executable
RUN chmod +x /app/Rhubarb/rhubarb

# Expose the port the app will listen on
EXPOSE 5000

# Run the app and pass the config file path
CMD ["python", "run.py", "-c", "./config/config.yaml"]
