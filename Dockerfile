# Use standard Python 3.10 slim image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

# Set working directory inside the container
WORKDIR /app

# Install system-level dependencies:
# tesseract-ocr for advanced OCR scanning
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt first to leverage Docker build cache
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend files
COPY . .

# Create persistent/local storage folders for uploads, audio files, and PDFs
RUN mkdir -p uploads audio pdfs

# Expose the application port
EXPOSE 10000

# Start the application using uvicorn (matching startCommand in render.yaml)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
