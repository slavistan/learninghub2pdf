FROM python:3.10.4-alpine3.15
RUN apk add build-base libffi-dev python3 py3-virtualenv py3-pip \
    chromium chromium-chromedriver inkscape fontconfig \
    mesa-dev mesa-gles
COPY config.yml main.py requirements.txt /app/
COPY learninghub/ /app/learninghub/
COPY app/ /app/app/
WORKDIR /app
RUN pip3 install -r requirements.txt
EXPOSE 5000
CMD python main.py