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

(
    VISIT_TYPE,
    FAMILY_NAME,
    FATHER,
    MOTHER,
    CHILDREN,
    IND_NAME,
    DATE,
    PUROK,
    NOTES,
) = range(9)


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
# CANCEL KEYBOARD
# ============================================================

CANCEL_KEYBOARD = [
    ["❌ CANCEL"]
]


def cancel_keyboard():
    return ReplyKeyboardMarkup(
        CANCEL_KEYBOARD,
        resize_keyboard=True,
        one_time_keyboard=False,
    )


# ============================================================
# RENDER HEALTH SERVER
# ============================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/plain"
        )
        self.end_headers()

        self.wfile.write(
            b"Visitation Bot is running!"
        )

    def log_message(self, format, *args):
        return


def run_web_server():

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
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


# ============================================================
# ISO WEEK
# ============================================================

def get_week_dates(year, week_number):

    try:

        start = datetime.strptime(
            f"{year}-W{week_number:02d}-1",
            "%G-W%V-%u"
        ).date()

        end = start + timedelta(
            days=6
        )

        return start, end

    except ValueError:

        return None, None


def get_week_visits(
    year,
    week_number
):

    start, end = get_week_dates(
        year,
        week_number
    )

    if not start:

        return [], None, None

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

    return rows, start, end


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
        "/week — Current week\n"
        "/week 01 — Specific week\n"
        "/week 34 2026 — Specific week + year\n"
        "/cancel — Kanselahin ang entry",

        parse_mode="Markdown",

        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )


# ============================================================
# ADD
# ============================================================

