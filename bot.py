"""Bot de Telegram para gerenciamento de licencas."""

import os
import json
import base64
import logging
import re
import secrets
from datetime import datetime, date, timedelta
import urllib.request
import urllib.error

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# Configuracao de logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Configuracoes via variaveis de ambiente
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
_repo_env = os.getenv("GITHUB_REPO", "PrinceOfFear/app-empresa-releases")
if "/" in _repo_env:
    GITHUB_OWNER, GITHUB_REPO = _repo_env.split("/", 1)
else:
    GITHUB_OWNER = "PrinceOfFear"
    GITHUB_REPO = _repo_env
ADMIN_USER_IDS = [x.strip() for x in os.getenv("AUTHORIZED_USER_ID", "").split(",") if x.strip()]


def is_admin(user_id: int) -> bool:
    """Verifica se o usuario e admin."""
    if not ADMIN_USER_IDS:
        return True
    return str(user_id) in ADMIN_USER_IDS


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
    chars = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    parts = []
    for _ in range(4):
        part = "".join(secrets.choice(chars) for _ in range(4))
        parts.append(part)
    return "-".join(parts)


def get_licenses():
    """Busca licenses.json do GitHub. Retorna (lista, sha)."""
    if not GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN nao configurado")
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


def save_licenses(licenses: list, sha, message: str) -> bool:
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
            return response.status in (200, 201)
    except Exception as e:
        logger.error(f"Erro ao salvar licencas: {e}")
        return False


def find_license_by_cpf(cpf: str, licenses: list):
    """Busca licenca por CPF/CNPJ."""
    cpf_clean = normalize_cpf_cnpj(cpf)
    for lic in licenses:
        lic_cpf = normalize_cpf_cnpj(lic.get("cpf_cnpj", ""))
        if lic_cpf == cpf_clean:
            return lic
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /start."""
    if not update.message or not update.effective_user:
        return
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    await update.message.reply_text(
        f"Ola, {update.effective_user.first_name}! 👋\n\n"
        "Comandos:\n"
        "/ativar CPF MESES [NOME]\n"
        "/renovar CPF MESES\n"
        "/cancelar CPF\n"
        "/status CPF\n"
        "/listar\n"
        "/ajuda"
    )


async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /ajuda."""
    if not update.message or not update.effective_user:
        return
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    await update.message.reply_text(
        "📚 COMANDOS\n\n"
        "/ativar 12345678901 1 - Ativa por 1 mes\n"
        "/ativar 12345678901 12 Empresa - Ativa por 12 meses\n"
        "/renovar 12345678901 1 - Renova +1 mes\n"
        "/cancelar 12345678901 - Cancela\n"
        "/status 12345678901 - Ver status\n"
        "/listar - Ver todas"
    )


