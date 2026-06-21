import pytest
from datetime import datetime

from src.services.parser_service import parse_message, ParsedTransaction, ParseResult


class TestBasicParsing:
    def test_simple_expense(self):
        result = parse_message("makan siang 50rb")
        assert len(result.transactions) == 1
        t = result.transactions[0]
        assert t.amount == 50000
        assert t.category == "Makanan"
        assert t.transaction_type == "expense"
        assert t.date == datetime.now().strftime("%Y-%m-%d")

    def test_simple_income(self):
        result = parse_message("gaji 5jt")
        t = result.transactions[0]
        assert t.amount == 5000000
        assert t.category == "Gaji"
        assert t.transaction_type == "income"


class TestAmountFormats:
    @pytest.mark.parametrize("text,expected", [
        ("makan 50rb", 50000),
        ("makan 50 rb", 50000),
        ("makan 50ribu", 50000),
        ("makan 50 ribu", 50000),
        ("makan 50k", 50000),
        ("makan 50.000", 50000),
        ("makan 50000", 50000),
        ("makan 50,000", 50000),
        ("belanja 5jt", 5000000),
        ("belanja 5 jt", 5000000),
        ("belanja 5juta", 5000000),
        ("belanja 5 juta", 5000000),
        ("belanja 5.000.000", 5000000),
        ("belanja 1,5jt", 1500000),
        ("belanja Rp 50.000", 50000),
        ("belanja 2.5jt", 2500000),
    ])
    def test_amount_format(self, text, expected):
        result = parse_message(text)
        assert result.transactions[0].amount == expected

    def test_amount_bare_large_number(self):
        result = parse_message("beli laptop 12500000")
        assert result.transactions[0].amount == 12_500_000

    def test_amount_rp_millions(self):
        result = parse_message("Rp 5.000.000")
        assert result.transactions[0].amount == 5_000_000

    def test_amount_decimal_ribu(self):
        result = parse_message("kopi 1,5rb")
        assert result.transactions[0].amount == 1500


class TestCategoryMatching:
    @pytest.mark.parametrize("text,expected_cat", [
        ("makan siang 50rb", "Makanan"),
        ("nasi goreng 30rb", "Makanan"),
        ("bensin 100rb", "Transportasi"),
        ("parkir 10rb", "Transportasi"),
        ("belanja bulanan 500rb", "Belanja"),
        ("listrik 200rb", "Tagihan"),
        ("pulsa 100rb", "Tagihan"),
        ("obat flu 50rb", "Kesehatan"),
        ("dokter 200rb", "Kesehatan"),
        ("nonton 50rb", "Hiburan"),
        ("buku coding 150rb", "Pendidikan"),
        ("donasi anak yatim 100rb", "Donasi"),
        ("hotel bandung 1jt", "Liburan"),
        ("transport 30rb", "Transportasi"),
        ("kopi starbucks 60rb", "Makanan"),
        ("gojek kantor 30rb", "Transportasi"),
        ("indomaret 50rb", "Belanja"),
        ("wifi bulanan 300rb", "Tagihan"),
        ("saham bca 1jt", "Investasi"),
        ("dikasih ibu 200rb", "Hadiah"),
    ])
    def test_category_match(self, text, expected_cat):
        result = parse_message(text)
        assert result.transactions[0].category == expected_cat

    def test_category_investasi(self):
        result = parse_message("beli reksadana 2jt")
        assert result.transactions[0].category == "Investasi"

    def test_category_liburan_jalan2(self):
        result = parse_message("jalan2 ke bandung 2jt")
        assert result.transactions[0].category == "Liburan"

    def test_category_kesehatan_rumah_sakit(self):
        result = parse_message("rumah sakit 500rb")
        assert result.transactions[0].category == "Kesehatan"

    def test_category_tagihan_pln(self):
        result = parse_message("bayar pln 150rb")
        assert result.transactions[0].category == "Tagihan"

    def test_category_hadiah_dapat(self):
        result = parse_message("dapat thr 500rb")
        assert result.transactions[0].category == "Hadiah"


