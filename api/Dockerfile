FROM python:3.12-bullseye

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE 1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED 1

RUN apt-get update -y && apt-get upgrade -y
RUN pip install pip --upgrade


COPY ./api/requirements.txt /api/requirements.txt

WORKDIR /api

RUN pip install --upgrade -r requirements.txt --no-cache

COPY ./models.py /api/models.py
COPY ./queries.py /api/queries.py
COPY ./api/app /api/app

CMD ["hypercorn", "--bind", "0.0.0.0:80", "app.main:app"]
