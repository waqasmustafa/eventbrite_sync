# -*- coding: utf-8 -*-
{
    "name": "NYC Events Sync",
    "summary": "Automatically import all public events in New York City from Ticketmaster Discovery API",
    "category": "Website/Events",
    "author": "Waqas Mustafa Developer",
    "license": "LGPL-3",
    "depends": ["event", "website_event"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_actions_server.xml",
        "views/res_config_settings_views.xml",
        "views/event_backend_views.xml",
        "views/website_event_templates.xml",
        "data/ir_cron.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
}
