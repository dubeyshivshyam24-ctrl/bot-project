import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
from database import init_db, add_user, get_user_data, complete_task_reward, reduce_balance
from keep_alive import keep_alive

# --- ⚠️ CONFIGURATION (TOKEN YAHAN DALEIN) ⚠️ ---
TOKEN = "7249424955:AAHINVDcb5mMCh1p_o_iW3LDcCl3zbS-63A"

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

# --- MONEY SETTINGS ---
REWARD_PER_CHANNEL = 5.00   # ₹5 per channel
REFER_REWARD = 0.05         # ₹5 per Refer (Maine 5 kar diya hai professional look ke liye)
MIN_WITHDRAW = 500
CURRENCY = "₹"

TOTAL_TASK_REWARD = REWARD_PER_CHANNEL * len(TASK_CHANNELS)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Helper: Check Subscription ---
async def check_subscription(user_id, channel_username, bot):
    try:
        member = await bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        return member.status in ['creator', 'administrator', 'member']
    except:
        return False

# --- Menu Design ---
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(f"🚀 Start Tasks | Earn {CURRENCY}{TOTAL_TASK_REWARD}", callback_data="tasks")],
        [InlineKeyboardButton("💼 Wallet", callback_data="balance"), InlineKeyboardButton("🔥 Refer & Earn", callback_data="invite")],
        [InlineKeyboardButton("🏦 Withdraw Money", callback_data="withdraw")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- START COMMAND (New Premium Look) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # Force Subscribe Check
    if not await check_subscription(user_id, MAIN_CHANNEL, context.bot):
        join_text = (
            f"🚫 **Access Restricted**\n\n"
            f"To use the **Premium Reward Bot**, verification is required.\n\n"
            f"1️⃣ Join Official Channel: {MAIN_CHANNEL}\n"
            f"2️⃣ Click Verify below."
        )
        keyboard = [[InlineKeyboardButton("🚀 Join Official Channel", url=f"https://t.me/{MAIN_CHANNEL.replace('@', '')}")],
                    [InlineKeyboardButton("✅ Verify Access", callback_data="check_join_main")]]
        await update.message.reply_text(join_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return

    # Referral Logic
    args = context.args
    referrer_id = None
    if args and args[0].isdigit():
        referrer_id = int(args[0])
        if referrer_id == user_id: referrer_id = None

    is_new = await add_user(user_id, referrer_id, REFER_REWARD)
    
    if is_new and referrer_id:
        try:
            await context.bot.send_message(chat_id=referrer_id, text=f"🎉 **New Referral!**\nUser: {user.first_name}\nReward: +{CURRENCY}{REFER_REWARD}", parse_mode=ParseMode.MARKDOWN)
        except: pass

    # --- PROFESSIONAL WELCOME MESSAGE ---
    welcome_text = (
        f"👋 **Welcome, {user.first_name}!**\n\n"
        f"Ready to monetize your time? Complete simple tasks and get paid instantly.\n\n"
        f"📊 **Current Payout Rates:**\n"
        f"├ 📂 **Task Bundle:** `{CURRENCY}{TOTAL_TASK_REWARD:.2f}`\n"
        f"└ 🗣️ **Per Referral:** `{CURRENCY}{REFER_REWARD:.2f}`\n\n"
        f"👇 *Tap a button below to start earning:*"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)

# --- ADMIN PAID COMMAND ---
async def admin_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username != ADMIN_USERNAME: return

    try:
        target_user_id = int(context.args[0])
        amount = float(context.args[1])
        new_bal = await reduce_balance(target_user_id, amount)
        if new_bal is not None:
            await update.message.reply_text(f"✅ **Transfer Complete**\nUser: `{target_user_id}`\nSent: `{CURRENCY}{amount}`", parse_mode=ParseMode.MARKDOWN)
            try: await context.bot.send_message(chat_id=target_user_id, text=f"🏧 **Withdrawal Successful**\n\nAmount: `{CURRENCY}{amount}` has been credited to your account. ✅", parse_mode=ParseMode.MARKDOWN)
            except: pass
        else: await update.message.reply_text("❌ Failed")
    except: await update.message.reply_text("Use: `/paid ID Amount`")

# --- BUTTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    if data == "check_join_main":
        if await check_subscription(user_id, MAIN_CHANNEL, context.bot):
            await add_user(user_id)
            await query.message.edit_text(f"✅ **Access Granted!**\nWelcome {query.from_user.first_name}.", reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
        else: await query.answer("❌ Please join the channel first!", show_alert=True)

    elif data == "tasks":
        user_data = await get_user_data(user_id)
        if user_data and user_data[2] == 1:
            await query.message.reply_text("✅ **Task Completed!**\nYou have already claimed this reward.", parse_mode=ParseMode.MARKDOWN); return
        
        # --- PROFESSIONAL TASK LIST ---
        task_text = (
            f"📋 **Premium Task Bundle**\n\n"
            f"Complete the steps below to unlock your reward.\n\n"
            f"💰 **Reward Value:** `{CURRENCY}{TOTAL_TASK_REWARD:.2f}`\n"
            f"👇 **Action Required:** Join these channels:"
        )
        btns = [[InlineKeyboardButton(f"🔹 Join {ch.replace('@','')}", url=f"https://t.me/{ch.replace('@','')}")] for ch in TASK_CHANNELS]
        btns.append([InlineKeyboardButton(f"💸 Claim {CURRENCY}{TOTAL_TASK_REWARD:.2f} Reward", callback_data="claim_task")])
        await query.message.reply_text(task_text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)

    elif data == "claim_task":
        not_joined = [ch for ch in TASK_CHANNELS if not await check_subscription(user_id, ch, context.bot)]
        if not not_joined:
            if await complete_task_reward(user_id, TOTAL_TASK_REWARD):
                await query.message.reply_text(f"🎉 **Task Verified!**\n\n`{CURRENCY}{TOTAL_TASK_REWARD:.2f}` has been added to your wallet.", parse_mode=ParseMode.MARKDOWN)
            else: await query.message.reply_text("⚠️ Reward already claimed.", parse_mode=ParseMode.MARKDOWN)
        else: await query.message.reply_text(f"❌ **Incomplete!**\nJoin these remaining channels:\n" + "\n".join(not_joined), parse_mode=ParseMode.MARKDOWN)

    elif data == "balance":
        d = await get_user_data(user_id)
        # --- PROFESSIONAL WALLET ---
        bal_text = (
            f"💳 **Your Wallet**\n\n"
            f"💵 **Available Balance:** `{CURRENCY}{d[0]:.2f}`\n"
            f"👥 **Total Referrals:** `{d[1]}`\n\n"
            f"min withdrawal: {CURRENCY}{MIN_WITHDRAW}"
        )
        await query.message.reply_text(bal_text, parse_mode=ParseMode.MARKDOWN)

    elif data == "invite":
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        # --- CLICKABLE LINK DESIGN ---
        invite_text = (
            f"🤝 **Refer & Earn Program**\n\n"
            f"Share your exclusive link with friends. When they join, you get paid!\n\n"
            f"🎁 **Reward:** `{CURRENCY}{REFER_REWARD:.2f}` per user\n\n"
            f"🔗 **Your Personal Link:**\n"
            f"`{link}`\n"
            f"*(Tap the link above to copy)*"
        )
        await query.message.reply_text(invite_text, parse_mode=ParseMode.MARKDOWN)

    elif data == "withdraw":
        d = await get_user_data(user_id)
        if d[0] >= MIN_WITHDRAW: await query.message.reply_text(f"✅ **Withdrawal Unlocked**\n\nSend your UPI/Bank details to:\n👤 @{ADMIN_USERNAME}", parse_mode=ParseMode.MARKDOWN)
        else: await query.answer(f"❌ Insufficient Balance! Min: {CURRENCY}{MIN_WITHDRAW}", show_alert=True)

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
