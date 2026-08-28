FROM node:20-bookworm-slim

# Install Chromium and necessary system dependencies for Puppeteer
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-ipafont-gothic \
    fonts-wqy-zenhei \
    fonts-thai-tlwg \
    fonts-kacst \
    fonts-freefont-ttf \
    libxss1 \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Skip downloading bundled Chromium since we use system chromium
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    NODE_ENV=production

WORKDIR /app

# Install all dependencies (including TypeScript compiler)
COPY package.json package-lock.json* ./
RUN npm install

# Copy source code and build config
COPY tsconfig.json ./
COPY src/ ./src/

# Compile TypeScript to dist/
RUN npm run build

# Expose API and QR Web UI port
EXPOSE 3019

# Run compiled WhatsApp connector bot
CMD ["node", "dist/bot.js"]
