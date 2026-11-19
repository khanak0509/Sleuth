FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf

WORKDIR /app

COPY requirements.txt .
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.0.0" \
 && pip install -r requirements.txt

RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

COPY . .

RUN useradd --create-home --uid 10001 app
USER app

ENV PORT=8080
EXPOSE 8080
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1 --timeout-keep-alive 75
