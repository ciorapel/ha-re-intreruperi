"""Client pentru portalul contulmeu.reteleelectrice.ro (doar întreruperi).

Flux: login prin formularul Visualforce -> redirect JS către frontdoor.jsp
(cookie de sesiune) -> pagina VF a întreruperilor (ViewState) -> POST A4J
cu methodN=PowerOutages. Fără token Aura: pentru întreruperi nu e nevoie.
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import re
import uuid
from dataclasses import dataclass

import aiohttp
from bs4 import BeautifulSoup

from . import const

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=60)
_NO_OUTAGE_RE = re.compile(r"nicio\s+întrerupere|nu avem înregistrat", re.I)
_VS = (
    "com.salesforce.visualforce.ViewState",
    "com.salesforce.visualforce.ViewStateVersion",
    "com.salesforce.visualforce.ViewStateMAC",
)
_VS_CSRF = "com.salesforce.visualforce.ViewStateCSRF"


def _title(text: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    return (m.group(1).strip()[:80] if m else "")


class AuthError(Exception):
    """Login eșuat sau sesiune expirată."""


class CannotConnect(Exception):
    """Portalul nu răspunde."""


@dataclass
class OutageStatus:
    pod: str
    ok: bool
    active: bool | None  # None = nu se poate stabili
    message: str
    check_flag: str | None  # valoarea brută checkInterruzione (pentru diagnostic)


def parse_outage_response(pod: str, body: str) -> OutageStatus:
    """Parsează răspunsul VF (fără rețea, ușor de testat)."""
    soup = BeautifulSoup(body, "html.parser")
    span = soup.find(id="j_id0:j_id2:asyncResponse")
    if span is None:
        raise AuthError("răspuns fără asyncResponse (sesiune expirată?)")
    try:
        data = json.loads(span.get_text())
    except ValueError as err:
        raise CannotConnect(f"JSON invalid în răspuns: {err}") from err
    d = data.get("data") or {}
    # mesajul vine codat HTML de două ori (&amp;#259;)
    message = html.unescape(html.unescape(d.get("messaggio", "")))
    ok = data.get("esito") == "OK" and d.get("esito") == "OK"
    active: bool | None = None
    if ok:
        # Euristică până avem un răspuns cu o întrerupere reală.
        active = not _NO_OUTAGE_RE.search(message)
    return OutageStatus(pod, ok, active, message, d.get("checkInterruzione"))


class ReteleElectriceClient:
    def __init__(self, session: aiohttp.ClientSession, email: str, password: str):
        self._s = session  # trebuie să aibă CookieJar(unsafe=True)
        self._email = email
        self._password = password

    @staticmethod
    async def _soup(text: str) -> BeautifulSoup:
        # paginile Salesforce sunt mari: nu parsăm în event loop
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, BeautifulSoup, text, "html.parser")

    async def login(self) -> None:
        try:
            self._s.cookie_jar.clear()
            async with self._s.get(
                const.LOGIN_PAGE, params={"startURL": "/s/"}, timeout=TIMEOUT
            ) as r:
                page = await r.text()
                _LOGGER.debug(
                    "Login GET %s -> HTTP %s, %d bytes, titlu=%r",
                    r.url, r.status, len(page), _title(page),
                )
            soup = await self._soup(page)
            form = soup.find("form")
            pw = form.find("input", {"type": "password"}) if form else None
            if form is None or pw is None:
                raise AuthError(
                    f"formular de login negăsit (HTTP {r.status}, titlu={_title(page)!r})"
                )
            user = next(
                (
                    i
                    for i in pw.find_all_previous("input")
                    if i.get("type") in ("text", "email") and i.get("name")
                ),
                None,
            )
            if user is None:
                raise AuthError("câmp utilizator negăsit în formular")

            form_id = form.get("id") or "loginPage:loginForm"
            payload = {
                i["name"]: i.get("value", "")
                for i in form.find_all("input", {"type": "hidden"})
                if i.get("name")
            }
            # ViewState* stau în pagină, în afara <form>; JS-ul portalului
            # (vfPrepareForms) le mută în formular la submit.
            for name in (*_VS, _VS_CSRF):
                el = soup.find("input", {"name": name})
                if el is not None and el.get("value"):
                    payload[name] = el["value"]
                elif name != _VS_CSRF:
                    raise AuthError(f"lipsește {name} în pagina de login")
            payload[user["name"]] = self._email
            payload[pw["name"]] = self._password
            # Butonul „Autentifică-te" e un link: JS-ul lui adaugă o pereche
            # nume=valoare prin jsfcljs(form, 'nume,valoare', ''). O citim din pagină.
            submit_pairs: dict[str, str] = {}
            m_js = re.search(
                r"jsfcljs\(\s*document\.forms\[['\"]" + re.escape(form_id)
                + r"['\"]\]\s*,\s*['\"]([^'\"]+)['\"]",
                page,
            )
            if m_js:
                parts = m_js.group(1).split(",")
                submit_pairs = dict(zip(parts[0::2], parts[1::2]))
            if not submit_pairs:
                submit_pairs = {f"{form_id}:j_id25": f"{form_id}:j_id25"}
            payload.update(submit_pairs)

            action = form.get("action") or "/PEDRO_SiteLogin?startURL=%2Fs%2F"
            url = action if action.startswith("http") else f"{const.BASE_URL}{action}"
            _LOGGER.debug(
                "Login formular: user=%s pw=%s submit=%s câmpuri=%d action=%s",
                user["name"], pw["name"], list(submit_pairs), len(payload), action,
            )
            async with self._s.post(
                url,
                data=payload,
                allow_redirects=False,
                headers={"Origin": const.BASE_URL, "Referer": const.LOGIN_PAGE},
                timeout=TIMEOUT,
            ) as r:
                body = await r.text()
                status = r.status
                location = r.headers.get("Location")
            _LOGGER.debug(
                "Login POST -> HTTP %s, Location=%s, %d bytes, titlu=%r",
                status, location, len(body), _title(body),
            )

            m = re.search(r"https?://[^'\"\s]*frontdoor\.jsp[^'\"\s]*", body)
            target = html.unescape(m.group(0)) if m else None
            if target is None and location and "login" not in location.lower():
                # unele răspunsuri folosesc redirect HTTP în loc de redirect JS
                target = location if location.startswith("http") else f"{const.BASE_URL}{location}"
            if target is None:
                raise AuthError(
                    "login eșuat (parolă greșită sau flux schimbat): "
                    f"HTTP {status}, titlu={_title(body)!r}, Location={location!r}"
                )
            async with self._s.get(target, timeout=TIMEOUT) as r:
                _LOGGER.debug("Login redirect GET -> HTTP %s, url final %s", r.status, r.url)
                if r.status != 200:
                    raise AuthError(f"redirect post-login HTTP {r.status}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnect(str(err)) from err

    async def get_outages(self, pod: str) -> OutageStatus:
        try:
            async with self._s.get(const.VF_OUTAGES, timeout=TIMEOUT) as r:
                page = await r.text()
                vf_info = f"HTTP {r.status}, url={r.url}, titlu={_title(page)!r}"
                _LOGGER.debug("VF GET %s, %d bytes", vf_info, len(page))
                if r.status in (401, 403):
                    raise AuthError(f"pagina VF refuzată: {vf_info}")
            soup = await self._soup(page)

            fields: dict[str, str] = {}
            for name in _VS:
                el = soup.find("input", {"name": name}) or soup.find("input", {"id": name})
                if el is None or not el.get("value"):
                    raise AuthError(f"lipsește {name} (sesiune expirată?) — {vf_info}")
                fields[name] = el["value"]
            csrf = soup.find("input", {"name": _VS_CSRF}) or soup.find("input", {"id": _VS_CSRF})
            if csrf is not None and csrf.get("value"):
                fields[_VS_CSRF] = csrf["value"]

            form = soup.find("form")
            form_id = (form.get("id") if form else None) or "j_id0:j_id2"
            m = re.search(r"j_id\d+:j_id\d+:j_id\d+", page)
            action_id = m.group(0) if m else f"{form_id}:j_id3"

            data = {
                "AJAXREQUEST": "_viewRoot",
                form_id: form_id,
                "methodN": "PowerOutages",
                "params": f"{pod},ro",
                "uniqueId": str(uuid.uuid4()),
                **fields,
                action_id: action_id,
            }
            async with self._s.post(
                const.VF_OUTAGES,
                data=data,
                headers={"Origin": const.BASE_URL, "Referer": const.VF_OUTAGES},
                timeout=TIMEOUT,
            ) as r:
                body = await r.text()
                _LOGGER.debug("VF POST -> HTTP %s, %d bytes", r.status, len(body))
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnect(str(err)) from err
        return parse_outage_response(pod, body)
