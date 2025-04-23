
# TokenFlow 🔐

**TokenFlow** is a Python-based CLI tool that automates OpenID Connect (OIDC) code flow testing across multiple services — all using a single browser login session.

It launches a real browser using Playwright, intercepts authorization codes, exchanges them for tokens, fetches userinfo, and logs test results into a CSV report.

---

## 🚀 Features

- ✅ Supports **multiple OIDC services** in one session
- 🧠 Captures `authorization_code` from form_post responses
- 🔁 Reuses browser session across tests
- 🧾 Exports a **CSV report** with pass/fail, timestamp, and identity
- 🔐 Redacts secrets and is safe to demo or audit

---

## 🛠️ Requirements

- Python 3.8+
- Playwright installed and set up:
  ```bash
  pip install -r requirements.txt
  playwright install
  ```

---

## 📦 Installation

```bash
git clone https://github.com/your-org/tokenflow.git
cd tokenflow
python3 -m venv myenv
source myenv/bin/activate     # or myenv\Scripts\activate on Windows
pip install -r requirements.txt
playwright install
```

---

## ⚙️ Usage

You can test multiple OIDC services with one login by passing inline JSON strings:

```bash
python tokenflow.py --output results.csv --json \
  '{ "name": "Service A", "auth_url": "<AUTH_URL>", "client_id": "<CLIENT_ID>", "client_secret": "<SECRET>", "token_url": "<TOKEN_URL>", "redirect_uri": "<REDIRECT_URI>", "userinfo_url": "<USERINFO_URL>" }' \
  '{ "name": "Service B", "auth_url": "<AUTH_URL>", "client_id": "<CLIENT_ID>", "client_secret": "<SECRET>", "token_url": "<TOKEN_URL>", "redirect_uri": "<REDIRECT_URI>", "userinfo_url": "<USERINFO_URL>" }'
```

> ⚠️ Make sure to URL-encode `scope`, `response_type`, etc., in your `auth_url`.  
> Avoid exposing real client secrets when sharing commands.

---

## 🧪 Output

A CSV file is generated (default: `tokenflow_results.csv`) with columns:

- Service Name
- Auth Code Captured
- Token Exchange (Success/Failed)
- UserInfo (email/sub)
- Timestamp
- Error (if any)

---

## 📄 Documentation

📘 [Download PDF Guide](https://your-link.com/TokenFlow_Documentation.pdf)

---

## 👤 Author

**Samay Bhojwani**  
[LinkedIn Profile](https://www.linkedin.com/in/samay-bhojwani-032060260/)

---

## 📜 License

MIT License © 2025 Samay Bhojwani
