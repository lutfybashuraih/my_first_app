FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN python -m pip install --upgrade pip
RUN pip install -r requirements.txt

ENV PORT=8080
EXPOSE 8080

CMD ["gunicorn", "app:app", "--workers", "3", "--bind", "0.0.0.0:$PORT"]
