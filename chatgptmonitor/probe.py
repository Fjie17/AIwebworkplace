"""ChatGPT connectivity probes and operational advice."""

from __future__ import annotations

import os
import sys
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

TARGETS: list[dict[str, str]] = [
    {"id": "chatgpt", "name": "chatgpt.com", "url": "https://chatgpt.com"},
    {"id": "api", "name": "api.openai.com", "url": "https://api.openai.com"},
    {"id": "openai", "name": "openai.com", "url": "https://openai.com"},
    {"id": "proxy_check", "name": "出口探测 (ipify)", "url": "https://api.ipify.org"},
]

HISTORY_SIZE = 60
DEFAULT_INTERVAL_SEC = 5.0
PROBE_TIMEOUT_SEC = 10.0


@dataclass
class ProbeResult:
    target_id: str
    name: str
    url: str
    ok: bool
    status_code: int | None
    latency_ms: float | None
    error: str | None
    via_proxy: bool
    checked_at: str
    body_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("body_text", None)
        return d


@dataclass
class AdviceItem:
    level: str  # ok | warn | critical | info
    title: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Snapshot:
    checked_at: str
    proxy_enabled: bool
    proxy_url: str | None
    public_ip: str | None
    overall: str  # healthy | degraded | down
    results: list[ProbeResult] = field(default_factory=list)
    advice: list[AdviceItem] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checked_at": self.checked_at,
            "proxy_enabled": self.proxy_enabled,
            "proxy_url": self.proxy_url,
            "public_ip": self.public_ip,
            "overall": self.overall,
            "results": [r.to_dict() for r in self.results],
            "advice": [a.to_dict() for a in self.advice],
            "stats": self.stats,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def detect_system_proxy() -> tuple[bool, str | None]:
    """Read Windows WinINET proxy, fall back to env vars."""
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            ) as key:
                enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
                server = ""
                try:
                    server, _ = winreg.QueryValueEx(key, "ProxyServer")
                except FileNotFoundError:
                    server = ""
                if int(enabled) == 1 and server:
                    # May be "http=127.0.0.1:7892;https=..." or "127.0.0.1:7892"
                    hostport = server
                    if "=" in server:
                        parts = dict(
                            p.split("=", 1) for p in server.split(";") if "=" in p
                        )
                        hostport = (
                            parts.get("https")
                            or parts.get("http")
                            or next(iter(parts.values()), "")
                        )
                    if hostport and "://" not in hostport:
                        hostport = f"http://{hostport}"
                    return True, hostport
        except OSError:
            pass

    for key in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy", "ALL_PROXY"):
        val = os.environ.get(key)
        if val:
            return True, val
    return False, None


async def probe_one(
    client: httpx.AsyncClient,
    target: dict[str, str],
    via_proxy: bool,
) -> ProbeResult:
    started = time.perf_counter()
    try:
        # HEAD can be blocked; GET with small read is more reliable for CF sites.
        resp = await client.get(
            target["url"],
            follow_redirects=True,
            headers={"User-Agent": "ChatGPTMonitor/1.0"},
        )
        latency_ms = (time.perf_counter() - started) * 1000
        # 401/403/421 still prove TCP+TLS+HTTP reached the edge.
        reachable = resp.status_code < 500
        body_text = None
        if target["id"] == "proxy_check" and reachable:
            body_text = resp.text.strip()[:64]
        return ProbeResult(
            target_id=target["id"],
            name=target["name"],
            url=target["url"],
            ok=reachable,
            status_code=resp.status_code,
            latency_ms=round(latency_ms, 1),
            error=None if reachable else f"HTTP {resp.status_code}",
            via_proxy=via_proxy,
            checked_at=_now_iso(),
            body_text=body_text,
        )
    except Exception as exc:  # noqa: BLE001 — surface any probe failure
        latency_ms = (time.perf_counter() - started) * 1000
        return ProbeResult(
            target_id=target["id"],
            name=target["name"],
            url=target["url"],
            ok=False,
            status_code=None,
            latency_ms=round(latency_ms, 1) if latency_ms < PROBE_TIMEOUT_SEC * 1000 else None,
            error=str(exc.__class__.__name__) + ": " + str(exc)[:160],
            via_proxy=via_proxy,
            checked_at=_now_iso(),
        )


