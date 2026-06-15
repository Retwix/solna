FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 21 = control; 21100-21110 = passive data range (keep in sync with .env)
EXPOSE 21 21100-21110
CMD ["python", "server.py"]
