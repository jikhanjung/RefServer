FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-kor \
    tesseract-ocr-eng \
    tesseract-ocr-jpn \
    tesseract-ocr-chi-sim \
    poppler-utils \
    ghostscript \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy model download script and download BGE-M3 model
COPY download_model.py .
RUN python download_model.py

# Copy application code
COPY app/ .

# Copy migrations
COPY migrations/ /app/migrations/

# Create data directory
RUN mkdir -p /data

# Expose port
EXPOSE 8000

# Run the application with database initialization
CMD ["sh", "-c", "python init_db.py && uvicorn main:app --host 0.0.0.0 --port 8000"]