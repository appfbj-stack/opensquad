import os
import logging
import asyncio
import json
import re
import subprocess
import tempfile
import traceback
import base64
from io import BytesIO
from datetime import datetime

import httpx
import google.generativeai as genai
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import yt_dlp
import instaloader
import feedparser

# ===== CONFIG =====
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

genai.configure(api_key=GOOGLE_API_KEY)
conversation_history = {}

# ===== FERRAMENTAS =====

def buscar_internet(query, max_results=8):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return 'Nenhum resultado encontrado.'
        out = 'RESULTADOS DA BUSCA:\n\n'
        for i, r in enumerate(results, 1):
            out += str(i) + '. ' + r.get('title','') + '\n'
            out += '   ' + r.get('body','')[:300] + '\n'
            out += '   URL: ' + r.get('href','') + '\n\n'
        return out
    except Exception as e:
        return 'Erro na busca: ' + str(e)

def buscar_noticias(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=8))
        if not results:
            return 'Nenhuma noticia encontrada.'
        out = 'NOTICIAS RECENTES:\n\n'
        for i, r in enumerate(results, 1):
            out += str(i) + '. ' + r.get('title','') + '\n'
            out += '   ' + r.get('body','')[:200] + '\n'
            out += '   Fonte: ' + r.get('source','') + ' | ' + r.get('date','') + '\n'
            out += '   URL: ' + r.get('url','') + '\n\n'
        return out
    except Exception as e:
        return 'Erro noticias: ' + str(e)

def ler_pagina_web(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for tag in soup(['script','style','nav','footer','header','aside']):
            tag.decompose()
        title = soup.title.string if soup.title else ''
        text = soup.get_text(separator='\n', strip=True)
        lines = [l for l in text.split('\n') if len(l.strip()) > 20]
        content = '\n'.join(lines[:100])
        return 'TITULO: ' + title + '\n\nCONTEUDO:\n' + content[:3000]
    except Exception as e:
        return 'Erro ao ler pagina: ' + str(e)

def buscar_videos_youtube(query):
    try:
        ydl_opts = {'quiet': True, 'extract_flat': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info('ytsearch10:' + query, download=False)
        if not result or 'entries' not in result:
            return 'Nenhum video encontrado.'
        out = 'VIDEOS DO YOUTUBE:\n\n'
        for i, v in enumerate(result['entries'][:8], 1):
            if v:
                vid_url = 'https://youtube.com/watch?v=' + str(v.get('id',''))
                out += str(i) + '. ' + str(v.get('title','')) + '\n'
                out += '   Canal: ' + str(v.get('channel', v.get('uploader',''))) + '\n'
                out += '   URL: ' + vid_url + '\n\n'
        return out
    except Exception as e:
        return 'Erro YouTube: ' + str(e)

def get_info_youtube(url):
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True}) as ydl:
            info = ydl.extract_info(url, download=False)
        out = 'TITULO: ' + str(info.get('title','')) + '\n'
        out += 'CANAL: ' + str(info.get('channel', info.get('uploader',''))) + '\n'
        out += 'DURACAO: ' + str(info.get('duration_string','')) + '\n'
        views = info.get('view_count', 0)
        out += 'VIEWS: ' + str(views) + '\n'
        out += 'DESCRICAO:\n' + str(info.get('description',''))[:800]
        return out
    except Exception as e:
        return 'Erro info YouTube: ' + str(e)

def buscar_instagram_perfil(username):
    try:
        L = instaloader.Instaloader(quiet=True)
        profile = instaloader.Profile.from_username(L.context, username.lstrip('@'))
        out = 'PERFIL INSTAGRAM: @' + profile.username + '\n'
        out += 'Nome: ' + str(profile.full_name) + '\n'
        out += 'Bio: ' + str(profile.biography) + '\n'
        out += 'Seguidores: ' + str(profile.followers) + '\n'
        out += 'Seguindo: ' + str(profile.followees) + '\n'
        out += 'Posts: ' + str(profile.mediacount) + '\n'
        out += 'Verificado: ' + ('Sim' if profile.is_verified else 'Nao') + '\n'
        return out
    except Exception as e:
        return 'Erro Instagram: ' + str(e)

