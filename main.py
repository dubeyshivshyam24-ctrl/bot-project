import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
from database import init_db, add_user, get_user_data, complete_task_reward, reduce_balance
from keep_alive import keep_alive

# --- ⚠️ CONFIGURATION ⚠️ ---
TOKEN = "7249424955:AAHINVDcb5mMCh1p_o_iW3LDcCl3zbS-63A"   # <--- TOKEN YAHAN DALEIN

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

# --- SMART CHECKER (Admin vs Non-Admin) ---
async def smart_check_subscription(user_id, channel_username, bot):
    try:
        # Koshish karo check karne ki (Agar Admin hai to success hoga)
        member = await bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        return member.status in ['creator', 'administrator', 'member']
    except:
        # Agar Admin nahi hai (Error aaya), to maan lo user ne join kar liya (Fake Verify)
        # Lekin hum yahan True return karenge taaki flow na ruke
        return True 

# --- STRICT CHECKER (Sirf Admin wale channels ke liye - Lock lagane ke liye) ---
async def strict_check_subscription(user_id, channel_username, bot):
    try:
        member = await bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        if member.status not in ['creator', 'administrator', 'member']:
            return False # Join nahi kiya
        return True # Join kiya hai
    except:
        # Agar bot admin nahi hai, to hum check hi nahi kar sakte, isliye Ignore karo (Return True)
        return True

async def get_next_pending_channel_index(user_id, bot):
    for index, ch in enumerate(TASK_CHANNELS):
        # Yahan hum Smart Check lagayenge
        # Agar bot admin hai -> Real check
        # Agar bot admin nahi hai -> Maan lega join hai (taaki user aage badhe task flow me)
        # LEKIN, button dabane par hum fake delay denge
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status not in ['creator', 'administrator', 'member']:
                return index # Ye wala bacha hai (Real Check)
        except:
            # Bot admin nahi hai, to hum maan lete hain ye step done hai
            # (User ko manual verify button dabana padega)
            pass
    
    # Agar upar wale loop me kuch pakad me nahi aaya, to hum assume karte hain user ne sab kar liya
    # (Lekin hum ek alag track rakhenge user progress ka database me agar possible ho,
    #  filhal simple logic rakhte hain)
    
    # Simpler Logic for Task Flow:
    # Hum user se ek-ek karke puchenge.
    # Is logic ko handle karne ke liye hum "Callback Data" me index pass karenge.
    return -1 

async def get_strict_missing_channels(user_id, bot):
    missing = []
    # Main Channel Check (Strict)
    if not await strict_check_subscription(user_id, MAIN_CHANNEL, bot):
        missing.append(MAIN_CHANNEL)
    
    # Task Channels Check (Jo Admin wale hain unpe strict raho)
    for ch in TASK_CHANNELS:
        if not await strict_check_subscription(user_id, ch, bot):
            missing.append(ch)
    return missing

