FROM python:3-alpine

# Necessary for build hooks
ARG BUILD_DATE
ARG VCS_REF

RUN apk add bash

# Good docker practice, plus we get microbadger badges
LABEL org.label-schema.build-date=$BUILD_DATE \
       org.label-schema.vcs-url="https://github.com/rubasace/radarr-custom-format-sync.git" \
       org.label-schema.vcs-ref=$VCS_REF \
       org.label-schema.schema-version="2.2-r1"

COPY entrypoint.sh /
COPY requirements.txt /

RUN chmod 755 /entrypoint.sh && pip install -r requirements.txt

#Note that we don't copy Config.txt - this needs to be bind-mounted
COPY CustomFormatSync.py /


VOLUME "/logs"

CMD [ "/entrypoint.sh" ]


