FROM python:3.12-slim

WORKDIR /app

# InsightFace/onnxruntime need a few system libs for image ops. g++ is only
# needed at install time to compile insightface's Cython extension (no prebuilt
# wheel on arm64) — purged afterwards to keep the image slim.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends g++ \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y g++ && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY . .

EXPOSE 9000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]
