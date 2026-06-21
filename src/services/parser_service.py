"""
Natural Language Message Parser for Indonesian text.
Converts casual Indonesian text like "makan siang 50rb" into structured transaction data.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from src.config import get_settings


@dataclass
class ParsedTransaction:
    amount: int                    # normalized to integer Rupiah
    category: str | None = None    # matched category name or None
    description: str = ""          # original text minus amount/keywords
    transaction_type: str = "expense"   # "expense" or "income"
    date: str = ""                 # ISO format YYYY-MM-DD
    confidence: float = 1.0        # 0.0 — 1.0
    candidates: list[str] = field(default_factory=list)  # alternative categories


@dataclass
class ParseResult:
    transactions: list[ParsedTransaction]
    errors: list[dict] = field(default_factory=list)
    needs_prompt: bool = False     # True if bot should ask user for clarification


AMOUNT_PATTERNS = [
    # "5jt", "5 jt", "5juta", "5 juta" → 5000000
    (r"(\d+[.,]?\d*)\s*jt\b", 1_000_000),
    (r"(\d+[.,]?\d*)\s*(?:juta|jt)\b", 1_000_000),
    # "50rb", "50 rb", "50ribu", "50 ribu" → 50000
    (r"(\d+[.,]?\d*)\s*rb\b", 1_000),
    (r"(\d+[.,]?\d*)\s*(?:ribu|rb)\b", 1_000),
    # "50k" → 50000
    (r"(\d+[.,]?\d*)\s*k\b", 1_000),
    # "1,5jt" → 1500000
    (r"(\d+[,.]\d+)\s*jt\b", 1_000_000),
    # "50.000", "50,000" → 50000 (dotted numbers)
    (r"Rp\s*(\d{1,3}(?:\.\d{3})*)", 1),
    (r"(\d{1,3}(?:\.\d{3})+)", 1),
    (r"(\d{1,3}(?:,\d{3})+)", 1),
    # Bare number "50000" → 50000
    (r"(?<!\d)(\d{4,})(?!\d)", 1),
]

CATEGORY_KEYWORDS = {
    "Makanan": ["makan", "nasi", "roti", "resto", "restoran", "cafe", "kopi", "es", "minum", "sarapan", "siang", "malam", "cemilan", "snack", "bakso", "soto", "mie", "ayam", "gorengan", "martabak", "pizza", "burger", "sushi", "warung", "warteg"],
    "Transportasi": ["bensin", "parkir", "ojek", "gojek", "grab", "taxi", "taksi", "bus", "kereta", "tol", "bbm", "pertamina", "transit", "angkot", "ojol", "transport", "transportasi"],
    "Belanja": ["belanja", "beli", "supermarket", "indomaret", "alfamart", "minimarket", "baju", "sepatu", "tas", "barang", "mall", "online", "shopee", "tokped", "tokopedia", "lazada", "olshop"],
    "Tagihan": ["listrik", "pln", "pulsa", "paket", "wifi", "internet", "air", "pdam", "sewa", "kos", "kontrakan", "iuran", "telpon", "telepon", "langganan", "subscription"],
    "Kesehatan": ["dokter", "obat", "apotek", "rs", "rumah sakit", "klinik", "vitamin", "cek up", "checkup", "mc", "medical", "bpjs", "asuransi"],
    "Hiburan": ["bioskop", "film", "nonton", "game", "games", "spotify", "netflix", "youtube", "musik", "konser", "main", "hangout", "nongkrong", "jalan", "rekreasi"],
    "Pendidikan": ["buku", "kursus", "belajar", "sekolah", "kuliah", "les", "pelatihan", "workshop", "seminar", "sertifikasi", "ujian"],
    "Gaji": ["gaji", "gajian", "salary", "upah", "honor", "dibayar", "dapet gaji"],
    "Investasi": ["investasi", "saham", "reksa", "reksadana", "crypto", "bitcoin", "deposito", "nabung", "tabung", "dividen", "bunga"],
    "Hadiah": ["hadiah", "dikasih", "dapat", "dapet", "bonus", "thr", "angpao", "oleh", "kado", "gift"],
    "Donasi": ["donasi", "sumbang", "amal", "zakat", "sedekah", "infaq", "wakaf"],
    "Liburan": ["liburan", "travel", "hotel", "tiket", "pesawat", "penginapan", "tour", "wisata", "jalan2"],
}

DATE_KEYWORDS = {
    "kemarin": lambda today: today - timedelta(days=1),
    "hari ini": lambda today: today,
    "tadi": lambda today: today,
    "besok": lambda today: today + timedelta(days=1),
}

INCOME_PHRASES = ["transfer masuk"]
INCOME_WORDS = [
    "gaji", "gajian", "dapat", "dapet", "dikasih", "bonus", "thr",
    "dividen", "dibayar", "honor", "upah",
]


def _clean_text(text: str) -> str:
    """Normalize whitespace in text."""
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_amount(text: str) -> tuple[int, str]:
    """Extract and normalize amount from text.

    Returns a tuple of (amount_in_rupiah, text_with_amount_replaced).
    """
    for pattern, multiplier in AMOUNT_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue

        number_str = match.group(1)
        try:
            if multiplier > 1:
                # Decimal number with scale suffix (e.g. 1,5jt → 1.5 juta)
                normalized = number_str.replace(",", ".")
                amount = int(float(normalized) * multiplier)
            else:
                # Thousands separator or bare number
                amount = int(number_str.replace(".", "").replace(",", ""))
        except ValueError:
            # Malformed number; try next pattern
            continue

        # Remove the matched amount and clean leftover whitespace
        new_text = text[: match.start()] + " " + text[match.end() :]
        return amount, _clean_text(new_text)

    return 0, text


def match_category(text: str) -> tuple[str | None, list[str], float]:
    """Match text against category keywords.

    Returns (best_match, candidates, confidence).
    """
    lower = text.lower()
    scores: dict[str, int] = {}

    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword in lower:
                # Longer keyword matches get higher weight, helping "jalan2" beat "jalan".
                score += len(keyword)
        if score > 0:
            scores[category] = score

    if not scores:
        return None, [], 0.0

    # Sort by score descending, then category name for deterministic order
    sorted_scores = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    best_match = sorted_scores[0][0]
    candidates = [category for category, _ in sorted_scores]

    if len(sorted_scores) == 1:
        confidence = 1.0
    else:
        top_score = sorted_scores[0][1]
        second_score = sorted_scores[1][1]
        if top_score > second_score:
            confidence = 0.7 + 0.3 * ((top_score - second_score) / top_score)
        else:
            confidence = 0.5

    return best_match, candidates, round(confidence, 2)


def extract_date(text: str, today: datetime) -> tuple[str, str]:
    """Extract date marker from text and return ISO date plus cleaned text."""
    lower = text.lower()

    for keyword, fn in DATE_KEYWORDS.items():
        if keyword in lower:
            date_str = fn(today).strftime("%Y-%m-%d")
            new_text = lower.replace(keyword, "", 1)
            return date_str, _clean_text(new_text)

    # Specific day of current month: "tanggal 15"
    match = re.search(r"\btanggal\s+(\d{1,2})\b", lower)
    if match:
        day = int(match.group(1))
        try:
            date_obj = today.replace(day=day)
        except ValueError:
            # Invalid day (e.g. Feb 30); fall back to today
            date_obj = today
        date_str = date_obj.strftime("%Y-%m-%d")
        new_text = lower[: match.start()] + lower[match.end() :]
        return date_str, _clean_text(new_text)

    return today.strftime("%Y-%m-%d"), lower


def is_income(text: str) -> bool:
    """Detect whether text describes income based on keywords."""
    lower = text.lower()
    for phrase in INCOME_PHRASES:
        if phrase in lower:
            return True
    for word in INCOME_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", lower):
            return True
    return False


def _build_description(text: str) -> str:
    """Build a clean description from text with amount/date already removed."""
    return _clean_text(text)


def _split_transactions(text: str) -> list[str]:
    """Split a message into multiple transaction parts.

    Comma separators inside numeric amounts (e.g. 1,5jt or 50,000) are kept intact.
    """
    parts: list[str] = []
    current = []
    i = 0
    while i < len(text):
        char = text[i]
        if char == "\n":
            parts.append("".join(current).strip())
            current = []
            i += 1
        elif char == ",":
            prev_is_digit = i > 0 and text[i - 1].isdigit()
            next_is_digit = i + 1 < len(text) and text[i + 1].isdigit()
            if prev_is_digit and next_is_digit:
                current.append(char)
                i += 1
            else:
                parts.append("".join(current).strip())
                current = []
                i += 1
                while i < len(text) and text[i].isspace():
                    i += 1
        else:
            current.append(char)
            i += 1
    if current:
        parts.append("".join(current).strip())
    return [part for part in parts if part]


def parse_message(text: str, today: datetime | None = None) -> ParseResult:
    """Main entry point. Parse a single text message into one or more ParsedTransactions."""
    if today is None:
        today = datetime.now()

    text = text.strip()
    if not text:
        return ParseResult(transactions=[])

    parts = _split_transactions(text)
    transactions: list[ParsedTransaction] = []
    errors: list[dict] = []

    for part in parts:
        date_str, text_without_date = extract_date(part, today)
        amount, text_without_amount = normalize_amount(text_without_date)

        if amount == 0:
            errors.append(
                {"message": f"Tidak dapat mengenali jumlah uang dalam: '{part}'"}
            )
            continue

        category, candidates, confidence = match_category(text_without_amount)
        transaction_type = "income" if is_income(part) else "expense"
        description = _build_description(text_without_amount)

        transactions.append(
            ParsedTransaction(
                amount=amount,
                category=category,
                description=description,
                transaction_type=transaction_type,
                date=date_str,
                confidence=confidence,
                candidates=candidates,
            )
        )

    needs_prompt = any(t.category is None for t in transactions)

    return ParseResult(
        transactions=transactions,
        errors=errors,
        needs_prompt=needs_prompt,
    )
