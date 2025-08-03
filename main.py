# pylint: disable=C0301, C0114
import json
import imaplib
import smtplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr
from email.header import decode_header
import time
import datetime
import logging
import socket
import re
import socks

def provider_in(address, provider_list):
    """Check if the provider is in the provider list"""
    for provider in provider_list:
        if address.endswith(provider):
            return True
    return False

def decode_mime_words(s):
    """Decodes a string containing multiple MIME words"""
    decoded_fragments = decode_header(s)
    return ''.join(
        str(fragment, encoding or 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

def add_mask(original_msg, content, is_html):
    """Adds a mask to the content"""
    original_subject = decode_mime_words(original_msg['Subject'])
    from_name, from_address = parseaddr(original_msg['From'])
    from_name = decode_mime_words(from_name)
    to_name, to_address = parseaddr(original_msg['To'])
    to_name = decode_mime_words(to_name)
    header = f"""<html><head></head><body><table style="background:#3d3d3d;padding:8px 16px;margin-top:30px;margin-bottom:30px;width:96%;border-radius:6px;max-width:1200px" width="100%" bgcolor="#3D3D3D" align="center"><tbody><tr><td width="50%" align="left" style="font-weight:bolder;color:#fff"><p style="font-size:x-large;margin-block:.2em">Forwarded Email</p>{'' if is_html else '<p style="font-size: medium; margin-block: 0.2em;">This email is plain text, it may have display issues</p>'}</td><td width="50%" align="right" style="color:#fff;text-align:right"><p style="margin-block: 0.1em">From: {from_name} &lt;<a href="mailto:{from_address}">{from_address}</a>&gt;</p><p style="margin-block: 0.1em">To: {to_name} &lt;<a href="mailto:{to_address}">{to_address}</a>&gt;</p><p style="margin-block:.1em">Subject: {original_subject}</p></td></tr></tbody></table><table style="padding:0;max-width:850px" width="100%" align="center"><tbody><tr><td style="padding-left:15px;padding-right:15px" width="100%">"""
    footer = """</td></tr></tbody></table><table style="background:#3d3d3d;padding:8px 16px;margin-top:30px;margin-bottom:30px;width:96%;border-radius:6px;max-width:1200px" width="100%" bgcolor="#3D3D3D" align="center"><tbody><tr><td width="50%" align="left" style="color:#d22;font-size:xx-large;font-weight:bolder">FORWARDED</td><td width="50%" align="right" style="color:#fff;text-align:left"><p style="font-size:x-large;font-weight:700;margin-block:0">Notice:</p><p style="margin-block:.1em">&emsp;This is a automatically forwarded email, which means it may contains something bad.</p><p style="margin-block:.1em">&emsp;You shouldn't reply directly to this email, it will never reach your destination!</p></td></tr></tbody></table></body></html>"""
    return header + content + footer

def load_config(config_file='config.json'):
    """Loads the configuration file"""
    with open(config_file, 'r', encoding='utf-8') as file:
        config = json.load(file)
    return config

def set_proxy(proxy_config):
    """Sets the proxy"""
    socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, proxy_config['server'], proxy_config['port'])
    socket.socket = socks.socksocket

def setup_logging():
    """Sets up the logging"""
    logger = logging.getLogger()
    logger.setLevel('DEBUG')
    basic_format = "%(asctime)s >> %(levelname)s - %(message)s"
    date_format = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(basic_format, date_format)
    chlr = logging.StreamHandler()
    chlr.setFormatter(formatter)
    chlr.setLevel('INFO')
    logger.addHandler(chlr)
    return logger

def get_unforwarded_emails(account_config, logger):
    """Gets the unforwarded emails"""
    if account_config['proxy']['enabled']:
        set_proxy(account_config['proxy'])

    if account_config['imap'].get('use_ssl', True):
        imap = imaplib.IMAP4_SSL(account_config['imap']['server'], account_config['imap']['port'], timeout=10)
    else:
        imap = imaplib.IMAP4(account_config['imap']['server'], account_config['imap']['port'], timeout=10)

    imap.login(account_config['email'], account_config['password'])

    if provider_in(account_config['email'], ["163.com", "126.com"]):
        imaplib.Commands['ID'] = 'AUTH'
        args = ("name","XXXX","contact","XXXX@163.com","version","1.0.0","vendor","myclient")
        imap._simple_command('ID', '("' + '" "'.join(args) + '")') # pylint: disable=W0212

    imap.select()

    _, messages = imap.search(None, 'UNSEEN')
    email_ids = messages[0].split()

    emails = []
    for email_id in email_ids:
        _, data = imap.fetch(email_id, '(RFC822)')
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1]) # pylint: disable=E1136
                emails.append((email_id, msg))
        imap.store(email_id, '+FLAGS', '\\Seen')

    imap.logout()
    if len(emails) > 0:
        logger.info(f"Retrieved {len(emails)} new emails from {account_config['email']}")
    return emails

