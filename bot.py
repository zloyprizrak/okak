import os
import json
from pathlib import Path
from datetime import datetime

import discord
from discord.ext import commands, tasks
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv


load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDS = os.getenv("GOOGLE_CREDS", "service_account.json")

HR_CHANNEL_ID = int(os.getenv("HR_CHANNEL_ID"))
PUNISH_CHANNEL_ID = int(os.getenv("PUNISH_CHANNEL_ID"))

CHECK_EVERY_SECONDS = 20
STATE_FILE = Path("state.json")

SHEET_REGISTRY = "Реестр Участников"
SHEET_HR = "Кадровый Аудит"
SHEET_PUNISH = "Аудит Взысканий"


def env_role(name: str) -> int | None:
    value = os.getenv(name)
    if not value or value.upper() in {"ID", "ID_РОЛИ"}:
        return None
    return int(value)


RANK_ROLES = {
    "Глава Защиты": env_role("ROLE_GLAVA_ZASHITY"),
    "Зам Главы Защиты": env_role("ROLE_ZAM_GLAVY_ZASHITY"),
    "Начальник Отдела": env_role("ROLE_NACHALNIK_OTDELA"),
    "Зам Начальника Отдела": env_role("ROLE_ZAM_NACHALNIKA_OTDELA"),
    "Главный Защитник": env_role("ROLE_GLAVNYI_ZASHITNIK"),
    "Ведущий Защитник": env_role("ROLE_VEDUSHII_ZASHITNIK"),
    "Старший Защитник": env_role("ROLE_STARSHII_ZASHITNIK"),
    "Защитник": env_role("ROLE_ZASHITNIK"),
    "Младший Защитник": env_role("ROLE_MLADSHII_ZASHITNIK"),
    "Помощник Защиты": env_role("ROLE_POMOSHCHNIK_ZASHITY"),
    "Старший Стажер": env_role("ROLE_STARSHII_STAZHER"),
    "Стажер": env_role("ROLE_STAZHER"),

    "Зам главы защиты": env_role("ROLE_ZAM_GLAVY_ZASHITY"),
    "Начальник отдела": env_role("ROLE_NACHALNIK_OTDELA"),
    "Зам начальника отдела": env_role("ROLE_ZAM_NACHALNIKA_OTDELA"),
    "Главный защитник": env_role("ROLE_GLAVNYI_ZASHITNIK"),
    "Ведущий защитник": env_role("ROLE_VEDUSHII_ZASHITNIK"),
    "Старший защитник": env_role("ROLE_STARSHII_ZASHITNIK"),
    "Младший защитник": env_role("ROLE_MLADSHII_ZASHITNIK"),
    "Помощник защиты": env_role("ROLE_POMOSHCHNIK_ZASHITY"),
    "Старший стажер": env_role("ROLE_STARSHII_STAZHER"),
}


SENIOR_STAFF_RANKS = {
    "Зам Начальника Отдела",
    "Начальник Отдела",
    "Зам Главы Защиты",
    "Глава Защиты",
    "Зам начальника отдела",
    "Начальник отдела",
    "Зам главы защиты",
}


SPECIAL_ROLES = {
    "Старший Состав": env_role("ROLE_STARSHII_SOSTAV"),
    "Курсант": env_role("ROLE_KURSANT"),
    "Уволен": env_role("ROLE_UVOLEN"),
}


DEPARTMENT_ROLES = {
    "Отдел Собственной Безопасности": env_role("ROLE_OTDEL_SOBSTVENNOY_BEZOPASNOSTI"),
    "Отдел Элитной Защиты": env_role("ROLE_OTDEL_ELITNOY_ZASHITY"),
    "Отдел Агитации": env_role("ROLE_OTDEL_AGITACII"),
    "Академия": env_role("ROLE_AKADEMIYA"),
    "Гос Служащий": env_role("ROLE_GOS_SLUZHASHCHII"),
}


PUNISH_ROLES = {
    1: env_role("ROLE_VYGOVOR_1"),
    2: env_role("ROLE_VYGOVOR_2"),
    3: env_role("ROLE_VYGOVOR_3"),
}


