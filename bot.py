import os
import sqlite3
from datetime import datetime, timedelta

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")

DB_FILE = "visitation.db"

NAME, CATEGORY, DATE, PUROK, NOTES = range(5)

CATEGORIES = ["Tatay", "Nanay", "Anak", "IND"]
PUROK_GROUPS = ["2-1", "2-2", "2-3"]


# ---------------- DATABASE ----------------

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            date_visited TEXT NOT NULL,
            purok_grupo TEXT NOT NULL,
            notes TEXT
        )
    """)

    conn.commit()
    conn.close()


def add_visit(name, category, date_visited, purok, notes):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO visits
        (name, category, date_visited, purok_grupo, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (name, category, date_visited, purok, notes))

    conn.commit()
    conn.close()


def get_all_visits():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, category, date_visited, purok_grupo, notes
        FROM visits
        ORDER BY date_visited DESC, id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return rows


def get_week_visits():
    today = datetime.now().date()
    start = today - timedelta(days=today.weekday())

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, category, date_visited, purok_grupo, notes
        FROM visits
        WHERE date_visited BETWEEN ? AND ?
        ORDER BY date_visited ASC
    """, (start.isoformat(), today.isoformat()))

    rows = cursor.fetchall()
    conn.close()

    return rows


# ---------------- START ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["/add", "/records"],
        ["/week"],
    ]

    await update.message.reply_text(
        "👋 Welcome sa Visitation Record Bot!\n\n"
        "Gamitin ang mga commands:\n"
        "/add — Magdagdag ng visitation record\n"
        "/records — Tingnan lahat ng records\n"
        "/week — Tingnan ang Visited of the Week",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
    )


# ---------------- ADD RECORD ----------------

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 Magdagdag tayo ng visitation record.\n\n"
        "Ilagay ang **Name**:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()

    keyboard = [[x] for x in CATEGORIES]

    await update.message.reply_text(
        "Piliin ang **Category**:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

    return CATEGORY


async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text.strip()

    if category not in CATEGORIES:
        await update.message.reply_text(
            "Piliin lamang ang: Tatay, Nanay, Anak, o IND."
        )
        return CATEGORY

    context.user_data["category"] = category

    await update.message.reply_text(
        "📅 Ilagay ang **Date Visited**.\n\n"
        "Format: YYYY-MM-DD\n"
        "Halimbawa: 2026-08-17",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

    return DATE


async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_text = update.message.text.strip()

    try:
        datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text(
            "❌ Mali ang format.\n"
            "Gamitin: YYYY-MM-DD\n"
            "Halimbawa: 2026-08-17"
        )
        return DATE

    context.user_data["date"] = date_text

    keyboard = [[x] for x in PUROK_GROUPS]

    await update.message.reply_text(
        "📍 Piliin ang **Purok-Grupo**:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

    return PUROK


async def get_purok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    purok = update.message.text.strip()

    if purok not in PUROK_GROUPS:
        await update.message.reply_text(
            "Piliin lamang ang 2-1, 2-2, o 2-3."
        )
        return PUROK

    context.user_data["purok"] = purok

    await update.message.reply_text(
        "📌 Ilagay ang **Notes**.\n\n"
        "Kung walang notes, i-type ang `None`.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

    return NOTES


async def get_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    notes = update.message.text.strip()

    if notes.lower() == "none":
        notes = ""

    context.user_data["notes"] = notes

    add_visit(
        context.user_data["name"],
        context.user_data["category"],
        context.user_data["date"],
        context.user_data["purok"],
        context.user_data["notes"]
    )

    await update.message.reply_text(
        "✅ **Visitation record saved!**\n\n"
        f"👤 Name: {context.user_data['name']}\n"
        f"📂 Category: {context.user_data['category']}\n"
        f"📅 Date: {context.user_data['date']}\n"
        f"📍 Purok-Grupo: {context.user_data['purok']}\n"
        f"📝 Notes: {context.user_data['notes'] or 'None'}",
        parse_mode="Markdown"
    )

    context.user_data.clear()

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "❌ Pagdaragdag ng record ay kinansela."
    )

    return ConversationHandler.END


# ---------------- RECORDS ----------------

async def records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_all_visits()

    if not rows:
        await update.message.reply_text(
            "📂 Wala pang visitation records."
        )
        return

    text = "📋 **VISITATION RECORDS**\n\n"

    for row in rows:
        record_id, name, category, date, purok, notes = row

        text += (
            f"#{record_id}\n"
            f"👤 {name}\n"
            f"📂 {category}\n"
            f"📅 {date}\n"
            f"📍 {purok}\n"
            f"📝 {notes or 'None'}\n"
            "──────────────\n"
        )

    # Telegram message limit protection
    chunks = []

    while len(text) > 4000:
        split_at = text.rfind("\n", 0, 4000)

        if split_at == -1:
            split_at = 4000

        chunks.append(text[:split_at])
        text = text[split_at:]

    chunks.append(text)

    for chunk in chunks:
        await update.message.reply_text(
            chunk,
            parse_mode="Markdown"
        )


# ---------------- WEEK ----------------

async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_week_visits()

    if not rows:
        await update.message.reply_text(
            "📅 Wala pang visitation record ngayong linggo."
        )
        return

    today = datetime.now().date()
    start = today - timedelta(days=today.weekday())

    text = (
        "🏆 **VISITED OF THE WEEK**\n\n"
        f"Week: {start.isoformat()} hanggang {today.isoformat()}\n\n"
    )

    for row in rows:
        record_id, name, category, date, purok, notes = row

        text += (
            f"👤 **{name}**\n"
            f"📂 {category}\n"
            f"📅 {date}\n"
            f"📍 {purok}\n"
            f"📝 {notes or 'None'}\n"
            "──────────────\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ---------------- MAIN ----------------

def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    init_db()

    app = Application.builder().token(TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_start)
        ],

        states={
            NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_name
                )
            ],

            CATEGORY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_category
                )
            ],

            DATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_date
                )
            ],

            PUROK: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_purok
                )
            ],

            NOTES: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_notes
                )
            ],
        },

        fallbacks=[
            CommandHandler("cancel", cancel)
        ],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("records", records))
    app.add_handler(CommandHandler("week", week))

    app.add_handler(conversation)

    print("Visitation Bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
