import re
import asyncio
import random
import io
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from config import WAITING_FOR_RESUME, WAITING_FOR_JD, client, MODEL_NAME, GENERATION_CONFIG, logger
from utils import extract_text_from_file, generate_docx, generate_pdf, generate_txt

# ─────────────────────────────────────────────────────────────────────────────
# Animated Waiting Messages
# ─────────────────────────────────────────────────────────────────────────────

WAIT_MESSAGES = [
    "🔬 Scanning your resume against the JD...",
    "🧠 DrCode AI is thinking hard...",
    "⚙️ Running ATS algorithms...",
    "📊 Calculating your keyword match score...",
    "✂️ Performing resume surgery...",
    "🚀 Almost there, hold tight...",
    "💡 Finding the hidden gaps in your profile...",
    "🎯 Matching skills to requirements...",
    "🕵️ Hunting for missing keywords...",
    "✍️ Rewriting your Ideal CV...",
    "⏳ Bas kuch derr aur, bhai!",
    "🔥 Thoda patience... magic ho raha hai!",
    "😎 DrCode never gives up on your career!",
    "📝 Adding power verbs to your experience...",
    "🏆 Optimizing for maximum ATS score...",
    "💪 Your career glow-up is loading...",
    "🎭 Crafting your professional story...",
    "🌟 Making your resume shine bright...",
    "⚡ Almost done! Don't go anywhere...",
    "🤖 AI is working overtime just for you!",
]