def calcular_codigo_python(codigo):
    try:
        result = subprocess.run(['python3', '-c', codigo], capture_output=True, text=True, timeout=10)
        out = ''
        if result.stdout:
            out += 'SAIDA:\n' + result.stdout
        if result.stderr:
            out += 'ERRO:\n' + result.stderr
        return out if out else 'Executado sem saida.'
    except subprocess.TimeoutExpired:
        return 'Timeout: codigo muito lento.'
    except Exception as e:
        return 'Erro: ' + str(e)

def verificar_clima(cidade):
    try:
        url = 'https://wttr.in/' + cidade + '?format=j1&lang=pt'
        resp = httpx.get(url, timeout=10)
        data = resp.json()
        current = data['current_condition'][0]
        desc = current['weatherDesc'][0]['value']
        temp_c = current['temp_C']
        feels = current['FeelsLikeC']
        humidity = current['humidity']
        wind = current['windspeedKmph']
        out = 'CLIMA EM ' + cidade.upper() + ':\n'
        out += 'Condicao: ' + desc + '\n'
        out += 'Temperatura: ' + temp_c + 'C (sensacao ' + feels + 'C)\n'
        out += 'Umidade: ' + humidity + '%\n'
        out += 'Vento: ' + wind + ' km/h\n'
        forecast = data.get('weather', [])
        if forecast:
            out += '\nPREVISAO 3 DIAS:\n'
            for day in forecast[:3]:
                date = day.get('date','')
                max_t = day.get('maxtempC','')
                min_t = day.get('mintempC','')
                out += '  ' + date + ': ' + min_t + 'C - ' + max_t + 'C\n'
        return out
    except Exception as e:
        return 'Erro clima: ' + str(e)

def _coin_id(symbol):
    ids = {'BTC':'bitcoin','ETH':'ethereum','BNB':'binancecoin','SOL':'solana',
           'ADA':'cardano','DOGE':'dogecoin','XRP':'ripple','MATIC':'matic-network',
           'AVAX':'avalanche-2','DOT':'polkadot'}
    return ids.get(symbol, symbol.lower())

def cotacao_cripto_e_moedas(simbolo):
    try:
        s = simbolo.upper().strip()
        cryptos = ['BTC','ETH','BNB','SOL','ADA','DOGE','XRP','MATIC','AVAX','DOT']
        if s in cryptos:
            coin_id = _coin_id(s)
            url = 'https://api.coingecko.com/api/v3/simple/price?ids=' + coin_id + '&vs_currencies=usd,brl'
            resp = httpx.get(url, timeout=10)
            data = resp.json()
            if coin_id in data:
                usd = data[coin_id].get('usd', 0)
                brl = data[coin_id].get('brl', 0)
                return 'COTACAO ' + s + ':\nUSD: $' + str(usd) + '\nBRL: R$' + str(brl)
        resp2 = httpx.get('https://economia.awesomeapi.com.br/json/last/' + s + '-BRL', timeout=10)
        data2 = resp2.json()
        key = list(data2.keys())[0] if data2 else None
        if key:
            d = data2[key]
            return 'COTACAO ' + s + '/BRL:\nCompra: R$' + str(round(float(d.get('bid',0)),4)) + '\nVenda: R$' + str(round(float(d.get('ask',0)),4)) + '\nVariacao: ' + str(d.get('pctChange','0')) + '%'
        return 'Cotacao nao encontrada para ' + s
    except Exception as e:
        return 'Erro cotacao: ' + str(e)

def buscar_imagens(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=5))
        if not results:
            return 'Nenhuma imagem encontrada.'
        out = 'IMAGENS:\n\n'
        for i, r in enumerate(results, 1):
            out += str(i) + '. ' + r.get('title','') + '\n'
            out += '   URL: ' + r.get('image','') + '\n\n'
        return out
    except Exception as e:
        return 'Erro imagens: ' + str(e)

def ler_rss_feed(url):
    try:
        feed = feedparser.parse(url)
        if not feed.entries:
            return 'Feed sem entradas ou URL invalida.'
        out = 'FEED: ' + feed.feed.get('title', url) + '\n\n'
        for i, entry in enumerate(feed.entries[:10], 1):
            out += str(i) + '. ' + entry.get('title','') + '\n'
            out += '   ' + entry.get('summary','')[:200] + '\n'
            out += '   URL: ' + entry.get('link','') + '\n\n'
        return out
    except Exception as e:
        return 'Erro RSS: ' + str(e)

