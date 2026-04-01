#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

console = Console()

API_BASE = "https://api.timeweb.cloud"
API_OLD_BASE = "https://timeweb.cloud"
MOSCOW_TZ = timezone(timedelta(hours=3))
DEBUG_STATS = False

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message


METRICS: dict[str, dict[str, str]] = {
    "cpu": {"label": "CPU", "source": "new", "api_key": "system.cpu.util"},
    "network_request": {"label": "Network request", "source": "new", "api_key": "network.request"},
    "network_response": {"label": "Network response", "source": "new", "api_key": "network.response"},
    "disk": {"label": "Disk", "source": "old", "old_key": "disk"},
    "ram": {"label": "RAM", "source": "old", "old_key": "ram"},
}


class Client:
    def __init__(self, token: str):
        self.token = token

    def _req(
        self,
        method: str,
        base: str,
        path: str,
        query: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = base + path
        if query:
            url += "?" + urllib.parse.urlencode(query)

        if DEBUG_STATS:
            console.print(f"[dim]REQ {method} {url}[/dim]")

        req = urllib.request.Request(url, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read().decode()
                if DEBUG_STATS:
                    console.print(f"[dim]RESP {method} {url} -> {r.status}[/dim]")
                return json.loads(data) if data else {}
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if DEBUG_STATS:
                console.print(f"[dim]ERR  {method} {url} -> {e.code}[/dim]")
                console.print(f"[dim]{body}[/dim]")
            raise ApiError(e.code, body or e.reason)
        except urllib.error.URLError as e:
            if DEBUG_STATS:
                console.print(f"[dim]ERR  {method} {url} -> NET[/dim]")
                console.print(f"[dim]{e}[/dim]")
            raise ApiError(-1, "Нет сети / DNS")

    def servers(self) -> list[dict[str, Any]]:
        return self._req("GET", API_BASE, "/api/v1/servers").get("servers", [])

    def server(self, sid: int) -> dict[str, Any]:
        return self._req("GET", API_BASE, f"/api/v1/servers/{sid}").get("server", {})

    def stats_old(self, sid: int, date_from: str, date_to: str) -> dict[str, Any]:
        query = {"date_from": date_from, "date_to": date_to}
        return self._req("GET", API_OLD_BASE, f"/api/v3/servers/{sid}/statistics", query)

    def stats_new_multi(self, sid: int, time_from: str, period_hours: int, keys: str) -> dict[str, Any]:
        encoded_time_from = urllib.parse.quote(time_from, safe="")
        encoded_keys = urllib.parse.quote(keys, safe=".;")
        path = f"/api/v1/servers/{sid}/statistics/{encoded_time_from}/{period_hours}/{encoded_keys}"
        return self._req("GET", API_BASE, path)

    def start(self, sid: int) -> None:
        self._req("POST", API_BASE, f"/api/v1/servers/{sid}/start")

    def stop(self, sid: int) -> None:
        self._req("POST", API_BASE, f"/api/v1/servers/{sid}/shutdown")

    def reboot(self, sid: int) -> None:
        self._req("POST", API_BASE, f"/api/v1/servers/{sid}/reboot")

    def hard_reboot(self, sid: int) -> None:
        self._req("POST", API_BASE, f"/api/v1/servers/{sid}/hard-reboot")

    def hard_shutdown(self, sid: int) -> None:
        self._req("POST", API_BASE, f"/api/v1/servers/{sid}/hard-shutdown")


def banner() -> None:
    console.print(
        Panel(
            "[bold cyan]Timeweb Cloud VPS CLI Manager[/bold cyan]\n"
            "[white]управление облачным сервером[/white]",
            border_style="blue",
        )
    )


def ask_token() -> str:
    console.print(Panel("🔐 Введите API ключ", border_style="magenta"))
    token = getpass.getpass("> ").strip()
    console.print("[yellow]⏳ Загрузка серверов...[/yellow]")
    return token


def ask(text: str) -> str:
    console.print(Panel(text, border_style="magenta"))
    return input("> ").strip()


def show_servers(lst: list[dict[str, Any]]) -> None:
    table = Table(title="Список серверов", box=box.ROUNDED)
    table.add_column("#", style="cyan")
    table.add_column("ID", style="yellow")
    table.add_column("Имя", style="green")
    table.add_column("Статус", style="magenta")
    table.add_column("Регион", style="blue")
    table.add_column("Комментарий", style="white")

    for i, s in enumerate(lst, 1):
        location = s.get("location")
        if isinstance(location, dict):
            region = location.get("name") or location.get("code") or "—"
        elif location:
            region = str(location)
        else:
            region = "—"

        table.add_row(
            str(i),
            str(s.get("id") or "—"),
            s.get("name") or "—",
            s.get("status") or "—",
            region,
            s.get("comment") or "—",
        )

    console.print(table)


def get_ip(s: dict[str, Any]) -> str:
    if s.get("public_ip"):
        return str(s.get("public_ip"))

    if isinstance(s.get("ips"), list) and s["ips"]:
        first = s["ips"][0]
        if isinstance(first, dict):
            return first.get("ip") or first.get("address") or first.get("value") or "—"
        return str(first)

    if isinstance(s.get("public_ips"), list) and s["public_ips"]:
        ip = s["public_ips"][0]
        if isinstance(ip, dict):
            return ip.get("ip") or ip.get("address") or ip.get("value") or "—"
        return str(ip)

    return "—"


def show_server(s: dict[str, Any]) -> None:
    table = Table(box=box.ROUNDED)
    table.add_column("Поле", style="cyan")
    table.add_column("Значение", style="green")

    table.add_row("id", str(s.get("id") or "—"))
    table.add_row("name", s.get("name") or "—")
    table.add_row("status", s.get("status") or "—")
    table.add_row("public ip", get_ip(s))

    location = s.get("location")
    if isinstance(location, dict):
        location = location.get("name") or location.get("code") or "—"
    table.add_row("location", str(location or "—"))
    table.add_row("comment", s.get("comment") or "—")

    console.print(Panel(table, title="Выбранный сервер", border_style="green"))


def draw_graph(values: list[float]) -> None:
    if not values:
        console.print("Нет данных")
        return

    width = max(10, console.size.width - 5)
    height = 10

    if len(values) > width:
        bucket_size = len(values) / width
        scaled: list[float] = []
        for i in range(width):
            start = int(i * bucket_size)
            end = int((i + 1) * bucket_size)
            if end <= start:
                end = min(start + 1, len(values))
            chunk = values[start:end] or [values[min(start, len(values) - 1)]]
            scaled.append(max(chunk))
    else:
        scaled = values[:]
        if len(scaled) < width:
            scaled.extend([scaled[-1]] * (width - len(scaled)))

    max_v = max(values)
    min_v = min(values)
    span = max(max_v - min_v, 1e-9)

    for h in range(height, -1, -1):
        line = ""
        for v in scaled:
            level = int((v - min_v) / span * height)
            line += "█" if level >= h else " "
        console.print(line)

    console.print(f"[dim]min={min_v:.2f} avg={mean(values):.2f} max={max_v:.2f}[/dim]")


def choose_metrics() -> list[str]:
    console.print(
        Panel(
            """
[cyan]1[/cyan] CPU
[green]2[/green] Network request
[yellow]3[/yellow] Network response
[magenta]4[/magenta] Disk
[blue]5[/blue] RAM

пример: 135
""",
            title="Выбор метрик",
            border_style="blue",
        )
    )

    raw = input("> ").strip()
    mapping = {
        "1": "cpu",
        "2": "network_request",
        "3": "network_response",
        "4": "disk",
        "5": "ram",
    }

    keys: list[str] = []
    for c in raw:
        if c in mapping:
            key = mapping[c]
            if key not in keys:
                keys.append(key)

    return keys or ["cpu"]


def choose_period_hours() -> Optional[int]:
    return 24


def build_old_range_iso_z(hours: int) -> tuple[str, str]:
    date_to = datetime.now(timezone.utc) - timedelta(minutes=5)
    date_from = date_to - timedelta(hours=hours)

    def fmt(dt: datetime) -> str:
        dt = dt.replace(microsecond=0)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    return fmt(date_from), fmt(date_to)


def build_new_time_from(hours: int) -> str:
    dt = datetime.now(MOSCOW_TZ) - timedelta(hours=hours)
    return (
        f"{WEEKDAYS[dt.weekday()]} {MONTHS[dt.month - 1]} {dt.day:02d} {dt.year} "
        f"{dt.strftime('%H:%M:%S')} GMT+0300 (Москва, стандартное время)"
    )


def first_numeric_value(item: dict[str, Any], preferred_keys: tuple[str, ...] = ()) -> Optional[float]:
    for key in preferred_keys:
        if key not in item:
            continue
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass

    for value in item.values():
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass

    return None


def metric_values(metric: str, series: Any) -> list[float]:
    if not isinstance(series, list) or not series:
        return []

    values: list[float] = []

    for item in series:
        if isinstance(item, (int, float)):
            values.append(float(item))
            continue

        if not isinstance(item, dict):
            continue

        if metric == "disk":
            read_v = item.get("read")
            write_v = item.get("write")
            total = 0.0
            found = False

            if isinstance(read_v, (int, float)):
                total += float(read_v)
                found = True
            if isinstance(write_v, (int, float)):
                total += float(write_v)
                found = True

            if found:
                values.append(total)
            continue

        if metric == "ram":
            used_v = item.get("used")
            total_v = item.get("total")
            if isinstance(used_v, (int, float)) and isinstance(total_v, (int, float)) and float(total_v) > 0:
                values.append(float(used_v) / float(total_v) * 100.0)
            elif isinstance(used_v, (int, float)):
                values.append(float(used_v))
            continue

        if metric == "cpu":
            v = first_numeric_value(item, ("value",))
            if v is not None:
                values.append(v)
            continue

        if metric in {"network_request", "network_response"}:
            v = first_numeric_value(item, ("value",))
            if v is not None:
                values.append(v)
            continue

    return values


def extract_new_series(payload: dict[str, Any], api_key: str) -> list[Any]:
    if not isinstance(payload, dict):
        return []

    statistics = payload.get("statistics")
    if isinstance(statistics, list):
        for metric in statistics:
            if isinstance(metric, dict) and metric.get("name") == api_key:
                lst = metric.get("list")
                if isinstance(lst, list):
                    return lst
        return []

    candidates = [api_key, api_key.replace(".", "_"), api_key.split(".")[-1]]
    for k in candidates:
        v = payload.get(k)
        if isinstance(v, list):
            return v

    for v in payload.values():
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            for vv in v.values():
                if isinstance(vv, list):
                    return vv

    return []


def sort_series_by_time(series: list[Any]) -> list[Any]:
    if not series or not isinstance(series, list) or not isinstance(series[0], dict):
        return series

    for tkey in ("time", "logged_at"):
        if tkey in series[0]:
            try:
                return sorted(series, key=lambda x: x.get(tkey))
            except Exception:
                return series
    return series


def extract_old_series(payload: dict[str, Any], key: str) -> list[Any]:
    if not isinstance(payload, dict):
        return []
    node = payload.get(key)
    if not isinstance(node, dict):
        return []
    series = node.get("statistic", [])
    return series if isinstance(series, list) else []


def _peak_info(metric: str, series: list[Any]) -> str | None:
    if not series:
        return None
    values = metric_values(metric, series)
    if not values:
        return None
    idx = max(range(len(values)), key=lambda i: values[i])
    item = series[idx] if idx < len(series) else None
    if isinstance(item, dict):
        ts = item.get("time") or item.get("logged_at")
        if ts:
            return f"peak at {ts}"
    return None


def fetch_and_show_metrics(client: Client, sid: int, hours: int, selected: list[str]) -> None:
    need_old = any(METRICS[m]["source"] == "old" for m in selected)
    old_payload: dict[str, Any] | None = None
    if need_old:
        date_from, date_to = build_old_range_iso_z(hours)
        if DEBUG_STATS:
            console.print(f"[dim]OLD fetch (ram/disk) date_from={date_from} date_to={date_to}[/dim]")
        old_payload = client.stats_old(sid, date_from, date_to)

    new_keys = [METRICS[m]["api_key"] for m in selected if METRICS[m]["source"] == "new"]
    new_payload: dict[str, Any] | None = None
    if new_keys:
        time_from = build_new_time_from(hours)
        keys_str = ";".join(new_keys)
        if DEBUG_STATS:
            console.print(f"[dim]NEW fetch keys={keys_str} hours={hours}[/dim]")
        new_payload = client.stats_new_multi(sid, time_from, hours, keys_str)

    for metric in selected:
        meta = METRICS[metric]

        try:
            if meta["source"] == "old":
                payload = old_payload or {}
                series = sort_series_by_time(extract_old_series(payload, meta["old_key"]))
                show_stats_metric(metric, series)
                continue

            if meta["source"] == "new":
                payload = new_payload or {}
                series = sort_series_by_time(extract_new_series(payload, meta["api_key"]))
                show_stats_metric(metric, series)
                continue

            console.print(Panel(f"Неизвестный source для метрики: {metric}", border_style="red"))

        except ApiError as e:
            console.print(Panel(f"Ошибка в метрике {meta['label']}:\n{e.status}: {e.message}", border_style="red"))


def show_stats_metric(metric: str, series: list[Any]) -> None:
    label = METRICS[metric]["label"]
    values = metric_values(metric, series)

    console.print(Panel(label, border_style="magenta"))

    if not values:
        console.print("[yellow]Нет данных[/yellow]")
        return

    if metric == "ram":
        console.print("[dim]RAM показан в процентах used/total[/dim]")
    elif metric == "disk":
        console.print("[dim]Disk = read + write[/dim]")

    peak = _peak_info(metric, series)
    if peak:
        console.print(f"[dim]{peak}[/dim]")

    draw_graph(values)


def server_menu(client: Client, srv: dict[str, Any]) -> None:
    while True:
        console.print(
            Panel(
                """
[cyan]1[/cyan] Обновить
[green]2[/green] Запуск
[yellow]3[/yellow] Остановка
[blue]4[/blue] Перезагрузка
[magenta]5[/magenta] Метрики
[red]6[/red] Hard reboot
[red]7[/red] Hard shutdown
[white]0[/white] Назад к списку серверов
""",
                border_style="blue",
            )
        )

        choice = input("> ").strip()

        try:
            sid = int(srv["id"])

            if choice == "1":
                srv = client.server(sid)
                show_server(srv)

            elif choice == "2":
                if Confirm.ask("Старт?"):
                    client.start(sid)

            elif choice == "3":
                if Confirm.ask("Стоп?"):
                    client.stop(sid)

            elif choice == "4":
                if Confirm.ask("Ребут?"):
                    client.reboot(sid)

            elif choice == "5":
                hours = choose_period_hours()
                if not hours:
                    console.print(Panel("Неверный период", border_style="red"))
                    continue

                selected = choose_metrics()
                fetch_and_show_metrics(client, sid, hours, selected)

            elif choice == "6":
                if Confirm.ask("Hard reboot?"):
                    client.hard_reboot(sid)

            elif choice == "7":
                if Confirm.ask("Hard shutdown?"):
                    client.hard_shutdown(sid)

            elif choice == "0":
                return

        except ApiError as e:
            console.print(Panel(f"Ошибка {e.status}: {e.message}", border_style="red"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    global DEBUG_STATS
    DEBUG_STATS = args.debug

    token = args.token or os.getenv("TIMEWEB_CLOUD_TOKEN")
    if not token:
        token = ask_token()

    client = Client(token)

    banner()

    while True:
        try:
            servers = client.servers()
            if not servers:
                console.print(Panel("Список серверов пуст", border_style="red"))
                return

            show_servers(servers)

            choice = ask("Выберите сервер (номер) или 0 для выхода")
            if choice == "0":
                return

            try:
                idx = int(choice) - 1
            except ValueError:
                console.print(Panel("Неверный номер сервера", border_style="red"))
                continue

            if idx < 0 or idx >= len(servers):
                console.print(Panel("Неверный номер сервера", border_style="red"))
                continue

            srv = client.server(int(servers[idx]["id"]))
            show_server(srv)
            server_menu(client, srv)

        except ApiError as e:
            console.print(Panel(f"Ошибка {e.status}: {e.message}", border_style="red"))
            return


if __name__ == "__main__":
    main()