def forward_emails(account_config, emails, logger):
    """Forwards the emails"""
    if account_config['proxy']['enabled']:
        set_proxy(account_config['proxy'])

    smtp = None
    if account_config['smtp'].get('use_ssl', False):
        smtp = smtplib.SMTP_SSL(account_config['smtp']['server'], account_config['smtp']['port'], timeout=10)
    else:
        smtp = smtplib.SMTP(account_config['smtp']['server'], account_config['smtp']['port'], timeout=10)
        if account_config['smtp'].get('use_starttls', False):
            smtp.starttls()

    smtp.login(account_config['email'], account_config['password'])

    for email_id, original_msg in emails:
        for recipient in account_config['forward']['to']:
            from_name, from_address = parseaddr(original_msg['From'])
            from_name = decode_mime_words(from_name)
            to_name, to_address = parseaddr(original_msg['To'])
            to_name = decode_mime_words(to_name)
            msg = MIMEMultipart('mixed')
            msg['From'] = f'"{from_name} ({from_address}) via Forwarder" <{account_config["email"]}>'
            msg['To'] = f'"{to_name} ({to_address}) via Forwarder" <{recipient}>'
            original_subject = decode_mime_words(original_msg['Subject'])
            msg['Subject'] = original_subject

            body = ""
            attachments = []
            if original_msg.is_multipart():
                for part in original_msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))

                    if "attachment" in content_disposition or part.get_filename():
                        attachments.append(part)
                    elif content_type == 'text/html':
                        body = part.get_payload(decode=True).decode()
                    elif content_type == 'text/plain' and not body:
                        body = part.get_payload(decode=True).decode()
            else:
                body = original_msg.get_payload(decode=True).decode()

            if not body:
                logger.error(f"Failed to extract body from email {email_id}")
                continue

            is_html = bool(re.compile(r'<[^>]+>').search(body))

            if not is_html:
                body = body.replace('\n', '<br>')

            html_content = add_mask(original_msg, body, is_html)
            msg.attach(MIMEText(html_content, 'html'))

            for attachment in attachments:
                filename = attachment.get_filename()
                if decode_header(filename):
                    filename = decode_mime_words(filename)
                attachment.add_header('Content-Disposition', 'attachment', filename=filename)
                msg.attach(attachment)

            smtp.sendmail(account_config['email'], recipient, msg.as_string())
            logger.info(f"Forwarded email {original_subject} from {account_config['email']} to {recipient}")

    smtp.quit()

def main():
    """Main function"""
    config = load_config()
    logger = setup_logging()

    while True:
        for account in config['accounts']:
            if account['enabled']:
                try:
                    emails = get_unforwarded_emails(account, logger)
                    if emails:
                        forward_emails(account, emails, logger)
                except Exception as e: # pylint: disable=W0718
                    logger.error(f"Error processing account {account['email']}: {str(e)}") # pylint: disable=W1203

        logger.info(datetime.datetime.now().strftime("Check finished at %Y-%m-%d %H:%M:%S"))
        time.sleep(config.get('check_interval', 60))

if __name__ == "__main__":
    main()
