FROM arm64v8/python:3.11-bullseye

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE 1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED 1

WORKDIR /api/

COPY ./requirements.txt /api/requirements.txt

RUN apt-get update -y && apt-get upgrade -y

RUN pip install pip --upgrade
RUN pip install --upgrade -r /api/requirements.txt

COPY ./app /api/app


CMD ["hypercorn", "--bind", "0.0.0.0:80", "app.main:app"]
