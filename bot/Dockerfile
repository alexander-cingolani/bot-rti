FROM arm64v8/python:3.11-alpine

WORKDIR /bot

COPY ./requirements.txt /bot/requirements.txt

RUN apk update
RUN apk upgrade

RUN apk add build-base
RUN apk add freetype-dev
RUN apk add tesseract-ocr
RUN apk --update add libxml2-dev libxslt-dev libffi-dev gcc musl-dev libgcc openssl-dev curl
RUN apk add jpeg-dev zlib-dev freetype-dev lcms2-dev openjpeg-dev tiff-dev tk-dev tcl-dev

COPY ./requirements.txt /bot/requirements.txt

RUN pip install pip --upgrade
RUN pip3 install python-telegram-bot[all] --pre
RUN pip3 install -r requirements.txt --use-pep517

COPY ./app /bot/app

CMD ["python3.11", "-m" , "app.main"]