from __future__ import annotations

import asyncio
import json
import re
from datetime import date
from time import monotonic
from urllib.parse import urljoin

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.logging import get_logger
from app.providers.base import (
    ProviderAuthError,
    ProviderQuotaExhaustedError,
    ProviderRateLimitedError,
    ProviderResult,
)

log = get_logger(__name__)

_BASE_URL = "https://app.scrapingbee.com/api/v1"
_KAYAK_DEFAULT_HOST = "www.kayak.com"
_MONEY_RE = re.compile(r"(-?\d[\d,]*(?:\.\d+)?)")
_HOURS_MINUTES_RE = re.compile(r"(?i)(\d+)\s*(?:hours|hour|hrs|hr|h)\s*(?:(\d+)\s*(?:minutes|minute|mins|min|m))?")
_MINUTES_ONLY_RE = re.compile(r"(?i)(\d+)\s*(?:minutes|minute|mins|min|m)")
_STOPS_RE = re.compile(r"(?i)\b(\d+)\s+stop(?:s)?\b")
_CURRENCY_CODE_RE = re.compile(r"\b([A-Z]{3})\b")
_KAYAK_HOST_BY_COUNTRY = {
    "au": "www.kayak.com.au",
    "ca": "www.ca.kayak.com",
    "de": "www.kayak.de",
    "es": "www.kayak.es",
    "fr": "www.kayak.fr",
    "ie": "www.kayak.ie",
    "in": "www.kayak.co.in",
    "it": "www.kayak.it",
    "jp": "www.kayak.co.jp",
    "mx": "www.kayak.com.mx",
    "nz": "www.kayak.co.nz",
    "sg": "www.kayak.sg",
    "uk": "www.kayak.co.uk",
    "us": "www.kayak.com",
}
_COUNTRY_CODE_BY_CURRENCY = {
    "AUD": "au",
    "CAD": "ca",
    "EUR": "ie",
    "GBP": "uk",
    "INR": "in",
    "JPY": "jp",
    "MXN": "mx",
    "NZD": "nz",
    "SGD": "sg",
    "USD": "us",
}
_CURRENCY_BY_COUNTRY = {
    "au": "AUD",
    "ca": "CAD",
    "de": "EUR",
    "es": "EUR",
    "fr": "EUR",
    "ie": "EUR",
    "in": "INR",
    "it": "EUR",
    "jp": "JPY",
    "mx": "MXN",
    "nz": "NZD",
    "sg": "SGD",
    "uk": "GBP",
    "us": "USD",
}
_CURRENCY_BY_SYMBOL = {
    "₹": "INR",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₩": "KRW",
}
_CURRENCY_BY_PRICE_TOKEN = {
    "A$": "AUD",
    "AU$": "AUD",
    "C$": "CAD",
    "CA$": "CAD",
    "HK$": "HKD",
    "NZ$": "NZD",
    "S$": "SGD",
    "SGD$": "SGD",
    "US$": "USD",
}
_ALLOWED_MARKETS = {"us", "ca"}
_FAST_MULTI_CITY_CARD_LIMIT = 90
_DEEP_MULTI_CITY_CARD_LIMIT = 180


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_market(value: object) -> str | None:
    market = str(value or "").strip().lower()
    if not market:
        return None
    if market not in _ALLOWED_MARKETS:
        raise ValueError("market must be one of: us, ca")
    return market


