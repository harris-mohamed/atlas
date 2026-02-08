FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create config directory
RUN mkdir -p config

# Run the bot
CMD ["python", "bot.py"]
