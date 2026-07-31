from __future__ import annotations

import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from proxyscraper.core.models import Proxy
from proxyscraper.export.file_export import FileExporter

logger = logging.getLogger(__name__)


class MailExporter:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_pass: str = "",
        from_addr: str = "",
        to_addrs: list[str] | None = None,
        use_tls: bool = True,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.from_addr = from_addr or smtp_user
        self.to_addrs = to_addrs or []
        self.use_tls = use_tls

    def export(
        self,
        proxies: list[Proxy],
        fmt: str = "txt",
        subject: str = "Proxy Scraper Export",
    ) -> None:
        if not self.to_addrs:
            logger.warning("No recipients configured for email export")
            return

        content = FileExporter().to_string(proxies, fmt)
        ext = fmt if fmt in ("txt", "csv", "json") else "txt"

        msg = MIMEMultipart()
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        msg["Subject"] = subject

        body = f"Proxy export: {len(proxies)} proxies attached."
        msg.attach(MIMEText(body, "plain"))

        attachment = MIMEApplication(content.encode("utf-8"), Name=f"proxies.{ext}")
        attachment["Content-Disposition"] = f'attachment; filename="proxies.{ext}"'
        msg.attach(attachment)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.smtp_user:
                    server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())

            logger.info("Emailed %d proxies to %s", len(proxies), ", ".join(self.to_addrs))
        except smtplib.SMTPException as e:
            logger.error("Email export failed: %s", e)
            raise
