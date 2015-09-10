FROM ubuntu:14.04

RUN apt-get update && apt-get install -y wget

RUN wget https://github.com/Yelp/dumb-init/releases/download/v0.2.0/dumb-init_0.2.0_amd64.deb --no-check-certificate
RUN sudo dpkg -i dumb-init_0.2.0_amd64.deb

CMD ["dumb-init", "tail", "-F", "log"]
