import re
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ConversationHandler,
)
from config import (
    TELEGRAM_BOT_TOKEN,
    CHOOSING_MODE, WAITING_FOR_RESUME_ATS, WAITING_FOR_JD,
    WAITING_FOR_RESUME_IMP, ASKING_TO_CHAT, IN_CHAT_MODE,
    logger,
)
from bot_handlers import (
    start_conversation, start_command, cancel, end_chat,
    choose_mode,
    handle_resume_ats, handle_jd,
    handle_resume_improve, handle_ask_to_chat, handle_chat,
)


def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(re.compile(r'(?i)hi drcode')), start_conversation),
            CommandHandler("start", start_command),
        ],
        states={
            # ── Mode selection ─────────────────────────────────────────────
            CHOOSING_MODE: [
                CallbackQueryHandler(choose_mode, pattern="^mode_"),
            ],

            # ── ATS Analysis ───────────────────────────────────────────────
            WAITING_FOR_RESUME_ATS: [
                MessageHandler(filters.Document.ALL, handle_resume_ats),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~filters.Regex(re.compile(r'(?i)cancel')),
                    handle_resume_ats
                ),
            ],
            WAITING_FOR_JD: [
                MessageHandler(filters.Document.ALL, handle_jd),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~filters.Regex(re.compile(r'(?i)cancel')),
                    handle_jd
                ),
            ],

            # ── Resume Improvement ─────────────────────────────────────────
            WAITING_FOR_RESUME_IMP: [
                MessageHandler(filters.Document.ALL, handle_resume_improve),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~filters.Regex(re.compile(r'(?i)cancel')),
                    handle_resume_improve
                ),
            ],

            # ── After improvement: offer career coach chat ─────────────────
            ASKING_TO_CHAT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_ask_to_chat
                ),
            ],

            # ── Career Coach Conversation Mode ─────────────────────────────
            IN_CHAT_MODE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_chat
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("end", end_chat),
            MessageHandler(filters.Regex(re.compile(r'(?i)^cancel$')), cancel),
        ],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)

    logger.info("🤖 DrCode HireAi bot is starting...")
    application.run_polling()


if __name__ == "__main__":
    main()
