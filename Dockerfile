FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run Job (nightly batch):   CMD ["python", "main.py"]
# Cloud Run Service (Slack listener): CMD ["uvicorn", "slack_listener:app", "--host", "0.0.0.0", "--port", "8080"]
CMD ["python", "main.py"]
