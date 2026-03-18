import os
import re
import time
import requests
import asyncio
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("8433156210:AAHxAD_eEpwpOqAhDIDjXVGlhBsKfo9Ow8A", "")
TIMEOUT = 8
WORKERS = 50

# ─── M3U PARSE ───────────────────────────────────────────
def parse_m3u(content):
    channels = []
    lines = content.strip().splitlines()
    i = 1 if lines and lines[0].strip().startswith('#EXTM3U') else 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF'):
            name = re.search(r',(.+)$', line)
            name = name.group(1).strip() if name else "Nomsiz"
            group = re.search(r'group-title="([^"]*)"', line)
            group = group.group(1) if group else "Boshqa"
            logo = re.search(r'tvg-logo="([^"]*)"', line)
            logo = logo.group(1) if logo else ""
            i += 1
            while i < len(lines) and lines[i].strip().startswith('#'):
                i += 1
            if i < len(lines):
                url = lines[i].strip()
                if url and not url.startswith('#'):
                    channels.append({'name': name, 'url': url, 'group': group, 'logo': logo})
        i += 1
    return channels

# ─── STREAM TEKSHIRISH ───────────────────────────────────
def check_stream(ch):
    try:
        r = requests.get(
            ch['url'], timeout=TIMEOUT, stream=True,
            headers={'User-Agent': 'Mozilla/5.0 (SMART-TV; Linux; Tizen 5.0)'},
            allow_redirects=True
        )
        if r.status_code in (200, 206):
            data = b''
            for chunk in r.iter_content(512):
                data += chunk
                if len(data) >= 200:
                    break
            if len(data) > 10:
                return ch, True
    except:
        pass
    return ch, False

# ─── KANALLARNI TEKSHIRISH ───────────────────────────────
def run_checker(channels):
    working = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(check_stream, ch): ch for ch in channels}
        for f in as_completed(futures):
            ch, ok = f.result()
            if ok:
                working.append(ch)
    return working

def save_m3u(channels):
    lines = ['#EXTM3U\n']
    for ch in channels:
        lines.append(f'#EXTINF:-1 tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]}\n')
        lines.append(ch['url'] + '\n')
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.m3u', delete=False, encoding='utf-8')
    tmp.writelines(lines)
    tmp.close()
    return tmp.name

# ─── BOT HANDLERLAR ──────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📺 *IPTV Playlist Checker Botga xush kelibsiz!*\n\n"
        "Bu bot M3U pleylistdagi ishlaydigan kanallarni topadi.\n\n"
        "*Qanday ishlatish:*\n"
        "1️⃣ M3U pleylist URL ni yuboring\n"
        "2️⃣ Bot tekshiradi va natijani yuboradi\n\n"
        "*Misol:*\n"
        "`https://example.com/playlist.m3u`\n\n"
        "🆓 Bepul xizmat!"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ *Yordam*\n\n"
        "• M3U URL yuboring → bot ishlaydigan kanallarni topadi\n"
        "• Natija `.m3u` fayl ko'rinishida yuboriladi\n"
        "• TiviMate, IPTV Smarters, VLC bilan ishlaydi\n\n"
        "*Buyruqlar:*\n"
        "/start — Botni ishga tushirish\n"
        "/help — Yordam\n"
        "/stats — Statistika"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = context.bot_data.get('total_checked', 0)
    users = context.bot_data.get('unique_users', set())
    text = (
        f"📊 *Bot statistikasi:*\n\n"
        f"👥 Foydalanuvchilar: `{len(users)}`\n"
        f"🔍 Tekshirilgan kanallar: `{total}`\n"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id

    # URL tekshirish
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "❌ Noto'g'ri URL!\n\nM3U pleylist linkini yuboring.\nMisol: `https://example.com/playlist.m3u`",
            parse_mode='Markdown'
        )
        return

    msg = await update.message.reply_text("⏳ Pleylist yuklanmoqda...")

    try:
        # M3U yuklab olish
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code != 200:
            await msg.edit_text(f"❌ Pleylist yuklanmadi! Status: {resp.status_code}")
            return

        content = resp.text
        channels = parse_m3u(content)

        if not channels:
            await msg.edit_text("❌ Pleylistda kanal topilmadi!")
            return

        total = len(channels)
        await msg.edit_text(
            f"🔍 *{total} ta kanal topildi*\n\n"
            f"⏳ Tekshirilmoqda... (~{total // 100 + 1} daqiqa)\n"
            f"Iltimos kuting...",
            parse_mode='Markdown'
        )

        # Tekshirish
        start_time = time.time()
        loop = asyncio.get_event_loop()
        working = await loop.run_in_executor(None, run_checker, channels)
        elapsed = time.time() - start_time

        if not working:
            await msg.edit_text("😔 Ishlaydigan kanal topilmadi!")
            return

        # Statistika yangilash
        context.bot_data['total_checked'] = context.bot_data.get('total_checked', 0) + total
        users = context.bot_data.get('unique_users', set())
        users.add(user_id)
        context.bot_data['unique_users'] = users

        # Fayl saqlash
        filepath = save_m3u(working)
        pct = len(working) / total * 100

        # Guruhlar
        groups = {}
        for ch in working:
            g = ch['group']
            groups[g] = groups.get(g, 0) + 1
        top_groups = sorted(groups.items(), key=lambda x: -x[1])[:5]
        groups_text = "\n".join([f"  • {g}: {c}" for g, c in top_groups])

        caption = (
            f"✅ *Tekshirish yakunlandi!*\n\n"
            f"📊 *Natija:*\n"
            f"🟢 Ishlaydigan: `{len(working)}` ({pct:.1f}%)\n"
            f"🔴 Ishlamaydi: `{total - len(working)}`\n"
            f"⏱ Vaqt: `{elapsed:.0f}` soniya\n\n"
            f"📁 *Top guruhlar:*\n{groups_text}\n\n"
            f"_TiviMate, IPTV Smarters yoki VLC ga yuklang_"
        )

        # Fayl yuborish
        with open(filepath, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename='working_playlist.m3u',
                caption=caption,
                parse_mode='Markdown'
            )

        await msg.delete()
        os.unlink(filepath)

    except requests.exceptions.Timeout:
        await msg.edit_text("❌ Pleylist yuklanmadi! URL ishlamayapti.")
    except Exception as e:
        await msg.edit_text(f"❌ Xato: {str(e)[:100]}")

# ─── MAIN ────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN yo'q! Environment variable qo'shing.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    print("✅ Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
