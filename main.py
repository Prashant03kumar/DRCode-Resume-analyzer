import re
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
from config import TELEGRAM_BOT_TOKEN, WAITING_FOR_RESUME, WAITING_FOR_JD, logger
from bot_handlers import (
    start_conversation, start_command, handle_resume, handle_jd, cancel
)

def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(re.compile(r'(?i)hi drcode')), start_conversation),
            CommandHandler("start", start_command)
        ],
        states={
            WAITING_FOR_RESUME: [
                MessageHandler(filters.Document.ALL, handle_resume),
                MessageHandler(filters.TEXT & ~(filters.COMMAND | filters.Regex(re.compile(r'(?i)cancel'))), handle_resume),
            ],
            WAITING_FOR_JD: [
                MessageHandler(filters.Document.ALL, handle_jd),
                MessageHandler(filters.TEXT & ~(filters.COMMAND | filters.Regex(re.compile(r'(?i)cancel'))), handle_jd),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex(re.compile(r'(?i)cancel')), cancel)
        ],
    )

    application.add_handler(conv_handler)
    
    logger.info("Bot is starting polling...")
    application.run_polling()  # Defaults to listening to all allowed updates safely

if __name__ == "__main__":
    main()
