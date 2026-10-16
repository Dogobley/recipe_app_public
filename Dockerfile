FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN addgroup --system app && adduser --system --ingroup app app

COPY --chown=app:app . ./

# collectstatic writes here at startup; create it now so the non-root `app`
# user owns it (a clean checkout has no staticfiles/ directory to copy in).
RUN mkdir -p /app/staticfiles && chown app:app /app/staticfiles

RUN chmod +x /app/docker-entrypoint.sh

# Set at build time (docker build --build-arg APP_VERSION=<tag>) so the image
# reports the same version however it is later retagged or redeployed.
ARG APP_VERSION=unknown
ENV APP_VERSION=$APP_VERSION

EXPOSE 8000

USER app

CMD ["/app/docker-entrypoint.sh"]
