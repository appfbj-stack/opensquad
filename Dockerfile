FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
COPY telegram-bot.js ./

RUN npm install --production node-telegram-bot-api @google/generative-ai node-fetch

CMD ["node", "telegram-bot.js"]
