# MailForwarder

**此README由 ChatGPT-4o 生成**

这个项目是一个邮件自动转发器，能够从指定的邮箱中读取未读邮件，并将其自动转发到配置文件中指定的收件人邮箱中。该项目支持使用代理服务器进行连接，并且可以处理包含附件的邮件。

## 功能特性

- 自动转发未读邮件
- 支持 HTML 和纯文本格式的邮件内容
- 支持邮件附件的转发
- 支持通过 SOCKS5 代理进行连接
- 支持多账户配置
- 可配置的检查间隔

## 安装与配置

### 环境要求

- Python 3.6+
- 需要安装以下 Python 库:
  - json
  - imaplib
  - smtplib
  - email
  - socks
  - logging

### 安装依赖

```sh
pip install pysocks
```

### 配置文件

请在项目根目录下创建一个名为 `config.json` 的配置文件，并根据以下格式进行配置（见`config-example.json`）：

```json
{
  "check_interval": 60,
  "accounts": [
    {
      "email": "your_email@example.com",
      "password": "your_password",
      "enabled": true,
      "imap": {
        "server": "imap.example.com",
        "port": 993,
        "use_ssl": true
      },
      "smtp": {
        "server": "smtp.example.com",
        "port": 587,
        "use_ssl": false,
        "use_starttls": true
      },
      "forward": {
        "to": ["forward_to@example.com"]
      },
      "proxy": {
        "enabled": false,
        "server": "proxy.example.com",
        "port": 1080
      }
    }
  ]
}
```

### 配置项说明

- `check_interval`: 检查邮件的时间间隔，单位为秒。
- `accounts`: 配置多个邮箱账户。
  - `email`: 邮箱地址。
  - `password`: 邮箱密码。
  - `enabled`: 是否启用该账户。
  - `imap`: IMAP 服务器配置。
    - `server`: IMAP 服务器地址。
    - `port`: IMAP 服务器端口。
    - `use_ssl`: 是否使用 SSL 连接。
  - `smtp`: SMTP 服务器配置。
    - `server`: SMTP 服务器地址。
    - `port`: SMTP 服务器端口。
    - `use_ssl`: 是否使用 SSL 连接。
    - `use_starttls`: 是否使用 STARTTLS 加密。
  - `forward`: 转发配置。
    - `to`: 转发邮件的收件人地址列表。
  - `proxy`: 代理服务器配置。
    - `enabled`: 是否启用代理。
    - `server`: 代理服务器地址。
    - `port`: 代理服务器端口。

## 使用说明

1. 确保已经安装了所有依赖项，并正确配置了 `config.json` 文件。
2. 运行脚本：
   ```sh
   python main.py
   ```

## 日志

该脚本会在控制台输出日志信息，记录程序的运行状态、邮件处理情况以及错误信息。

## 注意事项

- 请确保配置文件中的邮箱账号和密码正确无误，并且邮箱服务支持 IMAP 和 SMTP 协议。
- 转发的邮件会包含一个自定义的头部和尾部，以提示收件人该邮件是自动转发的邮件。

## 许可证

本项目遵循 MIT 许可证。详细信息请参见 LICENSE 文件。