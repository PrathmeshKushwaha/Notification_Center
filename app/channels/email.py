import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, html_body: str) -> bool:
    try:
        message = MIMEMultipart("alternative")
        message["From"] = settings.smtp_from
        message["To"] = to
        message["Subject"] = subject
        message.attach(MIMEText(html_body, "html"))

        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_pass,
        )
        logger.info(f"Email sent to {to}")
        return True

    except Exception as e:
        logger.error(f"Email send failed to {to}: {e}")
        raise