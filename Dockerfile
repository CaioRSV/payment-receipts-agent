FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Chromium and system dependencies required for headless browser rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    ca-certificates \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application source code
COPY . .

# Expose FastAPI's default port
EXPOSE 8000

# Start uvicorn server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
