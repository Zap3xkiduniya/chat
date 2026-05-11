import json, os, random, string, asyncio
from telegram import Update
from telegram.ext import *
from cryptography.fernet import Fernet

BOT_TOKEN = "7521115416:AAGAcnY4hfw9Fju3FSRhxlBSX6_ii_86JJU"
ADMIN_ID = 6325764594
DB_FILE = "db.json"

# ---------- DATABASE ----------
def load():
    if not os.path.exists(DB_FILE):
        return {"rooms":{}, "users":{}}
    return json.load(open(DB_FILE))

def save(d):
    json.dump(d, open(DB_FILE,"w"))

db = load()

# ---------- HELPERS ----------
def gen_code():
    return ''.join(random.choices(string.ascii_uppercase+string.digits,k=6))

def encrypt(data,key):
    return Fernet(key.encode()).encrypt(data).decode()

async def get_dp(bot, user_id):
    photos = await bot.get_user_profile_photos(user_id, limit=1)
    if photos.total_count > 0:
        file = await bot.get_file(photos.photos[0][-1].file_id)
        return file.file_path
    return None

async def fake_typing(ctx,chat):
    await ctx.bot.send_chat_action(chat,"typing")
    await asyncio.sleep(1.5)

async def delete_later(ctx,chat,msg,t):
    await asyncio.sleep(t)
    try:
        await ctx.bot.delete_message(chat,msg)
    except: pass

# ---------- ADMIN CREATE ROOM ----------
async def gen(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    limit=int(ctx.args[0])
    code=gen_code()
    db["rooms"][code]={
        "max":limit,
        "members":[],
        "key":Fernet.generate_key().decode(),
        "timer":0
    }
    save(db)
    await update.message.reply_text(f"🔑 ROOM KEY: {code}")

# ---------- JOIN ROOM ----------
async def redeem(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    uid=str(update.effective_user.id)
    code=ctx.args[0].upper()

    if code not in db["rooms"]:
        return await update.message.reply_text("❌ Invalid key")

    room=db["rooms"][code]
    if len(room["members"])>=room["max"]:
        return await update.message.reply_text("🚫 Room full")

    room["members"].append(uid)
    db["users"][uid]={"room":code,"name":"Anon"}
    save(db)

    await update.message.reply_text("🔐 Joined Private Chat")

# ---------- USERNAME ----------
async def name(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    uid=str(update.effective_user.id)
    if uid not in db["users"]: return
    db["users"][uid]["name"]=" ".join(ctx.args)
    save(db)
    await update.message.reply_text("✅ Name updated")

# ---------- TIMER ----------
async def timer(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    uid=str(update.effective_user.id)
    room=db["users"][uid]["room"]
    db["rooms"][room]["timer"]=int(ctx.args[0])
    save(db)
    await update.message.reply_text("⏳ Self-destruct ON")

# ---------- TEXT MESSAGE ----------
async def text_msg(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    uid=str(update.effective_user.id)
    if uid not in db["users"]: return

    room_code=db["users"][uid]["room"]
    room=db["rooms"][room_code]
    sender=db["users"][uid]["name"]

    enc=encrypt(update.message.text.encode(),room["key"])

    for member in room["members"]:
        if member!=uid:
            await fake_typing(ctx,member)
            dp=await get_dp(ctx.bot,uid)

            caption=f"👤 {sender}\n💬 {update.message.text}\n🔐 {enc}\n\n✓✓ Seen"

            if dp:
                msg=await ctx.bot.send_photo(member,dp,caption=caption)
            else:
                msg=await ctx.bot.send_message(member,caption)

            if room["timer"]>0:
                await delete_later(ctx,member,msg.message_id,room["timer"])

# ---------- PHOTO ----------
async def photo(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    uid=str(update.effective_user.id)
    if uid not in db["users"]: return

    room=db["rooms"][db["users"][uid]["room"]]
    sender=db["users"][uid]["name"]

    file=await update.message.photo[-1].get_file()
    path="temp.jpg"
    await file.download_to_drive(path)

    for m in room["members"]:
        if m!=uid:
            await fake_typing(ctx,m)
            msg=await ctx.bot.send_photo(m,open(path,"rb"),caption=f"📷 Photo from {sender}\n✓✓ Seen")
            if room["timer"]>0:
                await delete_later(ctx,m,msg.message_id,room["timer"])

# ---------- START ----------
app=ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("gen",gen))
app.add_handler(CommandHandler("redeem",redeem))
app.add_handler(CommandHandler("name",name))
app.add_handler(CommandHandler("timer",timer))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_msg))
app.add_handler(MessageHandler(filters.PHOTO,photo))

print("🔥 PRIVATE CHAT BOT RUNNING")
app.run_polling()