async def ativar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /ativar CPF MESES [NOME]."""
    if not update.message or not update.effective_user:
        return
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "Uso: /ativar CPF MESES [NOME]\n"
            "Exemplo: /ativar 12345678901 1\n"
            "Exemplo: /ativar 12345678901 12 Empresa XYZ"
        )
        return
    
    cpf = normalize_cpf_cnpj(args[0])
    if len(cpf) not in (11, 14):
        await update.message.reply_text("CPF/CNPJ invalido.")
        return
    
    try:
        meses = int(args[1])
        if meses < 1 or meses > 24:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("Meses deve ser 1-24.")
        return
    
    nome = " ".join(args[2:]) if len(args) > 2 else f"Cliente {cpf[-4:]}"
    
    await update.message.reply_text("⏳ Processando...")
    licenses, sha = get_licenses()
    
    existing = find_license_by_cpf(cpf, licenses)
    if existing:
        await update.message.reply_text(
            f"⚠️ Ja existe licenca para este CPF!\n"
            f"Cliente: {existing.get('customer')}\n"
            f"Use /renovar ou /cancelar."
        )
        return
    
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
    
    if save_licenses(licenses, sha, f"Ativar: {nome}"):
        await update.message.reply_text(
            f"✅ LICENCA ATIVADA!\n\n"
            f"👤 Cliente: {nome}\n"
            f"📄 CPF: {format_cpf_cnpj(cpf)}\n"
            f"📅 Validade: {meses} mes(es)\n"
            f"🔑 Chave: `{key}`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Erro ao salvar.")


async def renovar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /renovar CPF MESES."""
    if not update.message or not update.effective_user:
        return
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text("Uso: /renovar CPF MESES")
        return
    
    cpf = normalize_cpf_cnpj(args[0])
    try:
        meses = int(args[1])
    except ValueError:
        await update.message.reply_text("Meses invalido.")
        return
    
    await update.message.reply_text("⏳ Processando...")
    licenses, sha = get_licenses()
    
    lic = find_license_by_cpf(cpf, licenses)
    if not lic:
        await update.message.reply_text(f"❌ Licenca nao encontrada: {cpf}")
        return
    
    # Verificar status e data atual
    current_status = lic.get("status", "")
    current_key = lic.get("key", "")
    
    try:
        current_expires = date.fromisoformat(lic.get("expires", ""))
    except ValueError:
        current_expires = date.today()
    
    # REGRA CLARA:
    # Se status == "cancelled" OU chave está vazia OU data <= hoje:
    #   -> Começa do ZERO (hoje)
    # Se status == "active" E data > hoje:
    #   -> SOMA a partir da data de expiração
    
    is_cancelled = current_status == "cancelled"
    is_key_empty = not current_key or current_key.strip() == ""
    is_expired = current_expires <= date.today()
    
    # Licença deve começar do zero se: cancelada, sem chave, ou expirada
    should_start_from_zero = is_cancelled or is_key_empty or is_expired
    
    if should_start_from_zero:
        # Começa do zero absoluto (hoje)
        base_date = date.today()
        # Gerar nova chave
        lic["key"] = generate_license_key()
        motivo = "cancelada" if is_cancelled else ("sem chave" if is_key_empty else "expirada")
        logger.info(f"Renovando licenca ({motivo}) - comecando do zero: {base_date}")
        tipo = "REATIVADA (do zero)"
    else:
        # Licença ativa com dias restantes - SOMA a partir da expiração
        base_date = current_expires
        logger.info(f"Renovando licenca ATIVA - somando a partir de: {base_date}")
        tipo = "RENOVADA (+dias)"
    
    new_expires = base_date + timedelta(days=30 * meses)
    
    lic["expires"] = new_expires.isoformat()
    lic["status"] = "active"
    
    if save_licenses(licenses, sha, f"Renovar: {lic.get('customer')}"):
        await update.message.reply_text(
            f"✅ {tipo}!\n\n"
            f"👤 {lic.get('customer')}\n"
            f"📅 Início: {base_date.isoformat()}\n"
            f"📅 Validade: {new_expires.isoformat()}\n"
            f"⏱️ Período: {meses} mês(es)"
        )
    else:
        await update.message.reply_text("❌ Erro ao salvar.")


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /cancelar CPF."""
    if not update.message or not update.effective_user:
        return
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    args = context.args or []
    if len(args) < 1:
        await update.message.reply_text("Uso: /cancelar CPF")
        return
    
    cpf = normalize_cpf_cnpj(args[0])
    
    await update.message.reply_text("⏳ Processando...")
    licenses, sha = get_licenses()
    
    lic = find_license_by_cpf(cpf, licenses)
    if not lic:
        await update.message.reply_text(f"❌ Nao encontrada: {cpf}")
        return
    
    lic["status"] = "cancelled"
    lic["expires"] = date.today().isoformat()  # Zerar validade imediatamente
    lic["key"] = ""  # Invalidar chave
    
    if save_licenses(licenses, sha, f"Cancelar: {lic.get('customer')}"):
        await update.message.reply_text(
            f"✅ CANCELADA!\n👤 {lic.get('customer')}\n📅 Licença zerada."
        )
    else:
        await update.message.reply_text("❌ Erro ao salvar.")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /status CPF."""
    if not update.message or not update.effective_user:
        return
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    args = context.args or []
    if len(args) < 1:
        await update.message.reply_text("Uso: /status CPF")
        return
    
    cpf = normalize_cpf_cnpj(args[0])
    licenses, _ = get_licenses()
    
    lic = find_license_by_cpf(cpf, licenses)
    if not lic:
        await update.message.reply_text(f"❌ Nao encontrada: {cpf}")
        return
    
    status_emoji = {
        "active": "🟢",
        "expired": "🔴",
        "suspended": "🟡",
        "cancelled": "⚫",
    }.get(lic.get("status", ""), "⚪")
    
    try:
        expires = date.fromisoformat(lic.get("expires", ""))
        dias = (expires - date.today()).days
        if dias < 0:
            dias_texto = f"VENCIDA ({-dias}d)"
        elif dias == 0:
            dias_texto = "VENCE HOJE"
        else:
            dias_texto = f"Faltam {dias}d"
    except ValueError:
        dias_texto = "Data invalida"
    
    await update.message.reply_text(
        f"{status_emoji} STATUS\n\n"
        f"👤 {lic.get('customer')}\n"
        f"📄 {format_cpf_cnpj(cpf)}\n"
        f"📅 Expira: {lic.get('expires')}\n"
        f"⏰ {dias_texto}\n"
        f"🔑 {lic.get('key')}"
    )


async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /listar."""
    if not update.message or not update.effective_user:
        return
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acesso negado.")
        return
    
    licenses, _ = get_licenses()
    
    if not licenses:
        await update.message.reply_text("Nenhuma licenca.")
        return
    
    linhas = ["📋 LICENCAS\n"]
    
    for lic in licenses[:15]:
        status_emoji = {
            "active": "🟢",
            "expired": "🔴",
            "suspended": "🟡",
            "cancelled": "⚫",
        }.get(lic.get("status", ""), "⚪")
        
        cpf = lic.get("cpf_cnpj", "")
        cpf_masked = f"...{cpf[-4:]}" if len(cpf) > 4 else cpf
        
        linhas.append(
            f"{status_emoji} {lic.get('customer', 'N/A')[:15]} | {cpf_masked} | {lic.get('expires', '')}"
        )
    
    linhas.append(f"\nTotal: {len(licenses)}")
    await update.message.reply_text("\n".join(linhas))


def main() -> None:
    """Inicia o bot."""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN nao configurado!")
        return
    
    logger.info(f"Iniciando bot... Owner: {GITHUB_OWNER}, Repo: {GITHUB_REPO}")
    logger.info(f"Admins: {ADMIN_USER_IDS}")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ajuda", ajuda))
    app.add_handler(CommandHandler("ativar", ativar))
    app.add_handler(CommandHandler("renovar", renovar))
    app.add_handler(CommandHandler("cancelar", cancelar))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("listar", listar))
    
    logger.info("Bot iniciado!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
