"""Capital.com REST API client with automatic session refresh."""
import logging
import requests
from config import API_URL, CAPITAL_API_KEY, CAPITAL_EMAIL, CAPITAL_PASSWORD

logger = logging.getLogger(__name__)

_TIMEOUT = 30


class CapitalComClient:
    def __init__(self):
        self._cst: str | None = None
        self._security_token: str | None = None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self) -> bool:
        url = f"{API_URL}/session"
        headers = {
            "X-CAP-API-KEY": CAPITAL_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {"identifier": CAPITAL_EMAIL, "password": CAPITAL_PASSWORD}

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            logger.error("Auth network error: %s", exc)
            return False

        if resp.status_code != 200:
            logger.error("Auth failed %s: %s", resp.status_code, resp.text[:200])
            return False

        self._cst = resp.headers.get("CST")
        self._security_token = resp.headers.get("X-SECURITY-TOKEN")

        if not self._cst or not self._security_token:
            logger.error("Auth response missing tokens. Headers: %s", dict(resp.headers))
            return False

        logger.info("Authentication successful")
        return True

    def keep_alive(self) -> bool:
        """Ping /session to prevent idle timeout (~10 min on Capital.com)."""
        resp = self._request("GET", "/session")
        return resp is not None and resp.status_code == 200

    # ------------------------------------------------------------------
    # Internal request helper
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        return {
            "X-CAP-API-KEY": CAPITAL_API_KEY,
            "CST": self._cst or "",
            "X-SECURITY-TOKEN": self._security_token or "",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, endpoint: str, **kwargs):
        url = f"{API_URL}{endpoint}"
        try:
            resp = requests.request(
                method, url, headers=self._headers(), timeout=_TIMEOUT, **kwargs
            )
        except requests.RequestException as exc:
            logger.error("Request error %s %s: %s", method, endpoint, exc)
            return None

        if resp.status_code == 401:
            logger.warning("Session expired — re-authenticating")
            if self.authenticate():
                try:
                    resp = requests.request(
                        method, url, headers=self._headers(), timeout=_TIMEOUT, **kwargs
                    )
                except requests.RequestException as exc:
                    logger.error("Retry after re-auth failed: %s", exc)
                    return None
            else:
                logger.error("Re-authentication failed")
                return None

        return resp

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    def get_account_info(self) -> dict | None:
        resp = self._request("GET", "/accounts")
        if resp is None or resp.status_code != 200:
            logger.error("get_account_info failed: %s", resp.text[:200] if resp else "no response")
            return None
        accounts = resp.json().get("accounts", [])
        return accounts[0] if accounts else None

    def get_balance(self) -> float | None:
        info = self.get_account_info()
        if info:
            return float(info.get("balance", {}).get("balance", 0))
        return None

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    def get_candles(self, epic: str, resolution: str, count: int = 300) -> list | None:
        resp = self._request(
            "GET",
            f"/prices/{epic}",
            params={"resolution": resolution, "max": count},
        )
        if resp is None or resp.status_code != 200:
            logger.error("get_candles failed: %s", resp.text[:200] if resp else "no response")
            return None
        return resp.json().get("prices", [])

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def get_open_positions(self) -> list:
        resp = self._request("GET", "/positions")
        if resp is None or resp.status_code != 200:
            logger.error("get_positions failed: %s", resp.text[:200] if resp else "no response")
            return []
        return resp.json().get("positions", [])

    def place_order(
        self,
        epic: str,
        direction: str,
        size: int,
        stop_distance: int,
        profit_distance: int,
    ) -> dict | None:
        payload = {
            "epic": epic,
            "direction": direction,
            "size": size,
            "guaranteedStop": False,
            "stopDistance": stop_distance,
            "profitDistance": profit_distance,
        }
        resp = self._request("POST", "/positions", json=payload)
        if resp is None or resp.status_code not in (200, 201):
            logger.error("place_order failed: %s", resp.text[:200] if resp else "no response")
            return None
        data = resp.json()
        logger.info("Order placed: %s %s %s → ref=%s", direction, size, epic, data.get("dealReference"))
        return data

    def close_position(self, deal_id: str) -> bool:
        resp = self._request("DELETE", f"/positions/{deal_id}")
        if resp is None or resp.status_code != 200:
            logger.error("close_position failed: %s", resp.text[:200] if resp else "no response")
            return False
        logger.info("Position closed: %s", deal_id)
        return True