def pesquisar_wikipedia(tema):
    try:
        url = 'https://pt.wikipedia.org/w/api.php?action=query&list=search&srsearch=' + tema + '&format=json&srlimit=2'
        resp = httpx.get(url, timeout=10)
        data = resp.json()
        results = data.get('query', {}).get('search', [])
        if not results:
            return 'Nenhum resultado Wikipedia para: ' + tema
        out = 'WIKIPEDIA - ' + tema + ':\n\n'
        for r in results[:1]:
            title = r.get('title','')
            page_url = 'https://pt.wikipedia.org/wiki/' + title.replace(' ','_')
            page = ler_pagina_web(page_url)
            out += 'ARTIGO: ' + title + '\n' + page[:2000] + '\n\n'
        return out
    except Exception as e:
        return 'Erro Wikipedia: ' + str(e)

def get_data_hora():
    now = datetime.now()
    return 'Data/Hora: ' + now.strftime('%d/%m/%Y %H:%M:%S')

# ===== TOOLS DEFINITION =====
TOOL_FUNCTIONS = {
    'buscar_internet': buscar_internet,
    'buscar_noticias': buscar_noticias,
    'ler_pagina_web': ler_pagina_web,
    'buscar_videos_youtube': buscar_videos_youtube,
    'get_info_youtube': get_info_youtube,
    'buscar_instagram_perfil': buscar_instagram_perfil,
    'calcular_codigo_python': calcular_codigo_python,
    'verificar_clima': verificar_clima,
    'cotacao_cripto_e_moedas': cotacao_cripto_e_moedas,
    'buscar_imagens': buscar_imagens,
    'ler_rss_feed': ler_rss_feed,
    'pesquisar_wikipedia': pesquisar_wikipedia,
    'get_data_hora': lambda: get_data_hora(),
}

TOOLS_CONFIG = [genai.protos.Tool(
    function_declarations=[
        genai.protos.FunctionDeclaration(name='buscar_internet', description='Busca informacoes atualizadas na internet. Use para qualquer pergunta sobre fatos, noticias, pessoas, produtos.',
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={'query': genai.protos.Schema(type=genai.protos.Type.STRING), 'max_results': genai.protos.Schema(type=genai.protos.Type.INTEGER)}, required=['query'])),
        genai.protos.FunctionDeclaration(name='buscar_noticias', description='Busca noticias recentes sobre qualquer assunto.',
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={'query': genai.protos.Schema(type=genai.protos.Type.STRING)}, required=['query'])),
        genai.protos.FunctionDeclaration(name='ler_pagina_web', description='Le e extrai conteudo de qualquer URL ou pagina web.',
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={'url': genai.protos.Schema(type=genai.protos.Type.STRING)}, required=['url'])),
        genai.protos.FunctionDeclaration(name='buscar_videos_youtube', description='Busca videos no YouTube.',
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={'query': genai.protos.Schema(type=genai.protos.Type.STRING)}, required=['query'])),
        genai.protos.FunctionDeclaration(name='get_info_youtube', description='Pega informacoes detalhadas de um video do YouTube dada a URL.',
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={'url': genai.protos.Schema(type=genai.protos.Type.STRING)}, required=['url'])),
        genai.protos.FunctionDeclaration(name='buscar_instagram_perfil', description='Busca informacoes de perfil publico do Instagram.',
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={'username': genai.protos.Schema(type=genai.protos.Type.STRING)}, required=['username'])),
        genai.protos.FunctionDeclaration(name='calcular_codigo_python', description='Executa codigo Python para calculos, conversoes e analise de dados.',
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={'codigo': genai.protos.Schema(type=genai.protos.Type.STRING)}, required=['codigo'])),
        genai.protos.FunctionDeclaration(name='verificar_clima', description='Verifica clima atual e previsao de qualquer cidade.',
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={'cidade': genai.protos.Schema(type=genai.protos.Type.STRING)}, required=['cidade'])),
        genai.protos.FunctionDeclaration(name='cotacao_cripto_e_moedas', description='Cotacao de criptomoedas (BTC, ETH) e moedas (USD, EUR) em reais.',
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={'simbolo': genai.protos.Schema(type=genai.protos.Type.STRING)}, required=['simbolo'])),
        genai.protos.FunctionDeclaration(name='buscar_imagens', description='Busca imagens na internet.',
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={'query': genai.protos.Schema(type=genai.protos.Type.STRING)}, required=['query'])),
        genai.protos.FunctionDeclaration(name='ler_rss_feed', description='Le feed RSS de noticias.',
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={'url': genai.protos.Schema(type=genai.protos.Type.STRING)}, required=['url'])),
        genai.protos.FunctionDeclaration(name='pesquisar_wikipedia', description='Pesquisa artigos da Wikipedia em portugues.',
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={'tema': genai.protos.Schema(type=genai.protos.Type.STRING)}, required=['tema'])),
        genai.protos.FunctionDeclaration(name='get_data_hora', description='Retorna data e hora atual.',
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={}, required=[])),
    ]
)]

