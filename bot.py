import discord
from discord.ext import commands, tasks
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

SHEET_REGISTRY = "Реестр Участников"
SHEET_HR = "Кадровый аудит"

HR_CHANNEL_ID = int(os.getenv("HR_CHANNEL_ID"))

# РАНГИ (вставишь ID в .env)
RANK_ROLES = {
    "Курсант": int(os.getenv("ROLE_KURSANT")),
    "Стажер": int(os.getenv("ROLE_STAJER")),
    "Старший Стажер": int(os.getenv("ROLE_STAJER_PLUS")),
    "Помощник Защиты": int(os.getenv("ROLE_HELPER")),
    "Младший Защитник": int(os.getenv("ROLE_JUNIOR")),
    "Защитник": int(os.getenv("ROLE_DEFENDER")),
    "Старший Защитник": int(os.getenv("ROLE_SENIOR")),
    "Ведущий Защитник": int(os.getenv("ROLE_LEAD")),
    "Главный Защитник": int(os.getenv("ROLE_MAIN")),
    "Зам Начальника Отдела": int(os.getenv("ROLE_ZAM")),
    "Начальник Отдела": int(os.getenv("ROLE_BOSS")),
    "Зам Главы Защиты": int(os.getenv("ROLE_ZAM_MAIN")),
    "Глава Защиты": int(os.getenv("ROLE_GLAW")),
}

ROLE_SOSTAV = int(os.getenv("ROLE_SOSTAV"))

# ==========================================

def now():
    return datetime.now().strftime("%d.%m.%Y")


def get_sheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

    creds = Credentials.from_service_account_info(
        eval(os.getenv("GOOGLE_CREDS_JSON")),
        scopes=scopes
    )

    client = gspread.authorize(creds)
    book = client.open_by_key(SPREADSHEET_ID)

    return book.worksheet(SHEET_HR).get_all_records()


# ===== ПОИСК УЧАСТНИКА =====

def find_member(guild, name):
    name = name.lower()

    for m in guild.members:
        if m.nick and name in m.nick.lower():
            return m
        if name in m.name.lower():
            return m

    return None


# ===== СТРОКА КАК НА СКРИНЕ =====

def line(member):
    return f"🆔 [{member.id}] {member.mention}"


# ===== ВЫДАЧА РОЛЕЙ =====

async def give_rank(member, rank_name):
    if rank_name not in RANK_ROLES:
        return

    role = member.guild.get_role(RANK_ROLES[rank_name])
    if not role:
        return

    await member.add_roles(role)

    if rank_name in [
        "Зам Начальника Отдела",
        "Начальник Отдела",
        "Зам Главы Защиты",
        "Глава Защиты"
    ]:
        sostav = member.guild.get_role(ROLE_SOSTAV)
        if sostav:
            await member.add_roles(sostav)


# ===== ОТПРАВКА =====

async def send_log(text):
    ch = bot.get_channel(HR_CHANNEL_ID)
    if ch:
        msg = await ch.send(text)
        await msg.add_reaction("✅")


# ===== ОБРАБОТКА =====

async def handle(row, guild):
    name = row.get("Ник")
    action = row.get("Действие")
    rank = row.get("Ранг")
    reason = row.get("Причина")

    member = find_member(guild, name)

    if not member:
        print(f"❌ Не найден: {name}")
        return

    # ===== ПРИНЯТИЕ =====
    if action == "Принят":

        await give_rank(member, rank)

        text = (
            f"1. {line(member)}\n"
            f"2. 🆕 Принят на работу на ранг **{rank}** // {reason}\n"
            f"3. 📅 Дата принятия: **{now()}**"
        )

        await send_log(text)

    # ===== ПОВЫШЕНИЕ =====
    elif action == "Повышен":

        await give_rank(member, rank)

        text = (
            f"1. {line(member)}\n"
            f"2. ⬆️ Повышен на ранг **{rank}** // {reason}\n"
            f"3. 📅 Дата повышения: **{now()}**"
        )

        await send_log(text)

    # ===== УВОЛЬНЕНИЕ =====
    elif action == "Уволен":

        text = (
            f"1. {line(member)}\n"
            f"2. ⭕ Уволен из семьи // {reason}\n"
            f"3. 📅 Дата увольнения: **{now()}**"
        )

        await send_log(text)

    # ===== ПЕРЕВОД =====
    elif action == "Переведен":

        text = (
            f"1. {line(member)}\n"
            f"2. 🔁 Переведен в отдел: **{rank}** // {reason}\n"
            f"3. 📅 Дата перевода: **{now()}**"
        )

        await send_log(text)


# ===== LOOP =====

@tasks.loop(seconds=30)
async def check():
    guild = bot.get_guild(GUILD_ID)

    rows = get_sheets()

    for row in rows[-5:]:
        await handle(row, guild)


@bot.event
async def on_ready():
    print(f"Запущен как {bot.user}")
    check.start()


bot.run(TOKEN)
