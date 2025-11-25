FROM python:3.11-slim

WORKDIR /app

# Copiar dependências primeiro (melhor cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código do bot
COPY bot.py .

# Variáveis de ambiente necessárias (configurar no Railway/Render)
# TELEGRAM_BOT_TOKEN - Token do bot (obtido do @BotFather)
# AUTHORIZED_USER_ID - Seu ID de usuário Telegram
# GITHUB_TOKEN - Token do GitHub com permissão de escrita
# GITHUB_REPO - Repositório (ex: PrinceOfFear/app-empresa-releases)

# Executar o bot
CMD ["python", "bot.py"]
