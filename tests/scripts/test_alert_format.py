"""Tests for alert_format plain and HTML digest builders."""

from __future__ import annotations

from alert_format import (
    combine_alert_content,
    format_morning_digest_html,
    format_morning_digest_imessage,
    format_morning_digest_plain,
    format_premium_digest_html,
    format_premium_digest_plain,
    format_short_date_range,
    morning_digest_subject,
    region_deep_link,
    site_link_display,
)

SAMPLE_ECONOMY = [
    {
        "region": "California Coast",
        "price": 198,
        "origin": "SLC",
        "destination": "SAN",
        "out_date": "2026-08-19",
        "ret_date": "2026-08-22",
        "airline": "Alaska Airlines",
        "url": "https://www.google.com/travel/flights/booking?tfs=SHORT",
    },
    {
        "region": "DFW",
        "price": 253,
        "origin": "SLC",
        "destination": "DFW",
        "out_date": "2026-07-22",
        "ret_date": "2026-07-25",
        "airline": "Delta Air Lines",
        "url": "https://www.google.com/travel/flights/booking?tfs=DFW",
    },
]


class TestShortDates:
    def test_same_month_range(self):
        assert format_short_date_range("2026-08-19", "2026-08-22") == "Aug 19–22"

    def test_cross_month_range(self):
        assert format_short_date_range("2026-07-30", "2026-08-02") == "Jul 30–Aug 2"


class TestMorningDigestPlain:
    def test_skimmable_layout(self):
        msg = format_morning_digest_plain(SAMPLE_ECONOMY)
        assert "✈️ FLI-TRACKER · Morning Deals" in msg
        assert "1. California Coast · $198" in msg
        assert "SLC→SAN · Aug 19–22 · Alaska Airlines" in msg
        assert "flights.larrycorsini.com/?tab=California%20Coast" in msg
        assert "https://www.google.com/travel/flights/booking?tfs=SHORT" in msg
        assert "Book:" not in msg
        assert "• " not in msg

    def test_subject_includes_count_and_lowest(self):
        assert morning_digest_subject(SAMPLE_ECONOMY) == "Fli-Tracker: 2 morning deals from $198"


class TestMorningDigestHtml:
    def test_book_button_hides_long_url(self):
        html = format_morning_digest_html(SAMPLE_ECONOMY)
        assert "Book fare" in html
        assert "tfs=SHORT" in html
        assert "California Coast · $198" in html
        assert "SLC → SAN · Aug 19–22" in html


class TestPremiumDigestHtml:
    def test_renders_points_and_cash(self):
        deals = [
            {
                "destination": "London",
                "airport": "LHR",
                "origin": "SLC",
                "cabin_class": "BUSINESS",
                "price": 3200,
                "points": 85000,
                "out_date": "2026-08-01",
                "ret_date": "2026-08-10",
                "url": "https://example.com/book",
            }
        ]
        html = format_premium_digest_html(deals)
        plain = format_premium_digest_plain(deals)
        assert "London · Business · $3,200 · 85,000 pts" in html
        assert "London · Business · $3,200 · 85,000 pts" in plain
        assert "https://example.com/book" in html


class TestMorningDigestImessage:
    def test_omits_long_booking_urls(self):
        msg = format_morning_digest_imessage(SAMPLE_ECONOMY)
        assert "tfs=" not in msg
        assert "Book:" not in msg
        assert "flights.larrycorsini.com/?tab=California%20Coast" in msg
        assert "2 morning deals from $198" in msg

    def test_compact_deal_blocks(self):
        msg = format_morning_digest_imessage(SAMPLE_ECONOMY)
        assert "California Coast · $198" in msg
        assert "SLC→SAN · Aug 19–22 · Alaska Airlines" in msg
        assert "flights.larrycorsini.com/?tab=DFW" in msg


class TestCombineAlertContent:
    def test_merges_sections(self):
        subject, email_plain, imessage_plain, html = combine_alert_content(
            [
                ("Morning subject", "Morning Deals", "email-a", "imessage-a", "<card-a />"),
                ("Premium subject", "Premium Deals", "email-b", "imessage-b", "<card-b />"),
            ]
        )
        assert subject == "Fli-Tracker: deal alerts"
        assert "email-a" in email_plain and "email-b" in email_plain
        assert "imessage-a" in imessage_plain and "imessage-b" in imessage_plain
        assert imessage_plain.index("imessage-a") < imessage_plain.index("imessage-b")
        assert "Morning Deals" in html and "Premium Deals" in html

    def test_watching_section_leads_combined_imessage(self):
        subject, email_plain, imessage_plain, html = combine_alert_content(
            [
                (
                    "Featured subject",
                    "Watching",
                    "featured-email",
                    "📌 Watching\nDFW · from $237",
                    "<featured />",
                ),
                (
                    "Morning subject",
                    "Morning Deals",
                    "morning-email",
                    "✈️ Morning deals\nLAX · $199",
                    "<morning />",
                ),
            ]
        )
        assert imessage_plain.index("Watching") < imessage_plain.index("Morning deals")
        assert html.index("Watching") < html.index("Morning Deals")
        assert "featured-email" in email_plain
        assert subject == "Fli-Tracker: deal alerts"


class TestHelpers:
    def test_site_link_display_strips_https(self):
        assert site_link_display("https://flights.larrycorsini.com") == "flights.larrycorsini.com"

    def test_region_deep_link(self):
        assert region_deep_link("California Coast").endswith("?tab=California%20Coast")
