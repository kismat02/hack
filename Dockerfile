FROM python:3.11-slim-buster
WORKDIR /app
ADD . /app
RUN pip install --no-cache-dir --upgrade -r requirements.txt
EXPOSE 8888
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8888"]
