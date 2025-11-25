"""Bot de Telegram para gerenciamento de licencas.

Comandos disponiveis:
    /start - Mensagem de boas-vindas
    /ajuda - Lista de comandos
    /ativar CPF MESES [NOME] - Ativa nova licenca
    /renovar CPF MESES - Renova licenca existente
    /cancelar CPF - Cancela licenca
    /suspender CPF - Suspende licenca
    /status CPF - Ver status de uma licenca
    /listar - Lista todas as licencas
    /vencendo - Lista licencas que vencem em 7 dias
"""

import os
import json
import base64
import logging
import re
from datetime import datetime, date, timedelta
from typing import Any
import urllib.request
import urllib.error

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Configuracao de logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Configuracoes via variaveis de ambiente
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "PrinceOfFear")
GITHUB_REPO = os.getenv("GITHUB_REPO", "app-empresa-releases")
ADMIN_USER_IDS = os.getenv("ADMIN_USER_IDS", "").split(",")  # IDs permitidos

# Planos disponiveis
PLANOS = {
    "basico": {"nome": "Basico", "usuarios": 1, "preco": "R$ 49,90/mes"},
    "profissional": {"nome": "Profissional", "usuarios": 3, "preco": "R$ 89,90/mes"},
    "empresarial": {"nome": "Empresarial", "usuarios": 10, "preco": "R$ 149,90/mes"},
}


def is_admin(user_id: int) -> bool:
    """Verifica se o usuario e admin."""
    return str(user_id) in ADMIN_USER_IDS or not ADMIN_USER_IDS[0]


def normalize_cpf_cnpj(value: str) -> str:
    """Remove formatacao de CPF/CNPJ."""
    return re.sub(r"[^\d]", "", value)


def format_cpf_cnpj(value: str) -> str:
    """Formata CPF ou CNPJ."""
    digits = normalize_cpf_cnpj(value)
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    elif len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return value


def generate_license_key() -> str:
    """Gera uma nova chave de licenca."""
    import secrets
    import string
    chars = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    parts = []
    for _ in range(4):
        part = "".join(secrets.choice(chars) for _ in range(4))
        parts.append(part)
    return "-".join(parts)


# ==============================================================================
# GITHUB API
# ==============================================================================

def get_licenses() -> tuple[list[dict], str | None]:
    """Busca licenses.json do GitHub. Retorna (lista, sha)."""
    if not GITHUB_TOKEN:
        return [], None
    
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/licenses.json"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "LicenseBot/1.0",
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            content = base64.b64decode(data.get("content", "")).decode("utf-8")
            licenses_data = json.loads(content)
            return licenses_data.get("licenses", []), data.get("sha")
    except Exception as e:
        logger.error(f"Erro ao buscar licencas: {e}")
        return [], None


def save_licenses(licenses: list[dict], sha: str | None, message: str) -> bool:
    """Salva licenses.json no GitHub."""
    if not GITHUB_TOKEN:
        return False
    
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/licenses.json"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "LicenseBot/1.0",
    }
    
    data = {
        "licenses": licenses,
        "updated_at": datetime.now().isoformat(),
    }
    content_json = json.dumps(data, indent=2, ensure_ascii=False)
    content_b64 = base64.b64encode(content_json.encode("utf-8")).decode("utf-8")
    
    body = {
        "message": message,
        "content": content_b64,
    }
    if sha:
        body["sha"] = sha
    
    try:
        body_bytes = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=body_bytes, headers=headers, method="PUT")
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status == 200 or response.status == 201
    except Exception as e:
        logger.error(f"Erro ao salvar licencas: {e}")
        return False


def find_license_by_cpf(cpf: str, licenses: list[dict]) -> dict | None:
    """Busca licenca por CPF/CNPJ."""
    cpf_clean = normalize_cpf_cnpj(cpf)
    for lic in licenses:
        lic_cpf = normalize_cpf_cnpj(lic.get("cpf_cnpj", ""))
        if lic_cpf == cpf_clean:
            return lic
    return None


# ==============================================================================
# COMANDOS DO BOT
# ==============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /start."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Acesso negado. Voce nao esta autorizado.")
        return
    
    await update.message.reply_text(
        f"Ola, {user.first_name}! 👋\n\n"
        "Sou o bot de gerenciamento de licencas.\n\n"
        "Comandos disponiveis:\n"
        "/ativar CPF MESES [NOME] - Ativar licenca\n"
        "/renovar CPF MESES - Renovar licenca\n"
        "/cancelar CPF - Cancelar licenca\n"
        "/status CPF - Ver status\n"
        "/listar - Listar todas\n"
        "/vencendo - Licencas proximas do vencimento\n"
        "/ajuda - Ver todos os comandos"
    )


