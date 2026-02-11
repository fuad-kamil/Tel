FROM python:3.11-slim

# Ensure output is sent directly to terminal (no buffering)
ENV PYTHONUNBUFFERED=1

# Install system dependencies (ffmpeg and others if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set up a new user named "user" with user ID 1000
RUN useradd -m -u 1000 user

WORKDIR /app

# Copy requirements and install python dependencies
COPY --chown=user requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY --chown=user . .

# Switch to non-root user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Hugging Face expects the app to run on port 7860
ENV PORT=7860

CMD ["python", "bot.py"]