def build_advice(
    results: list[ProbeResult],
    proxy_enabled: bool,
    proxy_url: str | None,
) -> tuple[str, list[AdviceItem]]:
    by_id = {r.target_id: r for r in results}
    chatgpt = by_id.get("chatgpt")
    api = by_id.get("api")
    proxy_check = by_id.get("proxy_check")
    advice: list[AdviceItem] = []

    openai_ok = bool(chatgpt and chatgpt.ok) or bool(api and api.ok)
    proxy_ok = bool(proxy_check and proxy_check.ok)
    latencies = [
        r.latency_ms
        for r in results
        if r.target_id in ("chatgpt", "api", "openai") and r.ok and r.latency_ms
    ]
    avg_lat = sum(latencies) / len(latencies) if latencies else None

    if not proxy_enabled:
        advice.append(
            AdviceItem(
                "critical",
                "系统代理未开启",
                "当前没有检测到 Windows 系统代理。打开超实惠（或其它 VPN）并开启系统代理后再试。",
            )
        )
    elif not proxy_ok:
        advice.append(
            AdviceItem(
                "critical",
                "代理出口不可用",
                f"代理 {proxy_url or '未知'} 无法访问外网。重启代理客户端，或换一个节点。",
            )
        )

    if proxy_ok and not openai_ok:
        advice.append(
            AdviceItem(
                "critical",
                "代理能出国，但连不上 OpenAI",
                "换一个标注可用 ChatGPT/OpenAI 的节点，并开启远程 DNS / Fake-IP，避免本机 DNS 污染。",
            )
        )
    elif openai_ok and avg_lat is not None and avg_lat >= 6000:
        advice.append(
            AdviceItem(
                "warn",
                "延迟过高（>6s）",
                "节点偏远或拥堵。优先换香港 / 日本 / 新加坡低延迟节点；桌面端会长时间停在 Thinking。",
            )
        )
    elif openai_ok and avg_lat is not None and avg_lat >= 3500:
        advice.append(
            AdviceItem(
                "warn",
                "延迟偏高（3.5–6s）",
                "可用但体验差。可先换节点；Codex 里把 reasoning 从 high 调到 medium/low 也能加快响应。",
            )
        )

    if chatgpt and chatgpt.ok and chatgpt.status_code == 403:
        advice.append(
            AdviceItem(
                "info",
                "chatgpt.com 返回 403（Cloudflare）",
                "curl/探测被 CF 挑战很常见，桌面端有时仍可用。若 App 也卡住，换干净 IP 的节点。",
            )
        )

    if api and api.ok and api.status_code in (401, 421):
        advice.append(
            AdviceItem(
                "ok",
                "api.openai.com 已连通",
                f"HTTP {api.status_code} 表示 TLS/链路正常（未带有效 Key 时 401 属预期）。",
            )
        )

    if openai_ok and avg_lat is not None and avg_lat < 2000:
        advice.append(
            AdviceItem(
                "ok",
                "链路状态良好",
                "OpenAI 相关域名可达且延迟较低。若桌面端仍 Thinking，检查模型是否选了 Astra，或 reasoning=high。",
            )
        )

    # Codex-specific tip from earlier diagnosis
    advice.append(
        AdviceItem(
            "info",
            "Codex 配置提示",
            "真实配置在 CODEX_HOME（你这边是 D:\\codex）。日常任务用 Luna/Terra，难任务再用 Sol/Astra，可显著省 Plus 额度并减少等待。",
        )
    )

    if not proxy_ok and not openai_ok:
        overall = "down"
    elif not openai_ok or (avg_lat is not None and avg_lat >= 6000):
        overall = "degraded" if proxy_ok else "down"
    elif avg_lat is not None and avg_lat >= 3500:
        overall = "degraded"
    else:
        overall = "healthy"

    # Prefer critical/warn first in UI
    order = {"critical": 0, "warn": 1, "info": 2, "ok": 3}
    advice.sort(key=lambda a: order.get(a.level, 9))
    return overall, advice