def _extract_body_message(resp: httpx.Response) -> str:
    try:
        payload = resp.json()
    except Exception:
        return resp.text.strip()

    if isinstance(payload, dict):
        for key in ("message", "error", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return resp.text.strip()


def _is_quota_message(message: str) -> bool:
    lowered = message.lower()
    return any(
        token in lowered
        for token in (
            "no more credit",
            "not enough credit",
            "insufficient credit",
            "quota",
        )
    )


def _is_auth_message(message: str) -> bool:
    lowered = message.lower()
    return any(
        token in lowered
        for token in (
            "invalid api key",
            "missing api key",
            "unauthorized",
            "forbidden",
        )
    ) 


class ScrapingBeeProvider:
    """
    KAYAK page scraping via ScrapingBee's HTML API.

    ScrapingBee handles browser rendering / proxy rotation while this provider
    builds KAYAK search URLs and normalizes the extracted offers into the
    app's provider contract.
    """

    name = "scrapingbee"

    _AI_EXTRACT_RULES = {
        "offers": {
            "description": "visible KAYAK flight offers on the page",
            "type": "list",
            "output": {
                "price": {
                    "description": "total itinerary price as a number without currency symbols",
                    "type": "number",
                },
                "price_text": {
                    "description": "exact displayed itinerary price text including currency symbol or code",
                    "type": "string",
                },
                "airline": {
                    "description": "airline name or airline combination shown for the itinerary",
                    "type": "string",
                },
                "duration": {
                    "description": "total itinerary duration in minutes if inferable, otherwise 0",
                    "type": "number",
                },
                "duration_text": {
                    "description": "displayed itinerary duration text such as 23h 10m",
                    "type": "string",
                },
                "stops": {
                    "description": "number of stops as an integer where nonstop is 0",
                    "type": "number",
                },
                "link": {
                    "description": "deal or booking link for the itinerary if visible",
                    "type": "string",
                },
                "summary": {
                    "description": "short itinerary summary including times, stops, and other visible details",
                    "type": "string",
                },
            },
        }
    }

    _JS_SCENARIO = {
        "instructions": [
            {"wait": 3000},
            {"evaluate": "window.scrollTo(0, document.body.scrollHeight);"},
            {"wait": 3000},
        ]
    }

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = _BASE_URL,
        timeout: int = 30,
        max_retries: int = 3,
        concurrency_limit: int = 2,
        min_delay_seconds: float = 1.0,
        quota_cooldown_seconds: int = 3600,
        country_code: str = "us",
        premium_proxy: bool = False,
        stealth_proxy: bool = False,
        user_agent: str = "flight-harvester/1.0",
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._country_code = country_code.strip().lower()
        self._premium_proxy = premium_proxy
        self._stealth_proxy = stealth_proxy
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": user_agent.strip() or "flight-harvester/1.0",
            },
        )

        self._semaphore = asyncio.Semaphore(max(1, concurrency_limit))
        self._throttle_lock = asyncio.Lock()
        self._next_request_at = 0.0
        self._min_delay_seconds = max(0.0, min_delay_seconds)
        self._quota_blocked_until = 0.0
        self._quota_cooldown_seconds = quota_cooldown_seconds

    def is_configured(self) -> bool:
        return bool(self._api_key and self._base_url)

    async def close(self) -> None:
        await self._client.aclose()

    def _parse_partial_payload(self, body: str) -> dict | None:
        if '"offers"' not in body:
            return None

        offers_key = body.find('"offers"')
        list_start = body.find("[", offers_key)
        if list_start < 0:
            return None

        decoder = json.JSONDecoder()
        cursor = list_start + 1
        offers: list[dict[str, object]] = []

        while cursor < len(body):
            while cursor < len(body) and body[cursor] in " \r\n\t,":
                cursor += 1

            if cursor >= len(body) or body[cursor] == "]":
                break

            try:
                parsed, next_cursor = decoder.raw_decode(body, cursor)
            except json.JSONDecodeError:
                break

            if isinstance(parsed, dict):
                offers.append(parsed)
            cursor = next_cursor

        if not offers:
            return None

        return {"offers": offers}

    def _market_country_code(
        self,
        requested_currency: str | None = None,
        requested_market: str | None = None,
    ) -> str:
        normalized_market = _normalize_market(requested_market)
        if normalized_market:
            return normalized_market

        if self._country_code:
            return self._country_code

        normalized_currency = _clean_text(requested_currency).upper()
        if normalized_currency:
            mapped = _COUNTRY_CODE_BY_CURRENCY.get(normalized_currency)
            if mapped:
                return mapped
        return self._country_code or "us"

    def _kayak_site_base(
        self,
        requested_currency: str | None = None,
        requested_market: str | None = None,
    ) -> str:
        market_country_code = self._market_country_code(requested_currency, requested_market)
        host = _KAYAK_HOST_BY_COUNTRY.get(market_country_code, _KAYAK_DEFAULT_HOST)
        return f"https://{host}"

    def _detect_display_currency(
        self,
        price_text: object,
        *,
        requested_currency: str,
        market_country_code: str,
    ) -> str:
        raw = _clean_text(price_text)
        if raw:
            uppercase_raw = raw.upper()
            for token, currency_code in _CURRENCY_BY_PRICE_TOKEN.items():
                if token in uppercase_raw:
                    return currency_code
            code_match = _CURRENCY_CODE_RE.search(uppercase_raw)
            if code_match:
                code = code_match.group(1)
                if code in _COUNTRY_CODE_BY_CURRENCY:
                    return code
            for symbol, currency_code in _CURRENCY_BY_SYMBOL.items():
                if symbol in raw:
                    return currency_code
            if "$" in raw:
                return _CURRENCY_BY_COUNTRY.get(
                    market_country_code,
                    _clean_text(requested_currency).upper() or "USD",
                )
        requested = _clean_text(requested_currency).upper()
        if requested:
            return requested
        return _CURRENCY_BY_COUNTRY.get(market_country_code, "USD")

    def _base_request_params(
        self,
        target_url: str,
        *,
        country_code: str | None = None,
    ) -> dict[str, object]:
        params: dict[str, object] = {
            "api_key": self._api_key,
            "url": target_url,
            "render_js": "True",
            "block_resources": "False",
            "block_ads": "True",
            "device": "desktop",
            "timeout": min(self._timeout * 1000, 140_000),
            "wait": 4000,
            "window_width": 1600,
            "window_height": 2200,
        }
        effective_country_code = _clean_text(country_code).lower() or self._country_code
        if effective_country_code:
            params["country_code"] = effective_country_code
        if self._premium_proxy:
            params["premium_proxy"] = "True"
        if self._stealth_proxy:
            params["stealth_proxy"] = "True"
        return params

    def _quota_blocked(self) -> bool:
        return monotonic() < self._quota_blocked_until

    def _trip_quota_breaker(self) -> None:
        self._quota_blocked_until = monotonic() + self._quota_cooldown_seconds

    async def _wait_for_slot(self) -> None:
        async with self._throttle_lock:
            now = monotonic()
            wait_for = self._next_request_at - now
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            self._next_request_at = monotonic() + self._min_delay_seconds

    def _base_params(
        self,
        target_url: str,
        *,
        ai_extract_rules: dict[str, object] | None = None,
        js_scenario: dict[str, object] | None = None,
        country_code: str | None = None,
    ) -> dict[str, object]:
        params = self._base_request_params(target_url, country_code=country_code)
        params["ai_extract_rules"] = json.dumps(
            ai_extract_rules or self._AI_EXTRACT_RULES,
            separators=(",", ":"),
        )
        params["js_scenario"] = json.dumps(
            js_scenario or self._JS_SCENARIO,
            separators=(",", ":"),
        )
        return params

    def _raise_for_status(self, response: httpx.Response) -> None:
        message = _extract_body_message(response) or "ScrapingBee request failed."

        if response.status_code == 401:
            self._trip_quota_breaker()
            raise ProviderQuotaExhaustedError(message)

        if response.status_code == 403:
            raise ProviderAuthError(message)

        if response.status_code == 429:
            raise ProviderRateLimitedError(message or "ScrapingBee concurrency limit hit.")

        if response.status_code == 400 and _is_auth_message(message):
            raise ProviderAuthError(message)

        if response.status_code >= 400:
            if _is_quota_message(message):
                self._trip_quota_breaker()
                raise ProviderQuotaExhaustedError(message)
            raise RuntimeError(message)

    async def _get_payload(
        self,
        target_url: str,
        *,
        ai_extract_rules: dict[str, object] | None = None,
        js_scenario: dict[str, object] | None = None,
        country_code: str | None = None,
    ) -> dict:
        async with self._semaphore:
            await self._wait_for_slot()
            try:
                response = await self._client.get(
                    self._base_url,
                    params=self._base_params(
                        target_url,
                        ai_extract_rules=ai_extract_rules,
                        js_scenario=js_scenario,
                        country_code=country_code,
                    ),
                )
            except httpx.TimeoutException as exc:
                raise RuntimeError("ScrapingBee request timed out.") from exc
            except httpx.HTTPError as exc:
                raise RuntimeError("ScrapingBee request failed.") from exc

        self._raise_for_status(response)

        try:
            data = await asyncio.to_thread(response.json)
        except Exception as exc:
            partial = self._parse_partial_payload(response.text)
            if partial is not None:
                return partial
            raise RuntimeError("ScrapingBee returned invalid JSON.") from exc

        if not isinstance(data, dict):
            raise RuntimeError("ScrapingBee returned an unexpected response body.")

        return data

    async def _get_rendered_payload(
        self,
        target_url: str,
        *,
        js_scenario: dict[str, object],
        country_code: str | None = None,
    ) -> dict:
        params = self._base_request_params(target_url, country_code=country_code)
        params["json_response"] = "True"
        params["js_scenario"] = json.dumps(js_scenario, separators=(",", ":"))
        params["block_resources"] = "True"
        params["wait"] = 2500

        async with self._semaphore:
            await self._wait_for_slot()
            try:
                response = await self._client.get(
                    self._base_url,
                    params=params,
                )
            except httpx.TimeoutException as exc:
                raise RuntimeError("ScrapingBee request timed out.") from exc
            except httpx.HTTPError as exc:
                raise RuntimeError("ScrapingBee request failed.") from exc

        self._raise_for_status(response)

        try:
            data = await asyncio.to_thread(response.json)
        except Exception as exc:
            raise RuntimeError("ScrapingBee returned invalid rendered JSON.") from exc

        if not isinstance(data, dict):
            raise RuntimeError("ScrapingBee returned an unexpected rendered response body.")

        return data

    def _build_search_url(
        self,
        *,
        origin: str,
        destination: str,
        depart_date: date,
        return_date: date | None = None,
        market: str | None = None,
        currency: str = "USD",
    ) -> str:
        route = f"{origin.upper()}-{destination.upper()}"
        base_url = self._kayak_site_base(currency, market)
        if return_date:
            return (
                f"{base_url}/flights/{route}/"
                f"{depart_date.isoformat()}/{return_date.isoformat()}?sort=price_a"
            )
        return (
            f"{base_url}/flights/{route}/"
            f"{depart_date.isoformat()}?sort=price_a"
        )

    def _build_multi_city_js_scenario(
        self,
        legs: list[dict[str, object]],
    ) -> dict[str, object]:
        first = legs[0]
        second = legs[1]
        first_origin = str(first["departure_id"]).upper()
        first_destination = str(first["arrival_id"]).upper()
        second_origin = str(second["departure_id"]).upper()
        second_destination = str(second["arrival_id"]).upper()
        first_date = f"{first['outbound_date']:%B} {first['outbound_date'].day}, {first['outbound_date']:%Y}"
        second_date = f"{second['outbound_date']:%B} {second['outbound_date'].day}, {second['outbound_date']:%Y}"

        helper = (
            "window.fh={"
            "r:()=>{Array.from(document.querySelectorAll('[aria-label]'))"
            ".filter(e=>(e.getAttribute('aria-label')||'').includes('Remove leg number 3 from your search'))"
            ".forEach(n=>{let k=Object.keys(n).find(x=>x.startsWith('__reactProps$')),p=k&&n[k];"
            "p&&p.onClick?p.onClick({currentTarget:n,target:n,preventDefault(){},stopPropagation(){}}):n.click()});return 1},"
            "c:(s,i,v)=>{let n=document.querySelectorAll(s)[i],k=n&&Object.keys(n).find(x=>x.startsWith('__reactProps$')),p=k&&n[k];"
            "if(!p||!p.onChange)return 0;"
            "p.onChange({target:{value:v},currentTarget:n,preventDefault(){},stopPropagation(){}});return 1},"
            "o:(s,i)=>{let n=document.querySelectorAll(s)[i],l=n&&document.getElementById(n.getAttribute('aria-controls'));"
            "if(!l)return 0;"
            "let m=Array.from(l.querySelectorAll('[role=option]')).find(e=>e.id!=='nearby');"
            "if(!m)return 0;"
            "let k=Object.keys(m).find(x=>x.startsWith('__reactProps$')),p=k&&m[k];"
            "p&&p.onClick?p.onClick({currentTarget:m,target:m,preventDefault(){},stopPropagation(){}}):m.click();return 1},"
            "d:i=>{let n=Array.from(document.querySelectorAll('[aria-label]'))"
            ".filter(e=>(e.getAttribute('aria-label')||'').includes('Select start date from calendar input'))[i],"
            "k=n&&Object.keys(n).find(x=>x.startsWith('__reactProps$')),p=k&&n[k];"
            "if(!p||!p.onClick)return 0;"
            "p.onClick({currentTarget:n,target:n,preventDefault(){},stopPropagation(){}});return 1},"
            "p:l=>{let n=Array.from(document.querySelectorAll('[aria-label]')).find(e=>e.getAttribute('aria-label')===l),"
            "k=n&&Object.keys(n).find(x=>x.startsWith('__reactProps$')),p=k&&n[k];"
            "if(!n)return 0;"
            "p&&p.onClick?p.onClick({currentTarget:n,target:n,preventDefault(){},stopPropagation(){}}):n.click();return 1},"
            "s:()=>{let b=document.querySelector('button[aria-label=\"Search\"]'),k=b&&Object.keys(b).find(x=>x.startsWith('__reactProps$')),p=k&&b[k];"
            "if(!p||!p.onClick)return 0;"
            "p.onClick({currentTarget:b,target:b,preventDefault(){},stopPropagation(){}});return 1}"
            "};1"
        )

        return {
            "strict": False,
            "instructions": [
                {"evaluate": helper},
                {"evaluate": "fh.r()"},
                {"wait": 700},
                {"evaluate": f'fh.c("input[data-test-origin]",0,"{first_origin}")'},
                {"evaluate": f'fh.c("input[data-test-destination]",0,"{first_destination}")'},
                {"evaluate": f'fh.c("input[data-test-origin]",1,"{second_origin}")'},
                {"evaluate": f'fh.c("input[data-test-destination]",1,"{second_destination}")'},
                {"wait": 1500},
                {"evaluate": 'fh.o("input[data-test-origin]",0)'},
                {"evaluate": 'fh.o("input[data-test-destination]",0)'},
                {"evaluate": 'fh.o("input[data-test-origin]",1)'},
                {"evaluate": 'fh.o("input[data-test-destination]",1)'},
                {"wait": 1200},
                {"evaluate": "fh.d(0)"},
                {"wait": 700},
                {"evaluate": f'fh.p("{first_date}")'},
                {"wait": 700},
                {"evaluate": "fh.d(1)"},
                {"wait": 700},
                {"evaluate": f'fh.p("{second_date}")'},
                {"wait": 1200},
                {"evaluate": "fh.s()"},
                {"wait": 12_000},
            ],
        }

    def _build_multi_city_results_url(
        self,
        *,
        outbound_origin: str,
        outbound_destination: str,
        outbound_date: date,
        inbound_origin: str,
        inbound_destination: str,
        inbound_date: date,
        market: str | None = None,
        currency: str = "USD",
    ) -> str:
        base_url = self._kayak_site_base(currency, market)
        return (
            f"{base_url}/flights/"
            f"{outbound_origin.upper()}-{outbound_destination.upper()}/"
            f"{outbound_date.isoformat()}/"
            f"{inbound_origin.upper()}-{inbound_destination.upper()}/"
            f"{inbound_date.isoformat()}?sort=price_a"
        )

    def _build_multi_city_results_scenario(self, *, deep: bool = False) -> dict[str, object]:
        card_limit = _DEEP_MULTI_CITY_CARD_LIMIT if deep else _FAST_MULTI_CITY_CARD_LIMIT
        click_cheapest_script = (
            "(()=>{"
            "const norm=v=>(v||'').replace(/\\s+/g,' ').trim().toLowerCase();"
            "const visible=el=>{if(!el)return false;const r=el.getBoundingClientRect();"
            "return r.width>0&&r.height>0&&window.getComputedStyle(el).visibility!=='hidden';};"
            "const pick=Array.from(document.querySelectorAll('button,a,[role=\"button\"],div,span'))"
            ".filter(el=>visible(el)&&/^cheapest(?:\\s|$)/.test(norm(el.innerText||el.getAttribute('aria-label')||'')));"
            "if(!pick.length)return false;"
            "const target=pick[0].closest('button,a,[role=\"button\"]')||pick[0];"
            "target.click();"
            "return true;"
            "})()"
        )
        script = (
            "(()=>{"
            f"const cardLimit={card_limit};"
            "const isCard=node=>!!node&&!!node.querySelector('.nrc6-price-section .e2GB-price-text')"
            "&&node.querySelectorAll('ol.hJSA-list > li').length>=2;"
            "const raw=Array.from(document.querySelectorAll("
            "'div[aria-label^=\"Result item\"],div[data-resultid],div.nrc6,div[class*=\"nrc6\"]'"
            ")).filter(isCard);"
            "const roots=raw.filter((card,index)=>!raw.some((other,otherIndex)=>"
            "otherIndex!==index&&card.contains(other)&&isCard(other)"
            "));"
            "const clean=v=>(v||'').toString().trim();"
            "const tabText=label=>(Array.from(document.querySelectorAll('button,a,[role=\"button\"],div,span'))"
            ".find(el=>new RegExp('^'+label+'(?:\\\\s|$)').test(clean(el.innerText||el.getAttribute('aria-label')).replace(/\\\\s+/g,' ').toLowerCase()))"
            "?.innerText||'').trim();"
            "return JSON.stringify({"
            "card_count:roots.length,"
            "captured_count:roots.slice(0,cardLimit).length,"
            "cards:roots.slice(0,cardLimit).map(card=>({"
            "text:clean(card.innerText),"
            "price_text:clean(card.querySelector('.nrc6-price-section .e2GB-price-text')?.innerText),"
            "booking_href:clean(card.querySelector('.nrc6-price-section a[href*=\"/book/\"]')?.getAttribute('href')),"
            "cabin:clean(card.querySelector('.nrc6-price-section .Hy6H')?.innerText),"
            "airline_text:clean(card.querySelector('.J0g6-operator-text')?.innerText),"
            "legs:Array.from(card.querySelectorAll('ol.hJSA-list > li')).map(li=>({"
            "text:clean(li.innerText),"
            "airline:clean(li.querySelector('.tdCx-leg-carrier img')?.getAttribute('alt')),"
            "time_text:clean(li.querySelector('.VY2U .vmXl')?.innerText),"
            "route_text:clean(li.querySelector('.VY2U [dir=\"ltr\"]')?.innerText),"
            "stops_text:clean(li.querySelector('.JWEO .vmXl')?.innerText),"
            "layover_text:clean(li.querySelector('.JWEO .c_cgF')?.innerText),"
            "duration_text:clean(li.querySelector('.xdW8 .vmXl')?.innerText)"
            "})).filter(leg=>leg.text)"
            "})),"
            "summary:{cheapest:tabText('cheapest'),best:tabText('best')}"
            "});"
            "})()"
        )
        if not deep:
            return {
                "strict": False,
                "instructions": [
                    {"wait": 6_500},
                    {"evaluate": click_cheapest_script},
                    {"wait": 2_000},
                    {"evaluate": "window.scrollBy(0, 1200);"},
                    {"wait": 1_500},
                    {"evaluate": click_cheapest_script},
                    {"evaluate": "window.scrollBy(0, 1800);"},
                    {"wait": 1_500},
                    {"evaluate": "window.scrollBy(0, 2200);"},
                    {"wait": 2_000},
                    {"evaluate": script},
                ],
            }
        return {
            "strict": False,
            "instructions": [
                {"wait": 8_000},
                {"evaluate": click_cheapest_script},
                {"wait": 2_000},
                {"evaluate": "window.scrollBy(0, 1200);"},
                {"wait": 1_500},
                {"evaluate": "window.scrollBy(0, 1800);"},
                {"wait": 1_500},
                {"evaluate": click_cheapest_script},
                {"evaluate": "window.scrollBy(0, 2400);"},
                {"wait": 1_500},
                {"evaluate": "window.scrollBy(0, 2800);"},
                {"wait": 1_500},
                {"evaluate": "window.scrollBy(0, 3200);"},
                {"wait": 2_000},
                {"evaluate": script},
            ],
        }

    async def _parse_multi_city_rendered_payload(
        self,
        rendered: dict,
        *,
        currency: str,
        deep_link: str,
        market_country_code: str,
    ) -> tuple[list[ProviderResult], int, int]:
        cards_payload = self._extract_rendered_cards_payload(rendered)
        if cards_payload is None:
            return [], 0, 0

        card_count = 0
        captured_count = 0
        raw_count = cards_payload.get("card_count")
        if isinstance(raw_count, int) and raw_count >= 0:
            card_count = raw_count
        raw_captured_count = cards_payload.get("captured_count")
        if isinstance(raw_captured_count, int) and raw_captured_count >= 0:
            captured_count = raw_captured_count

        results = await asyncio.to_thread(
            self._normalize_multi_city_cards,
            cards_payload,
            currency=currency,
            deep_link=deep_link,
            market_country_code=market_country_code,
        )
        return results, card_count, captured_count

    def _filter_results_by_stops(
        self,
        results: list[ProviderResult],
        max_stops: int | None,
    ) -> list[ProviderResult]:
        if max_stops is None:
            return results
        return [result for result in results if result.stops <= max_stops]

    def _extract_rendered_cards_payload(self, rendered: dict) -> dict[str, object] | None:
        evaluate_results = rendered.get("evaluate_results")
        if not isinstance(evaluate_results, list) or not evaluate_results:
            return None
        for item in reversed(evaluate_results):
            if not isinstance(item, str):
                continue
            try:
                payload = json.loads(item)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and isinstance(payload.get("cards"), list):
                return payload
        return None

    def _rendered_payload_has_summary_prices(self, rendered: dict) -> bool:
        payload = self._extract_rendered_cards_payload(rendered)
        if payload is None:
            return False
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            return False
        return any(_clean_text(summary.get(key)) for key in ("cheapest", "best"))

    def _annotate_multi_city_results(
        self,
        results: list[ProviderResult],
        *,
        outbound_origin: str,
        outbound_destination: str,
        outbound_date: date,
        inbound_origin: str,
        inbound_destination: str,
        inbound_date: date,
    ) -> list[ProviderResult]:
        annotated: list[ProviderResult] = []
        for result in results:
            airline_parts = [part.strip() for part in result.airline.split("/") if part.strip()]
            outbound_airline = airline_parts[0] if airline_parts else result.airline
            return_airline = airline_parts[1] if len(airline_parts) > 1 else ""
            result.raw_data.update(
                {
                    "trip_type": "multi_city",
                    "outbound": {
                        "origin": outbound_origin,
                        "destination": outbound_destination,
                        "date": outbound_date.isoformat(),
                    },
                    "inbound": {
                        "origin": inbound_origin,
                        "destination": inbound_destination,
                        "date": inbound_date.isoformat(),
                    },
                    "outbound_airline": outbound_airline,
                    "return_airline": return_airline,
                    "return_origin": inbound_origin,
                    "return_destination": inbound_destination,
                    "return_date": inbound_date.isoformat(),
                }
            )
            annotated.append(result)
        return annotated

    def _parse_price(self, value: object) -> float | None:
        text = _clean_text(value)
        match = _MONEY_RE.search(text.replace(" ", ""))
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None

    def _parse_duration_minutes(
        self,
        summary: str,
        duration_text: str,
        duration_value: object = None,
    ) -> int:
        if isinstance(duration_value, (int, float)) and duration_value > 0:
            return int(duration_value)

        haystack = f"{summary} {duration_text}".strip()
        match = _HOURS_MINUTES_RE.search(haystack)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2) or 0)
            return hours * 60 + minutes

        match = _MINUTES_ONLY_RE.search(haystack)
        if match:
            return int(match.group(1))

        return 0

    def _parse_stops(self, summary: str, stops_value: object = None) -> int:
        if isinstance(stops_value, (int, float)) and stops_value >= 0:
            return int(stops_value)
        lowered = summary.lower()
        if "nonstop" in lowered or "non-stop" in lowered:
            return 0
        match = _STOPS_RE.search(summary)
        if match:
            return int(match.group(1))
        return 0

    def _normalize_multi_city_cards(
        self,
        payload: dict,
        *,
        currency: str,
        deep_link: str,
        market_country_code: str,
    ) -> list[ProviderResult]:
        raw_cards = payload.get("cards")
        if not isinstance(raw_cards, list):
            return []

        results: list[ProviderResult] = []
        for card in raw_cards:
            if not isinstance(card, dict):
                continue

            price = self._parse_price(card.get("price_text")) or self._parse_price(card.get("text"))
            if price is None:
                continue

            legs = card.get("legs")
            if not isinstance(legs, list) or len(legs) < 2:
                continue

            normalized_legs: list[dict[str, object]] = []
            unique_airlines: list[str] = []
            total_duration = 0
            max_stops = 0
            for leg in legs[:2]:
                if not isinstance(leg, dict):
                    continue
                airline = _clean_text(leg.get("airline"))
                if airline and airline not in unique_airlines:
                    unique_airlines.append(airline)
                duration_text = _clean_text(leg.get("duration_text"))
                layover_text = _clean_text(leg.get("layover_text"))
                stops_text = _clean_text(leg.get("stops_text"))
                route_text = _clean_text(leg.get("route_text"))
                total_duration += self._parse_duration_minutes(
                    "",
                    duration_text,
                )
                max_stops = max(
                    max_stops,
                    self._parse_stops(f"{stops_text} {layover_text}".strip()),
                )
                normalized_legs.append(
                    {
                        "airline": airline,
                        "time_text": _clean_text(leg.get("time_text")),
                        "route_text": route_text,
                        "stops_text": stops_text,
                        "layover_text": layover_text,
                        "duration_text": duration_text,
                        "text": _clean_text(leg.get("text")),
                    }
                )

            if len(normalized_legs) < 2:
                continue

            airline_text = _clean_text(card.get("airline_text"))
            display_airline = airline_text or " / ".join(unique_airlines) or "Unknown airline"
            booking_href = _clean_text(card.get("booking_href"))
            normalized_link = urljoin(deep_link, booking_href) if booking_href else deep_link
            card_text = _clean_text(card.get("text"))
            actual_currency = self._detect_display_currency(
                card.get("price_text") or card_text,
                requested_currency=currency,
                market_country_code=market_country_code,
            )

            results.append(
                ProviderResult(
                    price=price,
                    currency=actual_currency,
                    airline=display_airline,
                    deep_link=normalized_link,
                    provider=self.name,
                    duration_minutes=total_duration,
                    stops=max_stops,
                    raw_data={
                        "trip_type": "multi_city",
                        "duration_text": " / ".join(
                            leg["duration_text"]
                            for leg in normalized_legs
                            if isinstance(leg.get("duration_text"), str) and leg["duration_text"]
                        ),
                        "price_text": _clean_text(card.get("price_text")),
                        "summary": card_text,
                        "cabin": _clean_text(card.get("cabin")),
                        "legs": normalized_legs,
                        "outbound_airline": normalized_legs[0].get("airline") or "",
                        "return_airline": normalized_legs[1].get("airline") or "",
                    },
                )
            )

        return sorted(results, key=lambda item: item.price)

    def _normalize_flights(
        self,
        payload: dict,
        *,
        currency: str,
        deep_link: str,
        trip_type: str,
        market_country_code: str,
    ) -> list[ProviderResult]:
        offers = payload.get("offers")
        if not isinstance(offers, list):
            offers = payload.get("flights")
        if not isinstance(offers, list):
            return []

        results: list[ProviderResult] = []
        for offer in offers:
            if not isinstance(offer, dict):
                continue

            price = self._parse_price(offer.get("price"))
            if price is None:
                continue

            airline = _clean_text(offer.get("airline")) or "Unknown airline"
            duration_text = _clean_text(offer.get("duration_text")) or _clean_text(offer.get("time"))
            summary = _clean_text(offer.get("summary"))
            offer_link = _clean_text(offer.get("link"))
            normalized_link = urljoin(deep_link, offer_link) if offer_link else deep_link
            actual_currency = self._detect_display_currency(
                offer.get("price_text") or summary,
                requested_currency=currency,
                market_country_code=market_country_code,
            )

            results.append(
                ProviderResult(
                    price=price,
                    currency=actual_currency,
                    airline=airline,
                    deep_link=normalized_link,
                    provider=self.name,
                    duration_minutes=self._parse_duration_minutes(
                        summary,
                        duration_text,
                        offer.get("duration"),
                    ),
                    stops=self._parse_stops(summary, offer.get("stops")),
                    raw_data={
                        "trip_type": trip_type,
                        "price_text": _clean_text(offer.get("price_text")),
                        "duration_text": duration_text,
                        "summary": summary,
                    },
                )
            )

        return sorted(results, key=lambda item: item.price)

    async def _search_one_way_once(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        *,
        market: str | None = None,
        currency: str = "USD",
    ) -> list[ProviderResult]:
        if self._quota_blocked():
            raise ProviderQuotaExhaustedError("ScrapingBee quota cooldown active.")

        market_country_code = self._market_country_code(currency, market)
        target_url = self._build_search_url(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            market=market,
            currency=currency,
        )
        payload = await self._get_payload(target_url, country_code=market_country_code)
        results = self._normalize_flights(
            payload,
            currency=currency,
            deep_link=target_url,
            trip_type="one_way",
            market_country_code=market_country_code,
        )
        log.info(
            "scrapingbee_results",
            trip_type="one_way",
            origin=origin,
            destination=destination,
            date=depart_date.isoformat(),
            count=len(results),
            currency=currency,
        )
        return results

    async def _search_round_trip_once(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        return_date: date,
        *,
        market: str | None = None,
        currency: str = "USD",
    ) -> list[ProviderResult]:
        if self._quota_blocked():
            raise ProviderQuotaExhaustedError("ScrapingBee quota cooldown active.")

        market_country_code = self._market_country_code(currency, market)
        target_url = self._build_search_url(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            return_date=return_date,
            market=market,
            currency=currency,
        )
        payload = await self._get_payload(target_url, country_code=market_country_code)
        results = self._normalize_flights(
            payload,
            currency=currency,
            deep_link=target_url,
            trip_type="round_trip",
            market_country_code=market_country_code,
        )
        log.info(
            "scrapingbee_results",
            trip_type="round_trip",
            origin=origin,
            destination=destination,
            depart_date=depart_date.isoformat(),
            return_date=return_date.isoformat(),
            count=len(results),
            currency=currency,
        )
        return results

    async def _search_multi_city_once(
        self,
        legs: list[dict[str, object]],
        *,
        market: str | None = None,
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:
        if self._quota_blocked():
            raise ProviderQuotaExhaustedError("ScrapingBee quota cooldown active.")

        if len(legs) != 2:
            return []

        outbound = legs[0]
        inbound = legs[1]
        outbound_date = outbound.get("outbound_date")
        inbound_date = inbound.get("outbound_date")
        if not isinstance(outbound_date, date) or not isinstance(inbound_date, date):
            return []

        outbound_origin = str(outbound["departure_id"]).upper()
        outbound_destination = str(outbound["arrival_id"]).upper()
        inbound_origin = str(inbound["departure_id"]).upper()
        inbound_destination = str(inbound["arrival_id"]).upper()
        market_country_code = self._market_country_code(currency, market)
        target_url = self._build_multi_city_results_url(
            outbound_origin=outbound_origin,
            outbound_destination=outbound_destination,
            outbound_date=outbound_date,
            inbound_origin=inbound_origin,
            inbound_destination=inbound_destination,
            inbound_date=inbound_date,
            market=market,
            currency=currency,
        )

        rendered = await self._get_rendered_payload(
            target_url,
            js_scenario=self._build_multi_city_results_scenario(deep=False),
            country_code=market_country_code,
        )
        results, card_count, captured_count = await self._parse_multi_city_rendered_payload(
            rendered,
            currency=currency,
            deep_link=target_url,
            market_country_code=market_country_code,
        )
        eligible_results = self._filter_results_by_stops(results, max_stops)
        needs_deep_pass = not results or not eligible_results
        if (
            not needs_deep_pass
            and captured_count >= _FAST_MULTI_CITY_CARD_LIMIT
            and card_count > captured_count
            and len(eligible_results) < 5
        ):
            needs_deep_pass = True
        if needs_deep_pass:
            rendered = await self._get_rendered_payload(
                target_url,
                js_scenario=self._build_multi_city_results_scenario(deep=True),
                country_code=market_country_code,
            )
            results, _, _ = await self._parse_multi_city_rendered_payload(
                rendered,
                currency=currency,
                deep_link=target_url,
                market_country_code=market_country_code,
            )
        if not results and card_count == 0 and not self._rendered_payload_has_summary_prices(rendered):
            raise ValueError("KAYAK rendered page did not expose extractable result cards.")
        results = self._annotate_multi_city_results(
            results,
            outbound_origin=outbound_origin,
            outbound_destination=outbound_destination,
            outbound_date=outbound_date,
            inbound_origin=inbound_origin,
            inbound_destination=inbound_destination,
            inbound_date=inbound_date,
        )
        log.info(
            "scrapingbee_results",
            trip_type="multi_city",
            outbound=f"{outbound_origin}->{outbound_destination}",
            inbound=f"{inbound_origin}->{inbound_destination}",
            count=len(results),
            currency=currency,
            target_url=target_url,
        )
        return results

    def _should_retry(self, exc: BaseException) -> bool:
        return isinstance(exc, RuntimeError) and not isinstance(
            exc,
            (
                ProviderQuotaExhaustedError,
                ProviderAuthError,
            ),
        )

    async def search_one_way(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        adults: int = 1,
        cabin: str = "economy",
        market: str | None = None,
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:
        del adults, cabin

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential_jitter(initial=2, max=12),
            retry=retry_if_exception_type(RuntimeError)
            & retry_if_exception(self._should_retry),
            reraise=True,
        ):
            with attempt:
                results = await self._search_one_way_once(
                    origin=origin,
                    destination=destination,
                    depart_date=depart_date,
                    market=market,
                    currency=currency,
                )
                if max_stops is None:
                    return results
                return [result for result in results if result.stops <= max_stops]

        return []

    async def search_round_trip(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        return_date: date,
        adults: int = 1,
        cabin: str = "economy",
        market: str | None = None,
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:
        del adults, cabin

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential_jitter(initial=2, max=12),
            retry=retry_if_exception_type(RuntimeError)
            & retry_if_exception(self._should_retry),
            reraise=True,
        ):
            with attempt:
                results = await self._search_round_trip_once(
                    origin=origin,
                    destination=destination,
                    depart_date=depart_date,
                    return_date=return_date,
                    market=market,
                    currency=currency,
                )
                if max_stops is None:
                    return results
                return [result for result in results if result.stops <= max_stops]

        return []

    async def search_multi_city(
        self,
        legs: list[dict[str, object]],
        adults: int = 1,
        cabin: str = "economy",
        market: str | None = None,
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:
        del adults, cabin

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential_jitter(initial=2, max=12),
            retry=retry_if_exception_type(RuntimeError)
            & retry_if_exception(self._should_retry),
            reraise=True,
        ):
            with attempt:
                results = await self._search_multi_city_once(
                    legs=legs,
                    market=market,
                    currency=currency,
                    max_stops=max_stops,
                )
                if max_stops is None:
                    return results
                return self._filter_results_by_stops(results, max_stops)

        return []


class ScrapingBeePoolProvider:
    name = "scrapingbee"

    def __init__(
        self,
        api_keys: list[str],
        **provider_kwargs: object,
    ) -> None:
        self._providers = [
            ScrapingBeeProvider(api_key=api_key, **provider_kwargs)
            for api_key in api_keys
            if api_key.strip()
        ]
        self._cursor = 0

    def is_configured(self) -> bool:
        return any(provider.is_configured() for provider in self._providers)

    def _ordered_providers(self) -> list[ScrapingBeeProvider]:
        if not self._providers:
            return []

        start = self._cursor % len(self._providers)
        self._cursor = (self._cursor + 1) % len(self._providers)
        return self._providers[start:] + self._providers[:start]

    async def _search_with_failover(self, search_fn) -> list[ProviderResult]:
        last_exc: BaseException | None = None

        for provider in self._ordered_providers():
            try:
                return await search_fn(provider)
            except (
                ProviderQuotaExhaustedError,
                ProviderAuthError,
                ProviderRateLimitedError,
                RuntimeError,
            ) as exc:
                last_exc = exc
                continue

        if last_exc is not None:
            raise last_exc

        return []

    async def search_one_way(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        adults: int = 1,
        cabin: str = "economy",
        market: str | None = None,
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:
        return await self._search_with_failover(
            lambda provider: provider.search_one_way(
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                adults=adults,
                cabin=cabin,
                market=market,
                currency=currency,
                max_stops=max_stops,
            )
        )

    async def search_round_trip(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        return_date: date,
        adults: int = 1,
        cabin: str = "economy",
        market: str | None = None,
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:
        return await self._search_with_failover(
            lambda provider: provider.search_round_trip(
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                return_date=return_date,
                adults=adults,
                cabin=cabin,
                market=market,
                currency=currency,
                max_stops=max_stops,
            )
        )

    async def search_multi_city(
        self,
        legs: list[dict[str, object]],
        adults: int = 1,
        cabin: str = "economy",
        market: str | None = None,
        currency: str = "USD",
        max_stops: int | None = None,
    ) -> list[ProviderResult]:
        return await self._search_with_failover(
            lambda provider: provider.search_multi_city(
                legs=legs,
                adults=adults,
                cabin=cabin,
                market=market,
                currency=currency,
                max_stops=max_stops,
            )
        )

    async def close(self) -> None:
        for provider in self._providers:
            await provider.close()
