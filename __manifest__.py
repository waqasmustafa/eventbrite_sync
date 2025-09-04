# -*- coding: utf-8 -*-
{
    "name": "Eventbrite Sync (Minimal Website Display)",
    "version": "18.0.1.0.0",
    "summary": "Sync Eventbrite events every 5 hours, show only Image/Location/Time/+External Link on website",
    "category": "Website/Events",
    "author": "Your Company",
    "license": "LGPL-3",
    "depends": ["event", "website_event"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/event_backend_views.xml",
        "views/website_event_templates.xml",
        "data/ir_cron.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
}