def compute_stats(history: deque[Snapshot]) -> dict[str, Any]:
    if not history:
        return {}
    series: dict[str, list[float | None]] = {
        "chatgpt": [],
        "api": [],
        "openai": [],
        "proxy_check": [],
    }
    labels: list[str] = []
    for snap in history:
        labels.append(snap.checked_at[11:19] if len(snap.checked_at) >= 19 else snap.checked_at)
        by_id = {r.target_id: r for r in snap.results}
        for tid in series:
            r = by_id.get(tid)
            series[tid].append(r.latency_ms if r and r.ok else None)

    def summarize(vals: list[float | None]) -> dict[str, float | None]:
        nums = [v for v in vals if v is not None]
        if not nums:
            return {"avg": None, "min": None, "max": None, "success_rate": 0.0}
        return {
            "avg": round(sum(nums) / len(nums), 1),
            "min": round(min(nums), 1),
            "max": round(max(nums), 1),
            "success_rate": round(len(nums) / len(vals) * 100, 1),
        }

    return {
        "labels": labels,
        "series": series,
        "summary": {tid: summarize(vals) for tid, vals in series.items()},
        "sample_count": len(history),
    }


class MonitorService:
    def __init__(self, interval_sec: float = DEFAULT_INTERVAL_SEC) -> None:
        self.interval_sec = interval_sec
        self.history: deque[Snapshot] = deque(maxlen=HISTORY_SIZE)
        self.latest: Snapshot | None = None
        self._running = False

    async def run_once(self) -> Snapshot:
        proxy_enabled, proxy_url = detect_system_proxy()
        proxies = proxy_url if proxy_enabled and proxy_url else None

        timeout = httpx.Timeout(PROBE_TIMEOUT_SEC)
        async with httpx.AsyncClient(
            proxy=proxies,
            timeout=timeout,
            verify=True,
        ) as client:
            results: list[ProbeResult] = []
            public_ip: str | None = None
            for target in TARGETS:
                result = await probe_one(client, target, via_proxy=bool(proxies))
                results.append(result)
                if target["id"] == "proxy_check" and result.body_text:
                    public_ip = result.body_text

        overall, advice = build_advice(results, proxy_enabled, proxy_url)
        snap = Snapshot(
            checked_at=_now_iso(),
            proxy_enabled=proxy_enabled,
            proxy_url=proxy_url,
            public_ip=public_ip,
            overall=overall,
            results=results,
            advice=advice,
        )
        self.history.append(snap)
        snap.stats = compute_stats(self.history)
        self.latest = snap
        return snap

    async def loop(self) -> None:
        self._running = True
        while self._running:
            try:
                await self.run_once()
            except Exception:  # noqa: BLE001 — keep loop alive
                err = Snapshot(
                    checked_at=_now_iso(),
                    proxy_enabled=False,
                    proxy_url=None,
                    public_ip=None,
                    overall="down",
                    results=[],
                    advice=[
                        AdviceItem(
                            "critical",
                            "监控循环异常",
                            "内部探测失败，请查看控制台日志后重启监控服务。",
                        )
                    ],
                )
                self.latest = err
                self.history.append(err)
            await _async_sleep(self.interval_sec)

    def stop(self) -> None:
        self._running = False


async def _async_sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


def proxy_host_display(proxy_url: str | None) -> str:
    if not proxy_url:
        return "—"
    try:
        parsed = urlparse(proxy_url if "://" in proxy_url else f"http://{proxy_url}")
        return parsed.netloc or proxy_url
    except Exception:  # noqa: BLE001
        return proxy_url
