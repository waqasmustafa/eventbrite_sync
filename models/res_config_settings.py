# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    eventbrite_api_token = fields.Char(string="Eventbrite API Token")
    eventbrite_location = fields.Char(string="Search Location", default="New York", help="Enter city name to search for events (e.g., New York, Los Angeles, London)")
    eventbrite_org_id = fields.Char(string="Eventbrite Organization ID")
    eventbrite_search_mode = fields.Selection(
        [
            ("org", "Organization Events"),
            ("search", "Search by Location/Date"),
        ],
        default="org",
        string="Fetch Mode",
    )
    eventbrite_location_address = fields.Char(string="Search: City/Address (optional)")
    eventbrite_location_within = fields.Char(string="Search: Radius (e.g., 25km or 10mi)", default="25km")
    eventbrite_date_window_days = fields.Integer(string="Date Window (days ahead)", default=60)
    eventbrite_auto_publish = fields.Boolean(string="Auto-publish imported events", default=True)
    eventbrite_website_id = fields.Many2one("website", string="Default Website")
    restrict_website_to_eventbrite = fields.Boolean(
        string="Hide non-Eventbrite events from website",
        default=True,
        help="If enabled, the sync will unpublish website events that don't have an Eventbrite ID."
    )

    def set_values(self):
        res = super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("eventbrite.api_token", self.eventbrite_api_token or "")
        ICP.set_param("eventbrite.location_address", self.eventbrite_location or "New York")
        ICP.set_param("eventbrite.org_id", self.eventbrite_org_id or "")
        ICP.set_param("eventbrite.search_mode", self.eventbrite_search_mode)
        ICP.set_param("eventbrite.location_address", self.eventbrite_location_address or "")
        ICP.set_param("eventbrite.location_within", self.eventbrite_location_within or "25km")
        ICP.set_param("eventbrite.date_window_days", self.eventbrite_date_window_days or 60)
        ICP.set_param("eventbrite.auto_publish", "1" if self.eventbrite_auto_publish else "0")
        ICP.set_param("eventbrite.website_id", self.eventbrite_website_id.id or 0)
        ICP.set_param("eventbrite.restrict_only_api_events", "1" if self.restrict_website_to_eventbrite else "0")
        return res

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        res.update(
            eventbrite_api_token=ICP.get_param("eventbrite.api_token", ""),
            eventbrite_location=ICP.get_param("eventbrite.location_address", "New York"),
            eventbrite_org_id=ICP.get_param("eventbrite.org_id", ""),
            eventbrite_search_mode=ICP.get_param("eventbrite.search_mode", "org"),
            eventbrite_location_address=ICP.get_param("eventbrite.location_address", ""),
            eventbrite_location_within=ICP.get_param("eventbrite.location_within", "25km"),
            eventbrite_date_window_days=int(ICP.get_param("eventbrite.date_window_days", "60")),
            eventbrite_auto_publish=ICP.get_param("eventbrite.auto_publish", "1") == "1",
            eventbrite_website_id=int(ICP.get_param("eventbrite.website_id", "0")) or False,
            restrict_website_to_eventbrite=ICP.get_param("eventbrite.restrict_only_api_events", "1") == "1",
        )
        return res
