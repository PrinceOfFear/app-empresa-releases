# 🤖 Bot Telegram - Gerenciador de Licenças

Bot para gerenciar licenças do aplicativo diretamente pelo Telegram.

## 📋 Funcionalidades

| Comando | Descrição | Exemplo |
|---------|-----------|---------|
| `/ativar` | Ativa nova licença | `/ativar 123.456.789-00 3` |
| `/renovar` | Renova licença existente | `/renovar 123.456.789-00 1` |
| `/cancelar` | Cancela licença | `/cancelar 123.456.789-00` |
| `/status` | Consulta status de licença | `/status 123.456.789-00` |
| `/listar` | Lista todas as licenças | `/listar` |
| `/ajuda` | Mostra comandos disponíveis | `/ajuda` |

## 🚀 Deploy no Railway (Recomendado - Gratuito)

### Passo 1: Criar Bot no Telegram

1. Abra o Telegram e procure por `@BotFather`
2. Envie `/newbot`
3. Escolha um nome (ex: "Minha Empresa Licenças")
4. Escolha um username (ex: `minha_empresa_licencas_bot`)
5. **Guarde o token** que o BotFather enviar

### Passo 2: Descobrir seu User ID

1. Procure por `@userinfobot` no Telegram
2. Envie `/start`
3. **Guarde o número** do seu ID

### Passo 3: Deploy no Railway

1. Acesse [railway.app](https://railway.app) e faça login com GitHub
2. Clique em **"New Project"** → **"Deploy from GitHub repo"**
3. Selecione o repositório `app-empresa-releases`
4. Na aba **"Variables"**, adicione:

| Variável | Valor |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | Token do BotFather (passo 1) |
| `AUTHORIZED_USER_ID` | Seu ID (passo 2) |
| `GITHUB_TOKEN` | Seu token GitHub (mesmo do releases) |
| `GITHUB_REPO` | `PrinceOfFear/app-empresa-releases` |

5. Na aba **"Settings"** → **"Root Directory"**, coloque: `telegram-bot`
6. Clique em **"Deploy"**

### Passo 4: Testar

1. Abra o Telegram e procure pelo nome do seu bot
2. Envie `/ajuda`
3. Se responder, está funcionando! 🎉

## 🔧 Deploy Alternativo: Render

1. Acesse [render.com](https://render.com) e faça login
2. Clique em **"New"** → **"Background Worker"**
3. Conecte o repositório GitHub
4. Configure:
   - **Root Directory**: `telegram-bot`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
5. Adicione as variáveis de ambiente (mesmas do Railway)
6. Deploy!

## 💰 Fluxo de Venda

```
1. Cliente paga (Pix/transferência)
2. Você envia no Telegram: /ativar 123.456.789-00 1
3. Bot gera a chave e atualiza o GitHub
4. Você envia a chave para o cliente
5. Cliente ativa no app
```

## 🔒 Segurança

- ✅ Apenas seu ID pode executar comandos
- ✅ Outros usuários recebem mensagem de bloqueio
- ✅ Token GitHub usado apenas para atualizar licenses.json
- ✅ Comunicação criptografada (Telegram + HTTPS)

## 📊 Estrutura do licenses.json

```json
{
  "licenses": [
    {
      "key": "ABCD-1234-EFGH-5678",
      "cpf_cnpj": "123.456.789-00",
      "status": "active",
      "expires_at": "2025-07-15",
      "created_at": "2024-06-15",
      "plan": "mensal"
    }
  ]
}
```

## ⚠️ Troubleshooting

### Bot não responde
- Verifique se o token está correto
- Confirme que o bot está rodando no Railway/Render

### "Não autorizado"
- Verifique se `AUTHORIZED_USER_ID` está correto
- Use @userinfobot para confirmar seu ID

### Erro ao atualizar licenças
- Verifique se `GITHUB_TOKEN` tem permissão de escrita
- Confirme que o repositório está correto

---

**Dúvidas?** Abra uma issue no GitHub ou me envie mensagem! 🚀