async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /ajuda."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    texto = """📚 *COMANDOS DISPONIVEIS*

*Ativacao:*
`/ativar 12345678901 1`
`/ativar 12345678901 12 Empresa XYZ`
→ Ativa CPF por 1 ou 12 meses

*Renovacao:*
`/renovar 12345678901 1`
→ Renova por mais 1 mes

*Cancelamento:*
`/cancelar 12345678901`
→ Cancela a licenca

*Suspensao:*
`/suspender 12345678901`
→ Suspende temporariamente

*Consultas:*
`/status 12345678901`
→ Ver detalhes da licenca

`/listar`
→ Ver todas as licencas

`/vencendo`
→ Licencas que vencem em 7 dias

*Planos:*
`/plano basico 12345678901`
`/plano profissional 12345678901`
`/plano empresarial 12345678901`
→ Altera o plano
"""
    await update.message.reply_text(texto, parse_mode="Markdown")


async def ativar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /ativar CPF MESES [NOME]."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Uso: /ativar CPF MESES [NOME]\n"
            "Exemplo: /ativar 12345678901 1\n"
            "Exemplo: /ativar 12345678901 12 Empresa XYZ"
        )
        return
    
    cpf = normalize_cpf_cnpj(args[0])
    if len(cpf) not in (11, 14):
        await update.message.reply_text("CPF/CNPJ invalido. Use 11 ou 14 digitos.")
        return
    
    try:
        meses = int(args[1])
        if meses < 1 or meses > 24:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("Meses deve ser um numero entre 1 e 24.")
        return
    
    nome = " ".join(args[2:]) if len(args) > 2 else f"Cliente {cpf[-4:]}"
    
    # Buscar licencas existentes
    await update.message.reply_text("⏳ Processando...")
    licenses, sha = get_licenses()
    
    # Verificar se ja existe
    existing = find_license_by_cpf(cpf, licenses)
    if existing:
        await update.message.reply_text(
            f"⚠️ Ja existe licenca para este CPF/CNPJ!\n"
            f"Cliente: {existing.get('customer')}\n"
            f"Status: {existing.get('status')}\n\n"
            f"Use /renovar para estender ou /cancelar para remover."
        )
        return
    
    # Criar nova licenca
    key = generate_license_key()
    expires = (date.today() + timedelta(days=30 * meses)).isoformat()
    
    nova_licenca = {
        "key": key,
        "cpf_cnpj": cpf,
        "customer": nome,
        "email": "",
        "plan": "profissional",
        "status": "active",
        "expires": expires,
        "max_users": 3,
        "created_at": datetime.now().isoformat(),
    }
    
    licenses.append(nova_licenca)
    
    if save_licenses(licenses, sha, f"Ativar licenca: {nome}"):
        await update.message.reply_text(
            f"✅ *LICENCA ATIVADA!*\n\n"
            f"👤 Cliente: {nome}\n"
            f"📄 CPF/CNPJ: {format_cpf_cnpj(cpf)}\n"
            f"📅 Validade: {meses} mes(es)\n"
            f"⏰ Expira em: {expires}\n"
            f"📦 Plano: Profissional\n\n"
            f"O cliente pode ativar usando o CPF/CNPJ no app.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Erro ao salvar licenca. Tente novamente.")


async def renovar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /renovar CPF MESES."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Uso: /renovar CPF MESES\nExemplo: /renovar 12345678901 1")
        return
    
    cpf = normalize_cpf_cnpj(args[0])
    try:
        meses = int(args[1])
    except ValueError:
        await update.message.reply_text("Meses deve ser um numero.")
        return
    
    await update.message.reply_text("⏳ Processando...")
    licenses, sha = get_licenses()
    
    lic = find_license_by_cpf(cpf, licenses)
    if not lic:
        await update.message.reply_text(f"❌ Licenca nao encontrada para CPF/CNPJ: {cpf}")
        return
    
    # Calcular nova data
    try:
        current_expires = date.fromisoformat(lic["expires"])
    except (KeyError, ValueError):
        current_expires = date.today()
    
    base_date = max(current_expires, date.today())
    new_expires = base_date + timedelta(days=30 * meses)
    
    lic["expires"] = new_expires.isoformat()
    lic["status"] = "active"
    
    if save_licenses(licenses, sha, f"Renovar licenca: {lic.get('customer')}"):
        await update.message.reply_text(
            f"✅ *LICENCA RENOVADA!*\n\n"
            f"👤 Cliente: {lic.get('customer')}\n"
            f"📅 Nova validade: {new_expires.isoformat()}\n"
            f"➕ Adicionado: {meses} mes(es)",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Erro ao salvar. Tente novamente.")


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /cancelar CPF."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Uso: /cancelar CPF\nExemplo: /cancelar 12345678901")
        return
    
    cpf = normalize_cpf_cnpj(args[0])
    
    await update.message.reply_text("⏳ Processando...")
    licenses, sha = get_licenses()
    
    lic = find_license_by_cpf(cpf, licenses)
    if not lic:
        await update.message.reply_text(f"❌ Licenca nao encontrada para: {cpf}")
        return
    
    lic["status"] = "cancelled"
    
    if save_licenses(licenses, sha, f"Cancelar licenca: {lic.get('customer')}"):
        await update.message.reply_text(
            f"✅ Licenca CANCELADA!\n\n"
            f"👤 Cliente: {lic.get('customer')}\n"
            f"📄 CPF/CNPJ: {format_cpf_cnpj(cpf)}"
        )
    else:
        await update.message.reply_text("❌ Erro ao salvar. Tente novamente.")


async def suspender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /suspender CPF."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Uso: /suspender CPF")
        return
    
    cpf = normalize_cpf_cnpj(args[0])
    
    await update.message.reply_text("⏳ Processando...")
    licenses, sha = get_licenses()
    
    lic = find_license_by_cpf(cpf, licenses)
    if not lic:
        await update.message.reply_text(f"❌ Licenca nao encontrada para: {cpf}")
        return
    
    lic["status"] = "suspended"
    
    if save_licenses(licenses, sha, f"Suspender licenca: {lic.get('customer')}"):
        await update.message.reply_text(
            f"⚠️ Licenca SUSPENSA!\n\n"
            f"👤 Cliente: {lic.get('customer')}\n"
            f"Use /renovar para reativar."
        )
    else:
        await update.message.reply_text("❌ Erro ao salvar. Tente novamente.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /status CPF."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Uso: /status CPF")
        return
    
    cpf = normalize_cpf_cnpj(args[0])
    
    licenses, _ = get_licenses()
    lic = find_license_by_cpf(cpf, licenses)
    
    if not lic:
        await update.message.reply_text(f"❌ Licenca nao encontrada para: {cpf}")
        return
    
    status_emoji = {
        "active": "🟢",
        "expired": "🔴",
        "suspended": "🟡",
        "cancelled": "⚫",
    }.get(lic.get("status", ""), "⚪")
    
    try:
        expires = date.fromisoformat(lic.get("expires", ""))
        dias_restantes = (expires - date.today()).days
        if dias_restantes < 0:
            dias_texto = f"Expirado ha {-dias_restantes} dias"
        else:
            dias_texto = f"{dias_restantes} dias restantes"
    except ValueError:
        dias_texto = "Data invalida"
    
    await update.message.reply_text(
        f"{status_emoji} *STATUS DA LICENCA*\n\n"
        f"👤 Cliente: {lic.get('customer', 'N/A')}\n"
        f"📄 CPF/CNPJ: {format_cpf_cnpj(cpf)}\n"
        f"📧 Email: {lic.get('email', 'N/A')}\n"
        f"📦 Plano: {lic.get('plan', 'N/A')}\n"
        f"👥 Max usuarios: {lic.get('max_users', 'N/A')}\n"
        f"📅 Expira: {lic.get('expires', 'N/A')}\n"
        f"⏰ {dias_texto}\n"
        f"🔖 Status: {lic.get('status', 'N/A')}",
        parse_mode="Markdown"
    )


async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /listar."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    licenses, _ = get_licenses()
    
    if not licenses:
        await update.message.reply_text("Nenhuma licenca cadastrada.")
        return
    
    # Ordenar por status e data
    def sort_key(lic):
        status_order = {"active": 0, "suspended": 1, "expired": 2, "cancelled": 3}
        return (status_order.get(lic.get("status", ""), 9), lic.get("expires", ""))
    
    licenses.sort(key=sort_key)
    
    linhas = ["📋 *LICENCAS CADASTRADAS*\n"]
    
    for lic in licenses:
        status_emoji = {
            "active": "🟢",
            "expired": "🔴",
            "suspended": "🟡",
            "cancelled": "⚫",
        }.get(lic.get("status", ""), "⚪")
        
        cpf = lic.get("cpf_cnpj", lic.get("key", "N/A"))
        if len(cpf) > 8:
            cpf_masked = f"{cpf[:3]}...{cpf[-4:]}"
        else:
            cpf_masked = cpf
        
        linhas.append(
            f"{status_emoji} {lic.get('customer', 'N/A')[:20]}\n"
            f"   {cpf_masked} | {lic.get('expires', 'N/A')}"
        )
    
    linhas.append(f"\nTotal: {len(licenses)} licenca(s)")
    
    await update.message.reply_text("\n".join(linhas), parse_mode="Markdown")


async def vencendo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /vencendo - lista licencas proximas do vencimento."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    licenses, _ = get_licenses()
    hoje = date.today()
    limite = hoje + timedelta(days=7)
    
    proximas = []
    for lic in licenses:
        if lic.get("status") != "active":
            continue
        try:
            expires = date.fromisoformat(lic.get("expires", ""))
            if expires <= limite:
                dias = (expires - hoje).days
                proximas.append((lic, dias))
        except ValueError:
            pass
    
    if not proximas:
        await update.message.reply_text("✅ Nenhuma licenca vencendo nos proximos 7 dias!")
        return
    
    proximas.sort(key=lambda x: x[1])
    
    linhas = ["⚠️ *LICENCAS VENCENDO EM 7 DIAS*\n"]
    for lic, dias in proximas:
        if dias < 0:
            dias_texto = f"VENCIDA ({-dias}d)"
        elif dias == 0:
            dias_texto = "VENCE HOJE!"
        else:
            dias_texto = f"{dias} dias"
        
        linhas.append(
            f"• {lic.get('customer', 'N/A')}\n"
            f"  {lic.get('expires')} ({dias_texto})"
        )
    
    await update.message.reply_text("\n".join(linhas), parse_mode="Markdown")


async def plano(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /plano TIPO CPF."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    args = context.args
    if len(args) < 2:
        planos_texto = "\n".join(
            f"• {k}: {v['nome']} - {v['usuarios']} usuario(s) - {v['preco']}"
            for k, v in PLANOS.items()
        )
        await update.message.reply_text(
            f"Uso: /plano TIPO CPF\n\nPlanos disponiveis:\n{planos_texto}"
        )
        return
    
    tipo = args[0].lower()
    cpf = normalize_cpf_cnpj(args[1])
    
    if tipo not in PLANOS:
        await update.message.reply_text(f"Plano invalido. Use: {', '.join(PLANOS.keys())}")
        return
    
    await update.message.reply_text("⏳ Processando...")
    licenses, sha = get_licenses()
    
    lic = find_license_by_cpf(cpf, licenses)
    if not lic:
        await update.message.reply_text(f"❌ Licenca nao encontrada para: {cpf}")
        return
    
    plano_info = PLANOS[tipo]
    lic["plan"] = tipo
    lic["max_users"] = plano_info["usuarios"]
    
    if save_licenses(licenses, sha, f"Alterar plano: {lic.get('customer')} -> {tipo}"):
        await update.message.reply_text(
            f"✅ Plano alterado!\n\n"
            f"👤 Cliente: {lic.get('customer')}\n"
            f"📦 Novo plano: {plano_info['nome']}\n"
            f"👥 Usuarios: {plano_info['usuarios']}"
        )
    else:
        await update.message.reply_text("❌ Erro ao salvar. Tente novamente.")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para comandos desconhecidos."""
    await update.message.reply_text("Comando nao reconhecido. Use /ajuda para ver os comandos.")


def main() -> None:
    """Inicia o bot."""
    if not TELEGRAM_TOKEN:
        print("ERRO: TELEGRAM_TOKEN nao configurado!")
        print("Configure a variavel de ambiente TELEGRAM_TOKEN")
        return
    
    if not GITHUB_TOKEN:
        print("AVISO: GITHUB_TOKEN nao configurado. Bot funcionara em modo somente leitura.")
    
    print("Iniciando bot...")
    print(f"GitHub: {GITHUB_OWNER}/{GITHUB_REPO}")
    print(f"Admins: {ADMIN_USER_IDS}")
    
    # Criar aplicacao
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Registrar handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ajuda", ajuda))
    application.add_handler(CommandHandler("help", ajuda))
    application.add_handler(CommandHandler("ativar", ativar))
    application.add_handler(CommandHandler("renovar", renovar))
    application.add_handler(CommandHandler("cancelar", cancelar))
    application.add_handler(CommandHandler("suspender", suspender))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("listar", listar))
    application.add_handler(CommandHandler("vencendo", vencendo))
    application.add_handler(CommandHandler("plano", plano))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    
    # Iniciar
    print("Bot iniciado! Aguardando comandos...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
