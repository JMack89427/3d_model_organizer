FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY app/ .

# Create the upload directory
RUN mkdir -p uploads

# Expose the port the app runs on
EXPOSE 5050

# Command to run the application
CMD ["python", "3d_model_organizer.py"]