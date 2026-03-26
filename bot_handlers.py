import re
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from google.genai import types

from config import (
    CHOOSING_MODE, WAITING_FOR_RESUME_ATS, WAITING_FOR_JD,
    WAITING_FOR_RESUME_IMP, ASKING_TO_CHAT, IN_CHAT_MODE,
    client, MODEL_NAME, ATS_CONFIG, IMPROVE_CONFIG, CHAT_SYSTEM_INSTRUCTION, logger
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
    elapsed = 0
    msg_index = 0
    shuffled = WAIT_MESSAGES[:]
    random.shuffle(shuffled)
    while not stop_event.is_set():
        await asyncio.sleep(3)
        elapsed += 3
        if stop_event.is_set():
            break
        msg = shuffled[msg_index % len(shuffled)]
        msg_index += 1
        mins, secs = divmod(elapsed, 60)
        timer = f"{mins}m {secs}s" if mins else f"{secs}s"
        try:
            await status_msg.edit_text(
                f"⏳ *Processing...*\n\n{msg}\n\n"
                f"🕐 Time elapsed: `{timer}`\n_This usually takes 10–30 seconds..._",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Shared Utilities
# ─────────────────────────────────────────────────────────────────────────────

def mode_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 ATS Analysis  (Resume + JD)", callback_data="mode_ats")],
        [InlineKeyboardButton("✨ Improve Resume  (No JD needed)", callback_data="mode_improve")],
    ])


def parse_ai_response(full_text: str):
    """Splits AI output into (feedback_text, resume_text). Returns (full_text, None) on failure."""
    if "##RESUME_START##" in full_text and "##RESUME_END##" in full_text:
        parts    = full_text.split("##RESUME_START##")
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


