import os
import sqlite3
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ============================================================
# CONFIGURATION
# ============================================================

TOKEN = os.getenv("BOT_TOKEN")
DB_FILE = "visitation.db"

# Conversation states
VISIT_TYPE, FAMILY_NAME, FATHER, MOTHER, CHILDREN = range(5)
IND_NAME, DATE, PUROK, NOTES = range(5, 9)

VISIT_TYPES = [
    "🏠 FAMILY",
    "👤 INDIVIDUAL",
]

PUROK_GROUPS = [
    "2-1",
    "2-2",
    "2-3",
]


# ============================================================
# RENDER HEALTH SERVER
# ============================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(
            b"Visitation Bot is running!"
        )

    def log_message(self, format, *args):
        return


def run_web_server():
    port = int(
        os.environ.get("PORT", 10000)
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler,
    )

    server.serve_forever()


# ============================================================
# DATABASE
# ============================================================

def init_db():

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visit_type TEXT NOT NULL,
            household_name TEXT,
            individual_name TEXT,
            father TEXT,
            mother TEXT,
            children TEXT,
            date_visited TEXT NOT NULL,
            purok_grupo TEXT NOT NULL,
            notes TEXT
        )
    """)

    conn.commit()
    conn.close()


def add_family_visit(
    family_name,
    father,
    mother,
    children,
    date_visited,
    purok,
    notes,
):

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO visits (
            visit_type,
            household_name,
            individual_name,
            father,
            mother,
            children,
            date_visited,
            purok_grupo,
            notes
        )
        VALUES (
            'FAMILY',
            ?,
            NULL,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )
    """, (
        family_name,
        father,
        mother,
        children,
        date_visited,
        purok,
        notes,
    ))

    conn.commit()
    conn.close()


def add_individual_visit(
    name,
    date_visited,
    purok,
    notes,
):

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO visits (
            visit_type,
            household_name,
            individual_name,
            father,
            mother,
            children,
            date_visited,
            purok_grupo,
            notes
        )
        VALUES (
            'INDIVIDUAL',
            NULL,
            ?,
            NULL,
            NULL,
            NULL,
            ?,
            ?,
            ?
        )
    """, (
        name,
        date_visited,
        purok,
        notes,
    ))

    conn.commit()
    conn.close()


def get_all_visits():

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            visit_type,
            household_name,
            individual_name,
            father,
            mother,
            children,
            date_visited,
            purok_grupo,
            notes
        FROM visits
        ORDER BY date_visited DESC, id DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


def get_week_visits():

    today = datetime.now().date()

    iso_year, iso_week, iso_weekday = (
        today.isocalendar()
    )

    start = today - timedelta(
        days=iso_weekday - 1
    )

    end = start + timedelta(days=6)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            visit_type,
            household_name,
            individual_name,
            father,
            mother,
            children,
            date_visited,
            purok_grupo,
            notes
        FROM visits
        WHERE date_visited BETWEEN ? AND ?
        ORDER BY date_visited ASC, id ASC
    """, (
        start.isoformat(),
        end.isoformat(),
    ))

    rows = cursor.fetchall()

    conn.close()

    return (
        rows,
        iso_year,
        iso_week,
        start,
        end,
    )


# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    keyboard = [
        ["/add", "/records"],
        ["/week"],
    ]

    await update.message.reply_text(

        "👋 **WELCOME SA VISITATION RECORD BOT!**\n\n"

        "Commands:\n\n"

        "/add — Magdagdag ng visitation\n"
        "/records — Tingnan lahat ng records\n"
        "/week — Visited of the Week\n"
        "/cancel — Kanselahin ang kasalukuyang entry",

        parse_mode="Markdown",

        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )


# ============================================================
# ADD — CHOOSE TYPE
# ============================================================

