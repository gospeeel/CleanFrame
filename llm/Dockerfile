FROM python:3.12-slim

WORKDIR /service

COPY requirements.txt .

RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    mkdir -p /wheelhouse && \
    download_ok=0; \
    for attempt in 1 2 3 4 5; do \
      if python -m pip download --dest /wheelhouse --retries 10 --timeout 180 -r requirements.txt; then \
        download_ok=1; \
        break; \
      fi; \
      echo "pip download failed, retry ${attempt}/5"; \
      sleep 10; \
    done && \
    test "$download_ok" = "1" && \
    python -m pip install --no-index --find-links=/wheelhouse -r requirements.txt && \
    rm -rf /wheelhouse

COPY . .

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
