# Product Requirements Document (PRD): DrCode HireAi

## 1. Project Overview
**DrCode HireAi** is an intelligent Telegram bot that functions as an elite AI Career Coach and ATS (Applicant Tracking System) Expert. It is designed to assist job seekers by automatically analyzing, scoring, and improving their resumes. Beyond simple document rewriting, it offers a multi-turn, conversational coaching experience tailored to the user's specific profile and targeted job descriptions.

---

## 2. Problem Statement: What Problems Does It Solve?

### The Core Problem
Modern recruitment heavily relies on ATS systems to filter candidates before a human recruiter ever sees a resume. Many highly skilled candidates face instant rejection not because they lack qualifications, but due to:
- Poor resume formatting that ATS parsers cannot read.
- Missing critical keywords explicitly mentioned in the Job Description (JD).
- Weak action verbs and unquantified achievements.
Additionally, personalized career mentorship and professional resume writing services are often prohibitively expensive or inaccessible for early-career professionals and students.

### The Solution: DrCode HireAi
This project democratizes access to professional career coaching and resume optimization by providing:
1. **ATS Alignment:** Instant scoring of a resume against a specific JD to highlight gaps.
2. **Automated "Surgery":** Auto-generation of a perfectly formatted, professionally rewritten resume (returned in PDF, DOCX, and TXT) that highlights the candidate’s strengths and injects missing keywords naturally.
3. **Contextual Mentorship:** A conversing AI career coach that remembers the user’s resume and advises them on skill gaps, interview preparations, and personal projects.

---

## 3. Target Audience
- **Job Seekers (Freshers & Experienced):** Looking to bypass ATS filters and increase interview callbacks.
- **Professionals Pivoting Careers:** Needing to reframe existing experience to match entirely new job descriptions.
- **Students:** Requiring guidance on building their first professional CV and identifying skills to learn.

---

## 4. Key Features & How It Works (Step-by-Step)

The bot operates through three primary workflows managed via asynchronous Telegram conversation handlers.

### Flow 1: ATS Analysis Mode (Targeted Optimization)
**Goal:** Compare an existing resume against a specific Job Description and generate a tailored, high-scoring CV.
1. **Initiation:** User clicks "ATS Analysis" from the Telegram inline keyboard.
2. **Resume Upload:** User uploads their current CV (`.pdf`, `.docx`, or `.txt`). The bot extracts text using `pypdf` or `python-docx`.
3. **JD Input:** User provides the Job Description (via file upload or text message).
4. **AI Processing:** Google Gemini (`gemini-2.5-flash`) evaluates the text using a strict scoring rubric (Keyword Match, Experience, Achievements, Education, Formatting, Action Verbs) to calculate an ATS Score out of 100.
5. **Feedback Delivery:** The bot replies with an analysis report detailing Strengths, Missing Keywords, and actionable "Surgery Notes."
6. **File Generation:** The AI rewrites the resume to bridge the gaps. The bot converts this text back into polished, downloadable PDF, DOCX, and TXT files using `reportlab` and `python-docx`.
7. **Transition:** The bot invites the user to enter "Career Coach Mode" to discuss the results.

### Flow 2: Resume Improvement Mode (General Polish)
**Goal:** Enhance a resume's professional appeal without a specific target JD.
1. **Initiation:** User selects "Improve Resume".
2. **Upload & Parse:** User uploads their current CV.
3. **AI Processing:** Gemini rewrites the content with strong action verbs, quantified achievements, and standardizes the structure.
4. **Delivery:** The bot delivers a summary of Changes Made alongside the improved files (PDF, DOCX, TXT).
5. **Transition:** Invites the user to chat further.

### Flow 3: Career Coach Conversation Mode (Multi-Turn Chat)
**Goal:** Act as an interactive, personalized mentor.
1. **Context Seeding:** If the user types `start`, the bot initiates a Gemini chat session fully seeded with the user's *original resume*, the *target JD*, and the *improved resume*.
2. **Interaction:** The user can ask dynamic questions (e.g., "What projects should I build to meet these missing skills?", "Mock interview me for this role").
3. **Context-Aware Responses:** Because the history is cached, the AI provides highly specific advice rather than generic job-hunting tips.
4. **Graceful Exit:** The user can type `signoff` or `/end` to terminate the session respectfully.

---

## 5. Technical Architecture

### 5.1 Tech Stack
- **Core Language:** Python 3.x
- **Bot Framework:** `python-telegram-bot` (Used to interface with Telegram APIs, handle long-polling, and manage complex `ConversationHandler` states).
- **AI / LLM Engine:** Google Gemini 2.5 Flash via `google-genai` SDK (Used for intelligent resume analysis, generating ATS scores, dynamic rewriting, and powering the conversational Career Coach mode).
- **Document Parsing:** 
  - `pypdf`: Powerful pure-Python library to extract raw text content from uploaded PDF resumes.
  - `python-docx`: Used to parse and extract text from `.docx` files.
- **Document Generation:** 
  - `reportlab`: Advanced PDF generation library utilized to programmatically build the optimized CV with custom styling, typography, margins, headers, and bullet alignments.
  - `python-docx`: Retained to generate polished, editable `.docx` exports of the final rewritten CV.
  - Python's `io` Module: Used for processing in-memory byte streams (`io.BytesIO`), meaning files are passed back and forth to Telegram directly from RAM without creating messy temp files on the disk.
- **Asynchronous Execution:** `asyncio` (Enabled for running Gemini API calls in non-blocking background threads using `asyncio.to_thread` while powering dynamic waiting animations).
- **Environment & Logging:** `python-dotenv` (for loading `.env` variables securely) and Python's native `logging` module.
- **Text Processing:** Python's native `re` module (Crucial for regex matching contact info, system commands, and parsing AI outputs through `##RESUME_START##` blocks).

### 5.2 Key Design Patterns
- **State-Machine Conversations:** The app uses `ConversationHandler` to seamlessly route users through `WAITING_FOR_RESUME`, `WAITING_FOR_JD`, and `IN_CHAT_MODE`.
- **System Instructions:** Strict prompt engineering ensures the AI conforms to structured outputs (e.g., separating the feedback text from the `##RESUME_START##` code blocks).
- **Async Processing:** File processing and AI API calls run in `asyncio` threads paired with dynamic "animated waiting" messages to ensure high user retention during wait times.

---

## 6. Future Scope

While the current MVP successfully tackles parsing, rewriting, and coaching, future enhancements could include:
1. **LinkedIn Profile Integration:** Parsing a user's LinkedIn URL (via scraping APIs) directly into a resume.
2. **Database Persistence:** Storing user sessions and previously optimized resumes in MongoDB or PostgreSQL so returning users don't have to start from scratch.
3. **Multilingual Support:** Allowing users to generate resumes and get coaching in regional languages.
4. **Cover Letter Generation:** Adding workflows specifically to write matching cover letters alongside the optimized resume.