async def add_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data.clear()

    keyboard = [
        ["🏠 FAMILY"],
        ["👤 INDIVIDUAL"],
    ]

    await update.message.reply_text(

        "📝 **Anong klaseng visitation?**\n\n"

        "🏠 **FAMILY** — buong household/pamilya\n"
        "👤 **INDIVIDUAL** — isang tao lamang",

        parse_mode="Markdown",

        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return VISIT_TYPE


async def get_visit_type(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    visit_type = update.message.text.strip()

    if visit_type == "🏠 FAMILY":

        context.user_data["visit_type"] = "FAMILY"

        await update.message.reply_text(

            "🏠 **FAMILY VISITATION**\n\n"
            "Ilagay ang **Family / Household Name**.\n\n"
            "Halimbawa: Dela Cruz Family",

            parse_mode="Markdown",
        )

        return FAMILY_NAME

    if visit_type == "👤 INDIVIDUAL":

        context.user_data["visit_type"] = "INDIVIDUAL"

        await update.message.reply_text(

            "👤 **INDIVIDUAL VISITATION**\n\n"
            "Ilagay ang pangalan:",

            parse_mode="Markdown",
        )

        return IND_NAME

    await update.message.reply_text(
        "❌ Piliin lamang ang FAMILY o INDIVIDUAL."
    )

    return VISIT_TYPE


# ============================================================
# FAMILY
# ============================================================

async def get_family_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    family_name = update.message.text.strip()

    if not family_name:

        await update.message.reply_text(
            "❌ Pakilagay ang Family / Household Name."
        )

        return FAMILY_NAME

    context.user_data["family_name"] = family_name

    await update.message.reply_text(

        "👨 **TATAY**\n\n"
        "Ilagay ang pangalan ng tatay.\n"
        "Kung wala, i-type ang `None`.",

        parse_mode="Markdown",
    )

    return FATHER


async def get_father(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    father = update.message.text.strip()

    if father.lower() == "none":
        father = ""

    context.user_data["father"] = father

    await update.message.reply_text(

        "👩 **NANAY**\n\n"
        "Ilagay ang pangalan ng nanay.\n"
        "Kung wala, i-type ang `None`.",

        parse_mode="Markdown",
    )

    return MOTHER


async def get_mother(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    mother = update.message.text.strip()

    if mother.lower() == "none":
        mother = ""

    context.user_data["mother"] = mother

    await update.message.reply_text(

        "👦 **MGA ANAK**\n\n"
        "Ilagay ang mga anak.\n\n"
        "Kung maraming anak, paghiwalayin gamit ang comma.\n\n"
        "Halimbawa:\n"
        "Judas Dela Cruz, Marcos Dela Cruz\n\n"
        "Kung walang anak, i-type ang `None`.",

        parse_mode="Markdown",
    )

    return CHILDREN


async def get_children(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    children = update.message.text.strip()

    if children.lower() == "none":
        children = ""

    context.user_data["children"] = children

    await update.message.reply_text(

        "📅 Ilagay ang **Date Visited**.\n\n"
        "Format: YYYY-MM-DD\n"
        "Halimbawa: 2026-08-19",

        parse_mode="Markdown",

        reply_markup=ReplyKeyboardRemove(),
    )

    return DATE


# ============================================================
# INDIVIDUAL
# ============================================================

async def get_individual_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    name = update.message.text.strip()

    if not name:

        await update.message.reply_text(
            "❌ Pakilagay ang pangalan."
        )

        return IND_NAME

    context.user_data["individual_name"] = name

    await update.message.reply_text(

        "📅 Ilagay ang **Date Visited**.\n\n"
        "Format: YYYY-MM-DD\n"
        "Halimbawa: 2026-08-19",

        parse_mode="Markdown",

        reply_markup=ReplyKeyboardRemove(),
    )

    return DATE


# ============================================================
# DATE
# ============================================================

async def get_date(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    date_text = update.message.text.strip()

    try:

        datetime.strptime(
            date_text,
            "%Y-%m-%d",
        )

    except ValueError:

        await update.message.reply_text(

            "❌ Mali ang date format.\n\n"
            "Gamitin:\n"
            "YYYY-MM-DD\n\n"
            "Halimbawa:\n"
            "2026-08-19",
        )

        return DATE

    context.user_data["date"] = date_text

    keyboard = [
        [purok]
        for purok in PUROK_GROUPS
    ]

    await update.message.reply_text(

        "📍 Piliin ang **Purok-Grupo**:",

        parse_mode="Markdown",

        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return PUROK


# ============================================================
# PUROK
# ============================================================

async def get_purok(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    purok = update.message.text.strip()

    if purok not in PUROK_GROUPS:

        await update.message.reply_text(

            "❌ Piliin lamang ang:\n"
            "2-1\n"
            "2-2\n"
            "2-3",
        )

        return PUROK

    context.user_data["purok"] = purok

    await update.message.reply_text(

        "📌 Ilagay ang **Notes**.\n\n"
        "Kung walang notes, i-type ang `None`.",

        parse_mode="Markdown",

        reply_markup=ReplyKeyboardRemove(),
    )

    return NOTES


# ============================================================
# NOTES + SAVE
# ============================================================

async def get_notes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    notes = update.message.text.strip()

    if notes.lower() == "none":
        notes = ""

    context.user_data["notes"] = notes

    visit_type = context.user_data["visit_type"]

    # --------------------------------------------------------
    # SAVE FAMILY
    # --------------------------------------------------------

    if visit_type == "FAMILY":

        add_family_visit(

            context.user_data["family_name"],

            context.user_data["father"],

            context.user_data["mother"],

            context.user_data["children"],

            context.user_data["date"],

            context.user_data["purok"],

            context.user_data["notes"],
        )

        family_name = context.user_data["family_name"]
        father = context.user_data["father"]
        mother = context.user_data["mother"]
        children = context.user_data["children"]

        text = (
            "✅ **FAMILY VISITATION SAVED!**\n\n"

            f"🏠 **{family_name}**\n\n"

            f"👨 Tatay: {father or 'None'}\n"
            f"👩 Nanay: {mother or 'None'}\n"
            f"👦 Mga Anak: {children or 'None'}\n\n"

            f"📅 Date: {context.user_data['date']}\n"
            f"📍 Purok-Grupo: {context.user_data['purok']}\n"
            f"📝 Notes: {context.user_data['notes'] or 'None'}"
        )

    # --------------------------------------------------------
    # SAVE INDIVIDUAL
    # --------------------------------------------------------

    else:

        add_individual_visit(

            context.user_data["individual_name"],

            context.user_data["date"],

            context.user_data["purok"],

            context.user_data["notes"],
        )

        text = (
            "✅ **INDIVIDUAL VISITATION SAVED!**\n\n"

            f"👤 **{context.user_data['individual_name']}**\n\n"

            f"📅 Date: {context.user_data['date']}\n"
            f"📍 Purok-Grupo: {context.user_data['purok']}\n"
            f"📝 Notes: {context.user_data['notes'] or 'None'}"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
    )

    context.user_data.clear()

    return ConversationHandler.END


# ============================================================
# CANCEL
# ============================================================

async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data.clear()

    await update.message.reply_text(

        "❌ Visitation entry cancelled.",

        reply_markup=ReplyKeyboardRemove(),
    )

    return ConversationHandler.END


# ============================================================
# DISPLAY ONE RECORD
# ============================================================

def format_record(row):

    (
        record_id,
        visit_type,
        household_name,
        individual_name,
        father,
        mother,
        children,
        date,
        purok,
        notes,
    ) = row

    if visit_type == "FAMILY":

        return (
            f"#{record_id}\n"
            f"🏠 **{household_name}**\n\n"

            f"👨 Tatay: {father or 'None'}\n"
            f"👩 Nanay: {mother or 'None'}\n"
            f"👦 Mga Anak: {children or 'None'}\n\n"

            f"📅 {date}\n"
            f"📍 {purok}\n"
            f"📝 {notes or 'None'}\n"
            "──────────────\n"
        )

    return (
        f"#{record_id}\n"
        f"👤 **{individual_name}**\n"
        f"📅 {date}\n"
        f"📍 {purok}\n"
        f"📝 {notes or 'None'}\n"
        "──────────────\n"
    )


# ============================================================
# ALL RECORDS
# ============================================================

async def records(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    rows = get_all_visits()

    if not rows:

        await update.message.reply_text(
            "📂 Wala pang visitation records."
        )

        return

    text = (
        "📋 **ALL VISITATION RECORDS**\n\n"
    )

    for row in rows:

        text += format_record(row)

    # Telegram message limit

    chunks = []

    while len(text) > 4000:

        split_at = text.rfind(
            "\n",
            0,
            4000,
        )

        if split_at == -1:
            split_at = 4000

        chunks.append(
            text[:split_at]
        )

        text = text[split_at:]

    chunks.append(text)

    for chunk in chunks:

        await update.message.reply_text(
            chunk,
            parse_mode="Markdown",
        )


# ============================================================
# VISITED OF THE WEEK
# ============================================================

async def week(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    (
        rows,
        iso_year,
        iso_week,
        start,
        end,
    ) = get_week_visits()

    text = (

        "🏆 **VISITED OF THE WEEK**\n\n"

        f"📅 **YEAR: {iso_year}**\n"
        f"🔢 **WEEK: {iso_week}**\n"

        f"📆 {start.strftime('%B %d, %Y')}"
        f" – {end.strftime('%B %d, %Y')}\n\n"
    )

    if not rows:

        text += (
            "📂 Wala pang visitation "
            "record ngayong linggo."
        )

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
        )

        return

    for row in rows:

        text += format_record(row)

    # Telegram message limit

    chunks = []

    while len(text) > 4000:

        split_at = text.rfind(
            "\n",
            0,
            4000,
        )

        if split_at == -1:
            split_at = 4000

        chunks.append(
            text[:split_at]
        )

        text = text[split_at:]

    chunks.append(text)

    for chunk in chunks:

        await update.message.reply_text(
            chunk,
            parse_mode="Markdown",
        )


# ============================================================
# MAIN
# ============================================================

def main():

    if not TOKEN:

        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    init_db()

    # Render health server

    threading.Thread(
        target=run_web_server,
        daemon=True,
    ).start()

    # Telegram application

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    # --------------------------------------------------------
    # CONVERSATION
    # --------------------------------------------------------

    conversation = ConversationHandler(

        entry_points=[
            CommandHandler(
                "add",
                add_start,
            )
        ],

        states={

            VISIT_TYPE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_visit_type,
                )
            ],

            FAMILY_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_family_name,
                )
            ],

            FATHER: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_father,
                )
            ],

            MOTHER: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_mother,
                )
            ],

            CHILDREN: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_children,
                )
            ],

            IND_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_individual_name,
                )
            ],

            DATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_date,
                )
            ],

            PUROK: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_purok,
                )
            ],

            NOTES: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_notes,
                )
            ],
        },

        fallbacks=[
            CommandHandler(
                "cancel",
                cancel,
            )
        ],
    )

    # --------------------------------------------------------
    # COMMANDS
    # --------------------------------------------------------

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        CommandHandler(
            "records",
            records,
        )
    )

    app.add_handler(
        CommandHandler(
            "week",
            week,
        )
    )

    app.add_handler(
        conversation
    )

    # --------------------------------------------------------
    # START BOT
    # --------------------------------------------------------

    print(
        "Visitation Bot is running..."
    )

    app.run_polling()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