ALL_RANK_ROLE_IDS = list({r for r in RANK_ROLES.values() if r})
ALL_DEPARTMENT_ROLE_IDS = list({r for r in DEPARTMENT_ROLES.values() if r})
ALL_PUNISH_ROLE_IDS = list({r for r in PUNISH_ROLES.values() if r})


intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)


def normalize(value) -> str:
    return str(value or "").strip()


def clean_text(value) -> str:
    return (
        str(value or "")
        .lower()
        .replace("ё", "е")
        .replace("`", "")
        .replace("|", " ")
        .replace("[", " ")
        .replace("]", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace("_", " ")
        .replace("-", " ")
        .replace(".", " ")
        .replace(",", " ")
        .strip()
    )


def only_digits(value) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def date_now() -> str:
    return datetime.now().strftime("%d.%m.%Y")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))

    return {
        "registry": [],
        "hr": [],
        "punish": [],
    }


def save_state(state: dict):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def row_key(row: dict) -> str:
    return "|".join(normalize(v) for v in row.values())


def get_col(row: dict, *names: str) -> str:
    for name in names:
        if name in row:
            return normalize(row.get(name))
    return ""


def get_google_rows() -> dict:
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

    creds = Credentials.from_service_account_file(
        GOOGLE_CREDS,
        scopes=scopes
    )

    client = gspread.authorize(creds)
    book = client.open_by_key(SPREADSHEET_ID)

    return {
        "registry": book.worksheet(SHEET_REGISTRY).get_all_records(),
        "hr": book.worksheet(SHEET_HR).get_all_records(),
        "punish": book.worksheet(SHEET_PUNISH).get_all_records(),
    }


def get_role(guild: discord.Guild, role_id: int | None):
    if not role_id:
        return None
    return guild.get_role(role_id)


def role_mention(guild: discord.Guild, role_id: int | None, fallback: str) -> str:
    role = get_role(guild, role_id)

    if not role:
        print(f"❌ Роль не найдена для тега: {fallback} | ID: {role_id}")
        return f"`{fallback}`"

    return role.mention


def find_name_in_registry(registry_rows: list[dict], static: str) -> str:
    static_digits = only_digits(static)

    if not static_digits:
        return ""

    for row in registry_rows:
        row_static = get_col(row, "Статик")
        row_static_digits = only_digits(row_static)

        if row_static_digits == static_digits:
            name = get_col(row, "Имя Фамилия", "Ваше имя фамилия", "Ваше Имя Фамилия")
            if name:
                return name

    return ""


async def find_member_by_name(guild: discord.Guild, full_name: str) -> discord.Member | None:
    name_clean = clean_text(full_name)

    if not name_clean:
        return None

    for member in guild.members:
        display = clean_text(member.display_name)
        username = clean_text(member.name)
        global_name = clean_text(member.global_name) if member.global_name else ""

        if name_clean in display:
            print(f"✅ Участник найден по нику сервера: {member.display_name}")
            return member

        if name_clean in username:
            print(f"✅ Участник найден по username: {member.name}")
            return member

        if global_name and name_clean in global_name:
            print(f"✅ Участник найден по global_name: {member.global_name}")
            return member

    print(f"❌ Участник не найден по имени: {full_name}")
    return None


async def find_member_from_registry(
    guild: discord.Guild,
    registry_rows: list[dict],
    static: str = "",
    fallback_name: str = "",
) -> tuple[discord.Member | None, str]:
    name_from_registry = find_name_in_registry(registry_rows, static)
    final_name = name_from_registry or fallback_name

    print(f"🔎 Поиск участника: static='{static}' | name='{final_name}'")

    member = await find_member_by_name(guild, final_name)

    return member, final_name


def member_text(member: discord.Member | None, fallback: str) -> str:
    return member.mention if member else f"`{fallback}`"


async def send_to_hr(embed: discord.Embed):
    channel = bot.get_channel(HR_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)
    else:
        print("❌ Канал кадрового аудита не найден")


