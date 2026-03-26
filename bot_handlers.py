import re
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from config import (
    CHOOSING_MODE, WAITING_FOR_RESUME_ATS, WAITING_FOR_JD, WAITING_FOR_RESUME_IMP,
    client, MODEL_NAME, ATS_CONFIG, IMPROVE_CONFIG, logger
)
from utils import extract_text_from_file, generate_docx, generate_pdf, generate_txt


# ─────────────────────────────────────────────────────────────────────────────
# Animated Wait Messages
# ─────────────────────────────────────────────────────────────────────────────

WAIT_MESSAGES = [
    "🔬 Scanning your resume...",
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
    "☕ Grab a chai, almost ready!",
    "🎪 Turning your resume into pure gold...",
]


async def animated_wait(status_msg, stop_event: asyncio.Event):
    """Updates status message with countdown + random messages every 3s."""
    elapsed = 0
    msg_index = 0
    shuffled = WAIT_MESSAGES[:]
    random.shuffle(shuffled)

    while not stop_event.is_set():
        await asyncio.sleep(3)
        elapsed += 3
        if stop_event.is_set():
            break
        current_msg = shuffled[msg_index % len(shuffled)]
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
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Shared Helpers
# ─────────────────────────────────────────────────────────────────────────────

def mode_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎯 ATS Analysis  (Resume + JD)", callback_data="mode_ats"),
        ],
        [
            InlineKeyboardButton("✨ Improve Resume  (No JD needed)", callback_data="mode_improve"),
        ],
    ])


async def send_resume_files(update, resume_part, resume_format, resume_filename, caption_pdf, caption_txt):
    """Generates and sends PDF + TXT (and DOCX if applicable) to user."""
    # Always send PDF
    try:
        pdf_buf, pdf_fn = generate_pdf(resume_part, resume_filename)
        await update.message.reply_document(
            document=pdf_buf, filename=pdf_fn,
            caption=caption_pdf, parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"PDF error: {e}")
        await update.message.reply_text(f"⚠️ PDF generation failed: {e}")

    # Always send TXT
    try:
        txt_buf, txt_fn = generate_txt(resume_part, resume_filename)
        await update.message.reply_document(
            document=txt_buf, filename=txt_fn,
            caption=caption_txt, parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"TXT error: {e}")

    # Send DOCX if user uploaded a Word file
    if resume_format in ["docx", "doc"]:
        try:
            docx_buf, docx_fn = generate_docx(resume_part, resume_filename)
            await update.message.reply_document(
                document=docx_buf, filename=docx_fn,
                caption="📝 *Editable Word version (DOCX)*", parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"DOCX error: {e}")


def parse_ai_response(full_text):
    """Splits AI output into (feedback_text, resume_text). Returns (full_text, None) on failure."""
    if "##RESUME_START##" in full_text and "##RESUME_END##" in full_text:
        parts = full_text.split("##RESUME_START##")
        feedback = parts[0].strip()
        resume   = parts[1].split("##RESUME_END##")[0].strip()
        return feedback, resume

    # Fallback regex
    match = re.search(
        r'(?:📄\s*\*{0,2}IDEAL RESUME.*?\*{0,2}|IDEAL RESUME[^\n]*)\n(.*)',
        full_text, re.DOTALL | re.IGNORECASE
    )
    if match:
        return full_text[:match.start()].strip(), match.group(1).strip()

    return full_text, None


# ─────────────────────────────────────────────────────────────────────────────
# Entry Points
# ─────────────────────────────────────────────────────────────────────────────

