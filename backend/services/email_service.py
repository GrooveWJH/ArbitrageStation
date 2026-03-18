import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from sqlalchemy.orm import Session
from models.database import EmailConfig

logger = logging.getLogger(__name__)


def send_email(db: Session, subject: str, body: str) -> bool:
    cfg = db.query(EmailConfig).first()
    if not cfg or not cfg.is_enabled:
        logger.info("Email not configured or disabled, skipping.")
        return False

    recipients = [e.strip() for e in cfg.to_emails.split(",") if e.strip()]
    if not recipients:
        logger.warning("No recipient email addresses configured.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg.from_email
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(body, "html", "utf-8"))

        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg.smtp_user, cfg.smtp_password)
            server.sendmail(cfg.from_email, recipients, msg.as_string())

        logger.info(f"Email sent to {recipients}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_risk_alert(db: Session, rule_name: str, strategy_id: int, symbol: str,
                    exchange_long: str, exchange_short: str,
                    pnl_pct: float, action_taken: str):
    subject = f"[套利工具风控触发] {symbol} 亏损告警 - {rule_name}"
    body = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;">
    <h2 style="color:#d32f2f;">⚠️ 风控规则触发通知</h2>
    <table style="border-collapse:collapse;width:100%;max-width:600px;">
      <tr style="background:#fce4ec;"><td style="padding:8px;font-weight:bold;">触发规则</td><td style="padding:8px;">{rule_name}</td></tr>
      <tr><td style="padding:8px;font-weight:bold;">策略 ID</td><td style="padding:8px;">#{strategy_id}</td></tr>
      <tr style="background:#fce4ec;"><td style="padding:8px;font-weight:bold;">交易对</td><td style="padding:8px;">{symbol}</td></tr>
      <tr><td style="padding:8px;font-weight:bold;">多头交易所</td><td style="padding:8px;">{exchange_long}</td></tr>
      <tr style="background:#fce4ec;"><td style="padding:8px;font-weight:bold;">空头交易所</td><td style="padding:8px;">{exchange_short}</td></tr>
      <tr><td style="padding:8px;font-weight:bold;">当前亏损</td>
          <td style="padding:8px;color:#d32f2f;font-weight:bold;">{pnl_pct:.2f}%</td></tr>
      <tr style="background:#fce4ec;"><td style="padding:8px;font-weight:bold;">执行操作</td><td style="padding:8px;">{action_taken}</td></tr>
      <tr><td style="padding:8px;font-weight:bold;">触发时间</td><td style="padding:8px;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
    </table>
    <p style="color:#666;font-size:12px;margin-top:20px;">此邮件由套利交易工具自动发送，请勿直接回复。</p>
    </body></html>
    """
    return send_email(db, subject, body)
