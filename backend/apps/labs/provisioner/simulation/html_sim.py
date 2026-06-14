"""HTML / web server configuration simulation."""

from __future__ import annotations

from .base_sim import BaseRHELSimulator


class HtmlSimulator(BaseRHELSimulator):
    def __init__(self, scenario_slug: str = "sim-html-404-nginx"):
        super().__init__(scenario_slug=scenario_slug, hostname="web-server")
        self.state._mkdir("/var/www/html")
        self.state._write_file("/var/www/html/index.html", "<html><body><h1>Site Under Maintenance</h1></body></html>\n")
        self.state._mkdir("/etc/nginx/sites-enabled")
        self.state._write_file(
            "/etc/nginx/sites-enabled/default",
            "server {\n    listen 80;\n    server_name localhost;\n    root /var/www/wrong-path;\n}\n",
        )
