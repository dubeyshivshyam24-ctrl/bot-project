import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
from database import init_db, add_user, get_user_data, complete_task_reward, reduce_balance
from keep_alive import keep_alive

# --- ⚠️ CONFIGURATION (Yahan Token Dalein) ⚠️ ---
TOKEN = "7249424955:AAHINVDcb5mMCh1p_o_iW3LDcCl3zbS-63A"  # <--- Yahan apna Token paste karein

MAIN_CHANNEL = "@PersonalFinanceWithShiv"
ADMIN_USERNAME = "Mr_MorningStar524"

# Task Channels List
TASK_CHANNELS = [
    "@IAS_PrepQuiz_Zone",
    "@UPSC_Quiz_Vault",
    "@English_Speaking_Grammar_Shots",
    "@The_EnglishRoom5",
    "@SarkariJobsUpdateHub",
    "@GovernmentSchemesIndia",
    "@MinistryOfTourism"
]

# --- SETTINGS ---
REWARD_PER_CHANNEL = 5.00   
REFER_REWARD = 0.05        
MIN_WITHDRAW = 500        
CURRENCY = "₹"

TOTAL_TASK_REWARD = REWARD_PER_CHANNEL * len(TASK_CHANNELS)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Helper Functions ---
async def check_subscription(user_id, channel_username, bot):
    try:
        member = await bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        return member.status in ['creator', 'administrator', 'member']
    except:
        return False

# --- Main Menu ---
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(f"📋 Start Tasks (Earn {CURRENCY}{TOTAL_TASK_REWARD})", callback_data="tasks")],
        [InlineKeyboardButton("💼 Wallet", callback_data="balance"), InlineKeyboardButton("👫 Refer", callback_data="invite")],
        [InlineKeyboardButton("🏦 Withdraw", callback_data="withdraw")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if not await check_subscription(user_id, MAIN_CHANNEL, context.bot):
        join_text = (
            f"🔒 **Access Locked!**\n\n"
            f"Join our official channel first:\n👉 {MAIN_CHANNEL}\n\n"
            f"Then click **'Verify Joined'**"
        )
        keyboard = [[InlineKeyboardButton("🚀 Join Channel", url=f"https://t.me/{MAIN_CHANNEL.replace('@', '')}")],
                    [InlineKeyboardButton("✅ Verify Joined", callback_data="check_join_main")]]
        await update.message.reply_text(join_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return

    args = context.args
    referrer_id = None
    if args and args[0].isdigit():
        referrer_id = int(args[0])
        if referrer_id == user_id: referrer_id = None

    is_new = await add_user(user_id, referrer_id, REFER_REWARD)
    
    if is_new and referrer_id:
        try:
            await context.bot.send_message(chat_id=referrer_id, text=f"🎉 **New Referral!**\n+{CURRENCY}{REFER_REWARD} added!", parse_mode=ParseMode.MARKDOWN)
        except: pass

    welcome_text = (
        f"💎 **Welcome, {user.first_name}!**\n\n"
        f"Earn money by completing tasks.\n\n"
        f"💰 **Rates:**\n• Join Channels: **{CURRENCY}{TOTAL_TASK_REWARD}**\n• Refer: **{CURRENCY}{REFER_REWARD}**"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)

async def admin_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username != ADMIN_USERNAME: return

    try:
        target_user_id = int(context.args[0])
        amount = float(context.args[1])
        new_bal = await reduce_balance(target_user_id, amount)
        if new_bal is not None:
            await update.message.reply_text(f"✅ **Paid!**\nRemaining: {CURRENCY}{new_bal}", parse_mode=ParseMode.MARKDOWN)
            try: await context.bot.send_message(chat_id=target_user_id, text=f"💳 **Withdrawal of {CURRENCY}{amount} Sent!** ✅", parse_mode=ParseMode.MARKDOWN)
            except: pass
        else: await update.message.reply_text("❌ Error")
    except: await update.message.reply_text("Usage: `/paid UserID Amount`")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    if data == "check_join_main":
        if await check_subscription(user_id, MAIN_CHANNEL, context.bot):
            await add_user(user_id)
            await query.message.edit_text(f"✅ **Verified!**\nWelcome {query.from_user.first_name}.", reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
        else: await query.answer("❌ Join the channel first!", show_alert=True)

    elif data == "tasks":
        user_data = await get_user_data(user_id)
        if user_data and user_data[2] == 1:
            await query.message.reply_text("✅ **Task Completed!**", parse_mode=ParseMode.MARKDOWN); return
        
        task_text = f"📋 **Tasks:**\nJoin below channels to earn **{CURRENCY}{TOTAL_TASK_REWARD}**!\n"
        btns = [[InlineKeyboardButton(f"🔹 Join {ch.replace('@','')}", url=f"https://t.me/{ch.replace('@','')}")] for ch in TASK_CHANNELS]
        btns.append([InlineKeyboardButton(f"💰 Claim {CURRENCY}{TOTAL_TASK_REWARD} 💰", callback_data="claim_task")])
        await query.message.reply_text(task_text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)

    elif data == "claim_task":
        not_joined = [ch for ch in TASK_CHANNELS if not await check_subscription(user_id, ch, context.bot)]
        if not not_joined:
            if await complete_task_reward(user_id, TOTAL_TASK_REWARD):
                await query.message.reply_text(f"🎉 **Success!** {CURRENCY}{TOTAL_TASK_REWARD} added!", parse_mode=ParseMode.MARKDOWN)
            else: await query.message.reply_text("⚠️ Already claimed.", parse_mode=ParseMode.MARKDOWN)
        else: await query.message.reply_text(f"❌ **Incomplete!** Join:\n" + "\n".join(not_joined), parse_mode=ParseMode.MARKDOWN)

    elif data == "balance":
        d = await get_user_data(user_id)
        await query.message.reply_text(f"💼 **Wallet**\n💰 Balance: `{CURRENCY}{d[0]:.2f}`\n👥 Refers: `{d[1]}`", parse_mode=ParseMode.MARKDOWN)

    elif data == "invite":
        await query.message.reply_text(f"🔗 **Link:**\n`https://t.me/{context.bot.username}?start={user_id}`\nEarn **{CURRENCY}{REFER_REWARD}** per refer!", parse_mode=ParseMode.MARKDOWN)

    elif data == "withdraw":
        d = await get_user_data(user_id)
        if d[0] >= MIN_WITHDRAW: await query.message.reply_text(f"✅ **Eligible!**\nMsg Admin: @{ADMIN_USERNAME}", parse_mode=ParseMode.MARKDOWN)
        else: await query.answer(f"❌ Min Withdraw: {CURRENCY}{MIN_WITHDRAW}", show_alert=True)

if __name__ == '__main__':
    keep_alive()
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("paid", admin_paid))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()