async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Triggered when user says 'Hi DrCode'."""
    await update.message.reply_text(
        "👋 Hello! I'm *DrCode HireAi* — your elite AI Career Coach! 🤖\n\n"
        "What would you like to do today?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=mode_keyboard()
    )
    return CHOOSING_MODE


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "👋 Hello! I'm *DrCode HireAi* — your elite AI Career Coach! 🤖\n\n"
        "Type *Hi DrCode* to begin, or pick an option below:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=mode_keyboard()
    )
    return CHOOSING_MODE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Session cancelled. Type *Hi DrCode* to start again. 👋",
                                    parse_mode=ParseMode.MARKDOWN)
    context.user_data.clear()
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────────────
# Mode Selection (Inline Keyboard Callback)
# ─────────────────────────────────────────────────────────────────────────────

async def choose_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles inline button press for mode selection."""
    query = update.callback_query
    await query.answer()
    mode  = query.data  # "mode_ats" or "mode_improve"

    if mode == "mode_ats":
        context.user_data["mode"] = "ats"
        await query.edit_message_text(
            "🎯 *ATS Analysis Mode*\n\n"
            "*Step 1:* Please upload your *Resume* as a *PDF*, *DOCX*, or *TXT* file. 📄",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_RESUME_ATS

    elif mode == "mode_improve":
        context.user_data["mode"] = "improve"
        await query.edit_message_text(
            "✨ *Resume Improvement Mode*\n\n"
            "No JD needed! Just upload your *Resume* as a *PDF*, *DOCX*, or *TXT* file\n"
            "and I'll transform it into an industry-level CV. 🚀",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_RESUME_IMP

    return CHOOSING_MODE


# ─────────────────────────────────────────────────────────────────────────────
# ATS Flow
# ─────────────────────────────────────────────────────────────────────────────

async def handle_resume_ats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles resume upload for ATS analysis mode."""
    if not update.message.document:
        await update.message.reply_text("⚠️ Please upload a *PDF*, *DOCX*, or *TXT* file.",
                                        parse_mode=ParseMode.MARKDOWN)
        return WAITING_FOR_RESUME_ATS

    document = update.message.document
    file_ext = document.file_name.split(".")[-1].lower()
    if file_ext not in ["pdf", "docx", "doc", "txt"]:
        await update.message.reply_text("❌ Unsupported format. Please upload a *PDF*, *DOCX*, or *TXT* file.",
                                        parse_mode=ParseMode.MARKDOWN)
        return WAITING_FOR_RESUME_ATS

    file = await context.bot.get_file(document.file_id)
    await update.message.reply_text("📥 Reading your resume...")
    resume_text = await extract_text_from_file(file, document.file_name)

    if not resume_text:
        await update.message.reply_text("❌ Failed to read the file. Please try again.")
        return WAITING_FOR_RESUME_ATS

    context.user_data["resume"]          = resume_text
    context.user_data["resume_format"]   = file_ext
    context.user_data["resume_filename"] = document.file_name

    await update.message.reply_text(
        "✅ *Resume received!*\n\n"
        "*Step 2:* Now send the *Job Description (JD)*.\n"
        "Paste it as text or upload as *PDF*, *DOCX*, or *TXT*. 📋",
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_FOR_JD


async def handle_jd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles JD input and runs ATS analysis."""
    jd_text = ""

    if update.message.document:
        document = update.message.document
        file = await context.bot.get_file(document.file_id)
        jd_text = await extract_text_from_file(file, document.file_name)
        if not jd_text:
            await update.message.reply_text("❌ Failed to read the JD file. Please try again or paste as text.")
            return WAITING_FOR_JD
    elif update.message.text:
        jd_text = update.message.text
    else:
        await update.message.reply_text("Please send the JD as text or upload a file.")
        return WAITING_FOR_JD

    resume_text     = context.user_data.get("resume")
    resume_format   = context.user_data.get("resume_format", "pdf")
    resume_filename = context.user_data.get("resume_filename", "resume.pdf")

    status_msg = await update.message.reply_text(
        "⏳ *Analyzing your profile...*\n\n🔬 Scanning resume against JD...\n\n🕐 Time elapsed: `0s`\n_This usually takes 10–30 seconds..._",
        parse_mode=ParseMode.MARKDOWN
    )

    prompt     = f"Here is the Resume:\n{resume_text}\n\nHere is the Job Description:\n{jd_text}"
    stop_event = asyncio.Event()
    wait_task  = asyncio.create_task(animated_wait(status_msg, stop_event))

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL_NAME, contents=prompt, config=ATS_CONFIG,
        )
        full_text = response.text
    except Exception as e:
        stop_event.set(); await wait_task
        logger.error(f"Gemini ATS error: {e}")
        await status_msg.edit_text(f"❌ AI error: `{e}`\n\nPlease try again.", parse_mode=ParseMode.MARKDOWN)
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        stop_event.set(); await wait_task

    feedback, resume_part = parse_ai_response(full_text)
    await status_msg.delete()

    # Send feedback as text
    for i in range(0, len(feedback), 4000):
        await update.message.reply_text(feedback[i:i+4000])

    if resume_part:
        await update.message.reply_text("📎 *Generating your Optimized CV files...*", parse_mode=ParseMode.MARKDOWN)
        await send_resume_files(update, resume_part, resume_format, resume_filename,
                                "📄 *Optimized Resume (PDF)* — ATS-ready, send to recruiters!",
                                "📝 *Optimized Resume (TXT)* — plain text backup.")
    else:
        await update.message.reply_text("⚠️ Could not extract the rewritten CV. Full response:")
        for i in range(0, len(full_text), 4000):
            await update.message.reply_text(full_text[i:i+4000])

    context.user_data.clear()
    await update.message.reply_text("✅ *ATS Analysis complete!* Type *Hi DrCode* to start again. 🎯",
                                    parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────────────
# Improve Resume Flow
# ─────────────────────────────────────────────────────────────────────────────

async def handle_resume_improve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles resume upload for improvement mode (no JD needed)."""
    if not update.message.document:
        await update.message.reply_text("⚠️ Please upload a *PDF*, *DOCX*, or *TXT* file.",
                                        parse_mode=ParseMode.MARKDOWN)
        return WAITING_FOR_RESUME_IMP

    document = update.message.document
    file_ext = document.file_name.split(".")[-1].lower()
    if file_ext not in ["pdf", "docx", "doc", "txt"]:
        await update.message.reply_text("❌ Unsupported format. Upload a *PDF*, *DOCX*, or *TXT* file.",
                                        parse_mode=ParseMode.MARKDOWN)
        return WAITING_FOR_RESUME_IMP

    file = await context.bot.get_file(document.file_id)
    await update.message.reply_text("📥 Reading your resume...")
    resume_text = await extract_text_from_file(file, document.file_name)

    if not resume_text:
        await update.message.reply_text("❌ Failed to read the file. Please try again.")
        return WAITING_FOR_RESUME_IMP

    status_msg = await update.message.reply_text(
        "⏳ *Improving your resume...*\n\n✂️ Performing resume surgery...\n\n🕐 Time elapsed: `0s`\n_This usually takes 10–30 seconds..._",
        parse_mode=ParseMode.MARKDOWN
    )

    stop_event = asyncio.Event()
    wait_task  = asyncio.create_task(animated_wait(status_msg, stop_event))

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL_NAME, contents=f"Here is the Resume to improve:\n{resume_text}",
            config=IMPROVE_CONFIG,
        )
        full_text = response.text
    except Exception as e:
        stop_event.set(); await wait_task
        logger.error(f"Gemini improve error: {e}")
        await status_msg.edit_text(f"❌ AI error: `{e}`\n\nPlease try again.", parse_mode=ParseMode.MARKDOWN)
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        stop_event.set(); await wait_task

    feedback, resume_part = parse_ai_response(full_text)
    await status_msg.delete()

    # Send changes/feedback as text
    for i in range(0, len(feedback), 4000):
        await update.message.reply_text(feedback[i:i+4000])

    if resume_part:
        await update.message.reply_text("📎 *Generating your Improved CV files...*", parse_mode=ParseMode.MARKDOWN)
        await send_resume_files(update, resume_part, file_ext, document.file_name,
                                "📄 *Improved Resume (PDF)* — professional, ATS-ready CV!",
                                "📝 *Improved Resume (TXT)* — plain text version.")
    else:
        await update.message.reply_text("⚠️ Could not extract the improved CV. Full response:")
        for i in range(0, len(full_text), 4000):
            await update.message.reply_text(full_text[i:i+4000])

    context.user_data.clear()
    await update.message.reply_text(
        "✅ *Resume improvement complete!*\n\n"
        "You now have a professional, ATS-ready CV! 🏆\n"
        "Type *Hi DrCode* anytime to start again. 👨‍💻",
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END
