FROM docker.io/node:22.14-bookworm-slim

WORKDIR /app

COPY ./package.json /app

# Install npm packages with BuildKit cache mount for faster rebuilds
RUN --mount=type=cache,target=/root/.npm \
    npm install && npm cache clean --force

ENV PATH=./node_modules/.bin/:$PATH
