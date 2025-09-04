# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta, timezone
import time
import requests

from odoo import api, fields, models, _
from odoo.tools import html_sanitize

_logger = logging.getLogger(__name__)
EVENTBRITE_API = "https://www.eventbriteapi.com/v3"

# -----------------------------
# Extend event.event (minimal)
# -----------------------------
class EventEvent(models.Model):
    _inherit = "event.event"

    eventbrite_id = fields.Char(index=True, copy=False)
    external_url  = fields.Char(string="External Registration URL")
    eventbrite_changed = fields.Datetime()
    last_synced_at = fields.Datetime()
    eventbrite_status = fields.Char()

# --------------------------------
# Sync service (cron + manual run)
# --------------------------------
class EventbriteSync(models.TransientModel):
    _name = "eventbrite.sync"
    _description = "Eventbrite Sync Service"

    # Manual fetch button hook (used by Settings server action)
    def action_fetch_all_events(self):
        self.ensure_one()
        result = self._fetch_all_events_simple()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": result, "type": "success"},
        }

    @api.model
    def cron_sync_eventbrite(self):
        self._sync_eventbrite()

    # -------------- Simple Fetch (Auto-detect org) --------------
    def _fetch_all_events_simple(self):
        """Simple fetch that auto-detects organization ID from token"""
        ICP = self.env["ir.config_parameter"].sudo()
        token = ICP.get_param("eventbrite.api_token")
        if not token:
            return "Error: No API token found. Please enter your Eventbrite API token first."

        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            # First, get user info to find organization ID
            user_resp = requests.get(f"{EVENTBRITE_API}/users/me/", headers=headers, timeout=30)
            self._rate_limit_guard(user_resp)
            user_data = user_resp.json()
            
            # Get organizations for this user
            orgs_resp = requests.get(f"{EVENTBRITE_API}/users/me/organizations/", headers=headers, timeout=30)
            self._rate_limit_guard(orgs_resp)
            orgs_data = orgs_resp.json()
            
            if not orgs_data.get("organizations"):
                return "Error: No organizations found for this token. Please check your Eventbrite account."
            
            # Use the first organization
            org_id = orgs_data["organizations"][0]["id"]
            org_name = orgs_data["organizations"][0]["name"]
            
            # Store the org ID for future use
            ICP.set_param("eventbrite.org_id", org_id)
            ICP.set_param("eventbrite.search_mode", "org")
            ICP.set_param("eventbrite.auto_publish", "1")
            ICP.set_param("eventbrite.restrict_only_api_events", "1")
            
            # Now fetch events from this organization
            now = datetime.now(timezone.utc)
            end_dt = now + timedelta(days=60)  # Next 60 days
            
            events = self._fetch_org_events(headers, org_id, start_after=now, end_before=end_dt)
            
            created, updated, skipped = 0, 0, 0
            for ev in events:
                try:
                    res = self._upsert_minimal(ev, True, False)  # Auto-publish, no specific website
                    if res == "created": created += 1
                    elif res == "updated": updated += 1
                    else: skipped += 1
                except Exception:
                    _logger.exception("Failed to upsert EB event %s", ev.get("id"))
                    continue
            
            # Unpublish non-Eventbrite events
            self._unpublish_non_eventbrite_events(False)
            
            return f"Success! Found {len(events)} events from '{org_name}'. Created: {created}, Updated: {updated}, Skipped: {skipped}"
            
        except Exception as e:
            _logger.exception("Error in simple fetch")
            return f"Error: {str(e)}"

    # -------------- Core Sync --------------
    @api.model
    def _sync_eventbrite(self):
        ICP = self.env["ir.config_parameter"].sudo()
        token = ICP.get_param("eventbrite.api_token")
        if not token:
            _logger.warning("Eventbrite token missing; skipping sync.")
            return

        search_mode = ICP.get_param("eventbrite.search_mode", "org")
        org_id = ICP.get_param("eventbrite.org_id")
        location_address = ICP.get_param("eventbrite.location_address", "")
        within = ICP.get_param("eventbrite.location_within", "25km")
        date_window_days = int(ICP.get_param("eventbrite.date_window_days", "60"))
        auto_publish = ICP.get_param("eventbrite.auto_publish", "1") == "1"
        website_id = int(ICP.get_param("eventbrite.website_id", "0") or 0)
        restrict_only_api = ICP.get_param("eventbrite.restrict_only_api_events", "1") == "1"

        headers = {"Authorization": f"Bearer {token}"}
        now = datetime.now(timezone.utc)
        end_dt = now + timedelta(days=date_window_days)

        # Fetch events from Eventbrite
        if search_mode == "org":
            if not org_id:
                _logger.error("Eventbrite org_id required in Organization mode.")
                return
            events = self._fetch_org_events(headers, org_id, start_after=now, end_before=end_dt)
        else:
            events = self._search_events(headers, location_address, within, start=now, end=end_dt)

        created, updated, skipped = 0, 0, 0
        for ev in events:
            try:
                res = self._upsert_minimal(ev, auto_publish, website_id)
                if res == "created": created += 1
                elif res == "updated": updated += 1
                else: skipped += 1
            except Exception:
                _logger.exception("Failed to upsert EB event %s", ev.get("id"))
                continue

        # Optionally unpublish non-Eventbrite events so only API events show on site
        if restrict_only_api:
            self._unpublish_non_eventbrite_events(website_id)

        _logger.info("Eventbrite Sync: created=%s updated=%s skipped=%s total=%s",
                     created, updated, skipped, len(events))

    # -------------- EB Fetchers --------------
    def _fetch_org_events(self, headers, org_id, start_after, end_before):
        events, page = [], 1
        params = {
            "status": "live",
            "order_by": "start_asc",
            "page": page,
            "expand": "venue,logo",
            "time_filter": "start",
            "start_date.range_start": start_after.isoformat(),
            "start_date.range_end": end_before.isoformat(),
        }
        url = f"{EVENTBRITE_API}/organizations/{org_id}/events/"
        while True:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            self._rate_limit_guard(resp)
            data = resp.json()
            events += data.get("events", [])
            if not data.get("pagination", {}).get("has_more_items"):
                break
            page += 1
            params["page"] = page
        return events

    def _search_events(self, headers, address, within, start, end):
        events, page = [], 1
        params = {
            "sort_by": "date",
            "page": page,
            "expand": "venue,logo",
            "location.address": address or "",
            "location.within": within or "25km",
            "start_date.range_start": start.isoformat(),
            "start_date.range_end": end.isoformat(),
        }
        url = f"{EVENTBRITE_API}/events/search/"
        while True:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            self._rate_limit_guard(resp)
            data = resp.json()
            events += data.get("events", [])
            if not data.get("pagination", {}).get("has_more_items"):
                break
            page += 1
            params["page"] = page
        return events

    # -------------- UPSERT (Minimal fields only) --------------
    def _upsert_minimal(self, eb_event, auto_publish, website_id):
        Event = self.env["event.event"].sudo()

        eb_id = eb_event.get("id")
        if not eb_id:
            return "skipped"

        # Required minimal mapping
        name = (eb_event.get("name") or {}).get("text") or ""  # internal; not displayed on website
        start = eb_event.get("start") or {}
        end = eb_event.get("end") or {}

        start_local = start.get("local")
        start_tz = start.get("timezone")
        end_local = end.get("local")
        end_tz = end.get("timezone") or start_tz

        date_begin_utc = self._to_utc(start_local, start_tz)
        date_end_utc = self._to_utc(end_local, end_tz)

        status = eb_event.get("status")  # live, canceled, etc.
        external_url = eb_event.get("url")

        # Venue → res.partner
        venue = eb_event.get("venue") or {}
        venue_name = venue.get("name")
        venue_addr = (venue.get("address") or {})
        partner_id = False
        if venue_name or venue_addr:
            partner_id = self._get_or_create_venue_partner(venue_name, venue_addr)

        # Image (logo)
        logo = eb_event.get("logo") or {}
        logo_url = logo.get("url")

        # Change timestamp for idempotency
        changed = eb_event.get("changed") or eb_event.get("updated") or eb_event.get("created")
        changed_dt = None
        if changed:
            try:
                changed_dt = datetime.fromisoformat(changed.replace("Z", "+00:00"))
            except Exception:
                changed_dt = None

        existing = Event.search([("eventbrite_id", "=", eb_id)], limit=1)

        vals = {
            "name": name or "Event",           # internal only
            "date_begin": date_begin_utc,      # website shows time
            "date_end": date_end_utc,
            "external_url": external_url,      # website CTA uses this
            "eventbrite_status": status,
        }
        if partner_id:
            vals["address_id"] = partner_id
        if website_id:
            vals["website_id"] = website_id

        publish_flag = auto_publish and status in ("live", "scheduled", "started")
        unpublish_flag = status in ("canceled", "deleted")

        if existing:
            # Update only if EB changed is newer
            if changed_dt and existing.eventbrite_changed and changed_dt <= existing.eventbrite_changed:
                return "skipped"
            existing.write(vals)
            if logo_url:
                self._set_event_image(existing, logo_url)
            # publish/unpublish
            if publish_flag:
                existing.website_published = True
            if unpublish_flag:
                existing.website_published = False
                existing.active = False
            existing.eventbrite_changed = changed_dt
            existing.last_synced_at = fields.Datetime.now()
            return "updated"
        else:
            vals.update({
                "eventbrite_id": eb_id,
                "eventbrite_changed": changed_dt,
                "last_synced_at": fields.Datetime.now(),
                "website_published": publish_flag,
            })
            rec = Event.create(vals)
            if logo_url:
                self._set_event_image(rec, logo_url)
            if unpublish_flag:
                rec.website_published = False
                rec.active = False
            return "created"

    # -------------- Helpers --------------
    def _rate_limit_guard(self, resp):
        if resp.status_code == 429:
            _logger.warning("Eventbrite 429 rate limited; sleeping 5s...")
            time.sleep(5)
            return
        resp.raise_for_status()

    def _to_utc(self, local_iso, tzname):
        if not local_iso:
            return False
        try:
            dt = datetime.fromisoformat(local_iso)  # may be naive
            if dt.tzinfo is None:
                # store as-is; Odoo will treat as naive UTC
                return dt
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            return fields.Datetime.now()

    def _get_or_create_venue_partner(self, name, addr):
        Partner = self.env["res.partner"].sudo()
        pname = name or "Venue"
        # try match by name + city if available
        dom = [("name", "=", pname)]
        partner = Partner.search(dom, limit=1)
        vals = {"name": pname, "type": "other"}
        if addr:
            vals.update({
                "street": addr.get("address_1") or addr.get("address"),
                "street2": addr.get("address_2"),
                "city": addr.get("city"),
                "zip": addr.get("postal_code"),
            })
            country = self._find_country(addr.get("country"))
            if country:
                vals["country_id"] = country
        if partner:
            partner.write(vals)
            return partner.id
        return Partner.create(vals).id

    def _find_country(self, code_or_name):
        if not code_or_name:
            return False
        Country = self.env["res.country"].sudo()
        c = Country.search([("|", ("code", "=", code_or_name), ("name", "=", code_or_name))], limit=1)
        return c.id or False

    def _set_event_image(self, event_record, url):
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            event_record.image_1920 = r.content
        except Exception as e:
            _logger.warning("Failed to download event image: %s", e)

    def _unpublish_non_eventbrite_events(self, website_id):
        """Ensure only API-synced events show on website."""
        dom = [("website_published", "=", True), ("eventbrite_id", "=", False)]
        if website_id:
            dom.append(("website_id", "=", website_id))
        events = self.env["event.event"].sudo().search(dom, limit=1000)
        # Avoid deactivating (keep them in backend), just unpublish
        if events:
            events.write({"website_published": False})
            _logger.info("Unpublished %s non-Eventbrite events from website.", len(events))


