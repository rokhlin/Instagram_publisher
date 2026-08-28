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

# Install dependencies first for better Docker cache utilization
COPY package.json ./
RUN npm install --omit=dev

# Copy application files
COPY bot.js ./

# Expose API and QR Web UI port
EXPOSE 3019

# Run the WhatsApp connector bot
CMD ["node", "bot.js"]
