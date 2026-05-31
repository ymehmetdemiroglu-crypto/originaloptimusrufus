"""Display + manual stage-move helpers for the CLI. No business logic."""
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich import box

import db
from models import STAGES

console = Console()


def _stage_color(stage: str) -> str:
    colors = {
        "LISTING_FOUND": "dim",
        "WEAK_LISTING": "yellow",
        "WEAK_BRAND": "yellow",
        "BRAND_RESOLVED": "blue",
        "CONTACT_ENRICHED": "cyan",
        "EMAIL_DRAFTED": "cyan",
        "SEQUENCED": "magenta",
        "CALCULATOR_USED": "bright_cyan",
        "CALCULATOR_SUBMITTED": "bright_green",
        "LINKEDIN_CONNECTED": "bright_blue",
        "REPLIED": "blue",
        "DEMO_SCHEDULED": "magenta",
        "BETA_ACTIVE": "bright_magenta",
        "REVIEW_REQUESTED": "bright_yellow",
        "PAID": "bright_green",
        "SKIP": "red",
    }
    return colors.get(stage, "white")


def _fmt_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return "—"
    delta = datetime.utcnow() - dt
    hours = int(delta.total_seconds() // 3600)
    if hours < 24:
        return f"{hours}h ago"
    return f"{delta.days}d ago"


def show_dashboard():
    db.init_db()
    counts = db.get_pipeline_counts()
    last_scrape = db.get_last_scrape()
    total = sum(counts.values())

    pipeline_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    pipeline_table.add_column("Stage", style="bold")
    pipeline_table.add_column("Count", justify="right")

    active_stages = [
        "LISTING_FOUND", "WEAK_LISTING", "WEAK_BRAND",
        "CONTACT_ENRICHED", "EMAIL_DRAFTED", "SEQUENCED",
        "CALCULATOR_USED", "CALCULATOR_SUBMITTED",
        "REPLIED", "DEMO_SCHEDULED", "BETA_ACTIVE", "PAID",
    ]
    for stage in active_stages:
        count = counts.get(stage, 0)
        color = _stage_color(stage)
        pipeline_table.add_row(Text(stage, style=color), Text(str(count), style="bold " + color))

    scrape_info = f"Last scrape: {_fmt_dt(last_scrape)}" if last_scrape else "No scrape yet"
    stats_text = f"{scrape_info}\nTotal prospects: {total}"

    console.print(Panel(
        Columns([pipeline_table, Text(stats_text, style="dim")], equal=True),
        title="[bold]Optimus Rufus — Acquisition Pipeline[/bold]",
        border_style="bright_blue",
    ))


def list_prospects(stage: Optional[str] = None, limit: Optional[int] = None):
    db.init_db()
    prospects = db.list_prospects(stage)
    if limit:
        prospects = prospects[:limit]

    title = f"Prospects — {stage}" if stage else "All Prospects"
    table = Table(title=title, box=box.ROUNDED)
    table.add_column("ID", style="dim", width=14)
    table.add_column("Brand")
    table.add_column("Category")
    table.add_column("Stage")
    table.add_column("Weak", justify="right")
    table.add_column("Rufus", justify="right")
    table.add_column("Cite", justify="center")
    table.add_column("Age")

    for p in prospects:
        color = _stage_color(p.stage)
        prob = p.rufus_citation_probability or "—"
        prob_color = {"high": "green", "medium": "yellow", "low": "red"}.get(prob, "dim")
        table.add_row(
            p.id[:14],
            (p.brand or p.username or "—")[:24],
            (p.category or p.subreddit or "—")[:20],
            Text(p.stage, style=color),
            str(p.weakness_score or "—"),
            str(p.rufus_score or "—"),
            Text(prob[:6], style=prob_color),
            _fmt_dt(p.created_at),
        )

    console.print(table)
    console.print(f"[dim]{len(prospects)} prospects[/dim]")


def show_prospect(prospect_id: str):
    db.init_db()
    p = _fuzzy_find(prospect_id)
    if not p:
        console.print(f"[red]Prospect '{prospect_id}' not found.[/red]")
        return

    color = _stage_color(p.stage)

    info = Table(box=box.SIMPLE, show_header=False)
    info.add_column("Field", style="bold dim")
    info.add_column("Value")
    info.add_row("ID", p.id)
    info.add_row("Brand", p.brand or p.username or "—")
    info.add_row("ASIN", p.asin or "—")
    info.add_row("Category", p.category or p.subreddit or "—")
    info.add_row("Stage", Text(p.stage, style=color))
    info.add_row("Price", f"${p.listing_price}" if p.listing_price else "—")
    info.add_row("Reviews", f"{p.listing_review_count} @ {p.listing_rating}★" if p.listing_review_count else "—")
    info.add_row("Bullets / Images / Q&A", f"{p.bullet_count or 0} / {p.image_count or 0} / {p.qa_count or 0}")
    info.add_row("A+ content", "yes" if p.has_a_plus else "no")
    info.add_row("Weakness", f"{p.weakness_score or '—'}  signals={p.weakness_signals or '—'}")
    if p.rufus_score is not None:
        prob = p.rufus_citation_probability or "?"
        prob_color = {"high": "green", "medium": "yellow", "low": "red"}.get(prob, "white")
        info.add_row(
            "Rufus",
            f"[bold]{p.rufus_score}/100[/bold]  IA={p.intent_alignment_score} "
            f"AD={p.attribute_density_score} CR={p.conversational_readability_score} "
            f"QA={p.qa_coverage_score}  cite=[{prob_color}]{prob}[/{prob_color}]",
        )
        if p.rufus_summary:
            info.add_row("Rufus summary", p.rufus_summary)
    info.add_row("URL", p.post_url)
    info.add_row("Found", _fmt_dt(p.created_at))

    console.print(Panel(info, title=f"[bold]{p.post_title[:80]}[/bold]", border_style=color))

    if p.post_body:
        console.print(Panel(p.post_body[:1500], title="Bullets", border_style="dim"))

    if p.email_teardown:
        console.print(Panel(p.email_teardown, title="[cyan]Email Teardown[/cyan]", border_style="cyan"))

    if p.notes:
        console.print(Panel(p.notes, title="Notes", border_style="yellow"))


def move_stage(prospect_id: str, stage: str):
    db.init_db()
    stage = stage.upper()
    if stage not in STAGES:
        console.print(f"[red]Invalid stage '{stage}'. Valid: {', '.join(STAGES)}[/red]")
        return
    p = _fuzzy_find(prospect_id)
    if not p:
        console.print(f"[red]Prospect '{prospect_id}' not found.[/red]")
        return
    db.update_stage(p.id, stage)
    color = _stage_color(stage)
    console.print(f"[green]✓[/green] {p.brand or p.username} → [bold {color}]{stage}[/bold {color}]")


def add_note(prospect_id: str, note: str):
    db.init_db()
    p = _fuzzy_find(prospect_id)
    if not p:
        console.print(f"[red]Prospect '{prospect_id}' not found.[/red]")
        return
    db.add_note(p.id, note)
    console.print(f"[green]✓[/green] Note added to {p.brand or p.username}")


def show_stats():
    db.init_db()
    stats = db.get_stats()
    funnel = stats["funnel"]

    def pct(a, b):
        return f"{int(a/b*100)}%" if b else "—"

    funnel_table = Table(title="Conversion Funnel", box=box.SIMPLE, show_header=True)
    funnel_table.add_column("Stage", style="bold")
    funnel_table.add_column("Count", justify="right")
    funnel_table.add_column("Conv. Rate", justify="right", style="dim")

    rows = [
        ("Total in DB", funnel["total"], ""),
        ("Sequenced", funnel.get("messaged", 0), pct(funnel.get("messaged", 0), funnel["total"])),
        ("Replied", funnel["replied"], pct(funnel["replied"], funnel.get("messaged", 0) or 1)),
        ("Demo scheduled", funnel["demo"], pct(funnel["demo"], funnel["replied"] or 1)),
        ("Beta active", funnel["beta"], pct(funnel["beta"], funnel["demo"] or 1)),
        ("Paid", funnel["paid"], pct(funnel["paid"], funnel["beta"] or 1)),
    ]
    for name, count, rate in rows:
        color = "bright_green" if name == "Paid" else ("green" if count > 0 else "dim")
        funnel_table.add_row(name, Text(str(count), style=color), rate)

    console.print(funnel_table)


def export_csv(stage: Optional[str] = None):
    import csv
    db.init_db()
    prospects = db.list_prospects(stage)
    if not prospects:
        console.print("[dim]No prospects to export.[/dim]")
        return

    filename = f"export_{stage.lower() if stage else 'all'}_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
    fieldnames = [
        "id", "brand", "asin", "category", "stage", "weakness_score", "rufus_score",
        "rufus_citation_probability", "listing_price", "listing_rating", "listing_review_count",
        "contact_email", "contact_first_name", "contact_last_name", "contact_title",
        "domain", "post_url", "created_at",
    ]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in prospects:
            writer.writerow({
                "id": p.id,
                "brand": p.brand or "",
                "asin": p.asin or "",
                "category": p.category or "",
                "stage": p.stage,
                "weakness_score": p.weakness_score or "",
                "rufus_score": p.rufus_score or "",
                "rufus_citation_probability": p.rufus_citation_probability or "",
                "listing_price": p.listing_price or "",
                "listing_rating": p.listing_rating or "",
                "listing_review_count": p.listing_review_count or "",
                "contact_email": p.contact_email or "",
                "contact_first_name": p.contact_first_name or "",
                "contact_last_name": p.contact_last_name or "",
                "contact_title": p.contact_title or "",
                "domain": p.domain or "",
                "post_url": p.post_url,
                "created_at": p.created_at.isoformat() if p.created_at else "",
            })

    console.print(f"[green]✓[/green] Exported {len(prospects)} prospects to [bold]{filename}[/bold]")


def mark_replied(prospect_id: str, reply_text: Optional[str] = None):
    db.init_db()
    p = _fuzzy_find(prospect_id)
    if not p:
        console.print(f"[red]Prospect '{prospect_id}' not found.[/red]")
        return
    db.update_stage(p.id, "REPLIED")
    if reply_text:
        db.add_note(p.id, f"REPLY: {reply_text}")
    color = _stage_color("REPLIED")
    console.print(f"[green]✓[/green] {p.brand or p.username} → [bold {color}]REPLIED[/bold {color}]")


def open_prospect_url(prospect_id: str):
    import webbrowser
    db.init_db()
    p = _fuzzy_find(prospect_id)
    if not p:
        console.print(f"[red]Prospect '{prospect_id}' not found.[/red]")
        return
    webbrowser.open(p.post_url)
    console.print(f"[green]✓[/green] Opened {p.post_url}")


def _fuzzy_find(prospect_id: str):
    p = db.get_prospect(prospect_id)
    if p:
        return p
    for prospect in db.list_prospects():
        if prospect.id.startswith(prospect_id):
            return prospect
    return None
