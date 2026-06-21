"""AI-powered spending insights for premium users."""
import json
import logging
from collections import defaultdict
from datetime import datetime

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class InsightService:
    def __init__(self, gemini_api_key: str):
        self._api_key = gemini_api_key
        self.client = None
        if gemini_api_key:
            self.client = genai.Client(api_key=gemini_api_key)

    async def analyze(self, transactions: list[dict], categories: list[dict]) -> str:
        """Analyze spending patterns. Returns natural language insight in Indonesian."""
        if not transactions:
            return (
                "📊 Belum ada transaksi buat dianalisis. "
                "Yuk mulai catat pengeluaran dan pemasukan kamu!"
            )

        total_expense = sum(t.get("jumlah", 0) for t in transactions if t.get("tipe") == "expense")
        total_income = sum(t.get("jumlah", 0) for t in transactions if t.get("tipe") == "income")

        # Top 3 expense categories
        expenses_by_cat: dict[str, int] = defaultdict(int)
        for t in transactions:
            if t.get("tipe") == "expense":
                expenses_by_cat[t.get("kategori", "Lainnya")] += t.get("jumlah", 0)
        top_categories = sorted(expenses_by_cat.items(), key=lambda x: -x[1])[:3]

        # Monthly trend
        monthly_expense: dict[str, int] = defaultdict(int)
        monthly_income: dict[str, int] = defaultdict(int)
        for t in transactions:
            month = t.get("tanggal", "")[:7]
            if not month:
                continue
            if t.get("tipe") == "expense":
                monthly_expense[month] += t.get("jumlah", 0)
            elif t.get("tipe") == "income":
                monthly_income[month] += t.get("jumlah", 0)

        current_month = datetime.now().strftime("%Y-%m")
        current_expense = monthly_expense.get(current_month, 0)
        current_income = monthly_income.get(current_month, 0)

        summary = {
            "total_expense": total_expense,
            "total_income": total_income,
            "saldo": total_income - total_expense,
            "top_categories": [
                {"category": cat, "amount": amount}
                for cat, amount in top_categories
            ],
            "monthly_expense": dict(sorted(monthly_expense.items())),
            "monthly_income": dict(sorted(monthly_income.items())),
            "current_month": current_month,
            "current_expense": current_expense,
            "current_income": current_income,
        }

        if not self._api_key or self.client is None:
            return self._fallback_insight(summary)

        prompt = (
            "Analisis kebiasaan belanja user ini dalam Bahasa Indonesia yang santai dan friendly. "
            "Berikan insight singkat maksimal 5 kalimat, termasuk pola pengeluaran, "
            "kategori terbesar, dan saran praktis untuk menghemat.\n\n"
            f"{json.dumps(summary, ensure_ascii=False, indent=2)}"
        )

        try:
            response = await self.client.aio.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
            )
            text = response.text or ""
            text = text.strip()
            if text:
                return f"💡 *Insight Keuangan*\n\n{text}"
        except Exception as e:
            logger.exception("Gemini insight failed: %s", e)

        return self._fallback_insight(summary)

    def _fallback_insight(self, summary: dict) -> str:
        lines = ["💡 *Insight Keuangan*\n"]
        lines.append(
            f"Bulan ini: pengeluaran Rp {summary['current_expense']:,}, "
            f"pemasukan Rp {summary['current_income']:,}."
        )
        if summary["top_categories"]:
            lines.append("\n*3 kategori terbesar:*")
            for item in summary["top_categories"]:
                lines.append(f"• {item['category']}: Rp {item['amount']:,}")
        if summary["monthly_expense"]:
            months = list(summary["monthly_expense"].keys())
            if len(months) >= 2:
                last = summary["monthly_expense"][months[-2]]
                cur = summary["monthly_expense"][months[-1]]
                diff_pct = ((cur - last) / last * 100) if last else 0
                direction = "naik" if diff_pct >= 0 else "turun"
                lines.append(
                    f"\nPengeluaran {direction} {abs(diff_pct):.1f}% dibanding bulan lalu."
                )
        lines.append("\n_Yuk tetap disiplin catat transaksi setiap hari!_")
        return "\n".join(lines)
