# Используем базовый образ debian
FROM python:3.12-slim

ENV TZ=Europe/Moscow
RUN apt-get update && apt-get install -y nano htop vim default-libmysqlclient-dev build-essential python3-mysqldb
# RUN apt-get install -y wireguard iproute2 openresolv
# RUN source start-airflow.sh


WORKDIR /app

COPY . /app

RUN pip3 install poetry
RUN pip3 install --upgrade setuptools
RUN poetry install




CMD ["poetry", "run", "python3", "fastApi.py"]

