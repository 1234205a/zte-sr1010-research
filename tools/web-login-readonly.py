#!/usr/bin/env python3
"""Authenticate to an SR1010 Web UI and perform one read-only GET."""

import argparse
import getpass
import hashlib
import json
from urllib.parse import urljoin

import requests
import urllib3


class SR1010Web:
    def __init__(self, base_url: str, verify_tls: bool = False):
        self.base_url = base_url.rstrip("/") + "/"
        self.verify_tls = verify_tls
        self.session = requests.Session()
        self.session_token = ""
        if not verify_tls:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    def login(self, username: str, password: str):
        token = self.session.get(
            self._url("/?_type=loginsceneData&_tag=login_token_json"),
            verify=self.verify_tls,
            timeout=10,
        ).json()
        self.session_token = token["_sessionToken"]
        proof = hashlib.sha256((password + token["logintoken"]).encode()).hexdigest()
        payload = {
            "Username": username,
            "Password": proof,
            "action": "login",
            "Frm_Logintoken": "",
            "captchaCode": "",
            "_sessionTOKEN": self.session_token,
        }
        response = self.session.post(
            self._url("/?_type=loginData&_tag=login_entry"),
            data=payload,
            verify=self.verify_tls,
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
        if result.get("loginErrType"):
            raise RuntimeError(result)
        self.session_token = response.headers.get("x_xsrf_token", result.get("sess_token", ""))
        return result

    def get(self, path: str):
        response = self.session.get(self._url(path), verify=self.verify_tls, timeout=10)
        response.raise_for_status()
        return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://192.168.50.1")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password")
    parser.add_argument("--verify-tls", action="store_true")
    parser.add_argument("path", help="read-only path, including query string")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Web password: ")
    client = SR1010Web(args.base_url, args.verify_tls)
    result = client.login(args.username, password)
    print(json.dumps({"login_need_refresh": result.get("login_need_refresh")}, ensure_ascii=False))
    response = client.get(args.path)
    print(response.text)


if __name__ == "__main__":
    main()

