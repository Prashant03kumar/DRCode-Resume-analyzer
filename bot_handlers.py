import re
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config import WAITING_FOR_RESUME, WAITING_FOR_JD, model, logger
from utils import extract_text_from_file

async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Triggered when user says 'Hi DrCode'."""
    text = update.message.text.lower().strip()
    if "hi drcode" in text:
        await update.message.reply_text(
            "Hello! I am DrCode HireAi, an elite AI Career Coach and ATS Expert. 👨‍💻\n\n"
            "Please send me your *Resume* as a PDF, DOCX, or TXT file to begin.",
            parse_mode="Markdown"
        )
        return WAITING_FOR_RESUME
    return ConversationHandler.END

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Alternatively handle /start"""
    await update.message.reply_text(
        "Hello! I am DrCode HireAi, an elite AI Career Coach and ATS Expert. 👨‍💻\n\n"
        "To start, just type 'Hi DrCode' to begin.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text("Session cancelled. Type 'Hi DrCode' to start again.")
    context.user_data.clear()
    return ConversationHandler.END

async def handle_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the uploaded resume step."""
    if not update.message.document:
        await update.message.reply_text("Please upload a document (PDF, DOCX, TXT) for your resume.")
        return WAITING_FOR_RESUME

    document = update.message.document
    file = await context.bot.get_file(document.file_id)
    
    await update.message.reply_text("📥 Extracting your resume...")
    resume_text = await extract_text_from_file(file, document.file_name)
    
    if not resume_text:
        await update.message.reply_text(
            "❌ Failed to read your resume. Please ensure it's a valid PDF, Word, or TXT file, and that it isn't corrupted. Try again."
        )
        return WAITING_FOR_RESUME
    
    context.user_data["resume"] = resume_text
    
    await update.message.reply_text(
        "✅ Resume received! Now, please paste the **Job Description (JD)** as text, or upload it as a file.", 
        parse_mode="Markdown"
    )
    return WAITING_FOR_JD

async def handle_jd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the Job Description step and performs AI analysis."""
    jd_text = ""
    
    if update.message.document:
        document = update.message.document
        file = await context.bot.get_file(document.file_id)
        jd_text = await extract_text_from_file(file, document.file_name)
        if not jd_text:
            await update.message.reply_text(
                "❌ Failed to read your JD file. Please ensure it's a valid PDF, Word, or TXT file, or paste the text directly."
            )
            return WAITING_FOR_JD
    elif update.message.text:
        jd_text = update.message.text
    else:
        await update.message.reply_text("Please send the Job Description as regular text or upload it as a file.")
        return WAITING_FOR_JD
        
    context.user_data["jd"] = jd_text
    
    # Give the user waiting feedback
    status_message = await update.message.reply_text(
        "⏳ Processing... DrCode is performing surgery on your resume based on this JD. Please wait a moment...", 
        parse_mode="Markdown"
    )
    
    resume_text = context.user_data.get("resume")
    prompt = f"Here is the Resume:\n{resume_text}\n\nHere is the Job Description:\n{jd_text}"
    
    try:
        response = model.generate_content(prompt)
        final_response = response.text
        
        await status_message.delete()
        
        # Split message if it's over Telegram's 4096 character limit
        max_length = 4000
        for i in range(0, len(final_response), max_length):
            await update.message.reply_text(final_response[i:i+max_length])
                
    except Exception as e:
        logger.error(f"Error from Gemini API: {e}")
        await status_message.edit_text(f"❌ An error occurred during AI analysis: {str(e)}\n\nPlease try again later.")
        
    context.user_data.clear()
    await update.message.reply_text("Session complete. 👨‍💻 Type 'Hi DrCode' to analyze another resume.")
    
    return ConversationHandler.END
