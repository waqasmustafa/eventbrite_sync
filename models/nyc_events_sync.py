# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta, timezone
import time
import requests

from odoo import api, fields, models, _
from odoo.tools import html_sanitize

_logger = logging.getLogger(__name__)
TICKETMASTER_API = "https://app.ticketmaster.com/discovery/v2"

# -----------------------------
# Extend event.event (minimal)
# -----------------------------
class EventEvent(models.Model):
    _inherit = "event.event"

    ticketmaster_id = fields.Char(index=True, copy=False)
    external_url  = fields.Char(string="External Registration URL")
    ticketmaster_changed = fields.Datetime()
    last_synced_at = fields.Datetime()
    ticketmaster_status = fields.Char()
    event_category = fields.Char(string="Event Category")
    venue_name = fields.Char(string="Venue Name")

# --------------------------------
# Sync service (cron + manual run)
# --------------------------------
class NYCEventsSync(models.TransientModel):
    _name = "nyc.events.sync"
    _description = "NYC Events Sync Service"

    # Manual fetch button hook (used by Settings server action)
    def action_fetch_all_events(self):
        self.ensure_one()
        result = self._fetch_nyc_events()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": result, "type": "success"},
        }

    @api.model
    def cron_sync_nyc_events(self):
        self._sync_nyc_events()

    # -------------- NYC Events Fetch --------------
    def _fetch_nyc_events(self):
        """Fetch all NYC events from Ticketmaster Discovery API"""
        ICP = self.env["ir.config_parameter"].sudo()
        api_key = ICP.get_param("ticketmaster.api_key")
        if not api_key:
            return "Error: No Ticketmaster API key found. Please enter your Ticketmaster API key first."

        try:
            # Fetch all NYC events from Ticketmaster
            events = self._fetch_ticketmaster_events(api_key)
            
            # Store settings for future use
            ICP.set_param("ticketmaster.auto_publish", "1")
            ICP.set_param("ticketmaster.restrict_only_api_events", "1")
            
            created, updated, skipped = 0, 0, 0
            for event in events:
                try:
                    res = self._upsert_ticketmaster_event(event, True, False)  # Auto-publish, no specific website
                    if res == "created": created += 1
                    elif res == "updated": updated += 1
                    else: skipped += 1
                except Exception:
                    _logger.exception("Failed to upsert Ticketmaster event %s", event.get("id"))
                    continue
            
            # Unpublish non-Ticketmaster events
            self._unpublish_non_ticketmaster_events(False)
            
            return f"Success! Found {len(events)} NYC events from Ticketmaster. Created: {created}, Updated: {updated}, Skipped: {skipped}"
            
        except Exception as e:
            _logger.exception("Error in NYC events fetch")
            return f"Error: {str(e)}"

    # -------------- Core Sync --------------
    @api.model
    def _sync_nyc_events(self):
        ICP = self.env["ir.config_parameter"].sudo()
        api_key = ICP.get_param("ticketmaster.api_key")
        if not api_key:
            _logger.warning("Ticketmaster API key missing; skipping sync.")
            return

        auto_publish = ICP.get_param("ticketmaster.auto_publish", "1") == "1"
        website_id = int(ICP.get_param("ticketmaster.website_id", "0") or 0)
        restrict_only_api = ICP.get_param("ticketmaster.restrict_only_api_events", "1") == "1"

        try:
            # Fetch all NYC events from Ticketmaster
            events = self._fetch_ticketmaster_events(api_key)

            created, updated, skipped = 0, 0, 0
            for event in events:
                try:
                    res = self._upsert_ticketmaster_event(event, auto_publish, website_id)
                    if res == "created": created += 1
                    elif res == "updated": updated += 1
                    else: skipped += 1
                except Exception:
                    _logger.exception("Failed to upsert Ticketmaster event %s", event.get("id"))
                    continue

            # Optionally unpublish non-Ticketmaster events so only API events show on site
            if restrict_only_api:
                self._unpublish_non_ticketmaster_events(website_id)

            _logger.info("NYC Events Sync: created=%s updated=%s skipped=%s total=%s",
                         created, updated, skipped, len(events))
        except Exception as e:
            _logger.exception("Error in NYC events sync")

    # -------------- Ticketmaster Fetchers --------------
    def _fetch_ticketmaster_events(self, api_key):
        """Fetch all NYC events from Ticketmaster Discovery API"""
        events = []
        page = 0
        size = 200  # Maximum page size
        
        while True:
            params = {
                "apikey": api_key,
                "city": "New York",
                "countryCode": "US",
                "size": size,
                "page": page
            }
            
            url = f"{TICKETMASTER_API}/events.json"
            resp = requests.get(url, params=params, timeout=30)
            self._rate_limit_guard(resp)
            data = resp.json()
            
            page_events = data.get("_embedded", {}).get("events", [])
            events.extend(page_events)
            
            # Check if we have more pages
            page_info = data.get("page", {})
            if page_info.get("number", 0) >= page_info.get("totalPages", 0) - 1:
                break
                
            page += 1
            
            # Safety limit to prevent infinite loops
            if page > 50:  # Max 10,000 events (50 pages * 200 events)
                _logger.warning("Reached maximum page limit (50), stopping fetch")
                break
                
        _logger.info(f"Fetched {len(events)} events from Ticketmaster")
        return events

    # -------------- UPSERT Ticketmaster Events --------------
    def _upsert_ticketmaster_event(self, tm_event, auto_publish, website_id):
        Event = self.env["event.event"].sudo()

        tm_id = tm_event.get("id")
        if not tm_id:
            return "skipped"

        # Extract event data from Ticketmaster format
        name = tm_event.get("name", "Event")
        
        # Date handling
        dates = tm_event.get("dates", {})
        start_date = dates.get("start", {})
        date_begin_utc = self._parse_ticketmaster_date(start_date.get("dateTime"))
        
        # End date (optional)
        end_date = dates.get("end", {})
        date_end_utc = self._parse_ticketmaster_date(end_date.get("dateTime"))
        
        # Status
        status = tm_event.get("dates", {}).get("status", {}).get("code", "onsale")
        
        # External URL
        external_url = tm_event.get("url")
        
        # Venue information
        venue = tm_event.get("_embedded", {}).get("venues", [{}])[0] if tm_event.get("_embedded", {}).get("venues") else {}
        venue_name = venue.get("name", "")
        partner_id = self._get_or_create_venue_partner(venue_name, venue)
        
        # Event category/classification
        classifications = tm_event.get("classifications", [])
        event_category = ""
        if classifications:
            classification = classifications[0]
            segment = classification.get("segment", {})
            genre = classification.get("genre", {})
            event_category = f"{segment.get('name', '')} - {genre.get('name', '')}".strip(" -")
        
        # Images
        images = tm_event.get("images", [])
        image_url = None
        if images:
            # Get the largest image
            image_url = max(images, key=lambda x: x.get("width", 0) * x.get("height", 0)).get("url")

        existing = Event.search([("ticketmaster_id", "=", tm_id)], limit=1)

        vals = {
            "name": name,
            "date_begin": date_begin_utc,
            "date_end": date_end_utc,
            "external_url": external_url,
            "ticketmaster_status": status,
            "event_category": event_category,
            "venue_name": venue_name,
        }
        if partner_id:
            vals["address_id"] = partner_id
        if website_id:
            vals["website_id"] = website_id

        publish_flag = auto_publish and status in ("onsale", "rescheduled")
        unpublish_flag = status in ("cancelled", "postponed")

        if existing:
            existing.write(vals)
            if image_url:
                self._set_event_image(existing, image_url)
            # publish/unpublish
            if publish_flag:
                existing.website_published = True
            if unpublish_flag:
                existing.website_published = False
                existing.active = False
            existing.last_synced_at = fields.Datetime.now()
            return "updated"
        else:
            vals.update({
                "ticketmaster_id": tm_id,
                "last_synced_at": fields.Datetime.now(),
                "website_published": publish_flag,
            })
            rec = Event.create(vals)
            if image_url:
                self._set_event_image(rec, image_url)
            if unpublish_flag:
                rec.website_published = False
                rec.active = False
            return "created"

    # -------------- Helpers --------------
    def _rate_limit_guard(self, resp):
        if resp.status_code == 429:
            _logger.warning("Ticketmaster 429 rate limited; sleeping 5s...")
            time.sleep(5)
            return
        if resp.status_code == 400:
            _logger.error("Ticketmaster 400 Bad Request. Response: %s", resp.text)
            raise requests.exceptions.HTTPError(f"400 Bad Request: {resp.text}")
        resp.raise_for_status()

    def _parse_ticketmaster_date(self, date_str):
        """Parse Ticketmaster date string to UTC datetime"""
        if not date_str:
            return False
        try:
            # Ticketmaster dates are in ISO format with timezone
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            return fields.Datetime.now()

    def _get_or_create_venue_partner(self, name, venue_data):
        Partner = self.env["res.partner"].sudo()
        pname = name or "Venue"
        # try match by name + city if available
        dom = [("name", "=", pname)]
        partner = Partner.search(dom, limit=1)
        vals = {"name": pname, "type": "other"}
        if venue_data:
            # Ticketmaster venue format
            location = venue_data.get("location", {})
            address = venue_data.get("address", {})
            vals.update({
                "street": address.get("line1", ""),
                "street2": address.get("line2", ""),
                "city": location.get("city", ""),
                "zip": location.get("postalCode", ""),
                "state_id": self._find_state(location.get("stateCode")),
            })
            country = self._find_country(location.get("countryCode"))
            if country:
                vals["country_id"] = country
        if partner:
            partner.write(vals)
            return partner.id
        return Partner.create(vals).id

    def _find_country(self, code):
        if not code:
            return False
        Country = self.env["res.country"].sudo()
        c = Country.search([("code", "=", code.upper())], limit=1)
        return c.id or False

    def _find_state(self, code):
        if not code:
            return False
        State = self.env["res.country.state"].sudo()
        s = State.search([("code", "=", code.upper())], limit=1)
        return s.id or False

    def _set_event_image(self, event_record, url):
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            event_record.image_1920 = r.content
        except Exception as e:
            _logger.warning("Failed to download event image: %s", e)

    def _unpublish_non_ticketmaster_events(self, website_id):
        """Ensure only API-synced events show on website."""
        dom = [("website_published", "=", True), ("ticketmaster_id", "=", False)]
        if website_id:
            dom.append(("website_id", "=", website_id))
        events = self.env["event.event"].sudo().search(dom, limit=1000)
        # Avoid deactivating (keep them in backend), just unpublish
        if events:
            events.write({"website_published": False})
            _logger.info("Unpublished %s non-Ticketmaster events from website.", len(events))


