FROM python:3.11-alpine

WORKDIR /bot

COPY ./requirements.txt /bot/requirements.txt

RUN apk update
RUN apk upgrade

RUN apk add build-base
RUN apk add freetype-dev
RUN apk add tesseract-ocr

COPY ./requirements.txt /bot/requirements.txt

RUN pip3 install -r requirements.txt

COPY ./app /bot/app

CMD ["python3.11", "-m" , "app.main"]