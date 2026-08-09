FROM node:20-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends poppler-utils python3 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY . .

EXPOSE 3456
ENV PORT=3456
CMD ["node", "server.js"]
