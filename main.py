import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
from database import init_db, add_user, get_user_data, complete_task_reward, reduce_balance
from keep_alive import keep_alive

# --- ⚠️ CONFIGURATION ⚠️ ---
TOKEN = "7249424955:AAHINVDcb5mMCh1p_o_iW3LDcCl3zbS-63A"   # <--- APNA TOKEN YAHAN DALEIN

MAIN_CHANNEL = "@PersonalFinanceWithShiv"
ADMIN_USERNAME = "Mr_MorningStar524"

# Task Channels
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

async def get_next_pending_channel_index(user_id, bot):
    for index, ch in enumerate(TASK_CHANNELS):
        if not await check_subscription(user_id, ch, bot):
            return index
    return -1

async def get_missing_channels(user_id, bot):
    missing = []
    if not await check_subscription(user_id, MAIN_CHANNEL, bot):
        missing.append(MAIN_CHANNEL)
    for ch in TASK_CHANNELS:
        if not await check_subscription(user_id, ch, bot):
            missing.append(ch)
    return missing

# --- Premium Menus ---
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(f"🚀 Start Tasks | Earn {CURRENCY}{TOTAL_TASK_REWARD}", callback_data="start_task_flow")],
        [InlineKeyboardButton("💼 Wallet", callback_data="balance"), InlineKeyboardButton("💎 Refer & Earn", callback_data="invite")],
        [InlineKeyboardButton("🏦 Withdraw Funds", callback_data="withdraw")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Premium Text Generators ---
def get_welcome_message(user_name):
    return (
        f"💎 **REWARD VAULT** | ᴠɪᴘ ᴅᴀsʜʙᴏᴀʀᴅ\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 **Hello, {user_name}!**\n\n"
        f"🚀 **Ready to monetize your time?**\n"
        f"Complete premium tasks & invite friends to earn real cash instantly.\n\n"
        f"📊 **CURRENT PAYOUT RATES:**\n"
        f"➤ 📂 **Task Bundle:** `{CURRENCY}{TOTAL_TASK_REWARD:.2f}`\n"
        f"➤ 👥 **Per Referral:** `{CURRENCY}{REFER_REWARD:.2f}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 *Access your dashboard below:*"
    )

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # Entry Check
    if not await check_subscription(user_id, MAIN_CHANNEL, context.bot):
        join_text = (
            f"🔒 **ACCESS RESTRICTED**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ **Verification Required**\n\n"
            f"To access the **Reward Vault**, you must be a member of our official channel.\n\n"
            f"👉 **Channel:** {MAIN_CHANNEL}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👇 *Join below & click Verify:*"
        )
        keyboard = [
            [InlineKeyboardButton("🚀 Join Official Channel", url=f"https://t.me/{MAIN_CHANNEL.replace('@', '')}")],
            [InlineKeyboardButton("✅ Verify Access", callback_data="check_join_main")]
        ]
        await update.message.reply_text(join_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return

    # DB Entry
    args = context.args
    referrer_id = None
    if args and args[0].isdigit():
        referrer_id = int(args[0])
        if referrer_id == user_id: referrer_id = None

    is_new = await add_user(user_id, referrer_id, REFER_REWARD)
    if is_new and referrer_id:
        try:
            await context.bot.send_message(chat_id=referrer_id, text=f"🎉 **New Referral!**\nReward: +{CURRENCY}{REFER_REWARD}", parse_mode=ParseMode.MARKDOWN)
        except: pass

    await update.message.reply_text(get_welcome_message(user.first_name), reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)

# --- BUTTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    bot = context.bot
    await query.answer()

    if data == "check_join_main":
        if await check_subscription(user_id, MAIN_CHANNEL, bot):
            await add_user(user_id)
            await query.message.edit_text(get_welcome_message(query.from_user.first_name), reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
        else:
            await query.answer("❌ Access Denied! Join the channel first.", show_alert=True)

    # --- STEP-BY-STEP TASKS (Premium Design) ---
    elif data == "start_task_flow" or data == "verify_step":
        user_data = await get_user_data(user_id)
        if user_data and user_data[2] == 1:
             await query.message.edit_text(
                 f"✅ **TASK COMPLETED**\n━━━━━━━━━━━━━━━━\nYou have already claimed the **{CURRENCY}{TOTAL_TASK_REWARD}** reward.\nCheck back later for more.",
                 reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
             return

        next_index = await get_next_pending_channel_index(user_id, bot)

        # Completion
        if next_index == -1:
            if await complete_task_reward(user_id, TOTAL_TASK_REWARD):
                success_text = (
                    f"🎉 **CONGRATULATIONS!**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"✅ **All Steps Verification Successful.**\n\n"
                    f"💵 **Credit Amount:** `{CURRENCY}{TOTAL_TASK_REWARD:.2f}`\n"
                    f"💼 **Status:** Added to Wallet\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🚀 *Keep earning by inviting friends!*"
                )
                await query.message.edit_text(success_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
            else:
                await query.message.edit_text("⚠️ **Reward Already Claimed.**", reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
            return

        # Pending Step
        current_channel = TASK_CHANNELS[next_index]
        clean_name = current_channel.replace("@", "").replace("_", " ")
        
        step_text = (
            f"📋 **TASK PROGRESS** | Step {next_index + 1}/{len(TASK_CHANNELS)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"To proceed, please join the following channel:\n\n"
            f"📢 **Target:** {current_channel}\n"
            f"💰 **Step Value:** `{CURRENCY}{REWARD_PER_CHANNEL:.2f}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 *Join below & Click Verify to continue:*"
        )
        
        keyboard = [
            [InlineKeyboardButton(f"🔹 Join {clean_name} ↗️", url=f"https://t.me/{current_channel.replace('@', '')}")],
            [InlineKeyboardButton("✅ Verify & Next Step ➡️", callback_data="verify_step")]
        ]
        
        try: await query.message.edit_text(step_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        except: pass

    # --- WALLET / INVITE / WITHDRAW (Premium Design) ---
    elif data in ["withdraw", "invite", "balance"]:
        missing = await get_missing_channels(user_id, bot)
        if missing:
            error_text = (
                f"🚫 **ACTION BLOCKED**\n━━━━━━━━━━━━━━━\n"
                f"⚠️ **Membership Inactive**\n"
                f"You have unsubscribed from required channels.\n\n"
                f"👇 **Please Re-Join to Unlock:**\n"
            ) + "\n".join([f"🔸 {ch}" for ch in missing])
            btns = [[InlineKeyboardButton(f"Join {ch.replace('@','')}", url=f"https://t.me/{ch.replace('@','')}") for ch in missing]]
            btns.append([InlineKeyboardButton("🔄 Refresh Status", callback_data="check_join_main")])
            await query.message.edit_text(error_text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)
            return

        if data == "balance":
            d = await get_user_data(user_id)
            bal_text = (
                f"💳 **USER WALLET**\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"💵 **Available Balance:** `{CURRENCY}{d[0]:.2f}`\n"
                f"👥 **Total Referrals:** `{d[1]}`\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"🔓 **Min Withdrawal:** `{CURRENCY}{MIN_WITHDRAW:.2f}`"
            )
            await query.message.edit_text(bal_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)

        elif data == "invite":
            link = f"https://t.me/{context.bot.username}?start={user_id}"
            invite_text = (
                f"🤝 **REFER & EARN PROGRAM**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Invite friends and earn cash instantly!\n\n"
                f"🎁 **Per Valid Refer:** `{CURRENCY}{REFER_REWARD:.2f}`\n"
                f"🔗 **Your Exclusive Link:**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"`{link}`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"*(Tap the link above to copy)*"
            )
            await query.message.edit_text(invite_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)

        elif data == "withdraw":
            d = await get_user_data(user_id)
            if d[0] >= MIN_WITHDRAW:
                await query.message.edit_text(
                    f"✅ **WITHDRAWAL UNLOCKED**\n━━━━━━━━━━━━━━━━\nYour balance is sufficient.\n\n📩 **Send details to Admin:**\n👤 @{ADMIN_USERNAME}",
                    reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN
                )
            else:
                await query.answer(f"❌ Balance Low! Min: {CURRENCY}{MIN_WITHDRAW}", show_alert=True)

async def admin_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username != ADMIN_USERNAME: return
    try:
        uid, amt = int(context.args[0]), float(context.args[1])
        new_bal = await reduce_balance(uid, amt)
        if new_bal is not None:
            await update.message.reply_text(f"✅ **Processed!**\nRem: `{CURRENCY}{new_bal}`", parse_mode=ParseMode.MARKDOWN)
            try: await context.bot.send_message(uid, f"🏧 **PAYMENT RECEIVED**\n━━━━━━━━━━━━━━━\nAmount: `{CURRENCY}{amt}`\nStatus: ✅ Success", parse_mode=ParseMode.MARKDOWN)
            except: pass
    except: pass

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
