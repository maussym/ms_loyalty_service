from __future__ import annotations

import base64
import logging
from typing import Any
from urllib.parse import urljoin

import requests

from .config import Settings


class MoySkladClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.base_url.rstrip("/") + "/"
        self.session = requests.Session()
        self.timeout = settings.request_timeout
        self._metadata_cache: dict[str, dict[str, dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # auth
    # ------------------------------------------------------------------

    def _auth_header(self) -> dict[str, str]:
        mode = self.settings.auth_mode
        if mode == "bearer":
            if not self.settings.token:
                raise ValueError("MS_TOKEN is required for bearer auth")
            return {"Authorization": f"Bearer {self.settings.token}"}
        if mode == "basic":
            if not self.settings.login:
                raise ValueError("MS_LOGIN is required for basic auth")
            raw = f"{self.settings.login}:{self.settings.password}".encode("utf-8")
            token = base64.b64encode(raw).decode("ascii")
            return {"Authorization": f"Basic {token}"}
        raise ValueError(f"Unsupported MS_AUTH_MODE: {mode}")

    # ------------------------------------------------------------------
    # generic request
    # ------------------------------------------------------------------

    def request(self, method: str, path_or_url: str, *,
                params: dict[str, Any] | None = None,
                json: dict[str, Any] | list | None = None) -> dict[str, Any]:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            url = path_or_url
        else:
            url = urljoin(self.base_url, path_or_url.lstrip("/"))

        headers = {
            "Accept": "application/json;charset=utf-8",
            "Content-Type": "application/json;charset=utf-8",
        }
        headers.update(self._auth_header())

        logging.debug("MS %s %s", method, url)
        response = self.session.request(
            method, url, headers=headers, params=params,
            json=json, timeout=self.timeout,
        )
        if response.status_code >= 400:
            logging.error("MS error %s %s: %s", response.status_code, url, response.text)
            response.raise_for_status()
        if response.text:
            return response.json()
        return {}

    # ------------------------------------------------------------------
    # metadata helpers
    # ------------------------------------------------------------------

    def get_metadata(self, entity: str) -> dict[str, dict[str, Any]]:
        if entity in self._metadata_cache:
            return self._metadata_cache[entity]

        data = self.request("GET", f"/entity/{entity}/metadata")
        raw = data.get("attributes")

        # attributes can be a list of dicts or a collection reference (dict with meta/rows)
        if isinstance(raw, list):
            attrs = raw
        elif isinstance(raw, dict):
            attrs = raw.get("rows", [])
            # if only a meta reference with size>0, fetch the actual list
            if not attrs and (raw.get("meta") or {}).get("size", 0) > 0:
                href = raw["meta"].get("href", "")
                if href:
                    fetched = self.request("GET", href)
                    attrs = fetched.get("rows", [])
        else:
            attrs = []

        by_name: dict[str, dict[str, Any]] = {
            item.get("name"): item for item in attrs
            if isinstance(item, dict) and item.get("name")
        }
        self._metadata_cache[entity] = by_name
        return by_name

    def get_attribute_meta(self, entity: str, name: str) -> dict[str, Any] | None:
        if not name:
            return None
        return self.get_metadata(entity).get(name)

    def make_attribute(self, entity: str, name: str, value: Any) -> dict[str, Any]:
        meta = self.get_attribute_meta(entity, name)
        if not meta:
            raise ValueError(f"Attribute '{name}' not found for entity '{entity}'")
        return {"meta": meta.get("meta"), "value": value}

    # ------------------------------------------------------------------
    # entity / document CRUD
    # ------------------------------------------------------------------

    def get_document(self, doc_type: str, doc_id: str,
                     expand: str | None = None) -> dict[str, Any]:
        params = {"expand": expand} if expand else None
        return self.request("GET", f"/entity/{doc_type}/{doc_id}", params=params)

    def get_by_href(self, href: str, expand: str | None = None) -> dict[str, Any]:
        params = {"expand": expand} if expand else None
        return self.request("GET", href, params=params)

    def update_document(self, doc_type: str, doc_id: str,
                        payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/entity/{doc_type}/{doc_id}", json=payload)

    # ------------------------------------------------------------------
    # positions with pagination
    # ------------------------------------------------------------------

    def get_all_positions(self, doc_type: str, doc_id: str,
                          expand: str | None = "assortment") -> list[dict[str, Any]]:
        """Fetch every position of a document, paginating if > 100 rows."""
        base = f"/entity/{doc_type}/{doc_id}/positions"
        limit = 100
        offset = 0
        all_rows: list[dict[str, Any]] = []

        while True:
            params: dict[str, Any] = {"limit": limit, "offset": offset}
            if expand:
                params["expand"] = expand
            data = self.request("GET", base, params=params)
            rows = data.get("rows", [])
            all_rows.extend(rows)

            total = (data.get("meta") or {}).get("size", 0)
            if len(all_rows) >= total or not rows:
                break
            offset += limit

        return all_rows
