"""Shared plain-text and HTML formatters for Fli-Tracker deal alerts."""

from __future__ import annotations

import html
from datetime import datetime
from urllib.parse import quote

from tracker_config import SITE_URL

_DIVIDER = "─" * 28
_BRAND_PRIMARY = "#1F2A37"
_ACCENT = "#1A73E8"


def _parse_date(dt_str: str) -> datetime | None:
    if not dt_str:
        return None
    try:
        if "T" in dt_str:
            return datetime.fromisoformat(dt_str)
        return datetime.strptime(dt_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def format_weekday_date(dt_str: str) -> str:
    """Long date label for detail views (Wed, Jul 01)."""
    dt = _parse_date(dt_str)
    if dt is None:
        return dt_str or "—"
    return dt.strftime("%a, %b %d")


def format_short_date(dt_str: str) -> str:
    """Compact date label for alerts (Aug 19)."""
    dt = _parse_date(dt_str)
    if dt is None:
        return dt_str or "—"
    return dt.strftime("%b %d").replace(" 0", " ")


def format_short_date_range(out_date: str, ret_date: str) -> str:
    """Compact trip range (Aug 19–22 or Aug 19–Sep 2)."""
    out_dt = _parse_date(out_date)
    ret_dt = _parse_date(ret_date)
    if out_dt is None or ret_dt is None:
        return f"{out_date}–{ret_date}".strip("–") or "—"
    if out_dt.year == ret_dt.year and out_dt.month == ret_dt.month:
        return f"{out_dt.strftime('%b %d').replace(' 0', ' ')}–{ret_dt.day}"
    return f"{format_short_date(out_date)}–{format_short_date(ret_date)}"


def region_deep_link(region_name: str) -> str:
    return f"{SITE_URL}/?tab={quote(region_name)}"


def premium_deals_deep_link() -> str:
    return f"{SITE_URL}/#premium-deals"


def featured_deep_link(search_id: str | None = None) -> str:
    """Return the site deep link for the featured-trips spotlight."""
    if search_id:
        return f"{SITE_URL}/#featured-{search_id}"
    return f"{SITE_URL}/#featured"


def format_money(amount: int | float) -> str:
    return f"${int(amount):,}"


def format_points(amount: int | float) -> str:
    return f"{int(amount):,} pts"


def site_link_display(url: str) -> str:
    """Strip scheme for shorter, readable link text."""
    return url.removeprefix("https://").removeprefix("http://")


def morning_digest_subject(deals: list[dict]) -> str:
    if not deals:
        return "Fli-Tracker deal alert"
    lowest = min(int(d["price"]) for d in deals)
    count = len(deals)
    noun = "deal" if count == 1 else "deals"
    return f"Fli-Tracker: {count} morning {noun} from ${lowest}"


def premium_digest_subject(deals: list[dict]) -> str:
    if not deals:
        return "Fli-Tracker premium deal alert"
    count = len(deals)
    noun = "deal" if count == 1 else "deals"
    return f"Fli-Tracker: {count} premium {noun}"


def _format_economy_deal_plain(deal: dict, index: int, *, include_booking_url: bool) -> list[str]:
    region = deal["region"]
    price = int(deal["price"])
    origin = deal["origin"]
    dest = deal["destination"]
    dates = format_short_date_range(deal["out_date"], deal["ret_date"])
    airline = deal.get("airline") or "—"
    board = region_deep_link(region)
    book = deal.get("url") or board

    lines = [
        f"{index}. {region} · ${price}",
        f"   {origin}→{dest} · {dates} · {airline}",
        f"   ↗ {site_link_display(board)}",
    ]
    if include_booking_url and book != board:
        lines.append(f"   🔗 {book}")
    return lines


def _format_economy_deal_imessage(deal: dict) -> str:
    """Compact deal block with one short dashboard URL (no long Google tfs links)."""
    region = deal["region"]
    price = int(deal["price"])
    origin = deal["origin"]
    dest = deal["destination"]
    dates = format_short_date_range(deal["out_date"], deal["ret_date"])
    airline = deal.get("airline") or "—"
    board = region_deep_link(region)
    return f"{region} · ${price}\n{origin}→{dest} · {dates} · {airline}\n{board}"


def format_morning_digest_plain(deals: list[dict]) -> str:
    """Plain-text digest for email fallback (may include booking URLs)."""
    if not deals:
        return ""

    lines = [
        "✈️ FLI-TRACKER · Morning Deals",
        _DIVIDER,
        "",
    ]
    for index, deal in enumerate(deals, start=1):
        lines.extend(_format_economy_deal_plain(deal, index, include_booking_url=True))
        lines.append("")

    lines.extend([_DIVIDER, site_link_display(SITE_URL)])
    return "\n".join(lines).rstrip()


def format_morning_digest_imessage(deals: list[dict]) -> str:
    """IMessage digest — short tappable site links only (no tfs walls).

    iMessage cannot render custom hyperlink text via AppleScript; URLs must
    appear as plain text. Google Flights booking links are omitted here because
    they wrap across dozens of lines on iPhone. Tap the region link to open
    the dashboard and book from there. Direct book links are in HTML email.
    """
    if not deals:
        return ""

    lowest = min(int(d["price"]) for d in deals)
    header = (
        f"✈️ FLI-TRACKER · {len(deals)} morning deal{'' if len(deals) == 1 else 's'} from ${lowest}"
    )
    blocks = [_format_economy_deal_imessage(deal) for deal in deals]
    return header + "\n\n" + "\n\n".join(blocks) + f"\n\n{SITE_URL}"


def _compact_departure_time(out_dep_fmt: str) -> str:
    """Short label for iMessage (Wed 5:20 PM)."""
    if not out_dep_fmt:
        return ""
    parts = [p.strip() for p in out_dep_fmt.split(",")]
    if len(parts) >= 3:
        day = parts[0]
        time_part = parts[-1].lstrip("0")
        return f"{day} {time_part}"
    return out_dep_fmt


def _dedupe_featured_options(options: list[dict]) -> list[dict]:
    """Keep cheapest fare per departure window for alert text."""
    by_window: dict[str, dict] = {}
    for opt in sorted(options, key=lambda o: (o.get("price") or 9999, o.get("outDep") or "")):
        price = opt.get("price")
        if price is None:
            continue
        key = opt.get("windowLabel") or opt.get("outDep") or str(price)
        current = by_window.get(key)
        if current is None or price < current.get("price", 9999):
            by_window[key] = opt
    return sorted(by_window.values(), key=lambda o: (o.get("outDate") or "", o.get("outDep") or ""))


def _format_featured_option_line_plain(opt: dict, *, include_booking_url: bool) -> list[str]:
    origin = opt.get("origin") or "—"
    dest = opt.get("destination") or "—"
    dates = format_short_date_range(opt.get("outDate", ""), opt.get("retDate", ""))
    airline = opt.get("airline") or "—"
    window = opt.get("windowLabel") or ""
    price = int(opt["price"])
    out_time = _compact_departure_time(opt.get("outDepFmt") or "")
    ret_time = _compact_departure_time(opt.get("retArrFmt") or "")
    time_part = f" · {out_time} out"
    if ret_time:
        time_part = f"{time_part}, {ret_time} back"
    label = f"   {window} · ${price}" if window else f"   ${price}"
    lines = [label, f"   {origin}→{dest} · {dates} · {airline}{time_part}"]
    book = opt.get("url") or ""
    if include_booking_url and book:
        lines.append(f"   🔗 {book}")
    return lines


def _format_featured_option_line_imessage(opt: dict) -> str:
    origin = opt.get("origin") or "—"
    dest = opt.get("destination") or "—"
    dates = format_short_date_range(opt.get("outDate", ""), opt.get("retDate", ""))
    airline = opt.get("airline") or "—"
    window = opt.get("windowLabel") or ""
    price = int(opt["price"])
    out_time = _compact_departure_time(opt.get("outDepFmt") or "")
    prefix = f"{window} · ${price}" if window else f"${price}"
    time_suffix = f" · {out_time} out" if out_time else ""
    return f"{prefix}\n{origin}→{dest} · {dates} · {airline}{time_suffix}"


def _format_featured_deal_plain(deal: dict, index: int, *, include_booking_url: bool) -> list[str]:
    title = deal.get("title") or "Featured trip"
    price = int(deal["price"])
    board = deal.get("site_url") or featured_deep_link(deal.get("id"))
    blurb = (deal.get("blurb") or "").strip()
    options = _dedupe_featured_options(deal.get("options") or [])

    lines = [f"{index}. {title} · from ${price}"]
    if blurb:
        lines.append(f"   {blurb}")
    if options:
        for opt in options:
            lines.extend(_format_featured_option_line_plain(opt, include_booking_url=include_booking_url))
    else:
        origin = deal.get("origin") or "—"
        dest = deal.get("destination") or "—"
        dates = format_short_date_range(deal.get("out_date", ""), deal.get("ret_date", ""))
        airline = deal.get("airline") or "—"
        window = deal.get("window_label") or ""
        route = f"{origin}→{dest} · {dates}"
        if window:
            route = f"{route} · {window}"
        lines.append(f"   {route} · {airline}")
        if include_booking_url and deal.get("url"):
            lines.append(f"   🔗 {deal['url']}")
    lines.append(f"   ↗ {site_link_display(board)}")
    return lines


def _format_featured_deal_imessage(deal: dict) -> str:
    title = deal.get("title") or "Featured trip"
    price = int(deal["price"])
    board = deal.get("site_url") or featured_deep_link(deal.get("id"))
    blurb = (deal.get("blurb") or "").strip()
    options = _dedupe_featured_options(deal.get("options") or [])

    lines = [f"{title} · from ${price}"]
    if blurb:
        lines.append(blurb)
    if options:
        lines.extend(_format_featured_option_line_imessage(opt) for opt in options)
    else:
        origin = deal.get("origin") or "—"
        dest = deal.get("destination") or "—"
        dates = format_short_date_range(deal.get("out_date", ""), deal.get("ret_date", ""))
        airline = deal.get("airline") or "—"
        window = deal.get("window_label") or ""
        detail = f"{origin}→{dest} · {dates}"
        if window:
            detail = f"{detail} · {window}"
        lines.append(f"{detail} · {airline}")
    lines.append(board)
    return "\n".join(lines)


def format_featured_digest_plain(deals: list[dict]) -> str:
    """Plain-text featured-trip section for email fallback."""
    if not deals:
        return ""
    lines = [
        "📌 FLI-TRACKER · Watching",
        _DIVIDER,
        "",
    ]
    for index, deal in enumerate(deals, start=1):
        lines.extend(_format_featured_deal_plain(deal, index, include_booking_url=True))
        lines.append("")
    lines.extend([_DIVIDER, site_link_display(SITE_URL)])
    return "\n".join(lines).rstrip()


def format_featured_digest_imessage(deals: list[dict]) -> str:
    """IMessage featured section with short site deep links only."""
    if not deals:
        return ""
    lowest = min(int(d["price"]) for d in deals)
    header = f"📌 FLI-TRACKER · Watching · from ${lowest}"
    blocks = [_format_featured_deal_imessage(deal) for deal in deals]
    return header + "\n\n" + "\n\n".join(blocks)


def featured_digest_subject(deals: list[dict]) -> str:
    """Build the email/iMessage subject for featured-trip alerts."""
    if not deals:
        return "Fli-Tracker featured trip"
    lowest = min(int(d["price"]) for d in deals)
    title = deals[0].get("title") or "Featured trip"
    return f"Fli-Tracker: {title} from ${lowest}"


def _featured_digest_cards(deals: list[dict]) -> str:
    cards = []
    for deal in deals:
        title = deal.get("title") or "Featured trip"
        price = int(deal["price"])
        board = deal.get("site_url") or featured_deep_link(deal.get("id"))
        blurb = (deal.get("blurb") or "").strip()
        options = _dedupe_featured_options(deal.get("options") or [])
        if options:
            option_lines = []
            for opt in options:
                origin = opt.get("origin") or "—"
                dest = opt.get("destination") or "—"
                dates = format_short_date_range(opt.get("outDate", ""), opt.get("retDate", ""))
                window = opt.get("windowLabel") or ""
                airline = opt.get("airline") or "—"
                out_time = _compact_departure_time(opt.get("outDepFmt") or "")
                label = f"{window} · ${int(opt['price'])}" if window else f"${int(opt['price'])}"
                option_lines.append(
                    f"{html.escape(label)} — {html.escape(origin)} → {html.escape(dest)} · "
                    f"{html.escape(dates)} · {html.escape(airline)}"
                    + (f" · {html.escape(out_time)} out" if out_time else "")
                )
            subline = "<br>".join(option_lines)
            meta = blurb or "Pinned weekend search"
            book = options[0].get("url") or board
        else:
            origin = deal.get("origin") or "—"
            dest = deal.get("destination") or "—"
            dates = format_short_date_range(deal.get("out_date", ""), deal.get("ret_date", ""))
            airline = deal.get("airline") or "—"
            window = deal.get("window_label") or ""
            sub = f"{origin} → {dest} · {dates}"
            if window:
                sub = f"{sub} · {window}"
            subline = sub
            meta = airline
            book = deal.get("url") or board
        cards.append(
            _html_deal_card(
                headline=f"{title} · from ${price}",
                subline=subline,
                meta=meta,
                book_url=book,
                board_url=board,
            )
        )
    return "".join(cards)


def _format_premium_deal_plain(deal: dict, index: int, *, include_booking_url: bool) -> list[str]:
    dest = deal.get("destination") or deal.get("airport", "")
    cabin = deal.get("cabin_class", "BUSINESS").replace("_", " ").title()
    origin = deal.get("origin", "SLC")
    dates = format_short_date_range(deal.get("out_date", ""), deal.get("ret_date", ""))
    price_part = format_money(deal["price"]) if deal.get("price") is not None else ""
    points_part = format_points(deal["points"]) if deal.get("points") is not None else ""
    fare = " · ".join(part for part in (price_part, points_part) if part) or "—"
    book = deal.get("url") or premium_deals_deep_link()
    board = premium_deals_deep_link()

    lines = [
        f"{index}. {dest} · {cabin} · {fare}",
        f"   {origin} · {dates}",
        f"   ↗ {site_link_display(board)}",
    ]
    if include_booking_url and book != board:
        lines.append(f"   🔗 {book}")
    return lines


def _format_premium_deal_imessage(deal: dict) -> str:
    dest = deal.get("destination") or deal.get("airport", "")
    cabin = deal.get("cabin_class", "BUSINESS").replace("_", " ").title()
    origin = deal.get("origin", "SLC")
    dates = format_short_date_range(deal.get("out_date", ""), deal.get("ret_date", ""))
    price_part = format_money(deal["price"]) if deal.get("price") is not None else ""
    points_part = format_points(deal["points"]) if deal.get("points") is not None else ""
    fare = " · ".join(part for part in (price_part, points_part) if part) or "—"
    board = premium_deals_deep_link()
    return f"{dest} · {cabin} · {fare}\n{origin} · {dates}\n{board}"


def format_premium_digest_plain(deals: list[dict]) -> str:
    """Plain-text premium digest for email fallback."""
    if not deals:
        return ""

    lines = [
        "✨ FLI-TRACKER · Premium Deals",
        _DIVIDER,
        "",
    ]
    for index, deal in enumerate(deals, start=1):
        lines.extend(_format_premium_deal_plain(deal, index, include_booking_url=True))
        lines.append("")

    lines.extend([_DIVIDER, site_link_display(SITE_URL)])
    return "\n".join(lines).rstrip()


def format_premium_digest_imessage(deals: list[dict]) -> str:
    """IMessage premium digest with short dashboard links only."""
    if not deals:
        return ""

    header = f"✨ FLI-TRACKER · {len(deals)} premium deal{'' if len(deals) == 1 else 's'}"
    blocks = [_format_premium_deal_imessage(deal) for deal in deals]
    return header + "\n\n" + "\n\n".join(blocks) + f"\n\n{premium_deals_deep_link()}"


def _html_page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:{_BRAND_PRIMARY};">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3f4f6;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e5e7eb;">
          <tr>
            <td style="background:{_BRAND_PRIMARY};padding:20px 24px;">
              <div style="font-size:12px;letter-spacing:0.12em;text-transform:uppercase;color:#93c5fd;font-weight:700;">Fli-Tracker</div>
              <div style="font-size:22px;font-weight:700;color:#ffffff;margin-top:6px;">{html.escape(title)}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 24px 8px;">{body}</td>
          </tr>
          <tr>
            <td style="padding:8px 24px 24px;">
              <a href="{html.escape(SITE_URL)}" style="display:inline-block;color:{_ACCENT};font-size:14px;font-weight:600;text-decoration:none;">Open dashboard →</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _html_deal_card(
    *,
    headline: str,
    subline: str,
    meta: str,
    book_url: str,
    board_url: str,
) -> str:
    book = html.escape(book_url)
    board = html.escape(board_url)
    return f"""
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:16px;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
  <tr>
    <td style="padding:16px 18px;">
      <div style="font-size:18px;font-weight:700;color:{_BRAND_PRIMARY};">{html.escape(headline)}</div>
      <div style="font-size:14px;color:#4b5563;margin-top:6px;">{html.escape(subline)}</div>
      <div style="font-size:13px;color:#6b7280;margin-top:4px;">{html.escape(meta)}</div>
      <table role="presentation" cellspacing="0" cellpadding="0" style="margin-top:14px;">
        <tr>
          <td style="padding-right:10px;">
            <a href="{book}" style="display:inline-block;background:{_ACCENT};color:#ffffff;text-decoration:none;font-size:14px;font-weight:700;padding:10px 18px;border-radius:999px;">Book fare</a>
          </td>
          <td>
            <a href="{board}" style="display:inline-block;color:{_ACCENT};text-decoration:none;font-size:14px;font-weight:600;padding:10px 0;">View region</a>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""


def _morning_digest_cards(deals: list[dict]) -> str:
    cards = []
    for deal in deals:
        region = deal["region"]
        price = int(deal["price"])
        origin = deal["origin"]
        dest = deal["destination"]
        dates = format_short_date_range(deal["out_date"], deal["ret_date"])
        airline = deal.get("airline") or "—"
        board = region_deep_link(region)
        book = deal.get("url") or board
        cards.append(
            _html_deal_card(
                headline=f"{region} · ${price}",
                subline=f"{origin} → {dest} · {dates}",
                meta=airline,
                book_url=book,
                board_url=board,
            )
        )
    return "".join(cards)


def _premium_digest_cards(deals: list[dict]) -> str:
    cards = []
    for deal in deals:
        dest = deal.get("destination") or deal.get("airport", "")
        cabin = deal.get("cabin_class", "BUSINESS").replace("_", " ").title()
        origin = deal.get("origin", "SLC")
        dates = format_short_date_range(deal.get("out_date", ""), deal.get("ret_date", ""))
        price_part = format_money(deal["price"]) if deal.get("price") is not None else ""
        points_part = format_points(deal["points"]) if deal.get("points") is not None else ""
        fare = " · ".join(part for part in (price_part, points_part) if part) or "—"
        board = premium_deals_deep_link()
        book = deal.get("url") or board
        cards.append(
            _html_deal_card(
                headline=f"{dest} · {cabin} · {fare}",
                subline=f"{origin} · {dates}",
                meta="Premium cabin",
                book_url=book,
                board_url=board,
            )
        )
    return "".join(cards)


def format_morning_digest_html(deals: list[dict]) -> str:
    if not deals:
        return ""
    return _html_page("Morning Deals", _morning_digest_cards(deals))


def format_premium_digest_html(deals: list[dict]) -> str:
    if not deals:
        return ""
    return _html_page("Premium Deals", _premium_digest_cards(deals))


def combine_alert_content(
    sections: list[tuple[str, str, str, str, str]],
) -> tuple[str, str, str, str]:
    """Merge alert sections; tuple is (subject, title, email_plain, imessage_plain, cards_html)."""
    subject_hints = [section[0] for section in sections if section[0]]
    email_parts = [section[2] for section in sections if section[2]]
    imessage_parts = [section[3] for section in sections if section[3]]

    html_chunks: list[str] = []
    for _hint, title, _email, _imessage, cards in sections:
        if cards:
            html_chunks.append(
                f'<div style="font-size:13px;font-weight:700;letter-spacing:0.08em;'
                f'text-transform:uppercase;color:#6b7280;margin:0 0 12px;">{html.escape(title)}</div>'
                f"{cards}"
            )

    if len(subject_hints) == 1:
        subject = subject_hints[0]
    elif subject_hints:
        subject = "Fli-Tracker: deal alerts"
    else:
        subject = "Fli-Tracker deal alert"

    email_plain = "\n\n".join(email_parts)
    imessage_plain = "\n\n".join(imessage_parts)
    html_doc = _html_page("Deal Alerts", "".join(html_chunks)) if html_chunks else ""
    return subject, email_plain, imessage_plain, html_doc
