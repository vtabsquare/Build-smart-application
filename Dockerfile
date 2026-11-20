FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BUILDSMART_MODE=production \
    HOST=0.0.0.0 \
    PORT=10000

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose port
EXPOSE 10000

# Start production server
CMD ["python", "app/production.py"]
