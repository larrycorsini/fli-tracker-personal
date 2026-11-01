"""Tests for alert_format plain and HTML digest builders."""

from __future__ import annotations

from alert_format import (
    combine_alert_content,
    format_morning_digest_html,
    format_morning_digest_imessage,
    format_morning_digest_plain,
    format_premium_digest_html,
    format_premium_digest_imessage,
    format_premium_digest_plain,
    format_short_date_range,
    morning_digest_subject,
    premium_deal_deep_link,
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
        assert "Morning Deals" in html and "Premium Deals" in html


class TestHelpers:
    def test_site_link_display_strips_https(self):
        assert site_link_display("https://flights.larrycorsini.com") == "flights.larrycorsini.com"

    def test_region_deep_link(self):
        assert region_deep_link("California Coast").endswith("?tab=California%20Coast")

    def test_region_deep_link_includes_fare_params(self):
        link = region_deep_link("DFW", SAMPLE_ECONOMY[1])
        assert "tab=DFW" in link
        assert "o=SLC" in link
        assert "d=DFW" in link
        assert "out=2026-07-22" in link
        assert "ret=2026-07-25" in link
        assert link.endswith("#flights")

    def test_premium_deal_deep_link_is_unique(self):
        portland = {
            "destination": "Portland",
            "airport": "PDX",
            "origin": "SLC",
            "out_date": "2026-12-05",
            "cabin_class": "BUSINESS",
        }
        cancun = {
            "destination": "Cancun",
            "airport": "CUN",
            "origin": "SLC",
            "out_date": "2026-12-05",
            "cabin_class": "BUSINESS",
        }
        portland_link = premium_deal_deep_link(portland)
        cancun_link = premium_deal_deep_link(cancun)
        assert portland_link != cancun_link
        assert "deal=PDX" in portland_link
        assert "o=SLC" in portland_link
        assert "out=2026-12-05" in portland_link
        assert portland_link.endswith("#premium-deals")
        assert "deal=CUN" in cancun_link


class TestPremiumDigestImessage:
    def test_uses_cabin_field_instead_of_defaulting_to_business(self):
        deals = [
            {
                "destination": "Mexico City",
                "airport": "MEX",
                "origin": "SLC",
                "cabin": "Premium Economy",
                "price": 952,
                "points": 76160,
                "out_date": "2026-11-09",
                "ret_date": "2026-11-16",
            }
        ]
        msg = format_premium_digest_imessage(deals)
        assert "Premium Economy" in msg
        assert "Business" not in msg

    def test_each_deal_gets_its_own_dashboard_url(self):
        deals = [
            {
                "destination": "Portland",
                "airport": "PDX",
                "origin": "SLC",
                "cabin_class": "BUSINESS",
                "price": 387,
                "points": 30960,
                "out_date": "2026-12-05",
                "ret_date": "2026-12-15",
            },
            {
                "destination": "Cancun",
                "airport": "CUN",
                "origin": "SLC",
                "cabin_class": "BUSINESS",
                "price": 1080,
                "points": 86400,
                "out_date": "2026-12-05",
                "ret_date": "2026-12-10",
            },
        ]
        msg = format_premium_digest_imessage(deals)
        assert msg.count("#premium-deals") >= 2
        assert "deal=PDX" in msg
        assert "deal=CUN" in msg
        assert msg.split("deal=PDX")[0].count("deal=CUN") == 0


class TestMorningDigestImessageHighlight:
    def test_imessage_points_at_specific_fare(self):
        msg = format_morning_digest_imessage(SAMPLE_ECONOMY)
        assert "tab=DFW" in msg
        assert "o=SLC" in msg
        assert "out=2026-07-22" in msg
        assert "ret=2026-07-25" in msg