SYSTEM_PROMPT = ('Voce e um assistente pessoal extremamente capaz no Telegram. '
    'Voce tem acesso a ferramentas e DEVE usa-las automaticamente. '
    'FERRAMENTAS: buscar_internet (busca na web), buscar_noticias (noticias recentes), '
    'ler_pagina_web (le qualquer URL), buscar_videos_youtube, get_info_youtube, '
    'buscar_instagram_perfil, calcular_codigo_python, verificar_clima, '
    'cotacao_cripto_e_moedas, buscar_imagens, ler_rss_feed, pesquisar_wikipedia, get_data_hora. '
    'REGRAS: 1) SEMPRE use ferramentas para informacoes atualizadas. '
    '2) Para noticias/cotacoes/clima SEMPRE busque primeiro. '
    '3) Para URLs na mensagem SEMPRE leia a pagina. '
    '4) Responda em portugues do Brasil. '
    '5) Seja direto e util.')


async def processar_com_gemini(chat_id, mensagem, imagem_b64=None, mime_type=None):
    model = genai.GenerativeModel(
        model_name='gemini-2.0-flash',
        system_instruction=SYSTEM_PROMPT,
        tools=TOOLS_CONFIG
    )
    if chat_id not in conversation_history:
        conversation_history[chat_id] = []
    parts = []
    if imagem_b64:
        parts.append({'inline_data': {'mime_type': mime_type, 'data': imagem_b64}})
    parts.append({'text': mensagem})
    conversation_history[chat_id].append({'role': 'user', 'parts': parts})
    if len(conversation_history[chat_id]) > 30:
        conversation_history[chat_id] = conversation_history[chat_id][-30:]
    try:
        response = model.generate_content(conversation_history[chat_id])
        max_loops = 10
        loop = 0
        while loop < max_loops:
            loop += 1
            candidate = response.candidates[0]
            fn_call = None
            for p in candidate.content.parts:
                if hasattr(p, 'function_call') and p.function_call.name:
                    fn_call = p
                    break
            if not fn_call:
                break
            fn_name = fn_call.function_call.name
            fn_args = dict(fn_call.function_call.args)
            logger.info('Tool: ' + fn_name + ' args: ' + str(fn_args))
            conversation_history[chat_id].append({'role': 'model', 'parts': [fn_call]})
            if fn_name in TOOL_FUNCTIONS:
                fn_result = TOOL_FUNCTIONS[fn_name](**fn_args)
            else:
                fn_result = 'Ferramenta nao encontrada: ' + fn_name
            tool_resp = {
                'role': 'user',
                'parts': [{'function_response': {'name': fn_name, 'response': {'result': str(fn_result)}}}]
            }
            conversation_history[chat_id].append(tool_resp)
            response = model.generate_content(conversation_history[chat_id])
        final_text = response.text
        conversation_history[chat_id].append({'role': 'model', 'parts': [{'text': final_text}]})
        return final_text
    except Exception as e:
        logger.error('Erro Gemini: ' + traceback.format_exc())
        return 'Erro: ' + str(e)

# ===== HANDLERS TELEGRAM =====

