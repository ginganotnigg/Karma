# Use the official Python image as a base
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install ffmpeg and other necessary packages
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Flask and other necessary packages
RUN pip install --no-cache-dir flask flask_cors gunicorn

# Copy the application code into the container
COPY . .

# Copy the Rhubarb directory into the container
COPY Rhubarb /app/Rhubarb

# Ensure the Rhubarb executable is executable
RUN chmod +x /app/Rhubarb/rhubarb

# Expose the port the app runs on
EXPOSE 5000

# Command to run the application using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]