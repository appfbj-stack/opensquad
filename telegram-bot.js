import TelegramBot from 'node-telegram-bot-api';
import { GoogleGenerativeAI } from '@google/generative-ai';
import fetch from 'node-fetch';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import https from 'https';
import http from 'http';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY;

if (!TELEGRAM_BOT_TOKEN || !GOOGLE_API_KEY) {
  console.error('Missing TELEGRAM_BOT_TOKEN or GOOGLE_API_KEY');
  process.exit(1);
}

const bot = new TelegramBot(TELEGRAM_BOT_TOKEN, { polling: true });
const genAI = new GoogleGenerativeAI(GOOGLE_API_KEY);
const conversationHistory = new Map();

const model = genAI.getGenerativeModel({
  model: 'gemini-2.0-flash',
  systemInstruction: 'Voce e um assistente pessoal inteligente no Telegram. Responda em portugues do Brasil de forma clara e objetiva. Pode ajudar com pesquisa na internet, analise de imagens, codigo, redacao, traducao, calculos e muito mais.',
});

async function searchInternet(query) {
  try {
    const url = 'https://api.duckduckgo.com/?q=' + encodeURIComponent(query) + '&format=json&no_html=1&skip_disambig=1';
    const res = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
    const data = await res.json();
    let results = [];
    if (data.Answer) results.push('Resposta: ' + data.Answer);
    if (data.AbstractText) results.push(data.AbstractText);
    if (data.RelatedTopics) {
      data.RelatedTopics.filter(t => t.Text).slice(0, 5).forEach(t => results.push('- ' + t.Text));
    }
    return results.length > 0 ? results.join('
') : 'Sem resultados.';
  } catch (e) { return 'Erro na busca: ' + e.message; }
}

async function fetchUrl(url) {
  try {
    const res = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
    const html = await res.text();
    return html.replace(/<[^>]+>/g, ' ').replace(/s+/g, ' ').trim().substring(0, 3000);
  } catch (e) { return 'Erro ao acessar URL: ' + e.message; }
}

async function downloadFile(fileUrl, dest) {
  return new Promise((resolve, reject) => {
    const proto = fileUrl.startsWith('https') ? https : http;
    const file = fs.createWriteStream(dest);
    proto.get(fileUrl, res => { res.pipe(file); file.on('finish', () => { file.close(); resolve(dest); }); }).on('error', reject);
  });
}

function getHistory(chatId) {
  if (!conversationHistory.has(chatId)) conversationHistory.set(chatId, []);
  return conversationHistory.get(chatId);
}

async function askGemini(chatId, userMessage, imageData) {
  const history = getHistory(chatId);
  const chat = model.startChat({ history });
  let parts = [];
  if (imageData) parts.push({ inlineData: imageData });

  const urlMatch = userMessage.match(/https?://[^s]+/);
  const searchWords = ['pesquisa','pesquise','busca','busque','procura','procure','noticias','noticia','hoje','atual','preco','cotacao','quem e','o que e','qual e'];
  const needsSearch = searchWords.some(w => userMessage.toLowerCase().includes(w));

  let msg = userMessage;
  if (urlMatch) {
    const content = await fetchUrl(urlMatch[0]);
    msg += '

[Conteudo da pagina ' + urlMatch[0] + ']:
' + content;
  } else if (needsSearch) {
    const results = await searchInternet(userMessage);
    msg += '

[Resultados da internet]:
' + results;
  }

  parts.push({ text: msg });
  const result = await chat.sendMessage(parts);
  const response = result.response.text();

  history.push({ role: 'user', parts });
  history.push({ role: 'model', parts: [{ text: response }] });
  if (history.length > 20) history.splice(0, history.length - 20);
  return response;
}

bot.onText(//start/, msg => {
  const name = msg.from.first_name || 'amigo';
  bot.sendMessage(msg.chat.id,
    'Ola ' + name + '! Sou seu assistente com Gemini AI.

' +
    'Posso:
- Responder perguntas
- Pesquisar na internet
- Ler paginas web (cole uma URL)
' +
    '- Analisar imagens
- Transcrever audios
- Ajudar com codigo
- Traduzir textos
- Fazer calculos

' +
    'Comandos:
/start - Boas vindas
/clear - Limpar historico
/help - Ajuda

Pode falar!'
  );
});

bot.onText(//help/, msg => {
  bot.sendMessage(msg.chat.id,
    'Como usar:

' +
    'Pesquisa: "pesquise sobre X" ou "busque noticias"
' +
    'URL: cole um link e eu leio o conteudo
' +
    'Imagem: envie uma foto
' +
    'Audio: envie mensagem de voz
' +
    'Conversa: so falar normalmente!'
  );
});

bot.onText(//clear/, msg => {
  conversationHistory.delete(msg.chat.id);
  bot.sendMessage(msg.chat.id, 'Historico limpo!');
});

bot.on('message', async msg => {
  const chatId = msg.chat.id;
  if (msg.text && msg.text.startsWith('/')) return;
  if (!msg.text && !msg.photo && !msg.voice && !msg.audio) return;

  try {
    await bot.sendChatAction(chatId, 'typing');
    let userMessage = msg.text || msg.caption || '';
    let imageData = null;

    if (msg.photo) {
      const photo = msg.photo[msg.photo.length - 1];
      const fi = await bot.getFile(photo.file_id);
      const url = 'https://api.telegram.org/file/bot' + TELEGRAM_BOT_TOKEN + '/' + fi.file_path;
      const tmp = path.join(__dirname, 'tmp_' + Date.now() + '.jpg');
      await downloadFile(url, tmp);
      imageData = { data: fs.readFileSync(tmp).toString('base64'), mimeType: 'image/jpeg' };
      fs.unlinkSync(tmp);
      if (!userMessage) userMessage = 'Analise esta imagem em detalhes.';
    }

    if (msg.voice || msg.audio) {
      const media = msg.voice || msg.audio;
      const fi = await bot.getFile(media.file_id);
      const ext = msg.voice ? 'ogg' : 'mp3';
      const url = 'https://api.telegram.org/file/bot' + TELEGRAM_BOT_TOKEN + '/' + fi.file_path;
      const tmp = path.join(__dirname, 'tmp_' + Date.now() + '.' + ext);
      await downloadFile(url, tmp);
      const audioModel = genAI.getGenerativeModel({ model: 'gemini-2.0-flash' });
      const r = await audioModel.generateContent([
        { text: 'Transcreva este audio em portugues.' },
        { inlineData: { data: fs.readFileSync(tmp).toString('base64'), mimeType: msg.voice ? 'audio/ogg' : 'audio/mpeg' } }
      ]);
      const transcription = r.response.text();
      fs.unlinkSync(tmp);
      await bot.sendMessage(chatId, 'Transcricao: ' + transcription);
      userMessage = transcription;
    }

    if (!userMessage && !imageData) return;
    const response = await askGemini(chatId, userMessage, imageData);

    if (response.length <= 4096) {
      await bot.sendMessage(chatId, response, { parse_mode: 'Markdown' }).catch(() => bot.sendMessage(chatId, response));
    } else {
      for (let i = 0; i < response.length; i += 4096) {
        await bot.sendMessage(chatId, response.substring(i, i + 4096)).catch(() => {});
      }
    }
  } catch (err) {
    console.error('Error:', err);
    bot.sendMessage(chatId, 'Erro ao processar mensagem. Tente novamente.');
  }
});

bot.on('polling_error', err => console.error('Polling error:', err.message));
console.log('Bot Telegram com Gemini iniciado!');
