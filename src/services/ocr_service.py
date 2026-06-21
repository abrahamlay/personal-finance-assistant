"""OCR receipt scanner using Gemini Flash Vision."""
import base64
import json
import logging
from datetime import datetime

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

OCR_MONTHLY_LIMIT = 30


class OCRQuotaExceededError(Exception):
    """User has exceeded the monthly OCR scan limit."""
    pass


class OCRParseError(Exception):
    """Failed to parse Gemini OCR response."""
    pass


class OCRService:
    def __init__(self, api_key: str, token_store):
        self.client = genai.Client(api_key=api_key)
        self.token_store = token_store

    def _get_usage_key(self, telegram_id: str, month: str) -> str:
        return f"ocr:{telegram_id}:{month}"

    def _get_usage(self, telegram_id: str) -> int:
        month = datetime.now().strftime("%Y-%m")
        key = self._get_usage_key(telegram_id, month)
        user = self.token_store.get_user_token(telegram_id) or {}
        usage_data = user.get("ocr_usage") or "{}"
        try:
            usage = json.loads(usage_data)
        except (json.JSONDecodeError, TypeError):
            usage = {}
        return usage.get(key, 0)

    def _increment_usage(self, telegram_id: str) -> None:
        month = datetime.now().strftime("%Y-%m")
        key = self._get_usage_key(telegram_id, month)
        user = self.token_store.get_user_token(telegram_id) or {}
        usage_data = user.get("ocr_usage") or "{}"
        try:
            usage = json.loads(usage_data)
        except (json.JSONDecodeError, TypeError):
            usage = {}
        usage[key] = usage.get(key, 0) + 1
        self.token_store.update_user_token(telegram_id, ocr_usage=json.dumps(usage))

    async def scan(self, telegram_id: str, photo_bytes: bytes) -> dict:
        """Send receipt photo to Gemini, return structured data.

        Returns: {merchant, total_amount, items, category_suggestion, confidence, raw_response}
        """
        usage = self._get_usage(telegram_id)
        if usage >= OCR_MONTHLY_LIMIT:
            raise OCRQuotaExceededError(
                f"Batas scan OCR bulanan ({OCR_MONTHLY_LIMIT}) sudah tercapai."
            )

        encoded = base64.b64encode(photo_bytes).decode("utf-8")

        prompt = (
            "Baca struk belanja ini dan kembalikan hasil dalam format JSON. "
            "Field yang wajib ada: merchant (string), total_amount (integer tanpa titik/koma), "
            "items (array of {name, qty, price}), category_suggestion (satu dari: "
            "Makanan, Transportasi, Belanja, Tagihan, Kesehatan, Hiburan, Pendidikan, "
            "Donasi, Liburan, Lainnya), confidence (float 0.0-1.0). "
            "Jika tidak yakin, isi confidence rendah dan category_suggestion 'Lainnya'. "
            "Hanya kembalikan JSON, tanpa penjelasan tambahan."
        )

        try:
            response = await self.client.aio.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=prompt),
                            types.Part.from_bytes(data=photo_bytes, mime_type="image/jpeg"),
                        ],
                    )
                ],
            )
        except Exception as e:
            logger.exception("Gemini OCR API error for user %s", telegram_id)
            raise OCRParseError(f"Gagal memproses gambar: {e}")

        raw = response.text or ""
        parsed = self._parse_response(raw)
        parsed["raw_response"] = raw

        # Map category to user's categories
        categories = self._get_user_categories(telegram_id)
        parsed["category_suggestion"] = self._map_category(
            parsed.get("category_suggestion", "Lainnya"), categories
        )

        self._increment_usage(telegram_id)
        return parsed

    def _parse_response(self, raw: str) -> dict:
        """Extract JSON from markdown or raw text and normalize fields."""
        text = raw.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning("OCR JSON parse failed: %s", e)
            raise OCRParseError("Gagal memahami hasil scan. Coba foto ulang yang lebih jelas.")

        total = data.get("total_amount")
        try:
            total_amount = int(total)
        except (TypeError, ValueError):
            total_amount = 0

        confidence = data.get("confidence", 0.5)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.5

        return {
            "merchant": str(data.get("merchant", "")).strip() or "Tidak diketahui",
            "total_amount": total_amount,
            "items": data.get("items", []),
            "category_suggestion": str(data.get("category_suggestion", "Lainnya")).strip(),
            "confidence": confidence,
        }

    def _get_user_categories(self, telegram_id: str) -> list[str]:
        user = self.token_store.get_user_token(telegram_id) or {}
        raw = user.get("categories")
        if not raw:
            return []
        try:
            cats = json.loads(raw)
            if isinstance(cats, list):
                return [c["nama"] if isinstance(c, dict) else str(c) for c in cats]
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    def _map_category(self, suggestion: str, user_categories: list[str]) -> str:
        suggestion = suggestion.strip()
        if not suggestion:
            return "Lainnya"
        known = {
            "Makanan", "Transportasi", "Belanja", "Tagihan", "Kesehatan",
            "Hiburan", "Pendidikan", "Donasi", "Liburan", "Lainnya",
            "Gaji", "Investasi", "Hadiah",
        }
        if suggestion in known:
            return suggestion
        lowered = suggestion.lower()
        for cat in user_categories:
            if lowered in cat.lower() or cat.lower() in lowered:
                return cat
        return "Lainnya"