class TestDateExtraction:
    def test_kemarin(self):
        today = datetime(2026, 6, 21)
        result = parse_message("kemarin makan 50rb", today)
        assert result.transactions[0].date == "2026-06-20"

    def test_hari_ini(self):
        today = datetime(2026, 6, 21)
        result = parse_message("hari ini makan 50rb", today)
        assert result.transactions[0].date == "2026-06-21"

    def test_besok(self):
        today = datetime(2026, 6, 21)
        result = parse_message("besok bayar listrik 200rb", today)
        assert result.transactions[0].date == "2026-06-22"

    def test_tanggal_specific(self):
        today = datetime(2026, 6, 21)
        result = parse_message("tanggal 15 sewa 2jt", today)
        assert result.transactions[0].date == "2026-06-15"

    def test_tadi(self):
        today = datetime(2026, 6, 21)
        result = parse_message("tadi makan 50rb", today)
        assert result.transactions[0].date == "2026-06-21"

    def test_default_today(self):
        today = datetime(2026, 6, 21)
        result = parse_message("makan 50rb", today)
        assert result.transactions[0].date == "2026-06-21"


class TestIncomeDetection:
    @pytest.mark.parametrize("text", [
        "gaji 5jt",
        "dapat uang 100rb",
        "dapet thr 500rb",
        "dikasih ibu 200rb",
        "bonus akhir tahun 2jt",
        "transfer masuk 3jt",
        "dibayar project 1jt",
        "honor mengajar 500rb",
        "upah kerja 250rb",
    ])
    def test_income_keywords(self, text):
        result = parse_message(text)
        assert result.transactions[0].transaction_type == "income"

    def test_expense_bayar_listrik(self):
        result = parse_message("bayar listrik 200rb")
        assert result.transactions[0].transaction_type == "expense"

    def test_expense_transfer_to_person(self):
        result = parse_message("transfer budi 500rb")
        assert result.transactions[0].transaction_type == "expense"


class TestMultiTransaction:
    def test_comma_separated(self):
        result = parse_message("pulsa 100k, bensin 80rb")
        assert len(result.transactions) == 2
        assert result.transactions[0].amount == 100000
        assert result.transactions[1].amount == 80000

    def test_newline_separated(self):
        result = parse_message("makan 30rb\ntransport 20rb")
        assert len(result.transactions) == 2

    def test_mixed_comma_and_newline(self):
        result = parse_message("makan 30rb, kopi 20rb\ntransport 50rb")
        assert len(result.transactions) == 3


class TestDescriptionExtraction:
    def test_simple_description(self):
        result = parse_message("makan siang 50rb")
        assert result.transactions[0].description == "makan siang"

    def test_description_after_amount_removal(self):
        result = parse_message("transfer budi 500rb")
        assert result.transactions[0].description == "transfer budi"

    def test_description_with_date_removed(self):
        today = datetime(2026, 6, 21)
        result = parse_message("kemarin makan siang 50rb", today)
        assert result.transactions[0].description == "makan siang"


class TestConfidenceAndCandidates:
    def test_single_match_confidence_one(self):
        result = parse_message("makan siang 50rb")
        assert result.transactions[0].confidence == 1.0

    def test_multiple_candidates_returned(self):
        result = parse_message("belajar saham 1jt")
        t = result.transactions[0]
        assert len(t.candidates) >= 2
        assert "Investasi" in t.candidates
        assert "Pendidikan" in t.candidates

    def test_multiple_categories_low_confidence(self):
        result = parse_message("belajar saham 1jt")
        assert result.transactions[0].confidence < 1.0


class TestEdgeCases:
    def test_no_amount_returns_error(self):
        result = parse_message("makan siang")
        assert len(result.transactions) == 0
        assert len(result.errors) > 0

    def test_no_category_prompts_user(self):
        result = parse_message("50rb")
        assert result.transactions[0].category is None
        assert result.needs_prompt

    def test_empty_input(self):
        result = parse_message("")
        assert len(result.transactions) == 0

    def test_whitespace_only(self):
        result = parse_message("   ")
        assert len(result.transactions) == 0

    def test_transfer_to_person(self):
        result = parse_message("transfer budi 500rb")
        assert result.transactions[0].amount == 500000
        assert result.transactions[0].transaction_type == "expense"

    def test_parse_result_dataclass(self):
        result = parse_message("makan 50rb")
        assert isinstance(result, ParseResult)
        assert isinstance(result.transactions[0], ParsedTransaction)

    def test_multiple_parts_one_without_amount(self):
        result = parse_message("makan 50rb, minum")
        assert len(result.transactions) == 1
        assert len(result.errors) == 1

    def test_case_insensitive(self):
        result = parse_message("MAKAN SIANG 50RB")
        assert result.transactions[0].amount == 50000
        assert result.transactions[0].category == "Makanan"

    def test_amount_with_extra_spaces(self):
        result = parse_message("makan   50   rb")
        assert result.transactions[0].amount == 50000

    def test_no_category_still_has_amount_and_type(self):
        result = parse_message("bayar utang 100rb")
        t = result.transactions[0]
        assert t.amount == 100000
        assert t.transaction_type == "expense"
