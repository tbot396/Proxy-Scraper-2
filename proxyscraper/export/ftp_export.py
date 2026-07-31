from __future__ import annotations

import ftplib
import logging
from io import BytesIO

from proxyscraper.core.models import Proxy
from proxyscraper.export.file_export import FileExporter

logger = logging.getLogger(__name__)


class FTPExporter:
    def __init__(
        self,
        host: str,
        remote_path: str = "/proxies/latest.txt",
        username: str = "anonymous",
        password: str = "",
        port: int = 21,
        use_tls: bool = False,
    ) -> None:
        self.host = host
        self.remote_path = remote_path
        self.username = username
        self.password = password
        self.port = port
        self.use_tls = use_tls

    def export(self, proxies: list[Proxy], fmt: str = "txt") -> None:
        content = FileExporter().to_string(proxies, fmt)
        data = BytesIO(content.encode("utf-8"))

        try:
            if self.use_tls:
                ftp = ftplib.FTP_TLS()
            else:
                ftp = ftplib.FTP()

            ftp.connect(self.host, self.port)
            ftp.login(self.username, self.password)

            if self.use_tls:
                ftp.prot_p()

            ftp.storbinary(f"STOR {self.remote_path}", data)
            ftp.quit()

            logger.info("Uploaded %d proxies to ftp://%s%s", len(proxies), self.host, self.remote_path)
        except ftplib.all_errors as e:
            logger.error("FTP export failed: %s", e)
            raise
