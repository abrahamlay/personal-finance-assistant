"""Natural language and photo (OCR) message handlers."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.services.parser_service import parse_message
from src.services.transaction_service import TransactionService
from src.services.ocr_service import OCRService
from src.auth.token_store import TokenStore
from src.middleware import require_login, premium_required
from src.services.error_handler import bot_error_handler
from datetime import datetime


@require_login
async def handle_natural_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle non-command text messages: parse → create → confirm."""
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    token_store: TokenStore = context.bot_data["token_store"]
    tx_service: TransactionService = context.bot_data["tx_service"]
    budget_service = context.bot_data.get("budget_service")

    user = token_store.get_user_token(user_id)
    ss_id = user.get("spreadsheet_id")
    if not ss_id:
        await update.message.reply_text("🔐 Sambungkan Google Sheet dulu: /login")
        return

    # Parse
    result = parse_message(text)

    if result.errors:
        await update.message.reply_text(
            "⚠️ Gak bisa parse pesan kamu.\n"
            "Coba format: `makan siang 50rb` atau `gaji 5jt`\n"
            "Ketik /bantuan buat panduan lengkap.",
            parse_mode="Markdown",
        )
        return

    if result.needs_prompt:
        t = result.transactions[0]
        cats = ", ".join(t.candidates[:5]) if t.candidates else "?"
        await update.message.reply_text(
            f"Ditemukan jumlah: *Rp {t.amount:,}*\n"
            f"Tapi kategori kurang jelas: *{cats}*\n\n"
            f"Ketik ulang dengan kategori ya. Contoh: `makan siang 50rb`",
            parse_mode="Markdown",
        )
        return

    # Create transactions
    responses = []
    warnings = []
    for t in result.transactions:
        cat = t.category or "Lainnya"
        r = tx_service.create(user_id, ss_id, t.transaction_type, cat, t.amount, t.description, t.date)

        if r.get("was_duplicate"):
            responses.append(f"⚠️ Duplikat: {cat} Rp {t.amount:,}")
        else:
            emoji = {"income": "💰", "expense": "📤"}.get(t.transaction_type, "📌")
            responses.append(f"✅ Tercatat: {emoji} {cat} — Rp {t.amount:,} [#{r['row_id']}]")

            # Check budget warnings for expense transactions
            if budget_service and t.transaction_type == "expense":
                month_str = t.date[:7] if t.date else datetime.now().strftime("%Y-%m")
                warning = budget_service.track_transaction(
                    user_id, ss_id, cat, t.amount, month_str
                )
                if warning and warning not in warnings:
                    warnings.append(warning)

    # Daily summary
    total = r.get("today_total", {})
    body = "\n".join(responses)
    summary = f"\n📊 *Hari ini:* Rp {total.get('expense', 0):,} ({total.get('count', 0)} transaksi)"
    warning_text = "\n\n" + "\n".join(warnings) if warnings else ""

    await update.message.reply_text(body + summary + warning_text, parse_mode="Markdown")


@require_login
@premium_required("OCR Scanner")
@bot_error_handler
async def ocr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tell user to send a receipt photo for OCR scanning."""
    await update.message.reply_text(
        "📸 *OCR Scanner*\n\n"
        "Kirim foto struk belanja kamu, nanti aku baca otomatis!",
        parse_mode="Markdown",
    )


@require_login
@premium_required("OCR Scanner")
@bot_error_handler
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle receipt photos: OCR scan → show result → confirm dialog."""
    user_id = str(update.effective_user.id)
    token_store: TokenStore = context.bot_data["token_store"]
    ocr_service: OCRService = context.bot_data["ocr_service"]

    user = token_store.get_user_token(user_id)
    ss_id = user.get("spreadsheet_id")
    if not ss_id:
        await update.message.reply_text("🔐 Sambungkan Google Sheet dulu: /login")
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    photo_bytes = await file.download_as_bytearray()

    result = await ocr_service.scan(user_id, bytes(photo_bytes))

    # Store pending OCR result for callback handler
    context.user_data["ocr_result"] = result

    merchant = result.get("merchant", "Tidak diketahui")
    amount = result.get("total_amount", 0)
    category = result.get("category_suggestion", "Lainnya")
    confidence = result.get("confidence", 0.0)
    items = result.get("items", [])

    items_text = ""
    if items:
        items_text = "\n*Item:*\n" + "\n".join(
            f"• {item.get('name', '-')} x{item.get('qty', 1)} @ Rp {item.get('price', 0):,}"
            for item in items[:10]
        )

    if confidence < 0.6:
        await update.message.reply_text(
            "🤔 *Gak yakin nih. Ini struk apa?*\n\n"
            f"Merchant: {merchant}\n"
            f"Total: Rp {amount:,}\n"
            f"Kategori: {category}\n\n"
            "Ketik transaksi manual aja ya, contoh: `makan siang 50rb`",
            parse_mode="Markdown",
        )
        return

    text = (
        f"📸 *Hasil Scan Struk*\n\n"
        f"🏪 Merchant: {merchant}\n"
        f"💰 Total: Rp {amount:,}\n"
        f"📂 Kategori: {category}\n"
        f"🎯 Confidence: {confidence * 100:.0f}%"
        f"{items_text}\n\n"
        f"Mau simpan?"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Simpan", callback_data="ocr:save")],
        [InlineKeyboardButton("✏️ Edit Manual", callback_data="ocr:manual")],
    ])
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


@bot_error_handler(reply_target="callback_query")
async def ocr_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle OCR inline buttons: save or edit manually."""
    query = update.callback_query
    await query.answer()

    user_id = str(update.effective_user.id)
    token_store: TokenStore = context.bot_data["token_store"]
    tx_service: TransactionService = context.bot_data["tx_service"]
    budget_service = context.bot_data.get("budget_service")

    user = token_store.get_user_token(user_id)
    ss_id = user.get("spreadsheet_id")

    result = context.user_data.pop("ocr_result", None)
    data = query.data

    if data == "ocr:manual" or result is None:
        await query.edit_message_text(
            "✏️ Ketik transaksi manual ya. Contoh: `makan siang 50rb`",
            parse_mode="Markdown",
        )
        return

    if data == "ocr:save":
        today = datetime.now().strftime("%Y-%m-%d")
        category = result.get("category_suggestion", "Lainnya")
        amount = result.get("total_amount", 0)
        description = result.get("merchant", "")

        r = tx_service.create(
            user_id, ss_id, "expense", category, amount, description, today
        )

        if r.get("was_duplicate"):
            await query.edit_message_text(
                f"⚠️ Duplikat: {category} Rp {amount:,}",
                parse_mode="Markdown",
            )
            return

        total = r.get("today_total", {})
        warning_text = ""
        if budget_service:
            month_str = datetime.now().strftime("%Y-%m")
            warning = budget_service.track_transaction(
                user_id, ss_id, category, amount, month_str
            )
            if warning:
                warning_text = f"\n\n{warning}"

        await query.edit_message_text(
            f"✅ Tercatat: 📤 {category} — Rp {amount:,} [#{r['row_id']}]\n"
            f"📊 *Hari ini:* Rp {total.get('expense', 0):,} ({total.get('count', 0)} transaksi)"
            f"{warning_text}",
            parse_mode="Markdown",
        )
