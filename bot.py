import os
import asyncio
from pyrogram import Client, filters
from groq import Groq
import google.generativeai as genai
API_ID_RAW = os.getenv("API_ID", "").strip()
API_HASH = os.getenv("API_HASH", "").strip()
BOT_TOKEN_RAW = os.getenv("BOT_TOKEN", "")
BOT_TOKEN = BOT_TOKEN_RAW.strip().strip('"').strip("'")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("API_ID loaded:", bool(API_ID_RAW))
print("API_HASH loaded:", bool(API_HASH))
print("BOT_TOKEN loaded:", bool(BOT_TOKEN))
print("RAW length:", len(BOT_TOKEN_RAW), "| CLEAN length:", len(BOT_TOKEN))
print("Colon count:", BOT_TOKEN.count(":"))
print("Bot ID part:", BOT_TOKEN.split(":")[0])
print("Secret part length:", len(BOT_TOKEN.split(":")[-1]))
print("Has space/newline inside:", any(c.isspace() for c in BOT_TOKEN))

if not API_ID_RAW:
    raise ValueError("API_ID is missing")
if not API_HASH:
    raise ValueError("API_HASH is missing")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing")

API_ID = int(API_ID_RAW)

app = Client(
    "zizo_lecture_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)
groq_client = Groq(api_key=GROQ_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.5-flash")

# برومبت مخصص عشان المصطلحات التقنية تفضل بالإنجليزي
TRANSCRIBE_PROMPT = (
    "هذه محاضرة جامعية باللهجة المصرية تحتوي على مصطلحات تقنية وبرمجية باللغة الإنجليزية. "
    "اكتب المصطلحات الإنجليزية كما هي بحروفها الإنجليزية مثل: "
    "Database, SQL, MySQL, Apache, PHP, Python, HTML, CSS, Server, Client, HTTP, API, ERD, DFD, Laragon."
)

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text(
        "أهلاً بيك يا زيزو في بوت تفريغ وتلخيص المحاضرات 🎓\n"
        "ابعتلي أي ملف صوتي أو فويس نوت للمحاضرة، وهفرغهولك وألخصهولك على السيرفر من غير ما يسحب من باقتك."
    )

@app.on_message(filters.voice | filters.audio)
async def handle_audio(client, message):
    status_msg = await message.reply_text("⏳ جاري تحميل المحاضرة على السيرفر...")
    file_path = None
    
    try:
        # تحميل الملف على السيرفر فقط
        file_path = await message.download()
        
        await status_msg.edit_text("🎙️ جاري تفريغ الصوت إلى نص بدقة...")
        
        # التفريغ الصوتي عبر Groq Whisper
        with open(file_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(os.path.basename(file_path), audio_file.read()),
                model="whisper-large-v3",
                prompt=TRANSCRIBE_PROMPT,
                language="ar",
                response_format="text"
            )
        
        await status_msg.edit_text("🧠 جاري تلخيص المحاضرة واستخراج أهم النقاط بـ Gemini...")
        
        # التلخيص عبر Gemini
        summary_prompt = f"""
        أنت مساعد دراسي ذكي. قم بتلخيص نص المحاضرة التالي باللغة العربية بأسلوب منظم وواضح، 
        مع الحفاظ على جميع المصطلحات التقنية والبرمجية باللغة الإنجليزية كما هي، وشرحها ببساطة.
        قسم الرد إلى:
        1. ملخص سريع لأهم أفكار المحاضرة.
        2. شرح أهم المصطلحات التقنية التي وردت.
        3. 5 أسئلة متوقعة للامتحان بإجاباتها.

        نص المحاضرة:
        {transcription}
        """
        response = gemini_model.generate_content(summary_prompt)
        summary_text = response.text

        # إرسال التفريغ النصي كملف لو طويل، أو رسالة لو قصير
        if len(transcription) > 3500:
            txt_filename = f"{file_path}_transcript.txt"
            with open(txt_filename, "w", encoding="utf-8") as f:
                f.write(transcription)
            await message.reply_document(txt_filename, caption="📄 التفريغ النصي الكامل للمحاضرة")
            os.remove(txt_filename)
        else:
            await message.reply_text(f"📄 **التفريغ النصي:**\n\n{transcription}")

        # إرسال الملخص
        await message.reply_text(f"✨ **ملخص المحاضرة:**\n\n{summary_text}")
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ حصل خطأ أثناء المعالجة:\n`{str(e)}`")
    
    finally:
        # مسح الملف الصوتي من السيرفر فوراً لتوفير المساحة
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

print("🚀 البوت شغال وجاهز لاستقبال المحاضرات...")
app.run()