async def send_to_punish(embed: discord.Embed):
    channel = bot.get_channel(PUNISH_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)
    else:
        print("❌ Канал аудита взысканий не найден")


async def add_roles(
    member: discord.Member | None,
    guild: discord.Guild,
    role_ids: list[int | None],
):
    if not member:
        print("❌ Роли не выданы: участник не найден")
        return

    bot_member = guild.me
    roles_to_add = []

    print(f"\n=== ВЫДАЧА РОЛЕЙ ДЛЯ {member} ===")
    print(f"Высшая роль бота: {bot_member.top_role.name} | позиция {bot_member.top_role.position}")

    for role_id in role_ids:
        if not role_id:
            print("❌ Пустой ID роли. Проверь .env")
            continue

        role = guild.get_role(role_id)

        if not role:
            print(f"❌ Роль не найдена по ID: {role_id}")
            continue

        print(f"Проверяю роль: {role.name} | ID {role.id} | позиция {role.position}")

        if role in member.roles:
            print(f"ℹ️ У участника уже есть роль: {role.name}")
            continue

        if role >= bot_member.top_role:
            print(f"❌ Нельзя выдать роль {role.name}: она выше или равна роли бота")
            continue

        roles_to_add.append(role)

    if not roles_to_add:
        print("❌ Нет ролей для выдачи")
        return

    try:
        await member.add_roles(*roles_to_add, reason="Автоаудит из Google Sheets")
        print(f"✅ Выданы роли: {', '.join(r.name for r in roles_to_add)}")
    except discord.Forbidden:
        print("❌ Discord запретил выдачу ролей: нет прав или роль бота ниже")
    except discord.HTTPException as e:
        print(f"❌ Discord HTTP ошибка при выдаче ролей: {e}")


async def remove_roles(member: discord.Member | None, role_ids: list[int | None]):
    if not member:
        print("❌ Роли не сняты: участник не найден")
        return

    bot_member = member.guild.me
    ids = [role_id for role_id in role_ids if role_id]
    roles_to_remove = []

    for role in member.roles:
        if role.id in ids:
            if role >= bot_member.top_role:
                print(f"❌ Нельзя снять роль {role.name}: она выше или равна роли бота")
                continue
            roles_to_remove.append(role)

    if not roles_to_remove:
        print("ℹ️ Нет ролей для снятия")
        return

    try:
        await member.remove_roles(*roles_to_remove, reason="Автоаудит из Google Sheets")
        print(f"✅ Сняты роли: {', '.join(r.name for r in roles_to_remove)}")
    except discord.Forbidden:
        print("❌ Discord запретил снятие ролей")
    except discord.HTTPException as e:
        print(f"❌ Discord HTTP ошибка при снятии ролей: {e}")


async def remove_all_staff_roles(member: discord.Member | None):
    if not member:
        return

    ids = (
        ALL_RANK_ROLE_IDS
        + ALL_DEPARTMENT_ROLE_IDS
        + ALL_PUNISH_ROLE_IDS
        + [
            SPECIAL_ROLES["Курсант"],
            SPECIAL_ROLES["Старший Состав"],
        ]
    )

    await remove_roles(member, ids)


async def fire_member(member: discord.Member | None, guild: discord.Guild):
    if not member:
        return

    await remove_all_staff_roles(member)
    await add_roles(member, guild, [SPECIAL_ROLES["Уволен"]])


async def handle_new_registry(row: dict, guild: discord.Guild, registry_rows: list[dict]):
    static = get_col(row, "Статик")
    full_name = get_col(row, "Имя Фамилия", "Ваше имя фамилия", "Ваше Имя Фамилия")
    reason = get_col(row, "Причина")
    rank = get_col(row, "Ранг")

    member, final_name = await find_member_from_registry(
        guild=guild,
        registry_rows=registry_rows,
        static=static,
        fallback_name=full_name,
    )

    rank_tag = role_mention(guild, RANK_ROLES.get(rank), rank)

    embed = discord.Embed(
        title="📥 Новый участник",
        color=0x2ECC71
    )

    embed.add_field(
        name="👤 Сотрудник",
        value=f"{member_text(member, final_name)}\n`{static}`",
        inline=False
    )

    embed.add_field(
        name="📌 Действие",
        value=f"Принят в семью на ранг {rank_tag}",
        inline=False
    )

    embed.add_field(
        name="📝 Причина",
        value=reason if reason else "Не указана",
        inline=False
    )

    embed.set_footer(text=f"Дата: {date_now()}")

    await send_to_hr(embed)

    roles_to_add = [RANK_ROLES.get(rank)]

    if rank in {"Стажер", "Старший Стажер", "Старший стажер"}:
        roles_to_add.append(SPECIAL_ROLES["Курсант"])

    if rank in SENIOR_STAFF_RANKS:
        roles_to_add.append(SPECIAL_ROLES["Старший Состав"])

    await add_roles(member, guild, roles_to_add)