async def animated_wait(status_msg, stop_event: asyncio.Event):
    """Background task that updates the status message with countdown + random messages."""
    elapsed = 0
    msg_index = 0
    random.shuffle(WAIT_MESSAGES)

    while not stop_event.is_set():
        await asyncio.sleep(3)
        elapsed += 3
        if stop_event.is_set():
            break
        current_msg = WAIT_MESSAGES[msg_index % len(WAIT_MESSAGES)]
        msg_index += 1
        mins, secs = divmod(elapsed, 60)
        timer = f"{mins}m {secs}s" if mins else f"{secs}s"
        try:
            await status_msg.edit_text(
                f"⏳ *Analyzing your profile...*\n\n"
                f"{current_msg}\n\n"
                f"🕐 Time elapsed: `{timer}`\n"
                f"_This usually takes 10–30 seconds..._",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            pass  # Ignore Telegram "message not modified" errors


# ─────────────────────────────────────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────────────────────────────────────

async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Triggered when user says 'Hi DrCode'."""
    await update.message.reply_text(
        "👋 Hello! I'm *DrCode HireAi* — your elite AI Career Coach & ATS Expert! 🤖\n\n"
        "Let's supercharge your resume! 🚀\n\n"
        "*Step 1:* Please send me your *Resume* as a *PDF*, *DOCX*, or *TXT* file. 📄",
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_FOR_RESUME


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /start command."""
    await update.message.reply_text(
        "👋 Hello! I'm *DrCode HireAi* — your elite AI Career Coach & ATS Expert! 🤖\n\n"
        "Type *Hi DrCode* to begin your resume analysis! 🚀",
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text(
        "Session cancelled. Type *Hi DrCode* to start again. 👋",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data.clear()
    return ConversationHandler.END


async def handle_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the uploaded resume."""
    if not update.message.document:
        await update.message.reply_text(
            "⚠️ Please upload a *document* file (PDF, DOCX, or TXT) for your resume.",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_RESUME

    document = update.message.document
    file_ext = document.file_name.split(".")[-1].lower()

    if file_ext not in ["pdf", "docx", "doc", "txt"]:
        await update.message.reply_text(
            "❌ Unsupported format. Please upload a *PDF*, *DOCX*, or *TXT* file.",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_RESUME

    file = await context.bot.get_file(document.file_id)
    await update.message.reply_text("📥 Reading your resume...")

    resume_text = await extract_text_from_file(file, document.file_name)

    if not resume_text:
        await update.message.reply_text(
            "❌ Failed to read your resume. Please ensure the file is valid and not corrupted."
        )
        return WAITING_FOR_RESUME

    context.user_data["resume"]          = resume_text
    context.user_data["resume_format"]   = file_ext
    context.user_data["resume_filename"] = document.file_name

    await update.message.reply_text(
        "✅ *Resume received!* Great start!\n\n"
        "*Step 2:* Now please send me the *Job Description (JD)*.\n"
        "You can paste it as text or upload it as a *PDF*, *DOCX*, or *TXT* file. 📋",
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_FOR_JD


async def handle_jd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the JD and runs the full AI analysis."""
    jd_text = ""

    if update.message.document:
        document = update.message.document
        file = await context.bot.get_file(document.file_id)
        jd_text = await extract_text_from_file(file, document.file_name)
        if not jd_text:
            await update.message.reply_text(
                "❌ Failed to read the JD file. Please try uploading again or paste the text directly."
            )
            return WAITING_FOR_JD
    elif update.message.text:
        jd_text = update.message.text
    else:
        await update.message.reply_text(
            "Please send the Job Description as text or upload a PDF/DOCX/TXT file."
        )
        return WAITING_FOR_JD

    context.user_data["jd"] = jd_text

    # Show animated status
    status_message = await update.message.reply_text(
        "⏳ *Analyzing your profile...*\n\n"
        "🔬 Scanning your resume against the JD...\n\n"
        "🕐 Time elapsed: `0s`\n"
        "_This usually takes 10–30 seconds..._",
        parse_mode=ParseMode.MARKDOWN
    )

    resume_text     = context.user_data.get("resume")
    resume_format   = context.user_data.get("resume_format", "pdf")
    resume_filename = context.user_data.get("resume_filename", "resume.pdf")

    prompt = (
        f"Here is the Resume:\n{resume_text}\n\n"
        f"Here is the Job Description:\n{jd_text}"
    )

    # Start animated wait in background
    stop_event = asyncio.Event()
    wait_task  = asyncio.create_task(animated_wait(status_message, stop_event))

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL_NAME,
            contents=prompt,
            config=GENERATION_CONFIG,
        )
        full_text = response.text
    except Exception as e:
        stop_event.set()
        await wait_task
        logger.error(f"Gemini API error: {e}")
        await status_message.edit_text(
            f"❌ An error occurred during AI analysis:\n`{str(e)}`\n\nPlease try again later.",
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        stop_event.set()
        await wait_task

    # ── Parse AI output ────────────────────────────────────────────────────
    feedback_part = full_text
    resume_part   = None

    if "##RESUME_START##" in full_text and "##RESUME_END##" in full_text:
        parts         = full_text.split("##RESUME_START##")
        feedback_part = parts[0].strip()
        resume_raw    = parts[1].split("##RESUME_END##")[0].strip()
        resume_part   = resume_raw
    else:
        # Fallback: look for common ideal resume section headers
        match = re.search(
            r'(?:📄\s*\*{0,2}IDEAL RESUME.*?\*{0,2}|IDEAL RESUME[^\n]*)\n(.*)',
            full_text, re.DOTALL | re.IGNORECASE
        )
        if match:
            feedback_part = full_text[:match.start()].strip()
            resume_part   = match.group(1).strip()

    # ── Delete status, send feedback ──────────────────────────────────────
    await status_message.delete()

    max_len = 4000
    for i in range(0, len(feedback_part), max_len):
        await update.message.reply_text(feedback_part[i:i + max_len])

    # ── Send Optimized Resume as files ────────────────────────────────────
    if resume_part:
        await update.message.reply_text(
            "📎 *Generating your Optimized Resume files...*",
            parse_mode=ParseMode.MARKDOWN
        )

        # Always send PDF (looks like CV)
        try:
            pdf_buf, pdf_filename = generate_pdf(resume_part, resume_filename)
            await update.message.reply_document(
                document=pdf_buf,
                filename=pdf_filename,
                caption="📄 *Your DrCode Optimized Resume (PDF)* — ready to send to recruiters!",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"PDF generation error: {e}")
            await update.message.reply_text(f"⚠️ Could not generate PDF: {e}")

        # Always send TXT as well
        try:
            txt_buf, txt_filename = generate_txt(resume_part, resume_filename)
            await update.message.reply_document(
                document=txt_buf,
                filename=txt_filename,
                caption="📝 *Your DrCode Optimized Resume (TXT)* — plain text version.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"TXT generation error: {e}")

        # If user uploaded DOCX, also send DOCX
        if resume_format in ["docx", "doc"]:
            try:
                docx_buf, docx_filename = generate_docx(resume_part, resume_filename)
                await update.message.reply_document(
                    document=docx_buf,
                    filename=docx_filename,
                    caption="📝 *Your DrCode Optimized Resume (DOCX)* — editable Word version.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"DOCX generation error: {e}")
    else:
        await update.message.reply_text("⚠️ Could not extract the Ideal CV from the response. Here is the full output:")
        for i in range(0, len(full_text), max_len):
            await update.message.reply_text(full_text[i:i + max_len])

    context.user_data.clear()
    await update.message.reply_text(
        "✅ *Session complete!* Hope DrCode helped you land that job! 🎯\n\n"
        "Type *Hi DrCode* anytime to analyze another resume. 👨‍💻",
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END
