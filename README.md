
# TokenFlow

## Overview

**TokenFlow** is a Python-based CLI tool that automates OpenID Connect (OIDC) service validation across multiple services with a single login session.
It fetches metadata, launches a browser to capture authorization codes, exchanges them for tokens, and retrieves user information.

---

## Getting Started

### 1. Clone the repository
```bash
git clone https://your-org/tokenflow.git
cd tokenflow
```

### 2. Create a virtual environment
```bash
python3 -m venv myenv
source myenv/bin/activate  # (Linux/macOS)
myenv\Scripts\activate    # (Windows)
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
- `--json` to print userinfo claims as JSON.
- `--output <filename>` to specify a CSV output file.

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
A CSV report is generated after testing:

| Column | Description |
|:-------|:------------|
| Service Name | Service tested |
| Auth Code Captured | Yes/No |
| Token Exchange | Success/Failure |
| UserInfo | Retrieved info or status |
| Timestamp | Date and time of testing |
| Error | Any error message |

---

## Troubleshooting

- **invalid_grant**: Ensure client_id, redirect_uri, and secrets match.
- **No auth code extracted**: Complete login including MFA.
- **Environment variables missing**: Ensure the proper secret variables are set.
- **Browser issues**: Make sure to run `playwright install`.

---

## Notes
- Services must support authorization code or hybrid flow.
- Client secrets are managed securely via environment variables.
- Metadata is parsed dynamically for flexibility.

---

## Developed by
**Samay Bhojwani - 2025**

🔗 [Connect with me on LinkedIn](https://www.linkedin.com/in/samay-bhojwani-032060260/)

