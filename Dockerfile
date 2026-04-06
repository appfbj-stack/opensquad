FROM node:20-alpine

WORKDIR /app

# Copy bot files
COPY telegram-bot.js ./
COPY bot-package.json ./package.json

# Install dependencies
RUN npm install

CMD ["node", "telegram-bot.js"]
