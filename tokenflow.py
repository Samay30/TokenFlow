import requests
import argparse
import json
import sys
import csv
import time
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from urllib.parse import unquote_plus

SERVICE_MAP_FILE = Path(".tokenflow_services.json")

class Service:
    def __init__(self, name, auth_url, client_id, client_secret, token_url, redirect_uri, userinfo_url):
        self.name = name
        self.auth_url = auth_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.redirect_uri = redirect_uri
        self.userinfo_url = userinfo_url

def save_service_map(service_map):
    with open(SERVICE_MAP_FILE, "w") as f:
        json.dump(service_map, f, indent=2)

def load_service_map():
    if SERVICE_MAP_FILE.exists():
        with open(SERVICE_MAP_FILE) as f:
            return json.load(f)
    return {}

def add_service_to_map(name, metadata_url):
    service_map = load_service_map()
    service_map[name] = metadata_url
    save_service_map(service_map)
    print(f"✅ Added service '{name}' to local map.")

def parse_oidc_metadata(xml_content):
    ns = {
        "md": "urn:oasis:names:tc:SAML:2.0:metadata",
        "oidcmd": "urn:mace:shibboleth:metadata:oidc:1.0"
    }
    root = ET.fromstring(xml_content)
    client_id = root.find(".//oidcmd:ClientSecretKeyReference", ns).text
    redirect_uri = root.find(".//md:AssertionConsumerService", ns).attrib["Location"]
    auth_url = "https://shib-qa.unl.edu/idp/profile/oidc/authorize"
    token_url = "https://shib-qa.unl.edu/idp/profile/oidc/token"
    userinfo_url = "https://shib-qa.unl.edu/idp/profile/oidc/userinfo"
    return client_id, redirect_uri, auth_url, token_url, userinfo_url

def build_services_from_names(service_names):
    services = []
    service_map = load_service_map()
    for name in service_names:
        if name not in service_map:
            print(f"[❌] Service '{name}' not found in local map. Use --add-service to add it.")
            continue
        xml_url = service_map[name]
        try:
            response = requests.get(xml_url)
            response.raise_for_status()
            client_id, redirect_uri, auth_url, token_url, userinfo_url = parse_oidc_metadata(response.text)
            secret_env_key = name.upper() + "_SECRET"
            client_secret = os.environ.get(secret_env_key)
            if not client_secret:
                raise Exception(f"Environment variable '{secret_env_key}' not set.")
            svc = Service(
                name=name,
                auth_url=auth_url + f"?client_id={client_id}&scope=email%20openid&response_type=code%20id_token&redirect_uri={redirect_uri}&state=1234&response_mode=form_post&nonce=garbage",
                client_id=client_id,
                client_secret=client_secret,
                token_url=token_url,
                redirect_uri=redirect_uri,
                userinfo_url=userinfo_url
            )
            services.append(svc)
        except Exception as e:
            print(f"[⚠️] Failed to fetch metadata for '{name}': {e}")
    return services

def get_auth_code_via_playwright(auth_url, redirect_uri, context):
    page = context.new_page()
    auth_code = None

    def intercept_post(route, request):
        nonlocal auth_code
        if request.method == "POST" and redirect_uri in request.url:
            post_data = request.post_data
            if post_data:
                parsed_data = dict(pair.split('=') for pair in post_data.split('&') if '=' in pair)
                if 'code' in parsed_data:
                    auth_code = unquote_plus(parsed_data['code'])
                    print(f"[✅] Extracted auth code from POST payload: {auth_code}")
        route.continue_()

    page.route("**", intercept_post)

    print(f"[🌐] Navigating to auth URL: {auth_url}")
    page.goto(auth_url)
    print("[✍️] Please complete login in the browser window...")

    start_time = time.time()
    while time.time() - start_time < 120:
        current_url = page.url

        if "shib.unl.edu" in current_url and "shib-qa.unl.edu" not in current_url:
            fixed_url = current_url.replace("shib.unl.edu", "shib-qa.unl.edu")
            print(f"[🔧] Detected stale prod URL. Fixing to QA: {fixed_url}")
            try:
                page.goto(fixed_url)
                continue
            except Exception as e:
                print(f"[⚠️] Failed to navigate to QA URL: {e}")

        if auth_code:
            break

        print(f"[⏳] Waiting... Current URL: {current_url}")
        page.wait_for_timeout(1000)

    page.close()

    if not auth_code:
        raise Exception("Authorization code not found")

    return auth_code

def exchange_code_for_token(auth_code, client_id, client_secret, token_url, redirect_uri):
    data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(token_url, data=data, headers=headers)
    print(f"[📥] Response ({response.status_code}): {response.text}")
    response.raise_for_status()
    return response.json()

def get_user_info(access_token, userinfo_url):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(userinfo_url, headers=headers)
    response.raise_for_status()
    return response.json()

def main():
    parser = argparse.ArgumentParser(description="TokenFlow - Automated OIDC QA Testing Tool")
    parser.add_argument('--add-service', nargs=2, metavar=('NAME', 'METADATA_URL'), help='Add a new service')
    parser.add_argument('--list-services', action='store_true', help='List available services')
    parser.add_argument('--run', nargs='+', metavar='SERVICE_NAME', help='Run OIDC test on specified services')
    parser.add_argument('--output', default='tokenflow_results.csv', help='CSV file to write results to')
    parser.add_argument('--json', action='store_true', help='Print userinfo in JSON format')
    args = parser.parse_args()

    if args.add_service:
        name, url = args.add_service
        add_service_to_map(name, url)
        return

    if args.list_services:
        service_map = load_service_map()
        print("\nAvailable services:")
        for k, v in service_map.items():
            print(f"- {k}: {v}")
        return

    if args.run:
        services = build_services_from_names(args.run)
    else:
        print("[❌] No services specified. Use --run or --add-service.")
        return

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()

        for i, svc in enumerate(services):
            print(f"\n🔁 Starting test for: {svc.name}")
            result = {
                "Service Name": svc.name,
                "Auth Code Captured": "No",
                "Token Exchange": "Failed",
                "UserInfo": "N/A",
                "Timestamp": datetime.now().isoformat()
            }
            try:
                auth_code = get_auth_code_via_playwright(svc.auth_url, svc.redirect_uri, context)
                result["Auth Code Captured"] = "Yes"

                tokens = exchange_code_for_token(
                    auth_code, svc.client_id, svc.client_secret,
                    svc.token_url, svc.redirect_uri
                )
                result["Token Exchange"] = "Success"

                userinfo = get_user_info(tokens['access_token'], svc.userinfo_url)
                result["UserInfo"] = userinfo.get("email") or userinfo.get("sub") or "Retrieved"

                if args.json:
                    print(json.dumps({"service": svc.name, "userinfo": userinfo}, indent=2))
                else:
                    print("\n[👤] User Information:")
                    for key, value in userinfo.items():
                        print(f"  {key}: {value}")

            except Exception as e:
                print(f"[❌] Failed for {svc.name}: {e}")
                result["Error"] = str(e)

            results.append(result)

        context.close()
        browser.close()

    keys = ["Service Name", "Auth Code Captured", "Token Exchange", "UserInfo", "Timestamp", "Error"]
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    print(f"\n✅ Results saved to {args.output}")

if __name__ == '__main__':
    main()