async def handle_fire(row: dict, guild: discord.Guild, registry_rows: list[dict]):
    auditor_static = get_col(row, "Ваш Статик")
    target_static = get_col(row, "Статик Сотрудника", "Статик сотрудника")

    auditor_name_fallback = get_col(row, "Ваше Имя Фамилия", "Ваше имя фамилия")
    target_name_fallback = get_col(row, "Имя Фамилия Сотрудника", "Имя фамилия сотрудника", "Сотрудник")

    auditor, auditor_name = await find_member_from_registry(
        guild, registry_rows, auditor_static, auditor_name_fallback
    )

    target, target_name = await find_member_from_registry(
        guild, registry_rows, target_static, target_name_fallback
    )

    embed = discord.Embed(
        title="📤 Увольнение",
        color=0xE74C3C
    )

    embed.add_field(
        name="👮 Кто оформил",
        value=f"{member_text(auditor, auditor_name)}\n`{auditor_static}`",
        inline=False
    )

    embed.add_field(
        name="👤 Сотрудник",
        value=f"{member_text(target, target_name)}\n`{target_static}`",
        inline=False
    )

    embed.add_field(
        name="📌 Действие",
        value="Уволен из семьи",
        inline=False
    )

    embed.set_footer(text=f"Дата: {date_now()}")

    await send_to_hr(embed)
    await fire_member(target, guild)


async def handle_promotion(row: dict, guild: discord.Guild, registry_rows: list[dict]):
    auditor_static = get_col(row, "Ваш Статик")
    target_static = get_col(row, "Статик Сотрудника", "Статик сотрудника")

    auditor_name_fallback = get_col(row, "Ваше Имя Фамилия", "Ваше имя фамилия")
    target_name_fallback = get_col(row, "Имя Фамилия Сотрудника", "Имя фамилия сотрудника", "Сотрудник")

    old_rank = get_col(row, "С какого ранга", "Старый ранг", "На какой ранг понижаете?")
    new_rank = get_col(row, "На какой ранг повышаете?", "Новый ранг")
    reason = get_col(row, "Причина")

    auditor, auditor_name = await find_member_from_registry(
        guild, registry_rows, auditor_static, auditor_name_fallback
    )

    target, target_name = await find_member_from_registry(
        guild, registry_rows, target_static, target_name_fallback
    )

    new_rank_tag = role_mention(guild, RANK_ROLES.get(new_rank), new_rank)

    action_text = f"Повышен на ранг {new_rank_tag}"

    if old_rank in {"Старший Стажер", "Старший стажер"} and new_rank in {"Помощник Защиты", "Помощник защиты"}:
        action_text += "\nИ был переведен в Отдел Элитной Защиты"

    embed = discord.Embed(
        title="📈 Повышение",
        color=0x3498DB
    )

    embed.add_field(
        name="👮 Кто оформил",
        value=f"{member_text(auditor, auditor_name)}\n`{auditor_static}`",
        inline=False
    )

    embed.add_field(
        name="👤 Сотрудник",
        value=f"{member_text(target, target_name)}\n`{target_static}`",
        inline=False
    )

    embed.add_field(
        name="📌 Действие",
        value=action_text,
        inline=False
    )

    embed.add_field(
        name="📝 Причина",
        value=reason if reason else "Не указана",
        inline=False
    )

    embed.set_footer(text=f"Дата: {date_now()}")

    await send_to_hr(embed)

    await remove_roles(target, [RANK_ROLES.get(old_rank)])
    await add_roles(target, guild, [RANK_ROLES.get(new_rank)])

    if new_rank in SENIOR_STAFF_RANKS:
        await add_roles(target, guild, [SPECIAL_ROLES["Старший Состав"]])

    if old_rank in SENIOR_STAFF_RANKS and new_rank not in SENIOR_STAFF_RANKS:
        await remove_roles(target, [SPECIAL_ROLES["Старший Состав"]])

    if old_rank in {"Старший Стажер", "Старший стажер"} and new_rank in {"Помощник Защиты", "Помощник защиты"}:
        await remove_roles(target, [SPECIAL_ROLES["Курсант"]])
        await add_roles(target, guild, [DEPARTMENT_ROLES["Отдел Элитной Защиты"]])