async def add_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data.clear()

    keyboard = [
        ["🏠 FAMILY"],
        ["👤 INDIVIDUAL"],
        ["❌ CANCEL"],
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


# ============================================================
# VISIT TYPE
# ============================================================

async def get_visit_type(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    choice = update.message.text.strip()

    if choice == "❌ CANCEL":

        return await cancel(
            update,
            context
        )

    if choice == "🏠 FAMILY":

        context.user_data["visit_type"] = "FAMILY"

        await update.message.reply_text(

            "🏠 **FAMILY VISITATION**\n\n"

            "Ilagay ang **Family / Household Name**.\n\n"

            "Halimbawa:\n"
            "Dela Cruz Family",

            parse_mode="Markdown",

            reply_markup=cancel_keyboard(),
        )

        return FAMILY_NAME

    if choice == "👤 INDIVIDUAL":

        context.user_data["visit_type"] = "INDIVIDUAL"

        await update.message.reply_text(

            "👤 **INDIVIDUAL VISITATION**\n\n"

            "Ilagay ang pangalan:",

            parse_mode="Markdown",

            reply_markup=cancel_keyboard(),
        )

        return IND_NAME

    await update.message.reply_text(
        "❌ Piliin ang FAMILY o INDIVIDUAL."
    )

    return VISIT_TYPE


# ============================================================
# FAMILY NAME
# ============================================================

async def get_family_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    text = update.message.text.strip()

    if text == "❌ CANCEL":

        return await cancel(
            update,
            context
        )

    if not text:

        await update.message.reply_text(
            "❌ Pakilagay ang Family / Household Name.",
            reply_markup=cancel_keyboard()
        )

        return FAMILY_NAME

    context.user_data["family_name"] = text

    await update.message.reply_text(

        "👨 **TATAY**\n\n"

        "Ilagay ang pangalan ng tatay.\n"
        "Kung wala, i-type ang `None`.",

        parse_mode="Markdown",

        reply_markup=cancel_keyboard(),
    )

    return FATHER


# ============================================================
# FATHER
# ============================================================

async def get_father(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    father = update.message.text.strip()

    if father == "❌ CANCEL":

        return await cancel(
            update,
            context
        )

    if father.lower() == "none":

        father = ""

    context.user_data["father"] = father

    await update.message.reply_text(

        "👩 **NANAY**\n\n"

        "Ilagay ang pangalan ng nanay.\n"
        "Kung wala, i-type ang `None`.",

        parse_mode="Markdown",

        reply_markup=cancel_keyboard(),
    )

    return MOTHER


# ============================================================
# MOTHER
# ============================================================

async def get_mother(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    mother = update.message.text.strip()

    if mother == "❌ CANCEL":

        return await cancel(
            update,
            context
        )

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

        reply_markup=cancel_keyboard(),
    )

    return CHILDREN


# ============================================================
# CHILDREN
# ============================================================

async def get_children(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    children = update.message.text.strip()

    if children == "❌ CANCEL":

        return await cancel(
            update,
            context
        )

    if children.lower() == "none":

        children = ""

    context.user_data["children"] = children

    await update.message.reply_text(

        "📅 **DATE VISITED**\n\n"

        "Format: YYYY-MM-DD\n\n"

        "Halimbawa:\n"
        "2026-08-19",

        parse_mode="Markdown",

        reply_markup=cancel_keyboard(),
    )

    return DATE


# ============================================================
# INDIVIDUAL NAME
# ============================================================

async def get_individual_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    name = update.message.text.strip()

    if name == "❌ CANCEL":

        return await cancel(
            update,
            context
        )

    if not name:

        await update.message.reply_text(
            "❌ Pakilagay ang pangalan.",
            reply_markup=cancel_keyboard()
        )

        return IND_NAME

    context.user_data["individual_name"] = name

    await update.message.reply_text(

        "📅 **DATE VISITED**\n\n"

        "Format: YYYY-MM-DD\n\n"

        "Halimbawa:\n"
        "2026-08-19",

        parse_mode="Markdown",

        reply_markup=cancel_keyboard(),
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

    if date_text == "❌ CANCEL":

        return await cancel(
            update,
            context
        )

    try:

        datetime.strptime(
            date_text,
            "%Y-%m-%d"
        )

    except ValueError:

        await update.message.reply_text(

            "❌ Mali ang date format.\n\n"

            "Gamitin:\n"
            "YYYY-MM-DD\n\n"

            "Halimbawa:\n"
            "2026-08-19",

            reply_markup=cancel_keyboard()
        )

        return DATE

    context.user_data["date"] = date_text

    keyboard = [
        ["2-1"],
        ["2-2"],
        ["2-3"],
        ["❌ CANCEL"],
    ]

    await update.message.reply_text(

        "📍 **PILIIN ANG PUROK-GRUPO:**",

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

    if purok == "❌ CANCEL":

        return await cancel(
            update,
            context
        )

    if purok not in PUROK_GROUPS:

        await update.message.reply_text(

            "❌ Piliin lamang ang:\n"
            "2-1\n"
            "2-2\n"
            "2-3",

            reply_markup=cancel_keyboard()
        )

        return PUROK

    context.user_data["purok"] = purok

    await update.message.reply_text(

        "📌 **NOTES**\n\n"

        "Ilagay ang notes.\n\n"

        "Kung walang notes, i-type ang `None`.",

        parse_mode="Markdown",

        reply_markup=cancel_keyboard(),
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

    if notes == "❌ CANCEL":

        return await cancel(
            update,
            context
        )

    if notes.lower() == "none":

        notes = ""

    context.user_data["notes"] = notes

    visit_type = context.user_data["visit_type"]

    # --------------------------------------------------------
    # FAMILY
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

        text = (

            "✅ **FAMILY VISITATION SAVED!**\n\n"

            f"🏠 **{context.user_data['family_name']}**\n\n"

            f"👨 Tatay: "
            f"{context.user_data['father'] or 'None'}\n"

            f"👩 Nanay: "
            f"{context.user_data['mother'] or 'None'}\n"

            f"👦 Mga Anak: "
            f"{context.user_data['children'] or 'None'}\n\n"

            f"📅 Date: "
            f"{context.user_data['date']}\n"

            f"📍 Purok-Grupo: "
            f"{context.user_data['purok']}\n"

            f"📝 Notes: "
            f"{context.user_data['notes'] or 'None'}"
        )

    # --------------------------------------------------------
    # INDIVIDUAL
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

            f"👤 **"
            f"{context.user_data['individual_name']}"
            f"**\n\n"

            f"📅 Date: "
            f"{context.user_data['date']}\n"

            f"📍 Purok-Grupo: "
            f"{context.user_data['purok']}\n"

            f"📝 Notes: "
            f"{context.user_data['notes'] or 'None'}"
        )

    context.user_data.clear()

    await update.message.reply_text(

        text,

        parse_mode="Markdown",

        reply_markup=ReplyKeyboardRemove(),
    )

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

        "❌ **VISITATION CANCELLED**\n\n"
        "Walang record na na-save.",

        parse_mode="Markdown",

        reply_markup=ReplyKeyboardRemove(),
    )

    return ConversationHandler.END


# ============================================================
# FORMAT RECORD
# ============================================================

def format_record(
    row,
    show_week=True
):

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

    visit_date = datetime.strptime(
        date,
        "%Y-%m-%d"
    ).date()

    iso_year, iso_week, _ = (
        visit_date.isocalendar()
    )

    week_text = ""

    if show_week:

        week_text = (
            f"🔢 Year: {iso_year} | "
            f"Week: {iso_week:02d}\n"
        )

    if visit_type == "FAMILY":

        return (

            f"#{record_id}\n"

            f"🏠 **{household_name}**\n\n"

            f"👨 Tatay: "
            f"{father or 'None'}\n"

            f"👩 Nanay: "
            f"{mother or 'None'}\n"

            f"👦 Mga Anak: "
            f"{children or 'None'}\n\n"

            f"📅 {date}\n"

            f"{week_text}"

            f"📍 {purok}\n"

            f"📝 {notes or 'None'}\n"

            "──────────────\n"
        )

    return (

        f"#{record_id}\n"

        f"👤 **{individual_name}**\n"

        f"📅 {date}\n"

        f"{week_text}"

        f"📍 {purok}\n"

        f"📝 {notes or 'None'}\n"

        "──────────────\n"
    )


# ============================================================
# RECORDS
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

        text += format_record(
            row,
            show_week=True
        )

    chunks = []

    while len(text) > 4000:

        split_at = text.rfind(
            "\n",
            0,
            4000
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
            parse_mode="Markdown"
        )


# ============================================================
# WEEK
# ============================================================

async def week(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    today = datetime.now().date()

    current_year, current_week, _ = (
        today.isocalendar()
    )

    # --------------------------------------------------------
    # /week
    # --------------------------------------------------------

    if not context.args:

        year = current_year
        week_number = current_week

    # --------------------------------------------------------
    # /week 34
    # --------------------------------------------------------

    elif len(context.args) == 1:

        try:

            week_number = int(
                context.args[0]
            )

        except ValueError:

            await update.message.reply_text(

                "❌ Mali ang week number.\n\n"

                "Halimbawa:\n"
                "/week 01\n"
                "/week 34\n"
                "/week 53"
            )

            return

        year = current_year

    # --------------------------------------------------------
    # /week 34 2026
    # --------------------------------------------------------

    elif len(context.args) == 2:

        try:

            week_number = int(
                context.args[0]
            )

            year = int(
                context.args[1]
            )

        except ValueError:

            await update.message.reply_text(

                "❌ Mali ang format.\n\n"

                "Gamitin:\n"
                "/week 34 2026"
            )

            return

    else:

        await update.message.reply_text(

            "❌ Mali ang format.\n\n"

            "Gamitin:\n\n"

            "/week\n"
            "/week 01\n"
            "/week 34\n"
            "/week 34 2026"
        )

        return

    # --------------------------------------------------------
    # VALIDATE
    # --------------------------------------------------------

    start, end = get_week_dates(
        year,
        week_number
    )

    if not start:

        await update.message.reply_text(

            f"❌ Week {week_number:02d} "
            f"ay hindi valid para sa {year}."
        )

        return

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    rows, start, end = get_week_visits(
        year,
        week_number
    )

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    text = (

        "🏆 **VISITED OF THE WEEK**\n\n"

        f"📅 **YEAR: {year}**\n"

        f"🔢 **WEEK: {week_number:02d}**\n"

        f"📆 {start.strftime('%B %d, %Y')}"
        f" – {end.strftime('%B %d, %Y')}\n\n"
    )

    # --------------------------------------------------------
    # EMPTY
    # --------------------------------------------------------

    if not rows:

        text += (
            "📂 Wala pang visitation "
            f"record sa Week {week_number:02d}."
        )

        await update.message.reply_text(

            text,

            parse_mode="Markdown"
        )

        return

    # --------------------------------------------------------
    # RECORDS
    # --------------------------------------------------------

    for row in rows:

        text += format_record(
            row,
            show_week=False
        )

    # --------------------------------------------------------
    # SEND
    # --------------------------------------------------------

    chunks = []

    while len(text) > 4000:

        split_at = text.rfind(
            "\n",
            0,
            4000
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
            parse_mode="Markdown"
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
        daemon=True
    ).start()

    # Telegram application

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    # Conversation

    conversation = ConversationHandler(

        entry_points=[
            CommandHandler(
                "add",
                add_start
            )
        ],

        states={

            VISIT_TYPE: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    get_visit_type
                )
            ],

            FAMILY_NAME: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    get_family_name
                )
            ],

            FATHER: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    get_father
                )
            ],

            MOTHER: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    get_mother
                )
            ],

            CHILDREN: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    get_children
                )
            ],

            IND_NAME: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    get_individual_name
                )
            ],

            DATE: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    get_date
                )
            ],

            PUROK: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    get_purok
                )
            ],

            NOTES: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    get_notes
                )
            ],
        },

        fallbacks=[
            CommandHandler(
                "cancel",
                cancel
            )
        ],
    )

    # Commands

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "records",
            records
        )
    )

    app.add_handler(
        CommandHandler(
            "week",
            week
        )
    )

    app.add_handler(
        conversation
    )

    print(
        "Visitation Bot is running..."
    )

    app.run_polling()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
