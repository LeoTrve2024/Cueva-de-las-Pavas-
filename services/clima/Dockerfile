FROM python:3.12-slim
WORKDIR /app
COPY services/clima/pyproject.toml /app/pyproject.toml
COPY services/clima/src /app/src
RUN pip install --no-cache-dir .
ENV PYTHONUNBUFFERED=1
EXPOSE 8001
CMD ["uvicorn", "pavas_clima.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]