async def handle_department_transfer(row: dict, guild: discord.Guild, registry_rows: list[dict]):
    auditor_static = get_col(row, "Ваш Статик")
    target_static = get_col(row, "Статик Сотрудника", "Статик сотрудника")

    auditor_name_fallback = get_col(row, "Ваше Имя Фамилия", "Ваше имя фамилия")
    target_name_fallback = get_col(row, "Имя Фамилия Сотрудника", "Имя фамилия сотрудника", "Сотрудник")

    from_dept = get_col(row, "От куда перевод?", "Откуда перевод?", "От куда переведен", "Откуда переведен")
    to_dept = get_col(row, "Куда Перевод?", "Куда перевод?", "Куда переведен")
    reason = get_col(row, "Причина")

    auditor, auditor_name = await find_member_from_registry(
        guild, registry_rows, auditor_static, auditor_name_fallback
    )

    target, target_name = await find_member_from_registry(
        guild, registry_rows, target_static, target_name_fallback
    )

    from_tag = role_mention(guild, DEPARTMENT_ROLES.get(from_dept), from_dept)
    to_tag = role_mention(guild, DEPARTMENT_ROLES.get(to_dept), to_dept)

    embed = discord.Embed(
        title="🔁 Перевод отдела",
        color=0xF1C40F
    )

    embed.add_field(
        name="👮 Кто оформил",
        value=f"{member_text(auditor, auditor_name)}\n`{auditor_static}`",
        inline=False
    )

    embed.add_field(
        name="👤 Сотрудник",
        value=f"{member_text(target, target_name)}\n`{target_static}`",
        inline=False
    )

    embed.add_field(
        name="📌 Действие",
        value=f"Переведен из {from_tag} в {to_tag}",
        inline=False
    )

    embed.add_field(
        name="📝 Причина",
        value=reason if reason else "Не указана",
        inline=False
    )

    embed.set_footer(text=f"Дата: {date_now()}")

    await send_to_hr(embed)

    await remove_roles(target, [DEPARTMENT_ROLES.get(from_dept)])
    await add_roles(target, guild, [DEPARTMENT_ROLES.get(to_dept)])


