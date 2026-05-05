import os
import json
import discord
from discord.ext import commands, tasks
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ================== CONFIG ==================

TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
HR_CHANNEL_ID = int(os.getenv("HR_CHANNEL_ID"))

# ===== роли =====

def env_role(name):
    val = os.getenv(name)
    return int(val) if val else None

RANK_ROLES = {
    "Стажер": env_role("ROLE_STAZHER"),
    "Старший Стажер": env_role("ROLE_STARSHII_STAZHER"),
    "Помощник Защиты": env_role("ROLE_HELPER"),
    "Младший Защитник": env_role("ROLE_JUNIOR"),
    "Защитник": env_role("ROLE_DEFENDER"),
    "Старший Защитник": env_role("ROLE_SENIOR"),
    "Ведущий Защитник": env_role("ROLE_LEAD"),
    "Главный Защитник": env_role("ROLE_MAIN"),
    "Зам Начальника Отдела": env_role("ROLE_ZAM"),
    "Начальник Отдела": env_role("ROLE_BOSS"),
    "Зам Главы Защиты": env_role("ROLE_ZAM_MAIN"),
    "Глава Защиты": env_role("ROLE_GLAW"),
}

ROLE_SOSTAV = env_role("ROLE_SOSTAV")

# ============================================

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== helpers =====

def now():
    return datetime.now().strftime("%d.%m.%Y")


def user_line(member, static, name):
    mention = member.mention if member else "`Не найден`"
    return f"`🆔` **`[{static}] {name}`** (( {mention} ))"


def clean(text):
    return str(text).lower()


def find_member(guild, name):
    name = clean(name)

    for m in guild.members:
        if m.nick and name in clean(m.nick):
            return m
        if name in clean(m.name):
            return m

    return None


# ===== google =====

def get_rows():
    creds = Credentials.from_service_account_info(
        json.loads(os.getenv("GOOGLE_CREDS_JSON")),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )

    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID)

    return sheet.worksheet("Кадровый аудит").get_all_records()


# ===== роли =====

async def give_role(member, rank):
    role_id = RANK_ROLES.get(rank)

    if not role_id:
        return

    role = member.guild.get_role(role_id)

    if role:
        await member.add_roles(role)

    if rank in ["Зам Начальника Отдела", "Начальник Отдела", "Зам Главы Защиты", "Глава Защиты"]:
        sostav = member.guild.get_role(ROLE_SOSTAV)
        if sostav:
            await member.add_roles(sostav)


# ===== отправка =====

async def send(text):
    ch = bot.get_channel(HR_CHANNEL_ID)
    msg = await ch.send(text)
    await msg.add_reaction("✅")


# ===== обработка =====

async def handle(row, guild):
    action = row.get("Действие")
    name = row.get("Имя Фамилия")
    static = row.get("Статик")
    rank = row.get("Ранг")
    reason = row.get("Причина")

    member = find_member(guild, name)

    if not member:
        print("❌ не найден:", name)
        return

    # ===== ПРИНЯТИЕ =====
    if action == "Принят":

        await give_role(member, rank)

        text = (
            f"1. {user_line(member, static, name)}\n"
            f"2. `🆕` Принят на работу на ранг «__{rank}__» // {reason if reason else 'Собеседование'}\n"
            f"3. `📆` Дата принятия: **`{now()}`**"
        )

        await send(text)

    # ===== ПОВЫШЕНИЕ =====
    elif action == "Повышен":

        await give_role(member, rank)

        text = (
            f"1. {user_line(member, static, name)}\n"
            f"2. `📈` Повышен на ранг «__{rank}__» // {reason if reason else 'Не указана'}\n"
            f"3. `📆` Дата повышения: **`{now()}`**"
        )

        await send(text)

    # ===== УВОЛЬНЕНИЕ =====
    elif action == "Уволен":

        text = (
            f"1. {user_line(member, static, name)}\n"
            f"2. `⭕` Уволен из семьи // {reason if reason else 'Не указана'}\n"
            f"3. `📆` Дата увольнения: **`{now()}`**"
        )

        await send(text)

    # ===== ПЕРЕВОД =====
    elif action == "Переведен":

        text = (
            f"1. {user_line(member, static, name)}\n"
            f"2. `🔁` Переведен в отдел: **{rank}** // {reason if reason else 'Не указана'}\n"
            f"3. `📆` Дата перевода: **`{now()}`**"
        )

        await send(text)


# ===== loop =====

@tasks.loop(seconds=20)
async def loop_check():
    guild = bot.get_guild(GUILD_ID)

    rows = get_rows()

    for row in rows[-5:]:
        await handle(row, guild)


@bot.event
async def on_ready():
    print("бот запущен", bot.user)
    loop_check.start()


bot.run(TOKEN)
