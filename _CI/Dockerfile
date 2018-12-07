FROM python:3.7
ENV PYTHONUNBUFFERED 1
MAINTAINER Oleg Makarov <imflop@gmail.com>
COPY ./app/requirements.txt /
WORKDIR /
RUN pip install --upgrade pip && pip install -r requirements.txt
