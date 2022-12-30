FROM arm64v8/python:3.11-bullseye as base

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE 1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED 1

WORKDIR /bot

COPY ./requirements.txt /bot/requirements.txt


RUN apt-get update -y && apt-get upgrade -y
RUN apt-get install tesseract-ocr -y

COPY ./requirements.txt /bot/requirements.txt

RUN pip install pip --upgrade
RUN pip install -r requirements.txt

COPY ./app /bot/app

# DEBUGGER ##################################################################################################################
FROM base as debugger

RUN pip install debugpy

CMD [ "python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "--wait-for-client", "-m", "app.main", "-Xfrozen_modules=off" ]

# PRIMARY ##############################
FROM base as primary

CMD [ "python", "-m", "app.main" ]
