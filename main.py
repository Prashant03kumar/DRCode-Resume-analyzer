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
    handle_signoff, handle_unknown_outside,
    choose_mode, handle_random_in_mode_select,
    handle_resume_ats, handle_jd,
    handle_resume_improve, handle_ask_to_chat, handle_chat,
)

SIGNOFF_FILTER = filters.Regex(re.compile(r'(?i)^signoff$'))
HI_DRCODE_FILTER = filters.Regex(re.compile(r'(?i)hi drcode'))


def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(HI_DRCODE_FILTER, start_conversation),
            CommandHandler("start", start_command),
        ],
        states={
            # ── Mode selection ─────────────────────────────────────────────
            CHOOSING_MODE: [
                CallbackQueryHandler(choose_mode, pattern="^mode_"),
                MessageHandler(SIGNOFF_FILTER, handle_signoff),
                MessageHandler(HI_DRCODE_FILTER, start_conversation),
                # Random text or file while waiting for button press
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_random_in_mode_select),
                MessageHandler(filters.Document.ALL, handle_random_in_mode_select),
            ],

            # ── ATS Analysis ───────────────────────────────────────────────
            WAITING_FOR_RESUME_ATS: [
                MessageHandler(SIGNOFF_FILTER, handle_signoff),
                MessageHandler(HI_DRCODE_FILTER, start_conversation),
                MessageHandler(filters.Document.ALL, handle_resume_ats),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_resume_ats),
            ],
            WAITING_FOR_JD: [
                MessageHandler(SIGNOFF_FILTER, handle_signoff),
                MessageHandler(HI_DRCODE_FILTER, start_conversation),
                MessageHandler(filters.Document.ALL, handle_jd),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_jd),
            ],

            # ── Resume Improvement ─────────────────────────────────────────
            WAITING_FOR_RESUME_IMP: [
                MessageHandler(SIGNOFF_FILTER, handle_signoff),
                MessageHandler(HI_DRCODE_FILTER, start_conversation),
                MessageHandler(filters.Document.ALL, handle_resume_improve),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_resume_improve),
            ],

            # ── After analysis: offer career coach chat ────────────────────
            ASKING_TO_CHAT: [
                MessageHandler(SIGNOFF_FILTER, handle_signoff),
                MessageHandler(HI_DRCODE_FILTER, start_conversation),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ask_to_chat),
            ],

            # ── Career Coach Conversation Mode ─────────────────────────────
            IN_CHAT_MODE: [
                MessageHandler(SIGNOFF_FILTER, handle_signoff),
                MessageHandler(HI_DRCODE_FILTER, start_conversation),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("end", end_chat),
            MessageHandler(SIGNOFF_FILTER, handle_signoff),
            MessageHandler(HI_DRCODE_FILTER, start_conversation),
        ],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)

    # ── Global fallback: fires for ANY message outside an active session ───
    # (ConversationHandler didn't consume it)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_outside)
    )
    application.add_handler(
        MessageHandler(filters.Document.ALL, handle_unknown_outside)
    )
    # Global signoff command even outside session
    application.add_handler(
        MessageHandler(SIGNOFF_FILTER, handle_unknown_outside)
    )

    logger.info("🤖 DrCode HireAi bot is starting...")
    application.run_polling()


if __name__ == "__main__":
    main()
