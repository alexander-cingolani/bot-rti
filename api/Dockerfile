FROM python:3.11-bullseye

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE 1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED 1

RUN apt-get update -y && apt-get upgrade -y
RUN pip install pip --upgrade


COPY ./models.py /api/models.py
COPY ./queries.py /api/queries.py
WORKDIR /api
COPY ./api/app /api/app

ADD ./api/requirements.txt /api/requirements.txt
RUN pip install --upgrade -r /api/requirements.txt --no-cache


CMD ["hypercorn", "--bind", "0.0.0.0:80", "app.main:app"]
