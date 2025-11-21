import logging, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from database import init_db, add_user, get_user_data, complete_task_reward, reduce_balance
from keep_alive import keep_alive

# --- YAHAN EDIT KARNA HAI ---
TOKEN = "7249424955:AAHINVDcb5mMCh1p_o_iW3LDcCl3zbS-63A"  # BotFather wala token yahan chipkao
MAIN_CHANNEL = "@PersonalFinanceWithShiv"   # Apna Channel username
ADMIN_USERNAME = "Mr_MorningStar524"    # Apna khud ka username (bina @ ke)
TASK_CHANNELS = ["@IAS_PrepQuiz_Zone", "@UPSC_Quiz_Vault", "@The_EnglishRoom5", "@SarkariJobsUpdateHub","@English_Speaking_Grammar_Shots","@MinistryOfTourism","@GovernmentSchemesIndia"] # Task wale channels

REFER_REWARD = 0.05
TASK_REWARD = 5.0
MIN_WITHDRAW = 500.0

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def check(user_id, ch, bot):
    try:
        m = await bot.get_chat_member(ch, user_id)
        return m.status in ['creator', 'administrator', 'member']
    except: return False

async def start(update: Update, context):
    u = update.effective_user
    if not await check(u.id, MAIN_CHANNEL, context.bot):
        kb = [[InlineKeyboardButton("Join Channel", url=f"https://t.me/{MAIN_CHANNEL.replace('@','')}")], [InlineKeyboardButton("Check ✅", callback_data="chk")]]
        await update.message.reply_text(f"Join {MAIN_CHANNEL} first!", reply_markup=InlineKeyboardMarkup(kb))
        return

    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() and int(context.args[0]) != u.id else None
    if await add_user(u.id, ref_id, REFER_REWARD) and ref_id:
        try: await context.bot.send_message(ref_id, f"🎉 New Refer! +₹{REFER_REWARD}")
        except: pass
    await menu(update, u)

async def menu(update, user):
    kb = [[InlineKeyboardButton("Task (₹5)", callback_data="task")], [InlineKeyboardButton("Wallet", callback_data="bal"), InlineKeyboardButton("Invite", callback_data="inv")], [InlineKeyboardButton("Withdraw", callback_data="with")]]
    await update.message.reply_text(f"Hi {user.first_name}!", reply_markup=InlineKeyboardMarkup(kb))

async def btn(update: Update, context):
    q = update.callback_query
    uid = q.from_user.id
    d = q.data
    await q.answer()

    if d == "chk":
        if await check(uid, MAIN_CHANNEL, context.bot): await add_user(uid); await menu(update, q.from_user)
        else: await q.answer("Not Joined!", show_alert=True)
    elif d == "task":
        u = await get_user_data(uid)
        if u[2]: await q.message.reply_text("✅ Already Done!"); return
        kb = [[InlineKeyboardButton(f"Join {c}", url=f"https://t.me/{c.replace('@','')}")] for c in TASK_CHANNELS] + [[InlineKeyboardButton("Claim Reward", callback_data="clm")]]
        await q.message.reply_text("Join All:", reply_markup=InlineKeyboardMarkup(kb))
    elif d == "clm":
        rem = [c for c in TASK_CHANNELS if not await check(uid, c, context.bot)]
        if not rem: 
            if await complete_task_reward(uid, TASK_REWARD): await q.message.reply_text(f"🎉 ₹{TASK_REWARD} Added!")
            else: await q.message.reply_text("Already claimed.")
        else: await q.message.reply_text(f"❌ Join pending: {rem}")
    elif d == "bal":
        u = await get_user_data(uid)
        await q.message.reply_text(f"💰 ₹{u[0]:.2f}\n👥 Refers: {u[1]}")
    elif d == "inv":
        await q.message.reply_text(f"Link: https://t.me/{context.bot.username}?start={uid}")
    elif d == "with":
        u = await get_user_data(uid)
        if u[0] >= MIN_WITHDRAW: await q.message.reply_text(f"✅ Msg Admin @{ADMIN_USERNAME} for Withdraw")
        else: await q.message.reply_text(f"❌ Min ₹{MIN_WITHDRAW}", show_alert=True)

async def paid(update: Update, context):
    if update.effective_user.username != ADMIN_USERNAME: return
    try:
        uid, amt = int(context.args[0]), float(context.args[1])
        res = await reduce_balance(uid, amt)
        if res is not None: await update.message.reply_text(f"✅ Done. Bal: {res}"); await context.bot.send_message(uid, f"✅ Paid ₹{amt}")
        else: await update.message.reply_text("❌ Error")
    except: await update.message.reply_text("/paid ID AMOUNT")

if __name__ == '__main__':
    keep_alive()
    import asyncio
    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop); loop.run_until_complete(init_db())
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("paid", paid)); app.add_handler(CallbackQueryHandler(btn))
    app.run_polling()