async def start(update, context):
    name = update.effective_user.first_name or 'amigo'
    text = ('Ola ' + name + '! Sou seu assistente pessoal com Gemini AI.\n\n'
        'FERRAMENTAS:\n'
        'Busca na internet e noticias\n'
        'Leitura de paginas web (cole uma URL)\n'
        'YouTube (busca e info de videos)\n'
        'Instagram (perfis publicos)\n'
        'Clima de qualquer cidade\n'
        'Cotacao de cripto (BTC, ETH...) e moedas (USD, EUR...)\n'
        'Execucao de codigo Python (calculos)\n'
        'Wikipedia em portugues\n'
        'Analise de imagens e transcricao de audio\n\n'
        'EXEMPLOS:\n'
        'qual o clima em sao paulo hoje?\n'
        'cotacao do bitcoin\n'
        'ultimas noticias sobre ia\n'
        'busca videos de python no youtube\n'
        'perfil do @cristiano no instagram\n'
        'calcule 15% de 3500\n'
        '[envie foto para analise]\n'
        '[envie audio para transcricao]\n\n'
        '/clear para limpar historico | /ferramentas para ver ferramentas')
    await update.message.reply_text(text)

async def ferramentas_cmd(update, context):
    text = ('FERRAMENTAS ATIVAS:\n\n'
        '1. buscar_internet - Busca qualquer coisa na web\n'
        '2. buscar_noticias - Noticias recentes\n'
        '3. ler_pagina_web - Le qualquer URL\n'
        '4. buscar_videos_youtube - Busca no YouTube\n'
        '5. get_info_youtube - Info de video YouTube\n'
        '6. buscar_instagram_perfil - Perfil Instagram\n'
        '7. calcular_codigo_python - Executa Python\n'
        '8. verificar_clima - Clima de cidades\n'
        '9. cotacao_cripto_e_moedas - Cripto e moedas\n'
        '10. buscar_imagens - Busca imagens\n'
        '11. ler_rss_feed - Feeds RSS\n'
        '12. pesquisar_wikipedia - Wikipedia PT\n'
        '13. get_data_hora - Data e hora atual\n\n'
        'O Gemini escolhe a ferramenta automaticamente!')
    await update.message.reply_text(text)

async def clear_cmd(update, context):
    chat_id = update.effective_chat.id
    conversation_history.pop(chat_id, None)
    await update.message.reply_text('Historico limpo!')

async def handle_message(update, context):
    if not update.message:
        return
    chat_id = update.effective_chat.id
    mensagem = update.message.text or update.message.caption or ''
    imagem_b64 = None
    mime_type = None
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    try:
        if update.message.photo:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            data = await file.download_as_bytearray()
            imagem_b64 = base64.b64encode(bytes(data)).decode()
            mime_type = 'image/jpeg'
            if not mensagem:
                mensagem = 'Analise esta imagem detalhadamente.'
        elif update.message.voice or update.message.audio:
            media = update.message.voice or update.message.audio
            file = await context.bot.get_file(media.file_id)
            data = await file.download_as_bytearray()
            audio_b64 = base64.b64encode(bytes(data)).decode()
            ext_mime = 'audio/ogg' if update.message.voice else 'audio/mpeg'
            tm = genai.GenerativeModel('gemini-2.0-flash')
            resp = tm.generate_content([
                {'text': 'Transcreva este audio em portugues.'},
                {'inline_data': {'mime_type': ext_mime, 'data': audio_b64}}
            ])
            transcription = resp.text
            await update.message.reply_text('Transcricao: ' + transcription)
            mensagem = transcription
        if not mensagem and not imagem_b64:
            return
        response = await processar_com_gemini(chat_id, mensagem, imagem_b64, mime_type)
        MAX_LEN = 4096
        if len(response) <= MAX_LEN:
            await update.message.reply_text(response)
        else:
            for i in range(0, len(response), MAX_LEN):
                await update.message.reply_text(response[i:i+MAX_LEN])
                await asyncio.sleep(0.3)
    except Exception as e:
        logger.error('Erro: ' + traceback.format_exc())
        await update.message.reply_text('Erro: ' + str(e)[:200])


def main():
    if not TELEGRAM_TOKEN:
        raise ValueError('TELEGRAM_BOT_TOKEN nao configurado!')
    if not GOOGLE_API_KEY:
        raise ValueError('GOOGLE_API_KEY nao configurado!')
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', start))
    app.add_handler(CommandHandler('clear', clear_cmd))
    app.add_handler(CommandHandler('ferramentas', ferramentas_cmd))
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.VOICE | filters.AUDIO,
        handle_message
    ))
    logger.info('Bot Python com Gemini + Ferramentas iniciado!')
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == '__main__':
    main()