async def handle_punishment(row: dict, guild: discord.Guild, registry_rows: list[dict]):
    auditor_static = get_col(row, "Ваш Статик")
    target_static = get_col(row, "Статик Сотрудника", "Статик сотрудника")

    auditor_name_fallback = get_col(row, "Ваше Имя Фамилия", "Ваше имя фамилия")
    target_name_fallback = get_col(row, "Имя Фамилия Сотрудника", "Имя фамилия сотрудника", "Сотрудник")

    reason = get_col(row, "Причина")

    auditor, auditor_name = await find_member_from_registry(
        guild, registry_rows, auditor_static, auditor_name_fallback
    )

    target, target_name = await find_member_from_registry(
        guild, registry_rows, target_static, target_name_fallback
    )

    current_warn = 0

    if target:
        target_role_ids = [role.id for role in target.roles]

        if PUNISH_ROLES[1] in target_role_ids:
            current_warn = 1
        elif PUNISH_ROLES[2] in target_role_ids:
            current_warn = 2
        elif PUNISH_ROLES[3] in target_role_ids:
            current_warn = 3

    next_warn = min(current_warn + 1, 3)

    old_warn_role = PUNISH_ROLES.get(current_warn)
    new_warn_role = PUNISH_ROLES.get(next_warn)
    warn_tag = role_mention(guild, new_warn_role, f"Выговор {next_warn}/3")

    embed = discord.Embed(
        title="⚠️ Взыскание",
        color=0xE67E22
    )

    embed.add_field(
        name="👮 Кто оформил",
        value=f"{member_text(auditor, auditor_name)}\n`{auditor_static}`",
        inline=False
    )

    embed.add_field(
        name="👤 Сотрудник",
        value=f"{member_text(target, target_name)}\n`{target_static}`",
        inline=False
    )

    embed.add_field(
        name="📌 Действие",
        value=f"Получили {warn_tag}",
        inline=False
    )

    embed.add_field(
        name="📝 Причина",
        value=reason if reason else "Не указана",
        inline=False
    )

    embed.set_footer(text=f"Дата: {date_now()}")

    await send_to_punish(embed)

    if old_warn_role:
        await remove_roles(target, [old_warn_role])

    await add_roles(target, guild, [new_warn_role])

    if next_warn >= 3:
        fire_embed = discord.Embed(
            title="📤 Увольнение",
            color=0xE74C3C
        )

        fire_embed.add_field(
            name="👮 Кто оформил",
            value=f"{member_text(auditor, auditor_name)}\n`{auditor_static}`",
            inline=False
        )

        fire_embed.add_field(
            name="👤 Сотрудник",
            value=f"{member_text(target, target_name)}\n`{target_static}`",
            inline=False
        )

        fire_embed.add_field(
            name="📌 Действие",
            value="Уволен из семьи",
            inline=False
        )

        fire_embed.set_footer(text=f"Дата: {date_now()}")

        await send_to_hr(fire_embed)
        await fire_member(target, guild)


async def handle_hr_row(row: dict, guild: discord.Guild, registry_rows: list[dict]):
    action = get_col(row, "Действие").lower()

    if "уволь" in action:
        await handle_fire(row, guild, registry_rows)
        return

    if "повыш" in action:
        await handle_promotion(row, guild, registry_rows)
        return

    if "перевод" in action or "переведен" in action or "переведён" in action:
        await handle_department_transfer(row, guild, registry_rows)
        return

    print(f"❌ Неизвестное действие в кадровом аудите: {action}")


@tasks.loop(seconds=CHECK_EVERY_SECONDS)
async def check_sheets():
    guild = bot.get_guild(GUILD_ID)

    if not guild:
        print("❌ Сервер не найден. Проверь GUILD_ID")
        return

    state = load_state()

    try:
        rows = get_google_rows()
    except Exception as e:
        print(f"❌ Ошибка Google Sheets: {e}")
        return

    registry_rows = rows["registry"]

    current_registry_keys = []
    current_hr_keys = []
    current_punish_keys = []

    for row in rows["registry"]:
        key = row_key(row)
        current_registry_keys.append(key)

        if key not in state["registry"]:
            await handle_new_registry(row, guild, registry_rows)

    for row in rows["hr"]:
        key = row_key(row)
        current_hr_keys.append(key)

        if key not in state["hr"]:
            await handle_hr_row(row, guild, registry_rows)

    for row in rows["punish"]:
        key = row_key(row)
        current_punish_keys.append(key)

        if key not in state["punish"]:
            await handle_punishment(row, guild, registry_rows)

    state["registry"] = current_registry_keys
    state["hr"] = current_hr_keys
    state["punish"] = current_punish_keys

    save_state(state)


@check_sheets.before_loop
async def before_check_sheets():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    print(f"✅ Бот запущен как {bot.user}")

    guild = bot.get_guild(GUILD_ID)

    if guild:
        print(f"✅ Сервер найден: {guild.name}")
        print(f"✅ Высшая роль бота: {guild.me.top_role.name}")

    if not check_sheets.is_running():
        check_sheets.start()


bot.run(DISCORD_TOKEN)