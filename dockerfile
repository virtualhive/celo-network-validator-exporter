FROM python:3.10-slim

RUN apt-get update && apt-get -y install gcc 

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "-u", "./celo_network_validator_exporter.py" ]