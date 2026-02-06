from __future__ import annotations

import base64
import logging
from typing import Any, Iterable
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

    def request(self, method: str, path_or_url: str, *, params: dict[str, Any] | None = None,
                json: dict[str, Any] | None = None) -> dict[str, Any]:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            url = path_or_url
        else:
            url = urljoin(self.base_url, path_or_url.lstrip("/"))

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        headers.update(self._auth_header())

        logging.debug("MS request %s %s", method, url)
        response = self.session.request(method, url, headers=headers, params=params, json=json, timeout=self.timeout)
        if response.status_code >= 400:
            logging.error("MS error %s %s: %s", response.status_code, url, response.text)
            response.raise_for_status()
        if response.text:
            return response.json()
        return {}

    def get_metadata(self, entity: str) -> dict[str, Any]:
        cache_key = entity
        if cache_key in self._metadata_cache:
            return self._metadata_cache[cache_key]

        data = self.request("GET", f"/entity/{entity}/metadata")
        attrs = data.get("attributes", []) or []
        by_name: dict[str, dict[str, Any]] = {item.get("name"): item for item in attrs if item.get("name")}
        self._metadata_cache[cache_key] = by_name
        return by_name

    def get_attribute_meta(self, entity: str, name: str) -> dict[str, Any] | None:
        if not name:
            return None
        return self.get_metadata(entity).get(name)

    def make_attribute(self, entity: str, name: str, value: Any) -> dict[str, Any]:
        meta = self.get_attribute_meta(entity, name)
        if not meta:
            raise ValueError(f"Attribute '{name}' not found for entity '{entity}'")
        return {
            "meta": meta.get("meta"),
            "value": value,
        }

    def get_document(self, doc_type: str, doc_id: str, expand: str | None = None) -> dict[str, Any]:
        params = {"expand": expand} if expand else None
        return self.request("GET", f"/entity/{doc_type}/{doc_id}", params=params)

    def get_by_href(self, href: str, expand: str | None = None) -> dict[str, Any]:
        params = {"expand": expand} if expand else None
        return self.request("GET", href, params=params)

    def update_document(self, doc_type: str, doc_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/entity/{doc_type}/{doc_id}", json=payload)

    def update_positions(self, doc_type: str, doc_id: str, positions: Iterable[dict[str, Any]]) -> dict[str, Any]:
        payload = {"positions": list(positions)}
        return self.update_document(doc_type, doc_id, payload)

    def update_attributes(self, doc_type: str, doc_id: str, attributes: Iterable[dict[str, Any]]) -> dict[str, Any]:
        payload = {"attributes": list(attributes)}
        return self.update_document(doc_type, doc_id, payload)
