FROM python:3.12-slim
WORKDIR /app
COPY services/afluencia/pyproject.toml /app/pyproject.toml
COPY services/afluencia/src /app/src
RUN pip install --no-cache-dir .
ENV PYTHONUNBUFFERED=1
EXPOSE 8002
CMD ["uvicorn", "pavas_afluencia.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8002"]
