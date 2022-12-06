FROM arm64v8/python:3.11-alpine

WORKDIR /api/

COPY ./requirements.txt /api/requirements.txt

RUN apk update && apk upgrade

RUN pip install pip --upgrade
RUN pip install --no-cache-dir --upgrade -r /api/requirements.txt

COPY ./app /api/app

CMD ["hypercorn", "--bind", "0.0.0.0:80", "app.main:app"]
