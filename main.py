import json
import imaplib
import smtplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr
import time
import datetime
import logging
import socks
import socket

from email.header import decode_header

def decode_mime_words(s):
    decoded_fragments = decode_header(s)
    return ''.join(
        str(fragment, encoding or 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    )

def add_mask(original_msg, content):
    original_subject = decode_mime_words(original_msg['Subject'])
    from_name, from_address = parseaddr(original_msg['From'])
    from_name = decode_mime_words(from_name)
    to_name, to_address = parseaddr(original_msg['To'])
    to_name = decode_mime_words(to_name)
    header = f"""<table align=center style="background:#3d3d3d;padding:8px 16px;margin-top:30px;margin-bottom:30px;width:96%;border-radius:6px;max-width:1200px"width=100% bgcolor=#3D3D3D id=relay-email-header><tr><td style=font-size:xx-large;font-weight:bolder;color:#fff width=50% align=left>Forwarded Email<td style=color:#fff;text-align:right width=50% align=right><p>From: {from_name} &lt;{from_address}&gt;<p>To: {to_name} &lt;{to_address}&gt;<p>Subject: {original_subject}</table><table align=center style=padding:0;max-width:850px width=100%><tr><td style=padding-left:15px;padding-right:15px width=100%>"""
    footer = f"""<table align=center bgcolor=#3D3D3D style="background:#3d3d3d;padding:8px 16px;margin-top:30px;margin-bottom:30px;width:96%;border-radius:6px;max-width:1200px"width=100%><tr><td align=left style=color:#d22;font-size:xx-large;font-weight:bolder width=50%>FORWARDED<td align=right style=color:#fff;text-align:left width=50%><p style=font-size:x-large;font-weight:700;margin-block:0>Notice:<p style=margin-block:.1em> This is a automatically forwarded email, which means it may contains something bad.<p style=margin-block:.1em> You shouldn't reply directly to this email, it will never reach your destination!</table>"""
    return header + content + footer

def load_config(config_file='config.json'):
    with open(config_file, 'r') as file:
        config = json.load(file)
    return config

def set_proxy(proxy_config):
    socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, proxy_config['server'], proxy_config['port'])
    socket.socket = socks.socksocket

def setup_logging(filename):
    logger = logging.getLogger()
    logger.setLevel('DEBUG')
    BASIC_FORMAT = "%(asctime)s >> %(levelname)s - %(message)s"
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(BASIC_FORMAT, DATE_FORMAT)
    chlr = logging.StreamHandler()
    chlr.setFormatter(formatter)
    chlr.setLevel('INFO')
    fhlr = logging.FileHandler(filename)
    fhlr.setFormatter(formatter)
    logger.addHandler(chlr)
    logger.addHandler(fhlr)
    return logger

def get_unforwarded_emails(account_config, logger):
    if account_config['proxy']['enabled']:
        set_proxy(account_config['proxy'])
    
    if account_config['imap'].get('use_ssl', True):
        imap = imaplib.IMAP4_SSL(account_config['imap']['server'], account_config['imap']['port'])
    else:
        imap = imaplib.IMAP4(account_config['imap']['server'], account_config['imap']['port'])

    imap.login(account_config['email'], account_config['password'])
    
    if "163.com" in account_config['email'] or "126.com" in account_config['email']:
        imaplib.Commands['ID'] = ('AUTH')
        args = ("name","XXXX","contact","XXXX@163.com","version","1.0.0","vendor","myclient")
        typ, dat = imap._simple_command('ID', '("' + '" "'.join(args) + '")')

    imap.select()
    
    status, messages = imap.search(None, 'UNSEEN')
    email_ids = messages[0].split()
    
    emails = []
    for email_id in email_ids:
        status, data = imap.fetch(email_id, '(RFC822)')
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                if 'Forwarded' not in msg['Subject']:
                    emails.append((email_id, msg))
    imap.logout()
    if len(emails) > 0:
        logger.info(f"Retrieved {len(emails)} new emails from {account_config['email']}")
    return emails

def forward_emails(account_config, emails, logger):
    if account_config['proxy']['enabled']:
        set_proxy(account_config['proxy'])
    
    smtp = None
    if account_config['smtp'].get('use_ssl', False):
        smtp = smtplib.SMTP_SSL(account_config['smtp']['server'], account_config['smtp']['port'])
    else:
        smtp = smtplib.SMTP(account_config['smtp']['server'], account_config['smtp']['port'])
        if account_config['smtp'].get('use_starttls', False):
            smtp.starttls()
    
    smtp.login(account_config['email'], account_config['password'])
    
    for email_id, original_msg in emails:
        for recipient in account_config['forward']['to']:
            from_name, from_address = parseaddr(original_msg['From'])
            to_name, to_address = parseaddr(original_msg['To'])
            msg = MIMEMultipart('mixed')
            msg['From'] = f"{from_name} ({from_address}) via Forwarder <{account_config['email']}>"
            msg['To'] = f"{to_name} ({to_address}) via Forwarder <{recipient}>"
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
            
            html_content = add_mask(original_msg, body)
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
    config = load_config()
    logger = setup_logging(config['log'])
    
    while True:
        for account in config['accounts']:
            if account['enabled']:
                try:
                    emails = get_unforwarded_emails(account, logger)
                    if emails:
                        forward_emails(account, emails, logger)
                except Exception as e:
                    logger.error(f"Error processing account {account['email']}: {str(e)}")
        
        logger.info(datetime.datetime.now().strftime("Check finished at %Y-%m-%d %H:%M:%S"))
        time.sleep(config.get('check_interval', 60))

if __name__ == "__main__":
    main()
