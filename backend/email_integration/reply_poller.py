"""Email inbox poller and automated reply responder.

Periodically queries inbound email conversation responses, runs them
through reply classification, schedules automated objection handlers,
and alerts representatives of high-intent actions.
"""
import os
import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime
from email_integration.conversation_drafter import ConversationDrafter

class ReplyPoller:
    def __init__(self, db_client=None):
        self.db = db_client
        self.drafter = ConversationDrafter()

    async def poll_and_process_once(self) -> int:
        """Scan received inbound emails that haven't been responded to yet."""
        if not self.db:
            return 0

        processed_count = 0
        try:
            # Query conversations in status 'received'
            received_res = self.db.table("email_conversations").select("*").eq("status", "received").execute()
            if not received_res.data:
                return 0

            for entry in received_res.data:
                brand_key = entry.get("brand_key")
                reply_text = entry.get("body", "")
                conv_id = entry.get("id")

                if not brand_key or not reply_text:
                    continue

                # 1. Fetch brand context
                brand_res = self.db.table("brands").select("*").eq("brand_key", brand_key).limit(1).execute()
                if not brand_res.data:
                    continue
                brand_data = brand_res.data[0]

                # 2. Fetch anchor ASIN prospect data
                prospect_data = None
                asin = brand_data.get("anchor_asin")
                if asin and asin != "apollo_direct":
                    p_res = self.db.table("prospects").select("*").eq("asin", asin).limit(1).execute()
                    if p_res.data:
                        prospect_data = p_res.data[0]

                # 3. Classify reply using LLM (if not already classified)
                classification = entry.get("classification")
                if not classification:
                    from routers.email_engine import _classify_reply
                    classification = await _classify_reply(reply_text)

                # 4. Generate AI Draft response
                # Load previous conversation thread context
                prior_res = self.db.table("email_conversations").select("*").eq("brand_key", brand_key).order("created_at").execute()
                prior_thread = prior_res.data or []

                draft = await self.drafter.draft_response(
                    brand_data=brand_data,
                    prospect_data=prospect_data,
                    reply_text=reply_text,
                    conversation_context=prior_thread,
                    classification=classification
                )

                # 5. Apply stages according to reply category
                cat = classification.get("category", "NOISE").upper()
                new_stage = brand_data.get("stage", "REPLIED")
                if cat == "BOOKING_READY":
                    new_stage = "DEMO_SCHEDULED"
                elif cat == "INTERESTED":
                    new_stage = "DEMO_SCHEDULED"
                elif cat == "UNSUBSCRIBE" or cat == "COMPETITOR":
                    new_stage = "SKIP"
                elif cat == "WRONG_PERSON":
                    new_stage = "BRAND_RESOLVED"
                else:
                    new_stage = "REPLIED"

                # Update brand stage in database
                self.db.table("brands").update({
                    "stage": new_stage,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("brand_key", brand_key).execute()

                # Update current email status to processed and set classification
                self.db.table("email_conversations").update({
                    "status": "received", # keep as received but store classification
                    "classification": classification
                }).eq("id", conv_id).execute()

                # Insert the AI-drafted reply into email_conversations
                if draft:
                    self.db.table("email_conversations").insert({
                        "brand_key": brand_key,
                        "direction": "outbound",
                        "body": draft,
                        "ai_draft": draft,
                        "status": "pending",
                        "created_at": datetime.utcnow().isoformat()
                    }).execute()

                processed_count += 1

        except Exception as e:
            logging.error(f"Error during inbound email polling and processing: {e}")

        return processed_count

    async def start_polling_loop(self, interval_seconds: int = 60):
        """Continuously poll and process in the background."""
        logging.info("Starting background B2B email reply polling loop.")
        while True:
            await self.poll_and_process_once()
            await asyncio.sleep(interval_seconds)