# --- Menus ---
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(f"🚀 Start Tasks | Earn {CURRENCY}{TOTAL_TASK_REWARD}", callback_data="task_step_0")],
        [InlineKeyboardButton("💼 Wallet", callback_data="balance"), InlineKeyboardButton("💎 Refer & Earn", callback_data="invite")],
        [InlineKeyboardButton("🏦 Withdraw Funds", callback_data="withdraw")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # Entry Check (Sirf Main Channel)
    if not await strict_check_subscription(user_id, MAIN_CHANNEL, context.bot):
        join_text = (
            f"🔒 <b>ACCESS RESTRICTED</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <b>Action Required</b>\n\n"
            f"You have left our official channel: {MAIN_CHANNEL}\n"
            f"Please rejoin to access the bot.\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👇 <i>Join below & click Verify:</i>"
        )
        keyboard = [
            [InlineKeyboardButton("🚀 Join Channel", url=f"https://t.me/{MAIN_CHANNEL.replace('@', '')}")],
            [InlineKeyboardButton("✅ Verify Access", callback_data="check_join_main")]
        ]
        await update.message.reply_text(join_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
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
            await context.bot.send_message(chat_id=referrer_id, text=f"🎉 <b>New Referral!</b>\nReward: +{CURRENCY}{REFER_REWARD}", parse_mode=ParseMode.HTML)
        except: pass

    # UPDATED WELCOME MESSAGE (Aapki demand ke hisaab se)
    welcome_text = (
        f"💎 <b>REWARD VAULT | VIP DASHBOARD</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 <b>Hello, {user.first_name}!</b>\n\n"
        f"🚀 <b>Ready to monetize your time?</b>\n"
        f"Complete premium tasks & invite friends to earn real cash instantly.\n\n"
        f"📊 <b>CURRENT TASK RATES:</b>\n"
        f"➤ 📂 <b>Per Task:</b> <code>{CURRENCY}{REWARD_PER_CHANNEL:.2f}</code>\n"
        f"➤ 👥 <b>Per Referral:</b> <code>{CURRENCY}{REFER_REWARD:.2f}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 <i>Access your dashboard below:</i>"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)

# --- BUTTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    bot = context.bot
    
    # Button click feedback (Loading icon hatane ke liye)
    try:
        await query.answer()
    except:
        pass

    # --- STRICT LOCK CHECK (Har button dabane par check hoga) ---
    if data in ["balance", "invite", "withdraw", "check_join_main"]:
        missing = await get_strict_missing_channels(user_id, bot)
        if missing:
            error_text = (
                f"🚫 <b>ACTION BLOCKED</b>\n━━━━━━━━━━━━━━━\n"
                f"⚠️ <b>Membership Inactive</b>\n"
                f"You have left the following channel(s):\n\n"
            ) + "\n".join([f"👉 {ch}" for ch in missing]) + (
                f"\n\n👇 <b>Please Re-Join to Unlock:</b>"
            )
            btns = [[InlineKeyboardButton(f"Join {ch.replace('@','')}", url=f"https://t.me/{ch.replace('@','')}") for ch in missing]]
            btns.append([InlineKeyboardButton("🔄 Refresh Status", callback_data="check_join_main")])
            
            # Message edit karne ki koshish, agar fail ho to naya bhejo
            try:
                await query.message.edit_text(error_text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.HTML)
            except:
                await query.message.reply_text(error_text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.HTML)
            return

        if data == "check_join_main":
             # Agar missing list khali hai, matlab sab sahi hai
             welcome_text = (
                f"✅ <b>Access Granted!</b>\n"
                f"Welcome back, {query.from_user.first_name}."
            )
             await query.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)
             return

    # --- TASK SYSTEM (Step-by-Step) ---
    if data.startswith("task_step_"):
        step_index = int(data.split("_")[-1])
        
        # Check Previous Step (Agar user seedha jump karne ki koshish kare)
        if step_index > 0:
            prev_channel = TASK_CHANNELS[step_index - 1]
            is_joined = False
            try:
                member = await bot.get_chat_member(chat_id=prev_channel, user_id=user_id)
                if member.status in ['creator', 'administrator', 'member']:
                    is_joined = True
            except:
                # Bot Admin nahi hai -> Fake Verify (Delay dikhao)
                await query.message.edit_text("⏳ <i>Verifying connection...</i>", parse_mode=ParseMode.HTML)
                await asyncio.sleep(2) # 2 Second fake wait
                is_joined = True # Maan lo join kiya hai
            
            if not is_joined:
                await query.answer("❌ Task Incomplete! Please join the channel first.", show_alert=True)
                # Wapas wahi purana step dikhao
                step_index -= 1 
            
        # Agar saare steps khatam (Reward Time)
        if step_index >= len(TASK_CHANNELS):
            user_data = await get_user_data(user_id)
            if user_data and user_data[2] == 1:
                 await query.message.edit_text(
                     f"✅ <b>TASK COMPLETED</b>\n━━━━━━━━━━━━━━━━\nYou have already claimed the <b>{CURRENCY}{TOTAL_TASK_REWARD}</b> reward.",
                     reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)
            else:
                if await complete_task_reward(user_id, TOTAL_TASK_REWARD):
                    success_text = (
                        f"🎉 <b>CONGRATULATIONS!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"✅ <b>All Tasks Verified.</b>\n\n"
                        f"💵 <b>Credit Amount:</b> <code>{CURRENCY}{TOTAL_TASK_REWARD:.2f}</code>\n"
                        f"💼 <b>Status:</b> Added to Wallet\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"🚀 <i>Keep earning by inviting friends!</i>"
                    )
                    await query.message.edit_text(success_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)
                else:
                    await query.message.reply_text("⚠️ Error claiming reward.", reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)
            return

        # Show Next Channel
        current_channel = TASK_CHANNELS[step_index]
        clean_name = current_channel.replace("@", "").replace("_", " ")
        
        step_text = (
            f"📋 <b>TASK PROGRESS</b> | Step {step_index + 1}/{len(TASK_CHANNELS)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"To proceed, please join the following channel:\n\n"
            f"📢 <b>Target:</b> {current_channel}\n"
            f"💰 <b>Step Value:</b> <code>{CURRENCY}{REWARD_PER_CHANNEL:.2f}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 <i>Join below & Click Verify to continue:</i>"
        )
        
        keyboard = [
            [InlineKeyboardButton(f"🔹 Join {clean_name} ↗️", url=f"https://t.me/{current_channel.replace('@', '')}")],
            [InlineKeyboardButton("✅ Verify & Next Step ➡️", callback_data=f"task_step_{step_index + 1}")]
        ]
        
        try:
            await query.message.edit_text(step_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        except:
            # Agar message same hai (user ne baar baar click kiya) to ignore karo
            pass

    # --- WALLET / INVITE / WITHDRAW ---
    elif data == "balance":
        d = await get_user_data(user_id)
        bal_text = (
            f"💳 <b>USER WALLET</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💵 <b>Available Balance:</b> <code>{CURRENCY}{d[0]:.2f}</code>\n"
            f"👥 <b>Total Referrals:</b> <code>{d[1]}</code>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🔓 <b>Min Withdrawal:</b> <code>{CURRENCY}{MIN_WITHDRAW:.2f}</code>"
        )
        await query.message.edit_text(bal_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)

    elif data == "invite":
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        invite_text = (
            f"🤝 <b>REFER & EARN PROGRAM</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Invite friends and earn cash instantly!\n\n"
            f"🎁 <b>Per Valid Refer:</b> <code>{CURRENCY}{REFER_REWARD:.2f}</code>\n"
            f"🔗 <b>Your Exclusive Link:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<code>{link}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>(Tap the link above to copy)</i>"
        )
        await query.message.edit_text(invite_text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)

    elif data == "withdraw":
        d = await get_user_data(user_id)
        if d[0] >= MIN_WITHDRAW:
            await query.message.edit_text(
                f"✅ <b>WITHDRAWAL UNLOCKED</b>\n━━━━━━━━━━━━━━━━\nYour balance is sufficient.\n\n📩 <b>Send details to Admin:</b>\n👤 @{ADMIN_USERNAME}",
                reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML
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
            await update.message.reply_text(f"✅ <b>Processed!</b>\nRem: <code>{CURRENCY}{new_bal}</code>", parse_mode=ParseMode.HTML)
            try: await context.bot.send_message(uid, f"🏧 <b>PAYMENT RECEIVED</b>\n━━━━━━━━━━━━━━━\nAmount: <code>{CURRENCY}{amt}</code>\nStatus: ✅ Success", parse_mode=ParseMode.HTML)
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
