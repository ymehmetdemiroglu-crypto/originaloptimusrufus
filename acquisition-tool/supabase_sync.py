"""Supabase is now the primary store. This sync module is obsolete."""


def run_full_sync(stage_filter=None, console=None):
    msg = "supabase-sync is obsolete — Supabase is now the primary store."
    if console:
        console.print(f"[dim]{msg}[/dim]")
    else:
        print(msg)
    return {"brands_upserted": 0, "emails_upserted": 0, "errors": 0}


sync_brands = run_full_sync
sync_step_emails = run_full_sync
