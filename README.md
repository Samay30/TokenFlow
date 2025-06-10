

# TokenFlow

## Overview

**TokenFlow** is a Python-based CLI tool that automates OpenID Connect (OIDC) service validation across multiple services with a single login session.  
It fetches metadata, launches a browser to capture authorization codes, exchanges them for tokens, and retrieves user information—all without needing to repeat the login process or manually use Postman.

> 🛠️ Originally conceptualized and developed by **Samay Bhojwani** (2025) as part of an initiative to streamline IAM testing workflows using secure, scriptable, and user-friendly tools.

Read the full write-up on Medium:  
📄 [TokenFlow: Automating OIDC Testing Without Losing Your Mind (or Clicking Postman 100 Times)](https://medium.com/@samaybhojwani1/tokenflow-automating-oidc-testing-without-losing-your-mind-or-clicking-postman-100-times-a3957456f617)

---

## Getting Started

### 1. Clone the repository
```bash
git clone https://your-org/tokenflow.git
cd tokenflow
````

### 2. Create a virtual environment

```bash
python3 -m venv myenv
source myenv/bin/activate  # (Linux/macOS)
myenv\Scripts\activate     # (Windows)
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browsers

```bash
playwright install
```

---

## Usage

### Add a Service

Add an OIDC service dynamically using the metadata URL:

```bash
python tokenflow.py --add-service unpd0002 "https://git.unl.edu/iam-pub/metadata/-/raw/master/oidc/edu-unl-unpd0002.xml"
```

### Set Environment Variables for Secrets

```bash
export UNPD0002_SECRET="your-client-secret"
```

### Run Tests

```bash
python tokenflow.py --run unpd0002
```

Run multiple services together:

```bash
python tokenflow.py --run unpd0002 unpd0016
```

Optional flags:

* `--json` to print userinfo claims as JSON
* `--output <filename>` to specify a CSV output file

Example:

```bash
python tokenflow.py --run unpd0002 unpd0016 --json --output results.csv
```

### List All Saved Services

```bash
python tokenflow.py --list-services
```

---

## CSV Output

A CSV report is generated after each run:

| Column             | Description                        |
| ------------------ | ---------------------------------- |
| Service Name       | Name of the OIDC service tested    |
| Auth Code Captured | Whether the auth code was captured |
| Token Exchange     | Status of token exchange           |
| UserInfo           | Claims or info retrieved           |
| Timestamp          | Date and time of the test          |
| Error              | Any error message                  |

---

## Troubleshooting

* **invalid\_grant**: Ensure `client_id`, `redirect_uri`, and `client_secret` are correct.
* **No auth code extracted**: Complete login flow (including MFA).
* **Missing environment variables**: Make sure your client secrets are properly exported.
* **Playwright/browser errors**: Run `playwright install` to configure required browsers.

---

## Notes

* TokenFlow supports services using the **Authorization Code Flow** or **Hybrid Flow**.
* Secrets should always be passed via **environment variables**, not hard-coded.
* Metadata is parsed dynamically, allowing flexible service onboarding.

---

## Credits

This project was:

* 💡 **Ideated and built** by [**Samay Bhojwani**](https://www.linkedin.com/in/samay-bhojwani-032060260/)
* 📝 Documented publicly in this [Medium article](https://medium.com/@samaybhojwani1/tokenflow-automating-oidc-testing-without-losing-your-mind-or-clicking-postman-100-times-a3957456f617)
* 🔁 Designed to solve repetitive token testing across multiple services

---

## Connect

🔗 [Connect with me on LinkedIn](https://www.linkedin.com/in/samay-bhojwani-032060260/)

