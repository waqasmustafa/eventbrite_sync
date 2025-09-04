# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ticketmaster_api_key = fields.Char(string="Ticketmaster API Key")
    ticketmaster_auto_publish = fields.Boolean(string="Auto-publish imported events", default=True)
    ticketmaster_website_id = fields.Many2one("website", string="Default Website")
    restrict_website_to_ticketmaster = fields.Boolean(
        string="Hide non-Ticketmaster events from website",
        default=True,
        help="If enabled, the sync will unpublish website events that don't have a Ticketmaster ID."
    )

    def set_values(self):
        res = super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("ticketmaster.api_key", self.ticketmaster_api_key or "")
        ICP.set_param("ticketmaster.auto_publish", "1" if self.ticketmaster_auto_publish else "0")
        ICP.set_param("ticketmaster.website_id", self.ticketmaster_website_id.id or 0)
        ICP.set_param("ticketmaster.restrict_only_api_events", "1" if self.restrict_website_to_ticketmaster else "0")
        return res

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        res.update(
            ticketmaster_api_key=ICP.get_param("ticketmaster.api_key", ""),
            ticketmaster_auto_publish=ICP.get_param("ticketmaster.auto_publish", "1") == "1",
            ticketmaster_website_id=int(ICP.get_param("ticketmaster.website_id", "0")) or False,
            restrict_website_to_ticketmaster=ICP.get_param("ticketmaster.restrict_only_api_events", "1") == "1",
        )
        return res
