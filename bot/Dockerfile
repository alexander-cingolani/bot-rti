FROM python:3.12-bullseye as base

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE 1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED 1

RUN apt-get update -y && apt-get upgrade -y
RUN apt-get install tesseract-ocr -y
RUN pip install pip --upgrade

COPY ./bot/requirements.txt ./bot/requirements.txt

WORKDIR /bot

RUN pip install -r requirements.txt --no-cache

COPY ./models.py /bot/models.py
COPY ./queries.py /bot/queries.py
COPY ./documents.py /bot/documents.py
COPY ./assets /bot/app/assets

COPY ./bot/app /bot/app


# DEBUGGER ############################
FROM base as debugger

RUN pip install debugpy

CMD [ "python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "--wait-for-client", "-m", "app.main", "-Xfrozen_modules=off" ]

# PRIMARY #############################
FROM base as primary

CMD [ "python", "-m", "app.main" ]