async def send_resume_files(update, resume_part: str, resume_format: str,
                            resume_filename: str, label: str):
    """Generates and sends PDF, TXT, and DOCX (if applicable) to user."""
    base_label = label  # e.g. "Optimized" or "Improved"

    # PDF
    try:
        pdf_buf, pdf_fn = generate_pdf(resume_part, resume_filename)
        await update.message.reply_document(
            document=pdf_buf, filename=pdf_fn,
            caption=f"📄 *{base_label} Resume (PDF)* — professional, ATS-ready! Send it to recruiters.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"PDF error: {e}")
        await update.message.reply_text(f"⚠️ PDF generation failed: {e}")

    # DOCX — always send
    try:
        docx_buf, docx_fn = generate_docx(resume_part, resume_filename)
        await update.message.reply_document(
            document=docx_buf, filename=docx_fn,
            caption=f"📝 *{base_label} Resume (DOCX)* — editable Word format.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"DOCX error: {e}")

    # TXT
    try:
        txt_buf, txt_fn = generate_txt(resume_part, resume_filename)
        await update.message.reply_document(
            document=txt_buf, filename=txt_fn,
            caption=f"📋 *{base_label} Resume (TXT)* — plain text backup.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"TXT error: {e}")


async def run_gemini(prompt: str, config) -> str:
    """Runs Gemini in a thread and returns response text."""
    response = await asyncio.to_thread(
        client.models.generate_content,
        model=MODEL_NAME, contents=prompt, config=config,
    )
    return response.text


# ─────────────────────────────────────────────────────────────────────────────
# Entry Points
# ─────────────────────────────────────────────────────────────────────────────

async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Hello! I'm *DrCode HireAi* — your elite AI Career Coach! 🤖\n\n"
        "What would you like to do today?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=mode_keyboard()
    )
    return CHOOSING_MODE


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Hello! I'm *DrCode HireAi* — your elite AI Career Coach! 🤖\n\n"
        "Type *Hi DrCode* or pick an option below:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=mode_keyboard()
    )
    return CHOOSING_MODE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Session cancelled. Type *Hi DrCode* to start again. 👋",
                                    parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END


async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/end command — exits conversation mode."""
    context.user_data.clear()
    await update.message.reply_text(
        "👋 *Conversation ended.*\n\n"
        "It was great coaching you! You can upload a new resume anytime.\n"
        "Type *Hi DrCode* to start a new session. 🚀",
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END


async def handle_signoff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles 'signoff' keyword — graceful goodbye from anywhere."""
    context.user_data.clear()
    await update.message.reply_text(
        "🤝 *Signing off — DrCode HireAi*\n\n"
        "It was an honour coaching you today! 🏆\n"
        "Go get that dream job — you've got this! 🚀\n\n"
        "_Whenever you need me again, just type_ *Hi DrCode*.",
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END


async def handle_unknown_outside(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catches ALL random messages when no conversation session is active."""
    await update.message.reply_text(
        "🤖 *Hey there!*\n\n"
        "Looks like you haven't started a session yet.\n\n"
        "Type *Hi DrCode* to begin and I'll help you:\n"
        "• 🎯 Analyze your resume against a Job Description *(ATS Mode)*\n"
        "• ✨ Improve your resume professionally *(Improve Mode)*\n\n"
        "_Just say_ *Hi DrCode* _to get started!_ 🚀",
        parse_mode=ParseMode.MARKDOWN
    )


# ─────────────────────────────────────────────────────────────────────────────
# Mode Selection
# ─────────────────────────────────────────────────────────────────────────────

async def choose_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "mode_ats":
        context.user_data["mode"] = "ats"
        await query.edit_message_text(
            "🎯 *ATS Analysis Mode*\n\n"
            "*Step 1:* Upload your *Resume* as *PDF*, *DOCX*, or *TXT*. 📄",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_RESUME_ATS

    elif query.data == "mode_improve":
        context.user_data["mode"] = "improve"
        await query.edit_message_text(
            "✨ *Resume Improvement Mode*\n\n"
            "No JD needed! Upload your *Resume* as *PDF*, *DOCX*, or *TXT*.\n"
            "I'll transform it into an industry-level CV. 🚀",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_RESUME_IMP

    return CHOOSING_MODE


async def handle_random_in_mode_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fires when user types random text instead of pressing mode buttons."""
    await update.message.reply_text(
        "⬆️ Please choose a mode by tapping one of the buttons above!\n\n"
        "🎯 *ATS Analysis* — upload resume + job description\n"
        "✨ *Improve Resume* — just upload your resume\n\n"
        "_Or type_ *signoff* _to exit._",
        parse_mode=ParseMode.MARKDOWN
    )
    return CHOOSING_MODE


# ─────────────────────────────────────────────────────────────────────────────
# ATS Flow
# ─────────────────────────────────────────────────────────────────────────────

async def handle_resume_ats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.document:
        await update.message.reply_text("⚠️ Please upload a *PDF*, *DOCX*, or *TXT* file.",
                                        parse_mode=ParseMode.MARKDOWN)
        return WAITING_FOR_RESUME_ATS

    doc      = update.message.document
    file_ext = doc.file_name.split(".")[-1].lower()
    if file_ext not in ["pdf", "docx", "doc", "txt"]:
        await update.message.reply_text("❌ Unsupported format. Upload *PDF*, *DOCX*, or *TXT*.",
                                        parse_mode=ParseMode.MARKDOWN)
        return WAITING_FOR_RESUME_ATS

    file = await context.bot.get_file(doc.file_id)
    await update.message.reply_text("📥 Reading your resume...")
    resume_text = await extract_text_from_file(file, doc.file_name)
    if not resume_text:
        await update.message.reply_text("❌ Failed to read file. Please try again.")
        return WAITING_FOR_RESUME_ATS

    context.user_data.update({
        "resume": resume_text,
        "resume_format": file_ext,
        "resume_filename": doc.file_name,
    })
    await update.message.reply_text(
        "✅ *Resume received!*\n\n"
        "*Step 2:* Send the *Job Description (JD)* — paste as text or upload *PDF*/*DOCX*/*TXT*. 📋",
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_FOR_JD


async def handle_jd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    jd_text = ""
    if update.message.document:
        doc  = update.message.document
        file = await context.bot.get_file(doc.file_id)
        jd_text = await extract_text_from_file(file, doc.file_name)
        if not jd_text:
            await update.message.reply_text("❌ Failed to read JD file. Paste it as text or try again.")
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
        "⏳ *Processing...*\n\n🔬 Scanning resume against JD...\n\n🕐 Time elapsed: `0s`\n_This usually takes 10–30 seconds..._",
        parse_mode=ParseMode.MARKDOWN
    )
    stop_event = asyncio.Event()
    wait_task  = asyncio.create_task(animated_wait(status_msg, stop_event))

    try:
        full_text = await run_gemini(
            f"Resume:\n{resume_text}\n\nJob Description:\n{jd_text}", ATS_CONFIG
        )
    except Exception as e:
        stop_event.set(); await wait_task
        await status_msg.edit_text(f"❌ AI error: `{e}`", parse_mode=ParseMode.MARKDOWN)
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        stop_event.set(); await wait_task

    feedback, resume_part = parse_ai_response(full_text)
    await status_msg.delete()

    for i in range(0, len(feedback), 4000):
        await update.message.reply_text(feedback[i:i+4000])

    if resume_part:
        context.user_data["improved_resume"] = resume_part
        context.user_data["jd"] = jd_text          # save JD for chat context
        await update.message.reply_text("📎 *Generating your Optimized CV files...*",
                                        parse_mode=ParseMode.MARKDOWN)
        await send_resume_files(update, resume_part, resume_format, resume_filename, "Optimized")
    else:
        for i in range(0, len(full_text), 4000):
            await update.message.reply_text(full_text[i:i+4000])

    # ── Offer Career Coach Chat (same as Improve mode) ────────────────────
    await update.message.reply_text(
        "─────────────────────────────\n"
        "🤝 *Want to go deeper?*\n\n"
        "I can be your personal *Career Coach* — help you with:\n"
        "• Resume mistakes & improvements\n"
        "• Skill gaps & what to learn next\n"
        "• Project ideas for your profile\n"
        "• Interview preparation tips\n"
        "• Career guidance & roadmap\n\n"
        "Type *start* to begin a conversation, or *Hi DrCode* to start over.",
        parse_mode=ParseMode.MARKDOWN
    )
    return ASKING_TO_CHAT


# ─────────────────────────────────────────────────────────────────────────────
# Resume Improvement Flow  (with Career Coach Chat after)
# ─────────────────────────────────────────────────────────────────────────────

async def handle_resume_improve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.document:
        await update.message.reply_text("⚠️ Please upload a *PDF*, *DOCX*, or *TXT* file.",
                                        parse_mode=ParseMode.MARKDOWN)
        return WAITING_FOR_RESUME_IMP

    doc      = update.message.document
    file_ext = doc.file_name.split(".")[-1].lower()
    if file_ext not in ["pdf", "docx", "doc", "txt"]:
        await update.message.reply_text("❌ Unsupported format. Upload *PDF*, *DOCX*, or *TXT*.",
                                        parse_mode=ParseMode.MARKDOWN)
        return WAITING_FOR_RESUME_IMP

    file = await context.bot.get_file(doc.file_id)
    await update.message.reply_text("📥 Reading your resume...")
    resume_text = await extract_text_from_file(file, doc.file_name)
    if not resume_text:
        await update.message.reply_text("❌ Failed to read file. Please try again.")
        return WAITING_FOR_RESUME_IMP

    context.user_data.update({
        "resume": resume_text,
        "resume_format": file_ext,
        "resume_filename": doc.file_name,
    })

    status_msg = await update.message.reply_text(
        "⏳ *Processing...*\n\n✂️ Performing resume surgery...\n\n🕐 Time elapsed: `0s`\n_This usually takes 10–30 seconds..._",
        parse_mode=ParseMode.MARKDOWN
    )
    stop_event = asyncio.Event()
    wait_task  = asyncio.create_task(animated_wait(status_msg, stop_event))

    try:
        full_text = await run_gemini(
            f"Resume to improve:\n{resume_text}", IMPROVE_CONFIG
        )
    except Exception as e:
        stop_event.set(); await wait_task
        await status_msg.edit_text(f"❌ AI error: `{e}`", parse_mode=ParseMode.MARKDOWN)
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        stop_event.set(); await wait_task

    feedback, resume_part = parse_ai_response(full_text)
    await status_msg.delete()

    # ── Step 1 & 2: Improvement notes + Changes Made ──────────────────────
    for i in range(0, len(feedback), 4000):
        await update.message.reply_text(feedback[i:i+4000])

    # ── Step 1: Send all 3 file formats ───────────────────────────────────
    if resume_part:
        context.user_data["improved_resume"] = resume_part
        await update.message.reply_text("📎 *Generating your Improved CV files...*",
                                        parse_mode=ParseMode.MARKDOWN)
        await send_resume_files(update, resume_part, file_ext, doc.file_name, "Improved")
    else:
        for i in range(0, len(full_text), 4000):
            await update.message.reply_text(full_text[i:i+4000])

    # ── Step 3: Offer Career Coach Chat ───────────────────────────────────
    await update.message.reply_text(
        "─────────────────────────────\n"
        "🤝 *Want to go deeper?*\n\n"
        "I can be your personal *Career Coach* — help you with:\n"
        "• Resume mistakes & improvements\n"
        "• Skill gaps & what to learn next\n"
        "• Project ideas for your profile\n"
        "• Interview preparation tips\n"
        "• Career guidance & roadmap\n\n"
        "Type *start* to begin a conversation, or *Hi DrCode* to start over.",
        parse_mode=ParseMode.MARKDOWN
    )
    return ASKING_TO_CHAT


async def handle_ask_to_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles user response after improvement — 'start' or something else."""
    text = update.message.text.strip().lower()

    if text == "start":
        resume_text    = context.user_data.get("resume", "No resume provided.")
        improved       = context.user_data.get("improved_resume", "")

        # Build a Gemini chat session with full context baked in
        jd_text = context.user_data.get("jd", "")  # present only in ATS mode
        jd_section = f"The Job Description they were targeting:\n{jd_text}\n\n" if jd_text else ""
        context_prompt = (
            f"The user's ORIGINAL resume:\n{resume_text}\n\n"
            f"{jd_section}"
            f"The IMPROVED/OPTIMIZED resume we generated:\n{improved}\n\n"
            "Now enter career coach conversation mode. The user will ask you questions."
        )
        chat_config = types.GenerateContentConfig(
            temperature=0.4,
            max_output_tokens=2048,
            system_instruction=CHAT_SYSTEM_INSTRUCTION,
        )
        # Seed the chat history so Gemini knows the resume
        context.user_data["chat_history"] = [
            types.Content(role="user",  parts=[types.Part(text=context_prompt)]),
            types.Content(role="model", parts=[types.Part(text=(
                "Understood! I've reviewed your resume and the improvements we made. "
                "I'm now your personal Career Coach. Ask me anything — resume tweaks, "
                "skill gaps, interview prep, project ideas, or career roadmap. Let's go! 🚀"
            ))]),
        ]
        context.user_data["chat_config"] = chat_config

        await update.message.reply_text(
            "🎓 *Career Coach Mode Activated!*\n\n"
            "I've loaded your resume into my memory. Ask me anything!\n\n"
            "_Type_ `/end` _anytime to exit this mode._",
            parse_mode=ParseMode.MARKDOWN
        )
        return IN_CHAT_MODE

    else:
        # Random text — remind them what to type
        await update.message.reply_text(
            "💡 *Heads up!*\n\n"
            "To start a *Career Coach* conversation about your resume, type *start*\n"
            "To sign off and exit, type *signoff*\n"
            "To begin a brand new session, type *Hi DrCode*",
            parse_mode=ParseMode.MARKDOWN
        )
        return ASKING_TO_CHAT


# ─────────────────────────────────────────────────────────────────────────────
# Career Coach Chat Mode
# ─────────────────────────────────────────────────────────────────────────────

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles multi-turn career coaching conversation."""
    user_message = update.message.text.strip()
    chat_history = context.user_data.get("chat_history", [])
    chat_config  = context.user_data.get("chat_config")

    # Add user's new message to history
    chat_history.append(
        types.Content(role="user", parts=[types.Part(text=user_message)])
    )

    thinking_msg = await update.message.reply_text("💬 _DrCode is thinking..._",
                                                    parse_mode=ParseMode.MARKDOWN)
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL_NAME,
            contents=chat_history,
            config=chat_config,
        )
        reply = response.text

        # Add model reply to history for multi-turn memory
        chat_history.append(
            types.Content(role="model", parts=[types.Part(text=reply)])
        )
        context.user_data["chat_history"] = chat_history

        await thinking_msg.delete()

        # Split long replies
        for i in range(0, len(reply), 4000):
            await update.message.reply_text(reply[i:i+4000])

    except Exception as e:
        logger.error(f"Chat error: {e}")
        await thinking_msg.edit_text(f"❌ Error: `{e}`\n\nPlease try again.",
                                     parse_mode=ParseMode.MARKDOWN)

    return IN_CHAT_MODE
