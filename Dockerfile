# Imagem da API. Os embeddings ficam no PostgreSQL, então a imagem leva só o código.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/

# A API não roda como root dentro do contêiner
RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000

# A mesma imagem também roda a carga dos vetores, trocando o comando:
#   python -m scripts.load_vectors
CMD ["uvicorn", "src.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
