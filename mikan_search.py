#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mikan Search Tool - GUI 版 v6.2
单文件整合版：依赖自动安装 + 三种嗅探器 + 下载管理 + 自定义节点 + 历史 + 收藏
v6.2: 关键词高亮 + 蜜柑式通用解析
"""

import os
import sys
import io
import re
import json
import time
import queue
import shutil
import base64
import zipfile
import tarfile
import socket
import platform
import subprocess
import multiprocessing
import webbrowser
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime
from threading import Thread, Lock
from urllib.parse import urljoin, urlparse, quote, unquote
from typing import Optional, List, Dict, Tuple, Callable, Any

# ============================================================
# 【1】依赖自动检测 + 安装
# ============================================================
PIP_MIRRORS = [
    "https://pypi.tuna.tsinghua.edu.cn/simple/",
    "https://repo.huaweicloud.com/repository/pypi/simple/",
    "https://mirrors.aliyun.com/pypi/simple/",
]

REQUIRED_PACKAGES = {
    "PySide6": "PySide6",
    "requests": "requests",
    "bs4": "beautifulsoup4",
    "lxml": "lxml",
    "playwright": "playwright",
}


def _install_pkg(pkg, mirror):
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg, "-i", mirror, "--quiet"],
            capture_output=True
        )
        return r.returncode == 0
    except Exception:
        return False


def ensure_deps():
    missing = []
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)

    if not missing:
        return

    print("\n" + "=" * 60)
    print(f"📦 检测到缺失依赖: {', '.join(missing)}")
    print("=" * 60)
    print("正在自动安装（多镜像源，失败重试）...\n")

    for pkg in missing:
        installed = False
        for mirror in PIP_MIRRORS:
            print(f"  ⬇️  {pkg}  ←  {mirror}")
            if _install_pkg(pkg, mirror):
                print(f"  ✅ {pkg} 安装成功")
                installed = True
                break
        if not installed:
            print(f"  ❌ {pkg} 安装失败，请手动执行: pip install {pkg}")
            input("\n按回车键退出...")
            sys.exit(1)

    print("\n🌐 正在安装 Playwright 浏览器驱动（Chromium）...")
    print("   这一步会下载约 150MB，请耐心等待")
    try:
        os.environ["PLAYWRIGHT_DOWNLOAD_HOST"] = "https://registry.npmmirror.com/-/binary/playwright"
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=False
        )
        print("  ✅ Chromium 安装完成")
    except Exception as e:
        print(f"  ⚠️ Chromium 安装失败: {e}")

    print("\n" + "=" * 60)
    print("✅ 所有依赖安装完成，正在重启...")
    print("=" * 60 + "\n")
    time.sleep(1)
    os.execv(sys.executable, [sys.executable] + sys.argv)


ensure_deps()

# ============================================================
# 【2】正式导入
# ============================================================
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QComboBox,
    QSpinBox, QCheckBox, QFileDialog, QMessageBox, QDialog, QDialogButtonBox,
    QTabWidget, QSplitter, QFrame, QGroupBox, QMenu, QStatusBar, QToolBar,
    QFormLayout, QScrollArea, QAbstractItemView, QSystemTrayIcon, QRadioButton,
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QTimer, QSize, QMetaObject, Q_ARG, Slot,
)
from PySide6.QtGui import (
    QFont, QColor, QAction, QIcon, QPixmap, QPainter, QTextCursor,
)

import requests
from bs4 import BeautifulSoup

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="ignore")
            sys.stderr.reconfigure(encoding="utf-8", errors="ignore")
        except Exception:
            pass
    os.environ["PYTHONIOENCODING"] = "utf-8"


# ============================================================
# 【3】常量与配置
# ============================================================
BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

CUSTOM_NODES_FILE = CONFIG_DIR / "custom_nodes.json"
HISTORY_FILE = CONFIG_DIR / "history.json"
FAVORITES_FILE = CONFIG_DIR / "favorites.json"
DOWNLOADERS_CONFIG_FILE = CONFIG_DIR / "downloaders_config.json"
UI_SETTINGS_FILE = CONFIG_DIR / "ui_settings.json"

APP_VERSION = "6.2"
APP_NAME = "Mikan Search Tool"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BUILTIN_SOURCES = {
    "mikan": {
        "name": "蜜柑计划",
        "base_url": "https://mikanani.kas.pub",
        "search_url": "https://mikanani.kas.pub/Home/Search?searchstr={keyword}",
        "sniffer_type": "mikan",
        "desc": "资源丰富，推荐使用",
        "is_builtin": True,
    },
    "anime_garden": {
        "name": "动漫花园",
        "base_url": "https://animes.garden",
        "search_url": "https://animes.garden/resources/1?search={keyword}",
        "sniffer_type": "garden",
        "desc": "更新速度快",
        "is_builtin": True,
    },
}

SNIFFER_TYPES = {
    "mikan": {"label": "蜜柑式（表格解析）", "desc": "解析搜索结果表格，提取标题/大小/磁力/种子"},
    "garden": {"label": "花园式（keepshare 解码）", "desc": "找 keepshare.org 链接并解码磁力"},
    "brute": {"label": "暴力式（Playwright 多进程）", "desc": "用 Chromium 渲染页面，暴力嗅探 magnet 和 .torrent"},
}

DOWNLOADER_BROWSER = "browser"
DOWNLOADER_SYSTEM = "system_default"
DOWNLOADER_ARIA2_RPC = "aria2_rpc"
DOWNLOADER_ARIA2_CMD = "aria2_cmd"
DOWNLOADER_QBITTORRENT = "qbittorrent"
DOWNLOADER_TRANSMISSION = "transmission"

PAGE_SIZE_DEFAULT = 20
ARIA2_POLL_INTERVAL = 2000

LANGUAGES = {
    "zh_CN": {
        "name": "简体中文",
        "app_title": "Mikan 搜索工具 v{}",
        "tab_search": "🔍 搜索",
        "tab_history": "📜 历史",
        "tab_favorite": "⭐ 收藏",
        "tab_nodes": "🌐 节点",
        "tab_downloads": "📥 下载",
        "tab_settings": "⚙️ 设置",
        "search_placeholder": "输入关键词搜索...",
        "btn_search": "搜索",
        "btn_searching": "搜索中...",
        "btn_prev_page": "← 上一页",
        "btn_next_page": "下一页 →",
        "page_info": "第 {}/{} 页",
        "status_ready": "就绪",
        "status_searching": "正在搜索...",
        "status_found": "找到 {} 个结果",
        "status_no_result": "未找到结果",
        "status_error": "搜索失败: {}",
        "col_index": "#",
        "col_title": "标题",
        "col_size": "大小",
        "col_date": "日期",
        "col_subgroup": "字幕组",
        "col_resolution": "分辨率",
        "col_hash": "Hash",
        "col_source": "来源",
        "btn_copy_magnet": "📋 复制磁力",
        "btn_download_torrent": "💾 下载种子",
        "btn_send_to": "📤 发送到下载器",
        "btn_add_favorite": "⭐ 收藏",
        "btn_remove_favorite": "取消收藏",
        "menu_language": "🌐 语言",
        "menu_help": "❓ 帮助",
        "msg_select_first": "请先选择一个结果",
        "msg_no_magnet": "该结果没有磁力链接",
        "msg_no_torrent": "该结果没有种子链接",
        "msg_copied": "已复制到剪贴板",
        "msg_warning": "提示",
        "msg_error": "错误",
        "msg_success": "成功",
        "msg_confirm_delete": "确定要删除吗？",
    },
    "en_US": {
        "name": "English",
        "app_title": "Mikan Search Tool v{}",
        "tab_search": "🔍 Search",
        "tab_history": "📜 History",
        "tab_favorite": "⭐ Favorites",
        "tab_nodes": "🌐 Nodes",
        "tab_downloads": "📥 Downloads",
        "tab_settings": "⚙️ Settings",
        "search_placeholder": "Enter keyword...",
        "btn_search": "Search",
        "btn_searching": "Searching...",
        "btn_prev_page": "← Prev",
        "btn_next_page": "Next →",
        "page_info": "Page {}/{}",
        "status_ready": "Ready",
        "status_searching": "Searching...",
        "status_found": "Found {} results",
        "status_no_result": "No results",
        "status_error": "Search failed: {}",
        "col_index": "#",
        "col_title": "Title",
        "col_size": "Size",
        "col_date": "Date",
        "col_subgroup": "Group",
        "col_resolution": "Res",
        "col_hash": "Hash",
        "col_source": "Source",
        "btn_copy_magnet": "📋 Copy Magnet",
        "btn_download_torrent": "💾 Get Torrent",
        "btn_send_to": "📤 Send",
        "btn_add_favorite": "⭐ Favorite",
        "btn_remove_favorite": "Unfavorite",
        "menu_language": "🌐 Language",
        "menu_help": "❓ Help",
        "msg_select_first": "Please select a result",
        "msg_no_magnet": "No magnet link",
        "msg_no_torrent": "No torrent link",
        "msg_copied": "Copied",
        "msg_warning": "Warning",
        "msg_error": "Error",
        "msg_success": "Success",
        "msg_confirm_delete": "Are you sure?",
    },
}


class Translator:
    _instance = None
    _lang = "zh_CN"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def set_language(self, lang):
        if lang in LANGUAGES:
            self._lang = lang
            try:
                with open(CONFIG_DIR / "lang.json", "w", encoding="utf-8") as f:
                    json.dump({"language": lang}, f)
            except Exception:
                pass

    def get_language(self):
        return self._lang

    def tr(self, key, *args):
        text = LANGUAGES.get(self._lang, {}).get(key, key)
        if args:
            try:
                return text.format(*args)
            except Exception:
                return text
        return text


def tr(key, *args):
    return Translator().tr(key, *args)


# ============================================================
# 【4】工具函数
# ============================================================
def load_json_safe(file_path: Path, default: Any) -> Any:
    if not file_path.exists():
        return json.loads(json.dumps(default))
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        try:
            backup = file_path.with_suffix(file_path.suffix + ".broken")
            shutil.copy2(file_path, backup)
            print(f"⚠️ 配置文件损坏，已备份到 {backup}")
        except Exception:
            pass
        return json.loads(json.dumps(default))


def save_json_safe(file_path: Path, data: Any) -> bool:
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"⚠️ 保存失败 {file_path}: {e}")
        return False


def merge_defaults(data: dict, defaults: dict) -> dict:
    for k, v in defaults.items():
        if k not in data:
            data[k] = v
        elif isinstance(v, dict) and isinstance(data.get(k), dict):
            data[k] = merge_defaults(data[k], v)
    return data


def format_size(size_bytes) -> str:
    try:
        size_bytes = float(size_bytes)
    except Exception:
        return "0 B"
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.1f} {units[i]}"


def format_speed(speed_bytes) -> str:
    return format_size(speed_bytes) + "/s" if speed_bytes else "0 B/s"


def extract_hash(magnet: str) -> str:
    if not magnet:
        return ""
    m = re.search(r"btih:([a-fA-F0-9]{40})", magnet, re.I)
    if m:
        h = m.group(1)
        return f"{h[:8]}...{h[-8:]}"
    return ""


def make_result(title="", size="未知", date="未知", magnet="", torrent_url="",
                subgroup="未知", resolution="未知", keyword="", source="", url="") -> dict:
    return {
        "title": title.strip() if title else "",
        "size": size or "未知",
        "date": date or "未知",
        "magnet": magnet or "",
        "torrent_url": torrent_url or "",
        "subgroup": subgroup or "未知",
        "resolution": resolution or "未知",
        "keyword": keyword or "",
        "source": source or "",
        "url": url or "",
    }


# ============================================================
# 【5】嗅探器
# ============================================================
class SnifferBase:
    def __init__(self, node: dict, log_func: Optional[Callable] = None):
        self.node = node
        self.log_func = log_func or (lambda msg: None)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })

    def log(self, msg):
        try:
            self.log_func(msg)
        except Exception:
            pass

    def sniff(self, keyword: str) -> List[dict]:
        raise NotImplementedError

    def build_search_url(self, keyword: str) -> str:
        template = self.node.get("search_url", "")
        if not template:
            base = self.node.get("base_url", "")
            return base + quote(keyword)
        if "{keyword}" in template:
            return template.replace("{keyword}", quote(keyword))
        return template + quote(keyword)


class MikanSniffer(SnifferBase):
    def sniff(self, keyword: str) -> List[dict]:
        url = self.build_search_url(keyword)
        self.log(f"🍊 [蜜柑式] 请求: {url}")
        try:
            resp = self.session.get(url, timeout=30, allow_redirects=True)
            if resp.status_code != 200:
                self.log(f"❌ HTTP {resp.status_code}")
                return []
            resp.encoding = "utf-8"
            html = resp.text
        except Exception as e:
            self.log(f"❌ 请求失败: {e}")
            return []
        return self._parse(html, keyword)

    # ★ 本次改动：通用解析（从标题抠字幕组/分辨率，从整行文本抠大小/日期）
    def _parse(self, html: str, keyword: str) -> List[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        rows = soup.select("tr.js-search-results-row")
        if not rows:
            rows = soup.select("table tr")
        base_url = self.node.get("base_url", "")

        for idx, row in enumerate(rows, 1):
            try:
                title_elem = row.select_one("a.magnet-link-wrap")
                if not title_elem:
                    title_elem = row.select_one('a[href^="/Home/Episode/"]')
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                if not title:
                    continue
                title = re.sub(r"\s+", " ", title).strip()

                # 字幕组：[...] 里的第一个
                subgroup = "未知"
                m = re.match(r'^\s*\[([^\]]{1,40})\]', title)
                if m:
                    subgroup = m.group(1).strip()

                # 分辨率
                resolution = "未知"
                m = re.search(r'\b(2160p|1440p|1080p|720p|480p|4[Kk])\b', title)
                if m:
                    resolution = m.group(1)

                # 大小：从整行文本扫
                size = "未知"
                row_text = row.get_text(" ", strip=True)
                m = re.search(r'\b(\d+(?:\.\d+)?)\s*(GB|MB|KB|TB)\b', row_text, re.I)
                if m:
                    size = f"{m.group(1)} {m.group(2).upper()}"

                # 日期：先完整日期，再月-日
                date = "未知"
                m = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', row_text)
                if m:
                    date = m.group(1)
                else:
                    m = re.search(r'\b(\d{1,2}[-/]\d{1,2})\b', row_text)
                    if m:
                        date = m.group(1)

                # 磁力
                magnet = ""
                magnet_elem = row.select_one("a.js-magnet.magnet-link")
                if magnet_elem and magnet_elem.has_attr("href"):
                    href = magnet_elem["href"]
                    if href.startswith("magnet:"):
                        magnet = href
                if not magnet:
                    for elem in row.select('[onclick*="magnet"]'):
                        onclick = elem.get("onclick", "")
                        mm = re.search(r"'(magnet:[^']+)'", onclick)
                        if mm:
                            magnet = mm.group(1)
                            break
                if not magnet:
                    mm = re.search(r"magnet:\?xt=urn:btih:[a-fA-F0-9]{40}[^\s\"'<>]*", str(row), re.I)
                    if mm:
                        magnet = mm.group(0)

                # 种子
                torrent_url = ""
                torrent_elem = row.select_one("a.js-download.torrent-download")
                if torrent_elem and torrent_elem.has_attr("href"):
                    torrent_url = urljoin(base_url, torrent_elem["href"])

                # 详情页
                detail_url = ""
                if title_elem.has_attr("href"):
                    detail_url = urljoin(base_url, title_elem["href"])

                results.append(make_result(
                    title=title, size=size, date=date, magnet=magnet,
                    torrent_url=torrent_url, subgroup=subgroup,
                    resolution=resolution, keyword=keyword,
                    source=self.node.get("name", "custom_mikan"),
                    url=detail_url,
                ))
            except Exception:
                continue

        self.log(f"🍊 [蜜柑式] 解析到 {len(results)} 条")
        return results


class GardenSniffer(SnifferBase):
    def sniff(self, keyword: str) -> List[dict]:
        url = self.build_search_url(keyword)
        self.log(f"🌸 [花园式] 请求: {url}")
        try:
            resp = self.session.get(url, timeout=30, allow_redirects=True)
            if resp.status_code != 200:
                self.log(f"❌ HTTP {resp.status_code}")
                return []
            resp.encoding = "utf-8"
            html = resp.text
        except Exception as e:
            self.log(f"❌ 请求失败: {e}")
            return []
        return self._parse(html, keyword)

    def _parse(self, html: str, keyword: str) -> List[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        keepshare_links = soup.find_all("a", href=re.compile(r"keepshare\.org"))

        for idx, link in enumerate(keepshare_links, 1):
            try:
                href = link.get("href", "")
                magnet = ""
                if "magnet%3A" in href or "magnet:" in href:
                    decoded = unquote(href)
                    m = re.search(r"(magnet:\?xt=urn:btih:[a-zA-Z0-9]+)", decoded, re.I)
                    if m:
                        magnet = m.group(1)
                if not magnet:
                    continue

                title = ""
                parent = link.find_parent()
                container = None
                temp = link
                for _ in range(8):
                    temp = temp.parent
                    if not temp:
                        break
                    if len(temp.find_all("a")) >= 2:
                        container = temp
                        break

                if container:
                    title_link = container.find("a", href=re.compile(r"share\.dmhy\.org/topics/view/\d+"))
                    if title_link:
                        title = title_link.get_text(strip=True)
                    if not title:
                        title_link = container.find("a", class_=re.compile(r"text-link"))
                        if title_link:
                            title = title_link.get_text(strip=True)
                    if not title:
                        for text_elem in container.find_all(["span", "div", "a"]):
                            text = text_elem.get_text(strip=True)
                            if 20 < len(text) < 300 and "keepshare" not in text.lower():
                                title = text
                                break

                if not title:
                    title = link.get_text(strip=True)
                if not title or len(title) < 3:
                    title = f"{keyword} {idx}"

                title = re.sub(r"\s+", " ", title).strip()[:200]

                container_text = ""
                if container:
                    container_text = container.get_text()
                elif parent:
                    container_text = parent.get_text()

                size = "未知"
                m = re.search(r"([\d.]+)\s*(GB|MB|KB|TiB)", container_text, re.I)
                if m:
                    size = f"{m.group(1)} {m.group(2)}"

                date = "未知"
                m = re.search(r"(\d{4}-\d{2}-\d{2})", container_text)
                if m:
                    date = m.group(1)

                # 花园式也抠一下字幕组/分辨率
                subgroup = "未知"
                m = re.match(r'^\s*\[([^\]]{1,40})\]', title)
                if m:
                    subgroup = m.group(1).strip()
                resolution = "未知"
                m = re.search(r'\b(2160p|1440p|1080p|720p|480p|4[Kk])\b', title)
                if m:
                    resolution = m.group(1)

                results.append(make_result(
                    title=title, size=size, date=date, magnet=magnet,
                    subgroup=subgroup, resolution=resolution,
                    keyword=keyword,
                    source=self.node.get("name", "custom_garden"),
                ))
            except Exception:
                continue

        seen = set()
        unique = []
        for r in results:
            if r["magnet"] not in seen:
                seen.add(r["magnet"])
                unique.append(r)

        self.log(f"🌸 [花园式] 解析到 {len(unique)} 条")
        return unique


def _brute_worker(node: dict, url_queue, result_queue, max_pages: int, worker_id: int):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        result_queue.put(("log", f"❌ Worker {worker_id}: playwright 未安装"))
        result_queue.put(("done", worker_id))
        return

    def log(msg):
        result_queue.put(("log", f"[W{worker_id}] {msg}"))

    def find_next_page(html, base_url):
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")
        for el in soup.select('a[rel="next"]'):
            href = el.get("href")
            if href and not href.startswith(("#", "javascript:", "mailto:")):
                return urljoin(base_url, href)
        for sel in (".next a", ".pagination .next a", ".page-next a",
                    ".pager-next a", "a.next", ".next-page a"):
            for el in soup.select(sel):
                href = el.get("href")
                if href and not href.startswith(("#", "javascript:", "mailto:")):
                    return urljoin(base_url, href)
        patterns = ("下一页", "next", "›", "»", "下页")
        for a in soup.find_all("a", href=True):
            text = a.get_text().strip()
            for pat in patterns:
                if pat.lower() in text.lower():
                    href = a.get("href")
                    if href and not href.startswith(("#", "javascript:", "mailto:")):
                        return urljoin(base_url, href)
        return None

    def extract(html, base_url):
        magnets = set()
        torrents = set()
        for m in re.finditer(r"magnet:\?xt=urn:btih:[a-zA-Z0-9]{32,40}[^\s\"'<>]*", html, re.I):
            magnets.add(m.group(0))
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("magnet:"):
                magnets.add(href)
            elif href.lower().endswith(".torrent"):
                torrents.add(urljoin(base_url, href))
            elif "magnet" in href.lower() and "?" in href:
                decoded = unquote(href)
                m = re.search(r"(magnet:\?xt=urn:btih:[a-zA-Z0-9]+)", decoded, re.I)
                if m:
                    magnets.add(m.group(1))
        for el in soup.find_all(attrs={"data-magnet": True}):
            v = el.get("data-magnet", "")
            if v.startswith("magnet:"):
                magnets.add(v)
        for el in soup.find_all(attrs={"data-href": True}):
            v = el.get("data-href", "")
            if v.startswith("magnet:"):
                magnets.add(v)
            elif v.lower().endswith(".torrent"):
                torrents.add(urljoin(base_url, v))
        return list(magnets), list(torrents)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                ]
            )
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                java_script_enabled=True,
                bypass_csp=True,
            )
            page = context.new_page()
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']});
            """)
            pages_done = 0
            while pages_done < max_pages:
                try:
                    url = url_queue.get(timeout=2)
                except Exception:
                    break
                if url is None:
                    break
                log(f"抓取: {url}")
                try:
                    resp = page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    if not resp or resp.status >= 400:
                        log(f"❌ HTTP {resp.status if resp else 'No response'}")
                        continue
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                    for _ in range(2):
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(0.3)
                    html = page.content()
                except Exception as e:
                    log(f"❌ 抓取异常: {e}")
                    continue
                magnets, torrents = extract(html, url)
                log(f"✅ 找到 {len(magnets)} 磁力, {len(torrents)} 种子")
                for m in magnets:
                    result_queue.put(("result", make_result(
                        title=f"[暴力] {m[:70]}",
                        magnet=m,
                        keyword=node.get("_keyword", ""),
                        source=node.get("name", "custom_brute"),
                        url=url,
                    )))
                for t in torrents:
                    result_queue.put(("result", make_result(
                        title=f"[暴力] {Path(urlparse(t).path).name or t[:50]}",
                        torrent_url=t,
                        keyword=node.get("_keyword", ""),
                        source=node.get("name", "custom_brute"),
                        url=url,
                    )))
                next_url = find_next_page(html, url)
                if next_url:
                    url_queue.put(next_url)
                pages_done += 1
            browser.close()
    except Exception as e:
        log(f"❌ Worker 异常: {e}")
    finally:
        result_queue.put(("done", worker_id))


class BruteSniffer(SnifferBase):
    def sniff(self, keyword: str) -> List[dict]:
        search_url = self.build_search_url(keyword)
        self.log(f"🔥 [暴力式] 起始 URL: {search_url}")
        node = dict(self.node)
        node["_keyword"] = keyword
        max_pages = node.get("brute_max_pages", 5)
        concurrency = node.get("brute_concurrency", 3)
        concurrency = max(1, min(int(concurrency), 8))
        self.log(f"🔥 [暴力式] 最大 {max_pages} 页 / {concurrency} 并发")
        url_queue = multiprocessing.Queue()
        result_queue = multiprocessing.Queue()
        url_queue.put(search_url)
        workers = []
        for i in range(concurrency):
            p = multiprocessing.Process(
                target=_brute_worker,
                args=(node, url_queue, result_queue, max_pages, i),
                daemon=True,
            )
            p.start()
            workers.append(p)
        results = []
        workers_done = 0
        start_time = time.time()
        timeout = 300
        while workers_done < concurrency:
            if time.time() - start_time > timeout:
                self.log(f"⚠️ [暴力式] 超时（{timeout}s），强制结束")
                break
            try:
                msg_type, payload = result_queue.get(timeout=1)
            except Exception:
                alive = sum(1 for p in workers if p.is_alive())
                if alive == 0:
                    break
                continue
            if msg_type == "log":
                self.log(payload)
            elif msg_type == "result":
                results.append(payload)
            elif msg_type == "done":
                workers_done += 1
        for p in workers:
            if p.is_alive():
                p.terminate()
            p.join(timeout=2)
        seen = set()
        unique = []
        for r in results:
            key = r.get("magnet") or r.get("torrent_url")
            if key and key not in seen:
                seen.add(key)
                unique.append(r)
        self.log(f"🔥 [暴力式] 完成，共 {len(unique)} 条（去重后）")
        return unique


def create_sniffer(node: dict, log_func=None) -> Optional[SnifferBase]:
    stype = node.get("sniffer_type", "mikan")
    if stype == "mikan":
        return MikanSniffer(node, log_func)
    elif stype == "garden":
        return GardenSniffer(node, log_func)
    elif stype == "brute":
        return BruteSniffer(node, log_func)
    return None


# ==== 接块 2 ====


# ============================================================
# 【6】自定义节点管理
# ============================================================
class CustomNodeManager:
    def __init__(self):
        self.nodes: List[dict] = []
        self.load()

    def load(self):
        data = load_json_safe(CUSTOM_NODES_FILE, {"nodes": []})
        if isinstance(data, list):
            self.nodes = data
        elif isinstance(data, dict):
            self.nodes = data.get("nodes", [])
        else:
            self.nodes = []
        for n in self.nodes:
            if not isinstance(n, dict):
                continue
            merge_defaults(n, {
                "name": "", "sniffer_type": "mikan", "base_url": "",
                "search_url": "", "enabled": True,
                "brute_max_pages": 5, "brute_concurrency": 3,
                "created_at": "",
            })

    def save(self) -> bool:
        return save_json_safe(CUSTOM_NODES_FILE, {"nodes": self.nodes})

    def get_all(self) -> List[dict]:
        return list(self.nodes)

    def get_enabled(self) -> List[dict]:
        return [n for n in self.nodes if n.get("enabled", True)]

    def get(self, name: str) -> Optional[dict]:
        for n in self.nodes:
            if n.get("name") == name:
                return n
        return None

    def add(self, node: dict) -> Tuple[bool, str]:
        name = (node.get("name") or "").strip()
        if not name:
            return False, "节点名称不能为空"
        if self.get(name):
            return False, f"节点 '{name}' 已存在"
        if not node.get("base_url") and not node.get("search_url"):
            return False, "必须填写 base_url 或 search_url"
        node["name"] = name
        node.setdefault("sniffer_type", "mikan")
        node.setdefault("base_url", "")
        node.setdefault("search_url", "")
        node.setdefault("enabled", True)
        node.setdefault("brute_max_pages", 5)
        node.setdefault("brute_concurrency", 3)
        node.setdefault("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.nodes.append(node)
        if self.save():
            return True, "添加成功"
        return False, "保存失败"

    def update(self, old_name: str, new_data: dict) -> Tuple[bool, str]:
        for i, n in enumerate(self.nodes):
            if n.get("name") == old_name:
                new_data.setdefault("created_at", n.get("created_at", ""))
                new_data["name"] = old_name
                self.nodes[i] = new_data
                if self.save():
                    return True, "更新成功"
                return False, "保存失败"
        return False, f"找不到节点 '{old_name}'"

    def delete(self, name: str) -> Tuple[bool, str]:
        before = len(self.nodes)
        self.nodes = [n for n in self.nodes if n.get("name") != name]
        if len(self.nodes) < before:
            if self.save():
                return True, "已删除"
            return False, "保存失败"
        return False, f"找不到节点 '{name}'"

    def toggle_enabled(self, name: str) -> bool:
        for n in self.nodes:
            if n.get("name") == name:
                n["enabled"] = not n.get("enabled", True)
                return self.save()
        return False


# ============================================================
# 【7】下载历史
# ============================================================
HISTORY_MAX_ENTRIES = 500


class HistoryManager:
    def __init__(self):
        self.entries: List[dict] = []
        self.load()

    def load(self):
        data = load_json_safe(HISTORY_FILE, {"entries": []})
        if isinstance(data, dict):
            self.entries = data.get("entries", [])
        elif isinstance(data, list):
            self.entries = data
        else:
            self.entries = []
        for e in self.entries:
            if not isinstance(e, dict):
                continue
            merge_defaults(e, {
                "title": "", "size": "未知", "magnet": "", "torrent_url": "",
                "source": "", "downloader": "", "downloaded_at": "",
            })

    def save(self) -> bool:
        return save_json_safe(HISTORY_FILE, {"entries": self.entries})

    def add(self, result: dict, downloader: str) -> bool:
        entry = {
            "title": result.get("title", ""),
            "size": result.get("size", "未知"),
            "magnet": result.get("magnet", ""),
            "torrent_url": result.get("torrent_url", ""),
            "source": result.get("source", ""),
            "downloader": downloader,
            "downloaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        key = entry["magnet"] or entry["torrent_url"]
        if key:
            self.entries = [e for e in self.entries
                            if (e.get("magnet") or e.get("torrent_url")) != key]
        self.entries.insert(0, entry)
        self.entries = self.entries[:HISTORY_MAX_ENTRIES]
        return self.save()

    def get_all(self) -> List[dict]:
        return list(self.entries)

    def delete(self, index: int) -> bool:
        if 0 <= index < len(self.entries):
            del self.entries[index]
            return self.save()
        return False

    def clear(self) -> bool:
        self.entries = []
        return self.save()


# ============================================================
# 【8】收藏夹
# ============================================================
class FavoriteManager:
    def __init__(self):
        self.entries: List[dict] = []
        self.load()

    def load(self):
        data = load_json_safe(FAVORITES_FILE, {"entries": []})
        if isinstance(data, dict):
            self.entries = data.get("entries", [])
        elif isinstance(data, list):
            self.entries = data
        else:
            self.entries = []
        for e in self.entries:
            if not isinstance(e, dict):
                continue
            merge_defaults(e, {
                "title": "", "size": "未知", "date": "未知", "magnet": "",
                "torrent_url": "", "subgroup": "未知", "resolution": "未知",
                "source": "", "keyword": "", "url": "", "favorited_at": "",
            })

    def save(self) -> bool:
        return save_json_safe(FAVORITES_FILE, {"entries": self.entries})

    def _key(self, entry: dict) -> str:
        return entry.get("magnet") or entry.get("torrent_url") or entry.get("url") or entry.get("title", "")

    def contains(self, result: dict) -> bool:
        key = result.get("magnet") or result.get("torrent_url") or result.get("url") or result.get("title", "")
        if not key:
            return False
        for e in self.entries:
            if self._key(e) == key:
                return True
        return False

    def add(self, result: dict) -> Tuple[bool, str]:
        if self.contains(result):
            return False, "已在收藏夹"
        entry = {
            "title": result.get("title", ""),
            "size": result.get("size", "未知"),
            "date": result.get("date", "未知"),
            "magnet": result.get("magnet", ""),
            "torrent_url": result.get("torrent_url", ""),
            "subgroup": result.get("subgroup", "未知"),
            "resolution": result.get("resolution", "未知"),
            "source": result.get("source", ""),
            "keyword": result.get("keyword", ""),
            "url": result.get("url", ""),
            "favorited_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.entries.insert(0, entry)
        if self.save():
            return True, "已收藏"
        return False, "保存失败"

    def remove(self, result: dict) -> Tuple[bool, str]:
        key = result.get("magnet") or result.get("torrent_url") or result.get("url") or result.get("title", "")
        if not key:
            return False, "无效条目"
        before = len(self.entries)
        self.entries = [e for e in self.entries if self._key(e) != key]
        if len(self.entries) < before:
            if self.save():
                return True, "已取消收藏"
            return False, "保存失败"
        return False, "不在收藏夹"

    def get_all(self) -> List[dict]:
        return list(self.entries)

    def delete_by_index(self, index: int) -> bool:
        if 0 <= index < len(self.entries):
            del self.entries[index]
            return self.save()
        return False

    def clear(self) -> bool:
        self.entries = []
        return self.save()


# ============================================================
# 【9】下载器配置
# ============================================================
DEFAULT_DOWNLOADERS_CONFIG = {
    "download_dir": str(Path.home() / "Downloads" / "Mikan_Downloads"),
    "aria2_rpc": "http://localhost:6800/jsonrpc",
    "aria2_secret": "",
    "qbittorrent_webui": "http://localhost:8080",
    "qbittorrent_user": "admin",
    "qbittorrent_pass": "adminadmin",
    "transmission_rpc": "http://localhost:9091/transmission/rpc",
}

ARIA2_DOWNLOAD_URLS = {
    "Windows": "https://gh-proxy.org/https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip",
    "Linux": "https://gh-proxy.org/https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-linux-gnu-64bit-build1.tar.xz",
    "Darwin": "https://gh-proxy.org/https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-osx-darwin-build1.tar.xz",
}


class DownloaderConfig:
    def __init__(self):
        self.config = self.load()

    def load(self) -> dict:
        data = load_json_safe(DOWNLOADERS_CONFIG_FILE, DEFAULT_DOWNLOADERS_CONFIG)
        if not isinstance(data, dict):
            data = {}
        return merge_defaults(data, DEFAULT_DOWNLOADERS_CONFIG)

    def save(self) -> bool:
        return save_json_safe(DOWNLOADERS_CONFIG_FILE, self.config)

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value):
        self.config[key] = value


# ============================================================
# 【10】Aria2 自动安装
# ============================================================
class Aria2Installer:
    def __init__(self, log_func=None, progress_func=None):
        self.log = log_func or (lambda msg: None)
        self.progress = progress_func or (lambda cur, total: None)

    def check_command(self, cmd: str) -> bool:
        try:
            if platform.system() == "Windows":
                r = subprocess.run(["where", cmd], capture_output=True, timeout=3)
            else:
                r = subprocess.run(["which", cmd], capture_output=True, timeout=3)
            return r.returncode == 0
        except Exception:
            return False

    def find_aria2(self) -> Optional[str]:
        if self.check_command("aria2c"):
            return "aria2c"
        aria2_dir = BASE_DIR / "aria2"
        if platform.system() == "Windows":
            exe = aria2_dir / "aria2c.exe"
        else:
            exe = aria2_dir / "aria2c"
        if exe.exists():
            return str(exe)
        return None

    def install(self) -> Tuple[bool, str]:
        system = platform.system()
        if system not in ARIA2_DOWNLOAD_URLS:
            return False, f"不支持的系统: {system}"
        url = ARIA2_DOWNLOAD_URLS[system]
        self.log(f"📥 下载 Aria2: {url}")
        download_dir = BASE_DIR / "aria2_download"
        download_dir.mkdir(parents=True, exist_ok=True)
        local_file = download_dir / url.split("/")[-1]
        try:
            def _reporthook(block_num, block_size, total_size):
                if total_size > 0:
                    cur = block_num * block_size
                    self.progress(min(cur, total_size), total_size)
            urllib.request.urlretrieve(url, str(local_file), reporthook=_reporthook)
            self.log(f"✅ 下载完成: {local_file.name}")
        except Exception as e:
            return False, f"下载失败: {e}"
        self.log("📦 正在解压...")
        extract_dir = BASE_DIR / "aria2"
        extract_dir.mkdir(parents=True, exist_ok=True)
        try:
            if local_file.suffix == ".zip":
                with zipfile.ZipFile(local_file, "r") as zf:
                    zf.extractall(extract_dir)
            elif ".tar." in local_file.name:
                with tarfile.open(local_file, "r:*") as tf:
                    tf.extractall(extract_dir)
            else:
                return False, f"未知压缩格式: {local_file.suffix}"
            items = list(extract_dir.iterdir())
            dirs = [x for x in items if x.is_dir()]
            if len(dirs) == 1 and len(items) == 1:
                inner = dirs[0]
                for f in inner.iterdir():
                    shutil.move(str(f), str(extract_dir / f.name))
                inner.rmdir()
            self.log(f"✅ 解压完成: {extract_dir}")
        except Exception as e:
            return False, f"解压失败: {e}"
        finally:
            try:
                shutil.rmtree(download_dir)
            except Exception:
                pass
        if system != "Windows":
            exe = extract_dir / "aria2c"
            if exe.exists():
                os.chmod(str(exe), 0o755)
        exe = extract_dir / ("aria2c.exe" if system == "Windows" else "aria2c")
        if not exe.exists():
            return False, "解压后找不到 aria2c"
        self.log(f"✅ Aria2 安装完成: {exe}")
        return True, str(exe)


# ============================================================
# 【11】下载器管理器
# ============================================================
class LinkSender:
    def __init__(self, config: DownloaderConfig, log_func=None):
        self.cfg = config
        self.log = log_func or (lambda msg: None)
        self.aria2_path: Optional[str] = None
        self.aria2_rpc_available = False
        self.downloaders: List[dict] = []

    def detect_aria2(self) -> bool:
        installer = Aria2Installer(log_func=self.log)
        path = installer.find_aria2()
        if path:
            self.aria2_path = path
            return True
        return False

    def detect_aria2_rpc(self) -> bool:
        try:
            payload = {
                "jsonrpc": "2.0", "method": "aria2.getVersion",
                "id": "mikan", "params": [],
            }
            secret = self.cfg.get("aria2_secret", "")
            if secret:
                payload["params"] = [f"token:{secret}"]
            r = requests.post(self.cfg.get("aria2_rpc"), json=payload, timeout=3)
            if r.status_code == 200:
                data = r.json()
                if "result" in data:
                    self.aria2_rpc_available = True
                    return True
        except Exception:
            pass
        self.aria2_rpc_available = False
        return False

    def detect_qbittorrent(self) -> bool:
        try:
            r = requests.get(self.cfg.get("qbittorrent_webui"), timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def detect_transmission(self) -> bool:
        try:
            r = requests.get(
                self.cfg.get("transmission_rpc").replace("/rpc", "/web/"),
                timeout=3
            )
            return r.status_code == 200
        except Exception:
            return False

    def detect_all(self) -> List[dict]:
        self.detect_aria2()
        self.detect_aria2_rpc()
        downloaders = []
        downloaders.append({
            "id": DOWNLOADER_BROWSER, "name": "默认浏览器",
            "desc": "在浏览器中打开链接", "available": True,
        })
        if self.aria2_path:
            downloaders.append({
                "id": DOWNLOADER_ARIA2_RPC, "name": "Aria2 (RPC)",
                "desc": f"RPC: {self.cfg.get('aria2_rpc')}",
                "available": self.aria2_rpc_available,
            })
            downloaders.append({
                "id": DOWNLOADER_ARIA2_CMD, "name": "Aria2 (命令行)",
                "desc": f"可执行: {self.aria2_path}", "available": True,
            })
        else:
            downloaders.append({
                "id": DOWNLOADER_ARIA2_RPC, "name": "Aria2 (未安装)",
                "desc": "点击'设置'可自动安装", "available": False,
            })
        if self.detect_qbittorrent():
            downloaders.append({
                "id": DOWNLOADER_QBITTORRENT, "name": "qBittorrent (WebUI)",
                "desc": self.cfg.get("qbittorrent_webui"), "available": True,
            })
        if self.detect_transmission():
            downloaders.append({
                "id": DOWNLOADER_TRANSMISSION, "name": "Transmission (RPC)",
                "desc": self.cfg.get("transmission_rpc"), "available": True,
            })
        downloaders.append({
            "id": DOWNLOADER_SYSTEM, "name": "系统默认下载器",
            "desc": "用系统关联程序打开链接", "available": True,
        })
        self.downloaders = downloaders
        return downloaders

    def send(self, downloader_id: str, link: str, title: str = "") -> Tuple[bool, str]:
        if downloader_id == DOWNLOADER_BROWSER:
            return self._send_browser(link)
        elif downloader_id == DOWNLOADER_SYSTEM:
            return self._send_system(link)
        elif downloader_id == DOWNLOADER_ARIA2_RPC:
            return self._send_aria2_rpc(link, title)
        elif downloader_id == DOWNLOADER_ARIA2_CMD:
            return self._send_aria2_cmd(link, title)
        elif downloader_id == DOWNLOADER_QBITTORRENT:
            return self._send_qbittorrent(link)
        elif downloader_id == DOWNLOADER_TRANSMISSION:
            return self._send_transmission(link)
        return False, f"未知下载器: {downloader_id}"

    def _send_browser(self, link: str) -> Tuple[bool, str]:
        try:
            webbrowser.open(link)
            return True, "已在浏览器中打开"
        except Exception as e:
            return False, f"打开浏览器失败: {e}"

    def _send_system(self, link: str) -> Tuple[bool, str]:
        try:
            if platform.system() == "Windows":
                os.startfile(link)
            elif platform.system() == "Darwin":
                subprocess.run(["open", link])
            else:
                subprocess.run(["xdg-open", link])
            return True, "已用系统默认程序打开"
        except Exception as e:
            return False, f"打开失败: {e}"

    def _send_aria2_rpc(self, link: str, title: str) -> Tuple[bool, str]:
        if not self.aria2_rpc_available:
            return False, "Aria2 RPC 不可用（请检查设置里的 RPC 地址和密钥）"
        try:
            options = {"dir": self.cfg.get("download_dir", "")}
            if title:
                safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)[:80]
                options["out"] = safe_title
            params = [[link], options]
            secret = self.cfg.get("aria2_secret", "")
            if secret:
                params.insert(0, f"token:{secret}")
            payload = {
                "jsonrpc": "2.0", "id": "mikan",
                "method": "aria2.addUri", "params": params,
            }
            r = requests.post(self.cfg.get("aria2_rpc"), json=payload, timeout=8)
            if r.status_code != 200:
                return False, f"HTTP {r.status_code}\n响应: {r.text[:200]}"
            data = r.json()
            if "result" in data:
                return True, data["result"]
            err = data.get("error", {})
            return False, f"Aria2 错误 [{err.get('code', '')}]: {err.get('message', '未知')}"
        except requests.exceptions.ConnectionError:
            return False, (f"无法连接 Aria2 RPC\n\n"
                           f"地址: {self.cfg.get('aria2_rpc', '')}\n\n"
                           f"请确认:\n1. Aria2 正在运行\n2. RPC 已启用\n3. 端口未被防火墙拦截")
        except requests.exceptions.Timeout:
            return False, "Aria2 RPC 请求超时"
        except Exception as e:
            return False, f"发送失败: {type(e).__name__}: {e}"

    def _send_aria2_cmd(self, link: str, title: str) -> Tuple[bool, str]:
        if not self.aria2_path:
            return False, "aria2c 未找到"
        try:
            download_dir = self.cfg.get("download_dir", "")
            Path(download_dir).mkdir(parents=True, exist_ok=True)
            cmd = [self.aria2_path, f"--dir={download_dir}", "--seed-time=0"]
            if title:
                safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)[:80]
                cmd.append(f"--out={safe_title}")
            cmd.append(link)
            if platform.system() == "Windows":
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(cmd, start_new_session=True)
            return True, "已启动命令行下载"
        except Exception as e:
            return False, f"启动失败: {e}"

    def _send_qbittorrent(self, link: str) -> Tuple[bool, str]:
        try:
            webui = self.cfg.get("qbittorrent_webui", "").rstrip("/")
            if not webui:
                return False, "qBittorrent WebUI 地址未配置"
            session = requests.Session()
            session.headers.update({
                "Referer": webui, "Origin": webui, "User-Agent": USER_AGENT,
            })
            login_url = f"{webui}/api/v2/auth/login"
            login_data = {
                "username": self.cfg.get("qbittorrent_user", "admin"),
                "password": self.cfg.get("qbittorrent_pass", "adminadmin"),
            }
            r = session.post(login_url, data=login_data, timeout=8)
            if r.status_code != 200:
                return False, f"登录请求失败 HTTP {r.status_code}\n响应: {r.text[:200]}"
            body = r.text.strip()
            if "Fails" in body or "fail" in body.lower():
                return False, f"登录失败（用户名或密码错误）\n服务器返回: {body[:200]}"
            add_url = f"{webui}/api/v2/torrents/add"
            add_data = {
                "urls": link,
                "savepath": self.cfg.get("download_dir", ""),
                "category": "", "tags": "",
            }
            r = session.post(add_url, data=add_data, timeout=8)
            if r.status_code == 200:
                return True, "已发送到 qBittorrent"
            elif r.status_code == 415:
                return False, "不支持的种子格式"
            else:
                return False, f"添加失败 HTTP {r.status_code}\n响应: {r.text[:200]}"
        except requests.exceptions.ConnectionError:
            return False, (f"无法连接 qBittorrent\n\n"
                           f"请确认:\n1. qBittorrent 正在运行\n2. WebUI 已启用\n"
                           f"3. 地址正确: {self.cfg.get('qbittorrent_webui', '')}")
        except requests.exceptions.Timeout:
            return False, "qBittorrent 请求超时"
        except Exception as e:
            return False, f"发送失败: {type(e).__name__}: {e}"

    def _send_transmission(self, link: str) -> Tuple[bool, str]:
        try:
            session = requests.Session()
            url = self.cfg.get("transmission_rpc")
            r = session.post(url, timeout=3)
            session_id = r.headers.get("X-Transmission-Session-Id")
            if not session_id:
                return False, "无法获取 Transmission session ID"
            headers = {"X-Transmission-Session-Id": session_id}
            payload = {
                "method": "torrent-add",
                "arguments": {
                    "filename": link, "paused": False,
                    "download-dir": self.cfg.get("download_dir", ""),
                },
            }
            r = session.post(url, json=payload, headers=headers, timeout=5)
            if r.status_code == 200:
                result = r.json()
                if result.get("result") == "success":
                    return True, "已发送到 Transmission"
                return False, f"Transmission 返回: {result.get('result')}"
            return False, f"HTTP {r.status_code}"
        except Exception as e:
            return False, f"发送失败: {e}"


# ============================================================
# 【12】Aria2 进度轮询
# ============================================================
class Aria2ProgressPoller:
    def __init__(self, config: DownloaderConfig):
        self.cfg = config

    def tell_status(self, gid: str) -> Optional[dict]:
        try:
            params = [gid, ["gid", "status", "totalLength", "completedLength",
                            "downloadSpeed", "files", "errorMessage"]]
            secret = self.cfg.get("aria2_secret", "")
            if secret:
                params.insert(0, f"token:{secret}")
            payload = {
                "jsonrpc": "2.0", "id": "mikan",
                "method": "aria2.tellStatus", "params": params,
            }
            r = requests.post(self.cfg.get("aria2_rpc"), json=payload, timeout=3)
            if r.status_code == 200:
                data = r.json()
                if "result" in data:
                    return data["result"]
        except Exception:
            pass
        return None

    def pause(self, gid: str) -> bool:
        return self._simple_call("aria2.pause", gid)

    def unpause(self, gid: str) -> bool:
        return self._simple_call("aria2.unpause", gid)

    def remove(self, gid: str) -> bool:
        return self._simple_call("aria2.remove", gid)

    def _simple_call(self, method: str, gid: str) -> bool:
        try:
            params = [gid]
            secret = self.cfg.get("aria2_secret", "")
            if secret:
                params.insert(0, f"token:{secret}")
            payload = {
                "jsonrpc": "2.0", "id": "mikan",
                "method": method, "params": params,
            }
            r = requests.post(self.cfg.get("aria2_rpc"), json=payload, timeout=3)
            return r.status_code == 200
        except Exception:
            return False


# ============================================================
# 【13】搜索核心
# ============================================================
class SearchEngine:
    def __init__(self, node_manager: CustomNodeManager, log_func=None):
        self.node_manager = node_manager
        self.log = log_func or (lambda msg: None)

    def get_all_sources(self) -> List[dict]:
        sources = []
        for key, src in BUILTIN_SOURCES.items():
            sources.append({
                "id": key, "name": src["name"], "desc": src["desc"],
                "sniffer_type": src["sniffer_type"],
                "base_url": src["base_url"], "search_url": src["search_url"],
                "is_builtin": True, "enabled": True,
            })
        for node in self.node_manager.get_all():
            if not node.get("enabled", True):
                continue
            sources.append({
                "id": f"custom_{node['name']}",
                "name": node["name"],
                "desc": f"自定义 · {SNIFFER_TYPES.get(node.get('sniffer_type', ''), {}).get('label', '')}",
                "sniffer_type": node.get("sniffer_type", "mikan"),
                "base_url": node.get("base_url", ""),
                "search_url": node.get("search_url", ""),
                "is_builtin": False, "enabled": True,
                "raw_node": node,
            })
        return sources

    def get_source_by_id(self, source_id: str) -> Optional[dict]:
        for s in self.get_all_sources():
            if s["id"] == source_id:
                return s
        return None

    def search(self, source_id: str, keyword: str) -> List[dict]:
        source = self.get_source_by_id(source_id)
        if not source:
            self.log(f"❌ 找不到源: {source_id}")
            return []
        self.log(f"🔍 搜索源: {source['name']} | 关键词: {keyword}")
        node = {
            "name": source["name"],
            "base_url": source["base_url"],
            "search_url": source["search_url"],
            "sniffer_type": source["sniffer_type"],
        }
        if "raw_node" in source:
            raw = source["raw_node"]
            node["brute_max_pages"] = raw.get("brute_max_pages", 5)
            node["brute_concurrency"] = raw.get("brute_concurrency", 3)
        sniffer = create_sniffer(node, log_func=self.log)
        if not sniffer:
            self.log(f"❌ 无法创建嗅探器: {source['sniffer_type']}")
            return []
        try:
            results = sniffer.sniff(keyword)
            self.log(f"✅ {source['name']}: {len(results)} 条结果")
            return results
        except Exception as e:
            self.log(f"❌ 搜索异常: {e}")
            return []


# ============================================================
# 【14】后台线程
# ============================================================
class SearchWorker(QThread):
    progress = Signal(str)
    finished_ok = Signal(list)
    finished_err = Signal(str)

    def __init__(self, engine: SearchEngine, source_id: str, keyword: str):
        super().__init__()
        self.engine = engine
        self.source_id = source_id
        self.keyword = keyword

    def run(self):
        try:
            def log_func(msg):
                self.progress.emit(msg)
            tmp_engine = SearchEngine(self.engine.node_manager, log_func=log_func)
            results = tmp_engine.search(self.source_id, self.keyword)
            self.finished_ok.emit(results)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished_err.emit(str(e))


class Aria2InstallWorker(QThread):
    progress = Signal(int, int)
    log = Signal(str)
    finished_ok = Signal(str)
    finished_err = Signal(str)

    def run(self):
        try:
            installer = Aria2Installer(
                log_func=lambda m: self.log.emit(m),
                progress_func=lambda c, t: self.progress.emit(c, t),
            )
            ok, result = installer.install()
            if ok:
                self.finished_ok.emit(result)
            else:
                self.finished_err.emit(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished_err.emit(str(e))


class Aria2Poller(QThread):
    update_tasks = Signal(list)

    def __init__(self, config: DownloaderConfig, poll_interval_ms: int = ARIA2_POLL_INTERVAL):
        super().__init__()
        self.cfg = config
        self.poll_interval_ms = poll_interval_ms
        self._running = True

    def run(self):
        poller = Aria2ProgressPoller(self.cfg)
        while self._running:
            try:
                tasks = self._fetch_all(poller)
                self.update_tasks.emit(tasks)
            except Exception:
                pass
            elapsed = 0
            while elapsed < self.poll_interval_ms and self._running:
                self.msleep(100)
                elapsed += 100

    def _fetch_all(self, poller: Aria2ProgressPoller) -> List[dict]:
        tasks = []
        try:
            params_base = [
                ["gid", "status", "totalLength", "completedLength",
                 "downloadSpeed", "files", "errorMessage", "dir"],
            ]
            secret = self.cfg.get("aria2_secret", "")
            if secret:
                params_base.insert(0, f"token:{secret}")
            for method in ("aria2.tellActive", "aria2.tellWaiting", "aria2.tellStopped"):
                params = list(params_base)
                if method == "aria2.tellStopped":
                    params.append(0)
                    params.append(100)
                elif method == "aria2.tellWaiting":
                    params.append(0)
                    params.append(100)
                payload = {
                    "jsonrpc": "2.0", "id": "mikan",
                    "method": method, "params": params,
                }
                r = requests.post(self.cfg.get("aria2_rpc"), json=payload, timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    items = data.get("result", [])
                    if isinstance(items, list):
                        for it in items:
                            task = self._parse_task(it)
                            if task:
                                tasks.append(task)
        except Exception:
            pass
        return tasks

    def _parse_task(self, item: dict) -> Optional[dict]:
        try:
            total = int(item.get("totalLength", 0) or 0)
            completed = int(item.get("completedLength", 0) or 0)
            speed = int(item.get("downloadSpeed", 0) or 0)
            name = "未知"
            files = item.get("files", [])
            if files:
                path = files[0].get("path", "")
                if path:
                    name = Path(path).name
            if name == "未知":
                name = f"gid_{item.get('gid', '')[:8]}"
            progress = 0
            if total > 0:
                progress = int(completed * 100 / total)
                if progress > 100:
                    progress = 100
            status = item.get("status", "unknown")
            status_map = {
                "active": "下载中", "waiting": "等待中", "paused": "已暂停",
                "complete": "已完成", "error": "错误", "removed": "已移除",
            }
            return {
                "gid": item.get("gid", ""),
                "name": name, "total": total, "completed": completed,
                "progress": progress, "speed": speed,
                "status": status, "status_display": status_map.get(status, status),
                "dir": item.get("dir", ""), "error": item.get("errorMessage", ""),
            }
        except Exception:
            return None

    def stop(self):
        self._running = False
        self.wait(2000)


# ==== 接块 3 ====


# ============================================================
# 【15】UI - 通用工具
# ============================================================
def make_table(headers: List[str], widths: Optional[List[int]] = None) -> QTableWidget:
    """创建标准表格（强制黑底白字）"""
    t = QTableWidget()
    t.setColumnCount(len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setAlternatingRowColors(False)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setStretchLastSection(False)

    if widths:
        for i, w in enumerate(widths):
            t.setColumnWidth(i, w)
        if len(widths) > 1:
            t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
    else:
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    return t


def msg_info(parent, title, text):
    QMessageBox.information(parent, title, text)


def msg_warn(parent, title, text):
    QMessageBox.warning(parent, title, text)


def msg_error(parent, title, text):
    QMessageBox.critical(parent, title, text)


def msg_yesno(parent, title, text) -> bool:
    return QMessageBox.question(
        parent, title, text,
        QMessageBox.Yes | QMessageBox.No
    ) == QMessageBox.Yes


# ============================================================
# 【16】SearchTab（含关键词高亮）
# ============================================================
class SearchTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.engine: SearchEngine = main_window.engine
        self.cfg: DownloaderConfig = main_window.dl_config
        self.history: HistoryManager = main_window.history
        self.favorites: FavoriteManager = main_window.favorites

        self.all_results: List[dict] = []
        self.current_page = 1
        self.page_size = PAGE_SIZE_DEFAULT
        self.worker: Optional[SearchWorker] = None
        self.current_keyword = ""

        self.init_ui()
        self.refresh_sources()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        top = QHBoxLayout()
        top.addWidget(QLabel("源:"))
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(220)
        self.source_combo.setMinimumHeight(32)
        top.addWidget(self.source_combo)
        top.addSpacing(8)
        top.addWidget(QLabel("关键词:"))
        self.keyword_edit = QLineEdit()
        self.keyword_edit.setMinimumHeight(32)
        self.keyword_edit.setPlaceholderText(tr("search_placeholder"))
        self.keyword_edit.returnPressed.connect(self.start_search)
        top.addWidget(self.keyword_edit, 1)
        self.search_btn = QPushButton(tr("btn_search"))
        self.search_btn.setMinimumHeight(32)
        self.search_btn.setMinimumWidth(90)
        self.search_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; border-radius: 6px;"
        )
        self.search_btn.clicked.connect(self.start_search)
        top.addWidget(self.search_btn)
        layout.addLayout(top)

        headers = [
            tr("col_index"), tr("col_title"), tr("col_size"), tr("col_date"),
            tr("col_subgroup"), tr("col_resolution"), tr("col_hash"), tr("col_source"),
        ]
        widths = [50, 400, 90, 110, 100, 100, 130, 120]
        self.table = make_table(headers, widths)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_table_context_menu)
        # 用 cellDoubleClicked（标题列是 QLabel，不是 item）
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        self.table.itemSelectionChanged.connect(self.update_fav_btn)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.prev_btn = QPushButton(tr("btn_prev_page"))
        self.prev_btn.setMinimumHeight(30)
        self.prev_btn.clicked.connect(self.prev_page)
        bottom.addWidget(self.prev_btn)
        self.page_label = QLabel(tr("page_info", 1, 1))
        self.page_label.setMinimumWidth(120)
        self.page_label.setAlignment(Qt.AlignCenter)
        bottom.addWidget(self.page_label)
        self.next_btn = QPushButton(tr("btn_next_page"))
        self.next_btn.setMinimumHeight(30)
        self.next_btn.clicked.connect(self.next_page)
        bottom.addWidget(self.next_btn)
        bottom.addSpacing(20)
        self.copy_btn = QPushButton(tr("btn_copy_magnet"))
        self.copy_btn.setMinimumHeight(30)
        self.copy_btn.clicked.connect(self.copy_magnet)
        bottom.addWidget(self.copy_btn)
        self.torrent_btn = QPushButton(tr("btn_download_torrent"))
        self.torrent_btn.setMinimumHeight(30)
        self.torrent_btn.clicked.connect(self.download_torrent)
        bottom.addWidget(self.torrent_btn)
        self.send_btn = QPushButton(tr("btn_send_to"))
        self.send_btn.setMinimumHeight(30)
        self.send_btn.clicked.connect(self.send_to_downloader)
        bottom.addWidget(self.send_btn)
        self.fav_btn = QPushButton(tr("btn_add_favorite"))
        self.fav_btn.setMinimumHeight(30)
        self.fav_btn.clicked.connect(self.toggle_favorite)
        bottom.addWidget(self.fav_btn)
        bottom.addStretch()
        layout.addLayout(bottom)

    # ---------------- 关键词高亮 ----------------
    def _highlight_keyword(self, text: str, keyword: str) -> str:
        """在文本里高亮关键词，返回 HTML 格式"""
        if not text:
            return ""
        # HTML 转义
        safe = (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))
        if not keyword:
            return safe
        safe_kw = (keyword
                   .replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;"))
        try:
            pattern = re.compile(re.escape(safe_kw), re.IGNORECASE)
            highlighted = pattern.sub(
                lambda m: (
                    f'<span style="background-color: #FFD700; '
                    f'color: #000000; font-weight: bold;">'
                    f'{m.group(0)}</span>'
                ),
                safe
            )
            return highlighted
        except Exception:
            return safe

    # ---------------- 源刷新 ----------------
    def refresh_sources(self):
        current = self.source_combo.currentData()
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        for s in self.engine.get_all_sources():
            label = s["name"]
            if not s["is_builtin"]:
                label += " ⭐"
            self.source_combo.addItem(label, s["id"])
        if current:
            idx = self.source_combo.findData(current)
            if idx >= 0:
                self.source_combo.setCurrentIndex(idx)
        self.source_combo.blockSignals(False)

    # ---------------- 搜索 ----------------
    def start_search(self):
        if self.worker and self.worker.isRunning():
            msg_warn(self, tr("msg_warning"), "搜索正在进行中")
            return
        keyword = self.keyword_edit.text().strip()
        if not keyword:
            msg_warn(self, tr("msg_warning"), "请输入关键词")
            return
        source_id = self.source_combo.currentData()
        if not source_id:
            msg_warn(self, tr("msg_warning"), "请选择搜索源")
            return

        self.current_keyword = keyword
        self.table.setRowCount(0)
        self.all_results = []
        self.current_page = 1
        self.search_btn.setEnabled(False)
        self.search_btn.setText(tr("btn_searching"))
        self.mw.status_bar.showMessage(tr("status_searching"))

        self.worker = SearchWorker(self.engine, source_id, keyword)
        self.worker.progress.connect(self.on_search_progress)
        self.worker.finished_ok.connect(self.on_search_ok)
        self.worker.finished_err.connect(self.on_search_err)
        self.worker.start()

    def on_search_progress(self, msg):
        self.mw.log(f"[搜索] {msg}")

    def on_search_ok(self, results):
        self.search_btn.setEnabled(True)
        self.search_btn.setText(tr("btn_search"))
        self.all_results = results
        if not results:
            self.mw.status_bar.showMessage(tr("status_no_result"))
            return
        self.mw.status_bar.showMessage(tr("status_found", len(results)))
        self.render_page()

    def on_search_err(self, err):
        self.search_btn.setEnabled(True)
        self.search_btn.setText(tr("btn_search"))
        self.mw.status_bar.showMessage(tr("status_error", err))
        msg_error(self, tr("msg_error"), f"搜索失败:\n{err}")

    # ---------------- 渲染当前页（含高亮） ----------------
    def render_page(self):
        total = len(self.all_results)
        total_pages = max(1, (total + self.page_size - 1) // self.page_size)
        self.current_page = max(1, min(self.current_page, total_pages))
        start = (self.current_page - 1) * self.page_size
        end = min(start + self.page_size, total)
        page_results = self.all_results[start:end]

        self.table.setRowCount(0)
        for i, r in enumerate(page_results):
            row = self.table.rowCount()
            self.table.insertRow(row)
            hash_str = extract_hash(r.get("magnet", ""))
            title = r.get("title", "")

            # 序号
            item0 = QTableWidgetItem(str(start + i + 1))
            item0.setForeground(QColor("#ffffff"))
            item0.setData(Qt.UserRole, start + i)
            self.table.setItem(row, 0, item0)

            # 标题列：用 QLabel 支持 HTML 高亮
            title_label = QLabel()
            title_label.setTextFormat(Qt.RichText)
            title_label.setText(self._highlight_keyword(title, self.current_keyword))
            title_label.setStyleSheet(
                "color: #ffffff; padding: 4px 6px; background: transparent;"
            )
            title_label.setToolTip(title)
            self.table.setCellWidget(row, 1, title_label)

            # 其他列
            other_cells = [
                r.get("size", "未知"),
                r.get("date", "未知"),
                r.get("subgroup", "未知"),
                r.get("resolution", "未知"),
                hash_str,
                r.get("source", ""),
            ]
            for col_offset, val in enumerate(other_cells, start=2):
                item = QTableWidgetItem(str(val))
                item.setForeground(QColor("#ffffff"))
                self.table.setItem(row, col_offset, item)

        self.page_label.setText(tr("page_info", self.current_page, total_pages))
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < total_pages)
        self.update_fav_btn()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.render_page()

    def next_page(self):
        total = len(self.all_results)
        total_pages = max(1, (total + self.page_size - 1) // self.page_size)
        if self.current_page < total_pages:
            self.current_page += 1
            self.render_page()

    def get_selected_result(self) -> Optional[dict]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        idx_item = self.table.item(row, 0)
        if not idx_item:
            return None
        real_idx = idx_item.data(Qt.UserRole)
        if real_idx is None or real_idx < 0 or real_idx >= len(self.all_results):
            return None
        return self.all_results[real_idx]

    def update_fav_btn(self):
        result = self.get_selected_result()
        if result and self.favorites.contains(result):
            self.fav_btn.setText(tr("btn_remove_favorite"))
        else:
            self.fav_btn.setText(tr("btn_add_favorite"))

    def copy_magnet(self):
        result = self.get_selected_result()
        if not result:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        magnet = result.get("magnet", "")
        if not magnet:
            msg_warn(self, tr("msg_warning"), tr("msg_no_magnet"))
            return
        QApplication.clipboard().setText(magnet)
        self.mw.status_bar.showMessage(tr("msg_copied"))

    def download_torrent(self):
        result = self.get_selected_result()
        if not result:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        torrent_url = result.get("torrent_url", "")
        if not torrent_url:
            msg_warn(self, tr("msg_warning"), tr("msg_no_torrent"))
            return
        default_name = re.sub(r'[<>:"/\\|?*]', "_", result.get("title", "download"))[:80] + ".torrent"
        save_dir = Path(self.cfg.get("download_dir", str(Path.home())))
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / default_name
        referer = result.get("url", "") or "https://mikanani.kas.pub/"
        headers = {
            "User-Agent": USER_AGENT,
            "Referer": referer,
            "Accept": "*/*",
        }
        try:
            r = requests.get(torrent_url, headers=headers, timeout=30)
            if r.status_code != 200:
                msg_error(self, tr("msg_error"),
                          f"下载种子失败\n\nHTTP {r.status_code}\nURL: {torrent_url}")
                return
            if r.content[:1] != b'd':
                msg_error(self, tr("msg_error"),
                          f"返回的不是种子文件\n\n可能是 HTML 错误页\n\nURL: {torrent_url}")
                return
            save_path.write_bytes(r.content)
            self.mw.log(f"✅ 种子已保存: {save_path}")
            self.mw.status_bar.showMessage(f"种子已保存: {save_path.name}")
            msg_info(self, tr("msg_success"), f"种子已保存到:\n{save_path}")
        except Exception as e:
            msg_error(self, tr("msg_error"), f"下载种子失败:\n{type(e).__name__}: {e}")

    def send_to_downloader(self):
        result = self.get_selected_result()
        if not result:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        dlg = DownloaderDialog(self.mw, self.cfg, result, self.mw.sender)
        ret = dlg.exec()
        downloader_id, used_link = dlg.get_choice()
        if downloader_id:
            self.history.add(result, downloader_id)
            self.mw.log(f"📤 发送记录: {downloader_id}")
            if hasattr(self.mw, "history_tab"):
                self.mw.history_tab.refresh()
        if ret == QDialog.Accepted:
            self.mw.status_bar.showMessage(f"✅ 已发送到 {downloader_id}")

    def toggle_favorite(self):
        result = self.get_selected_result()
        if not result:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        if self.favorites.contains(result):
            ok, msg = self.favorites.remove(result)
        else:
            ok, msg = self.favorites.add(result)
        if ok:
            self.mw.status_bar.showMessage(msg)
            self.mw.log(f"⭐ {msg}")
            self.update_fav_btn()
            if hasattr(self.mw, "favorite_tab"):
                self.mw.favorite_tab.refresh()

    def on_cell_double_clicked(self, row, col):
        """双击任何列 → 复制磁力"""
        self.copy_magnet()

    def on_table_context_menu(self, pos):
        menu = QMenu(self)
        act_copy = QAction(tr("btn_copy_magnet"), self)
        act_copy.triggered.connect(self.copy_magnet)
        menu.addAction(act_copy)
        act_torrent = QAction(tr("btn_download_torrent"), self)
        act_torrent.triggered.connect(self.download_torrent)
        menu.addAction(act_torrent)
        menu.addSeparator()
        act_send = QAction(tr("btn_send_to"), self)
        act_send.triggered.connect(self.send_to_downloader)
        menu.addAction(act_send)
        act_fav = QAction(tr("btn_add_favorite"), self)
        act_fav.triggered.connect(self.toggle_favorite)
        menu.addAction(act_fav)
        menu.exec(self.table.viewport().mapToGlobal(pos))


# ============================================================
# 【17】HistoryTab
# ============================================================
class HistoryTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.history: HistoryManager = main_window.history
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        top = QHBoxLayout()
        title = QLabel("📜 下载历史")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        top.addWidget(title)
        top.addStretch()
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setMinimumHeight(30)
        self.refresh_btn.clicked.connect(self.refresh)
        top.addWidget(self.refresh_btn)
        self.clear_btn = QPushButton("🗑️ 清空全部")
        self.clear_btn.setMinimumHeight(30)
        self.clear_btn.setStyleSheet("background-color: #8a4a4a; color: white;")
        self.clear_btn.clicked.connect(self.clear_all)
        top.addWidget(self.clear_btn)
        layout.addLayout(top)

        headers = ["时间", "标题", "大小", "来源", "下载器"]
        widths = [140, 400, 90, 120, 120]
        self.table = make_table(headers, widths)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_context_menu)
        self.table.itemDoubleClicked.connect(self.on_double_clicked)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.count_label = QLabel("共 0 条")
        self.count_label.setStyleSheet("color: #888;")
        bottom.addWidget(self.count_label)
        bottom.addStretch()
        layout.addLayout(bottom)

    def refresh(self):
        entries = self.history.get_all()
        self.table.setRowCount(0)
        for i, e in enumerate(entries):
            row = self.table.rowCount()
            self.table.insertRow(row)
            cells = [
                e.get("downloaded_at", ""),
                e.get("title", ""),
                e.get("size", "未知"),
                e.get("source", ""),
                e.get("downloader", ""),
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setForeground(QColor("#ffffff"))
                if col == 0:
                    item.setData(Qt.UserRole, i)
                self.table.setItem(row, col, item)
        self.count_label.setText(f"共 {len(entries)} 条")

    def get_selected_index(self) -> int:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return -1
        row = rows[0].row()
        item = self.table.item(row, 0)
        if item:
            idx = item.data(Qt.UserRole)
            return idx if idx is not None else -1
        return -1

    def get_selected_entry(self) -> Optional[dict]:
        idx = self.get_selected_index()
        if idx < 0:
            return None
        entries = self.history.get_all()
        if idx < len(entries):
            return entries[idx]
        return None

    def on_double_clicked(self, item):
        self.resend_to_downloader()

    def on_context_menu(self, pos):
        menu = QMenu(self)
        act_resend = QAction("📤 重新发送", self)
        act_resend.triggered.connect(self.resend_to_downloader)
        menu.addAction(act_resend)
        act_copy = QAction("📋 复制磁力", self)
        act_copy.triggered.connect(self.copy_magnet)
        menu.addAction(act_copy)
        menu.addSeparator()
        act_delete = QAction("🗑️ 删除此条", self)
        act_delete.triggered.connect(self.delete_selected)
        menu.addAction(act_delete)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def resend_to_downloader(self):
        entry = self.get_selected_entry()
        if not entry:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        result = make_result(
            title=entry.get("title", ""),
            size=entry.get("size", "未知"),
            magnet=entry.get("magnet", ""),
            torrent_url=entry.get("torrent_url", ""),
            source=entry.get("source", ""),
        )
        dlg = DownloaderDialog(self.mw, self.mw.dl_config, result, self.mw.sender)
        if dlg.exec() == QDialog.Accepted:
            downloader_id, _ = dlg.get_choice()
            if downloader_id:
                self.mw.log(f"📤 重新发送: {downloader_id}")

    def copy_magnet(self):
        entry = self.get_selected_entry()
        if not entry:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        magnet = entry.get("magnet", "")
        if not magnet:
            msg_warn(self, tr("msg_warning"), tr("msg_no_magnet"))
            return
        QApplication.clipboard().setText(magnet)
        self.mw.status_bar.showMessage(tr("msg_copied"))

    def delete_selected(self):
        idx = self.get_selected_index()
        if idx < 0:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        if not msg_yesno(self, tr("msg_warning"), tr("msg_confirm_delete")):
            return
        self.history.delete(idx)
        self.refresh()

    def clear_all(self):
        if not msg_yesno(self, tr("msg_warning"), "确定要清空所有历史吗？"):
            return
        self.history.clear()
        self.refresh()


# ============================================================
# 【18】FavoriteTab
# ============================================================
class FavoriteTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.favorites: FavoriteManager = main_window.favorites
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        top = QHBoxLayout()
        title = QLabel("⭐ 收藏夹")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        top.addWidget(title)
        top.addStretch()
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setMinimumHeight(30)
        self.refresh_btn.clicked.connect(self.refresh)
        top.addWidget(self.refresh_btn)
        self.send_btn = QPushButton("📤 发送选中")
        self.send_btn.setMinimumHeight(30)
        self.send_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.send_btn.clicked.connect(self.send_selected)
        top.addWidget(self.send_btn)
        self.clear_btn = QPushButton("🗑️ 清空全部")
        self.clear_btn.setMinimumHeight(30)
        self.clear_btn.setStyleSheet("background-color: #8a4a4a; color: white;")
        self.clear_btn.clicked.connect(self.clear_all)
        top.addWidget(self.clear_btn)
        layout.addLayout(top)

        headers = [
            tr("col_index"), tr("col_title"), tr("col_size"), tr("col_date"),
            tr("col_subgroup"), tr("col_resolution"), tr("col_hash"), tr("col_source"),
        ]
        widths = [50, 400, 90, 110, 100, 100, 130, 120]
        self.table = make_table(headers, widths)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_context_menu)
        self.table.itemDoubleClicked.connect(self.on_double_clicked)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.count_label = QLabel("共 0 条")
        self.count_label.setStyleSheet("color: #888;")
        bottom.addWidget(self.count_label)
        bottom.addStretch()
        layout.addLayout(bottom)

    def refresh(self):
        entries = self.favorites.get_all()
        self.table.setRowCount(0)
        for i, e in enumerate(entries):
            row = self.table.rowCount()
            self.table.insertRow(row)
            hash_str = extract_hash(e.get("magnet", ""))
            cells = [
                str(i + 1),
                e.get("title", ""),
                e.get("size", "未知"),
                e.get("date", "未知"),
                e.get("subgroup", "未知"),
                e.get("resolution", "未知"),
                hash_str,
                e.get("source", ""),
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setForeground(QColor("#ffffff"))
                if col == 0:
                    item.setData(Qt.UserRole, i)
                self.table.setItem(row, col, item)
        self.count_label.setText(f"共 {len(entries)} 条")

    def get_selected_entry(self) -> Optional[dict]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        item = self.table.item(row, 0)
        if not item:
            return None
        idx = item.data(Qt.UserRole)
        if idx is None:
            return None
        entries = self.favorites.get_all()
        if idx < len(entries):
            return entries[idx]
        return None

    def on_double_clicked(self, item):
        self.send_selected()

    def on_context_menu(self, pos):
        menu = QMenu(self)
        act_send = QAction("📤 发送到下载器", self)
        act_send.triggered.connect(self.send_selected)
        menu.addAction(act_send)
        act_copy = QAction("📋 复制磁力", self)
        act_copy.triggered.connect(self.copy_magnet)
        menu.addAction(act_copy)
        menu.addSeparator()
        act_remove = QAction("❌ 取消收藏", self)
        act_remove.triggered.connect(self.remove_selected)
        menu.addAction(act_remove)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def send_selected(self):
        entry = self.get_selected_entry()
        if not entry:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        result = make_result(
            title=entry.get("title", ""),
            size=entry.get("size", "未知"),
            date=entry.get("date", "未知"),
            magnet=entry.get("magnet", ""),
            torrent_url=entry.get("torrent_url", ""),
            subgroup=entry.get("subgroup", "未知"),
            resolution=entry.get("resolution", "未知"),
            source=entry.get("source", ""),
            url=entry.get("url", ""),
        )
        dlg = DownloaderDialog(self.mw, self.mw.dl_config, result, self.mw.sender)
        if dlg.exec() == QDialog.Accepted:
            downloader_id, _ = dlg.get_choice()
            if downloader_id:
                self.mw.history.add(result, downloader_id)
                self.mw.log(f"📤 已从收藏发送: {downloader_id}")

    def copy_magnet(self):
        entry = self.get_selected_entry()
        if not entry:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        magnet = entry.get("magnet", "")
        if not magnet:
            msg_warn(self, tr("msg_warning"), tr("msg_no_magnet"))
            return
        QApplication.clipboard().setText(magnet)
        self.mw.status_bar.showMessage(tr("msg_copied"))

    def remove_selected(self):
        entry = self.get_selected_entry()
        if not entry:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        if not msg_yesno(self, tr("msg_warning"), "确定要取消收藏吗？"):
            return
        self.favorites.remove(entry)
        self.refresh()
        if hasattr(self.mw, "search_tab"):
            self.mw.search_tab.update_fav_btn()

    def clear_all(self):
        if not msg_yesno(self, tr("msg_warning"), "确定要清空收藏夹吗？"):
            return
        self.favorites.clear()
        self.refresh()
        if hasattr(self.mw, "search_tab"):
            self.mw.search_tab.update_fav_btn()


# ============================================================
# 【19】NodesTab
# ============================================================
class NodesTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.node_manager: CustomNodeManager = main_window.node_manager
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        top = QHBoxLayout()
        title = QLabel("🌐 自定义节点")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        top.addWidget(title)
        top.addStretch()
        self.add_btn = QPushButton("➕ 新建节点")
        self.add_btn.setMinimumHeight(30)
        self.add_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.add_btn.clicked.connect(self.add_node)
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        info = QLabel(
            "💡 自定义节点允许你添加第三方资源站\n"
            "   内置站点（蜜柑计划、动漫花园）不可修改"
        )
        info.setStyleSheet("color: #888; font-size: 11px; padding: 6px; background: #1a1a1a; border-radius: 6px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        headers = ["名称", "嗅探方式", "Base URL", "搜索 URL 模板", "状态"]
        widths = [140, 150, 220, 340, 80]
        self.table = make_table(headers, widths)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_context_menu)
        self.table.itemDoubleClicked.connect(self.edit_node)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.count_label = QLabel("共 0 个节点")
        self.count_label.setStyleSheet("color: #888;")
        bottom.addWidget(self.count_label)
        bottom.addStretch()
        self.edit_btn = QPushButton("✏️ 编辑")
        self.edit_btn.setMinimumHeight(30)
        self.edit_btn.clicked.connect(self.edit_node)
        bottom.addWidget(self.edit_btn)
        self.toggle_btn = QPushButton("✅ 启用/禁用")
        self.toggle_btn.setMinimumHeight(30)
        self.toggle_btn.clicked.connect(self.toggle_enabled)
        bottom.addWidget(self.toggle_btn)
        self.delete_btn = QPushButton("🗑️ 删除")
        self.delete_btn.setMinimumHeight(30)
        self.delete_btn.setStyleSheet("background-color: #8a4a4a; color: white;")
        self.delete_btn.clicked.connect(self.delete_node)
        bottom.addWidget(self.delete_btn)
        layout.addLayout(bottom)

    def refresh(self):
        nodes = self.node_manager.get_all()
        self.table.setRowCount(0)
        for i, n in enumerate(nodes):
            row = self.table.rowCount()
            self.table.insertRow(row)
            sniffer_label = SNIFFER_TYPES.get(n.get("sniffer_type", ""), {}).get("label", n.get("sniffer_type", ""))
            enabled = n.get("enabled", True)
            status = "✅ 启用" if enabled else "❌ 禁用"
            cells = [
                n.get("name", ""),
                sniffer_label,
                n.get("base_url", ""),
                n.get("search_url", ""),
                status,
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setForeground(QColor("#ffffff"))
                if col == 0:
                    item.setData(Qt.UserRole, i)
                if col == 4 and not enabled:
                    item.setForeground(QColor("#888888"))
                self.table.setItem(row, col, item)
        self.count_label.setText(f"共 {len(nodes)} 个节点")

    def get_selected_node(self) -> Optional[dict]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        item = self.table.item(row, 0)
        if not item:
            return None
        idx = item.data(Qt.UserRole)
        if idx is None:
            return None
        nodes = self.node_manager.get_all()
        if idx < len(nodes):
            return nodes[idx]
        return None

    def on_context_menu(self, pos):
        menu = QMenu(self)
        act_edit = QAction("✏️ 编辑", self)
        act_edit.triggered.connect(self.edit_node)
        menu.addAction(act_edit)
        act_toggle = QAction("✅ 启用/禁用", self)
        act_toggle.triggered.connect(self.toggle_enabled)
        menu.addAction(act_toggle)
        menu.addSeparator()
        act_delete = QAction("🗑️ 删除", self)
        act_delete.triggered.connect(self.delete_node)
        menu.addAction(act_delete)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def add_node(self):
        dlg = NodeEditDialog(self.mw)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            ok, msg = self.node_manager.add(data)
            if ok:
                self.mw.log(f"✅ 添加节点: {data['name']}")
                self.refresh()
                if hasattr(self.mw, "search_tab"):
                    self.mw.search_tab.refresh_sources()
            else:
                msg_error(self, tr("msg_error"), msg)

    def edit_node(self):
        node = self.get_selected_node()
        if not node:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        dlg = NodeEditDialog(self.mw, node)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            ok, msg = self.node_manager.update(node["name"], data)
            if ok:
                self.mw.log(f"✅ 更新节点: {node['name']}")
                self.refresh()
                if hasattr(self.mw, "search_tab"):
                    self.mw.search_tab.refresh_sources()
            else:
                msg_error(self, tr("msg_error"), msg)

    def toggle_enabled(self):
        node = self.get_selected_node()
        if not node:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        self.node_manager.toggle_enabled(node["name"])
        self.refresh()
        if hasattr(self.mw, "search_tab"):
            self.mw.search_tab.refresh_sources()

    def delete_node(self):
        node = self.get_selected_node()
        if not node:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        if not msg_yesno(self, tr("msg_warning"), f"确定要删除节点 '{node['name']}' 吗？"):
            return
        self.node_manager.delete(node["name"])
        self.refresh()
        if hasattr(self.mw, "search_tab"):
            self.mw.search_tab.refresh_sources()


# ==== 接块 4 ====


# ============================================================
# 【20】DownloadsTab
# ============================================================
class DownloadsTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.cfg: DownloaderConfig = main_window.dl_config
        self.poller: Optional[Aria2Poller] = None
        self.init_ui()
        self.start_polling()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        top = QHBoxLayout()
        title = QLabel("📥 下载管理 (Aria2)")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        top.addWidget(title)
        top.addStretch()
        self.refresh_btn = QPushButton("🔄 立即刷新")
        self.refresh_btn.setMinimumHeight(30)
        self.refresh_btn.clicked.connect(self.manual_refresh)
        top.addWidget(self.refresh_btn)
        self.auto_label = QLabel("自动刷新: 每 2 秒")
        self.auto_label.setStyleSheet("color: #888; font-size: 11px;")
        top.addWidget(self.auto_label)
        layout.addLayout(top)

        self.info_label = QLabel(
            "💡 只有通过「Aria2 RPC」发送的任务才会显示在这里\n"
            "   使用其他下载器请到对应软件查看进度"
        )
        self.info_label.setStyleSheet("color: #888; font-size: 11px; padding: 6px; background: #1a1a1a; border-radius: 6px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        headers = ["文件名", "大小", "进度", "速度", "状态"]
        widths = [400, 100, 200, 120, 100]
        self.table = make_table(headers, widths)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_context_menu)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.count_label = QLabel("共 0 个任务")
        self.count_label.setStyleSheet("color: #888;")
        bottom.addWidget(self.count_label)
        bottom.addStretch()
        self.pause_btn = QPushButton("⏸️ 暂停")
        self.pause_btn.setMinimumHeight(30)
        self.pause_btn.clicked.connect(self.pause_selected)
        bottom.addWidget(self.pause_btn)
        self.resume_btn = QPushButton("▶️ 继续")
        self.resume_btn.setMinimumHeight(30)
        self.resume_btn.clicked.connect(self.resume_selected)
        bottom.addWidget(self.resume_btn)
        self.remove_btn = QPushButton("🗑️ 移除")
        self.remove_btn.setMinimumHeight(30)
        self.remove_btn.setStyleSheet("background-color: #8a4a4a; color: white;")
        self.remove_btn.clicked.connect(self.remove_selected)
        bottom.addWidget(self.remove_btn)
        layout.addLayout(bottom)

    def start_polling(self):
        self.poller = Aria2Poller(self.cfg, ARIA2_POLL_INTERVAL)
        self.poller.update_tasks.connect(self.on_tasks_update)
        self.poller.start()

    def stop_polling(self):
        if self.poller:
            self.poller.stop()
            self.poller = None

    def manual_refresh(self):
        if not self.poller:
            return
        try:
            poller = Aria2ProgressPoller(self.cfg)
            tasks = self.poller._fetch_all(poller)
            self.on_tasks_update(tasks)
        except Exception as e:
            self.mw.log(f"⚠️ 刷新失败: {e}")

    @Slot(list)
    def on_tasks_update(self, tasks: list):
        selected_gid = None
        rows = self.table.selectionModel().selectedRows()
        if rows:
            item = self.table.item(rows[0].row(), 0)
            if item:
                selected_gid = item.data(Qt.UserRole)

        self.table.setRowCount(0)
        for i, t in enumerate(tasks):
            row = self.table.rowCount()
            self.table.insertRow(row)
            cells = [
                t.get("name", ""),
                format_size(t.get("total", 0)),
                f"{t.get('progress', 0)}%",
                format_speed(t.get("speed", 0)),
                t.get("status_display", ""),
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setForeground(QColor("#ffffff"))
                if col == 0:
                    item.setData(Qt.UserRole, t.get("gid", ""))
                if col == 4:
                    status = t.get("status", "")
                    if status == "active":
                        item.setForeground(QColor("#4CAF50"))
                    elif status == "error":
                        item.setForeground(QColor("#e74c3c"))
                    elif status == "complete":
                        item.setForeground(QColor("#2196F3"))
                self.table.setItem(row, col, item)

            if selected_gid and t.get("gid") == selected_gid:
                self.table.selectRow(row)

        self.count_label.setText(f"共 {len(tasks)} 个任务")

    def get_selected_gid(self) -> Optional[str]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        if item:
            return item.data(Qt.UserRole)
        return None

    def on_context_menu(self, pos):
        menu = QMenu(self)
        act_pause = QAction("⏸️ 暂停", self)
        act_pause.triggered.connect(self.pause_selected)
        menu.addAction(act_pause)
        act_resume = QAction("▶️ 继续", self)
        act_resume.triggered.connect(self.resume_selected)
        menu.addAction(act_resume)
        menu.addSeparator()
        act_remove = QAction("🗑️ 移除", self)
        act_remove.triggered.connect(self.remove_selected)
        menu.addAction(act_remove)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def pause_selected(self):
        gid = self.get_selected_gid()
        if not gid:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        poller = Aria2ProgressPoller(self.cfg)
        if poller.pause(gid):
            self.mw.log(f"⏸️ 已暂停: {gid[:8]}")

    def resume_selected(self):
        gid = self.get_selected_gid()
        if not gid:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        poller = Aria2ProgressPoller(self.cfg)
        if poller.unpause(gid):
            self.mw.log(f"▶️ 已继续: {gid[:8]}")

    def remove_selected(self):
        gid = self.get_selected_gid()
        if not gid:
            msg_warn(self, tr("msg_warning"), tr("msg_select_first"))
            return
        if not msg_yesno(self, tr("msg_warning"), "确定要移除该任务吗？\n（已下载的文件不会删除）"):
            return
        poller = Aria2ProgressPoller(self.cfg)
        if poller.remove(gid):
            self.mw.log(f"🗑️ 已移除: {gid[:8]}")

    def closeEvent(self, event):
        self.stop_polling()
        event.accept()


# ============================================================
# 【21】SettingsTab
# ============================================================
class SettingsTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.cfg: DownloaderConfig = main_window.dl_config
        self.install_worker: Optional[Aria2InstallWorker] = None
        self.init_ui()
        self.load()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("⚙️ 设置")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # 通用
        group1 = QGroupBox("📁 通用")
        form1 = QFormLayout(group1)
        self.download_dir_edit = QLineEdit()
        self.download_dir_edit.setMinimumHeight(30)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.download_dir_edit, 1)
        dir_browse = QPushButton("📂 浏览")
        dir_browse.setMinimumHeight(30)
        dir_browse.clicked.connect(self.browse_download_dir)
        dir_row.addWidget(dir_browse)
        form1.addRow("下载目录:", dir_row)
        layout.addWidget(group1)

        # Aria2
        group2 = QGroupBox("⬇️ Aria2")
        form2 = QFormLayout(group2)
        self.aria2_rpc_edit = QLineEdit()
        self.aria2_rpc_edit.setMinimumHeight(30)
        form2.addRow("RPC 地址:", self.aria2_rpc_edit)
        self.aria2_secret_edit = QLineEdit()
        self.aria2_secret_edit.setMinimumHeight(30)
        self.aria2_secret_edit.setPlaceholderText("留空为无密钥")
        form2.addRow("RPC 密钥:", self.aria2_secret_edit)

        aria2_status_row = QHBoxLayout()
        self.aria2_status_label = QLabel("检测中...")
        self.aria2_status_label.setStyleSheet("color: #888;")
        aria2_status_row.addWidget(self.aria2_status_label, 1)
        self.aria2_install_btn = QPushButton("📥 自动安装 Aria2")
        self.aria2_install_btn.setMinimumHeight(30)
        self.aria2_install_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        self.aria2_install_btn.clicked.connect(self.install_aria2)
        aria2_status_row.addWidget(self.aria2_install_btn)
        form2.addRow("状态:", aria2_status_row)

        self.aria2_progress = QProgressBar()
        self.aria2_progress.setVisible(False)
        form2.addRow("", self.aria2_progress)
        layout.addWidget(group2)

        # qBittorrent
        group3 = QGroupBox("🌊 qBittorrent")
        form3 = QFormLayout(group3)
        self.qb_webui_edit = QLineEdit()
        self.qb_webui_edit.setMinimumHeight(30)
        form3.addRow("WebUI 地址:", self.qb_webui_edit)
        self.qb_user_edit = QLineEdit()
        self.qb_user_edit.setMinimumHeight(30)
        form3.addRow("用户名:", self.qb_user_edit)
        self.qb_pass_edit = QLineEdit()
        self.qb_pass_edit.setMinimumHeight(30)
        self.qb_pass_edit.setEchoMode(QLineEdit.Password)
        form3.addRow("密码:", self.qb_pass_edit)
        layout.addWidget(group3)

        # Transmission
        group4 = QGroupBox("📡 Transmission")
        form4 = QFormLayout(group4)
        self.tr_rpc_edit = QLineEdit()
        self.tr_rpc_edit.setMinimumHeight(30)
        form4.addRow("RPC 地址:", self.tr_rpc_edit)
        layout.addWidget(group4)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.save_btn = QPushButton("💾 保存设置")
        self.save_btn.setMinimumHeight(36)
        self.save_btn.setMinimumWidth(120)
        self.save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; border-radius: 6px;")
        self.save_btn.clicked.connect(self.save)
        btn_row.addWidget(self.save_btn)
        self.reset_btn = QPushButton("🔄 恢复默认")
        self.reset_btn.setMinimumHeight(36)
        self.reset_btn.clicked.connect(self.reset_defaults)
        btn_row.addWidget(self.reset_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

        self.check_aria2_status()

    def load(self):
        self.download_dir_edit.setText(self.cfg.get("download_dir", ""))
        self.aria2_rpc_edit.setText(self.cfg.get("aria2_rpc", ""))
        self.aria2_secret_edit.setText(self.cfg.get("aria2_secret", ""))
        self.qb_webui_edit.setText(self.cfg.get("qbittorrent_webui", ""))
        self.qb_user_edit.setText(self.cfg.get("qbittorrent_user", ""))
        self.qb_pass_edit.setText(self.cfg.get("qbittorrent_pass", ""))
        self.tr_rpc_edit.setText(self.cfg.get("transmission_rpc", ""))

    def save(self):
        self.cfg.set("download_dir", self.download_dir_edit.text().strip())
        self.cfg.set("aria2_rpc", self.aria2_rpc_edit.text().strip())
        self.cfg.set("aria2_secret", self.aria2_secret_edit.text().strip())
        self.cfg.set("qbittorrent_webui", self.qb_webui_edit.text().strip())
        self.cfg.set("qbittorrent_user", self.qb_user_edit.text().strip())
        self.cfg.set("qbittorrent_pass", self.qb_pass_edit.text().strip())
        self.cfg.set("transmission_rpc", self.tr_rpc_edit.text().strip())
        if self.cfg.save():
            self.mw.status_bar.showMessage("✅ 设置已保存")
            self.mw.log("✅ 设置已保存")
            self.mw.sender.detect_all()
        else:
            msg_error(self, tr("msg_error"), "保存失败")

    def reset_defaults(self):
        if not msg_yesno(self, tr("msg_warning"), "确定要恢复默认设置吗？"):
            return
        self.download_dir_edit.setText(DEFAULT_DOWNLOADERS_CONFIG["download_dir"])
        self.aria2_rpc_edit.setText(DEFAULT_DOWNLOADERS_CONFIG["aria2_rpc"])
        self.aria2_secret_edit.setText("")
        self.qb_webui_edit.setText(DEFAULT_DOWNLOADERS_CONFIG["qbittorrent_webui"])
        self.qb_user_edit.setText(DEFAULT_DOWNLOADERS_CONFIG["qbittorrent_user"])
        self.qb_pass_edit.setText(DEFAULT_DOWNLOADERS_CONFIG["qbittorrent_pass"])
        self.tr_rpc_edit.setText(DEFAULT_DOWNLOADERS_CONFIG["transmission_rpc"])

    def browse_download_dir(self):
        folder = QFileDialog.getExistingDirectory(
            self, "选择下载目录", self.download_dir_edit.text() or str(Path.home())
        )
        if folder:
            self.download_dir_edit.setText(folder)

    def check_aria2_status(self):
        installer = Aria2Installer()
        path = installer.find_aria2()
        if path:
            self.aria2_status_label.setText(f"✅ 已安装: {path}")
            self.aria2_status_label.setStyleSheet("color: #6a9a6a;")
            self.aria2_install_btn.setText("🔄 重新安装")
        else:
            self.aria2_status_label.setText("❌ 未安装")
            self.aria2_status_label.setStyleSheet("color: #e74c3c;")
            self.aria2_install_btn.setText("📥 自动安装")

    def install_aria2(self):
        if self.install_worker and self.install_worker.isRunning():
            msg_warn(self, tr("msg_warning"), "安装正在进行中")
            return
        if not msg_yesno(self, tr("msg_warning"),
                         "将自动下载 Aria2（约 5-10MB）\n是否继续？"):
            return
        self.aria2_progress.setVisible(True)
        self.aria2_progress.setRange(0, 100)
        self.aria2_progress.setValue(0)
        self.aria2_install_btn.setEnabled(False)
        self.install_worker = Aria2InstallWorker()
        self.install_worker.progress.connect(self.on_install_progress)
        self.install_worker.log.connect(lambda m: self.mw.log(m))
        self.install_worker.finished_ok.connect(self.on_install_ok)
        self.install_worker.finished_err.connect(self.on_install_err)
        self.install_worker.start()

    def on_install_progress(self, cur, total):
        if total > 0:
            self.aria2_progress.setValue(int(cur * 100 / total))

    def on_install_ok(self, path):
        self.aria2_progress.setVisible(False)
        self.aria2_install_btn.setEnabled(True)
        self.check_aria2_status()
        msg_info(self, tr("msg_success"), f"✅ Aria2 安装成功\n{path}")
        self.mw.sender.detect_all()

    def on_install_err(self, err):
        self.aria2_progress.setVisible(False)
        self.aria2_install_btn.setEnabled(True)
        msg_error(self, tr("msg_error"), f"❌ 安装失败\n{err}")


# ============================================================
# 【22】DownloaderDialog
# ============================================================
class DownloaderDialog(QDialog):
    def __init__(self, parent, cfg: DownloaderConfig, result: dict, sender: LinkSender):
        super().__init__(parent)
        self.cfg = cfg
        self.result = result
        self.sender = sender
        self.selected_downloader: Optional[str] = None
        self.used_link: str = ""
        self.setWindowTitle("📤 发送到下载器")
        self.setMinimumWidth(520)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        info_group = QGroupBox("📄 资源信息")
        info_layout = QVBoxLayout(info_group)
        title_label = QLabel(self.result.get("title", "")[:120])
        title_label.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        title_label.setWordWrap(True)
        info_layout.addWidget(title_label)
        meta = []
        if self.result.get("size", "未知") != "未知":
            meta.append(f"大小: {self.result['size']}")
        if self.result.get("date", "未知") != "未知":
            meta.append(f"日期: {self.result['date']}")
        if self.result.get("resolution", "未知") != "未知":
            meta.append(f"分辨率: {self.result['resolution']}")
        if meta:
            meta_label = QLabel(" | ".join(meta))
            meta_label.setStyleSheet("color: #888; font-size: 11px;")
            info_layout.addWidget(meta_label)
        layout.addWidget(info_group)

        self.link_options = []
        if self.result.get("magnet"):
            self.link_options.append(("magnet", "磁力链接", self.result["magnet"]))
        if self.result.get("torrent_url"):
            self.link_options.append(("torrent", "种子链接", self.result["torrent_url"]))

        if not self.link_options:
            msg_error(self, tr("msg_error"), "该资源没有可用的链接")
            self.reject()
            return

        if len(self.link_options) > 1:
            link_group = QGroupBox("🔗 链接类型")
            link_layout = QVBoxLayout(link_group)
            self.link_combo = QComboBox()
            self.link_combo.setMinimumHeight(30)
            for key, label, _ in self.link_options:
                self.link_combo.addItem(label, key)
            link_layout.addWidget(self.link_combo)
            layout.addWidget(link_group)
        else:
            self.link_combo = None

        downloader_group = QGroupBox("📤 下载器")
        downloader_layout = QVBoxLayout(downloader_group)
        self.downloaders = self.sender.detect_all()

        first_available = True
        for d in self.downloaders:
            row = QHBoxLayout()
            radio = QRadioButton(d["name"])
            radio.setMinimumHeight(28)
            if not d["available"]:
                radio.setEnabled(False)
                radio.setText(f"{d['name']}  (不可用)")
            if d["available"] and first_available:
                self.selected_downloader = d["id"]
                radio.setChecked(True)
                first_available = False
            radio.toggled.connect(
                lambda checked, did=d["id"]: self.on_downloader_selected(checked, did)
            )
            row.addWidget(radio, 1)
            desc = QLabel(d["desc"])
            desc.setStyleSheet("color: #666; font-size: 10px;")
            row.addWidget(desc, 2)
            downloader_layout.addLayout(row)
        layout.addWidget(downloader_group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.send_btn = QPushButton("📤 发送")
        self.send_btn.setMinimumHeight(36)
        self.send_btn.setMinimumWidth(100)
        self.send_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; border-radius: 6px;")
        self.send_btn.clicked.connect(self.do_send)
        btn_layout.addWidget(self.send_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def on_downloader_selected(self, checked, downloader_id):
        if checked:
            self.selected_downloader = downloader_id

    def get_current_link(self) -> str:
        if self.link_combo is not None:
            key = self.link_combo.currentData()
            for k, _, link in self.link_options:
                if k == key:
                    return link
        return self.link_options[0][2]

    def do_send(self):
        if not self.selected_downloader:
            msg_warn(self, tr("msg_warning"), "请选择一个下载器")
            return
        link = self.get_current_link()
        title = self.result.get("title", "")

        if self.selected_downloader in (DOWNLOADER_BROWSER, DOWNLOADER_SYSTEM):
            ok, msg = self.sender.send(self.selected_downloader, link, title)
            if ok:
                self.used_link = link
                self.accept()
            else:
                msg_error(self, tr("msg_error"), msg)
            return

        if self.selected_downloader == DOWNLOADER_ARIA2_RPC:
            ok, msg = self.sender.send(self.selected_downloader, link, title)
            if ok:
                self.used_link = link
                self.accept()
                p = self.parent()
                if hasattr(p, "downloads_tab"):
                    QTimer.singleShot(500, p.downloads_tab.manual_refresh)
            else:
                reply = QMessageBox.question(
                    self, "RPC 不可用",
                    f"Aria2 RPC 连接失败:\n{msg}\n\n是否改用「Aria2 命令行」模式？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    ok2, msg2 = self.sender.send(DOWNLOADER_ARIA2_CMD, link, title)
                    if ok2:
                        self.used_link = link
                        self.accept()
                    else:
                        msg_error(self, tr("msg_error"), msg2)
            return

        ok, msg = self.sender.send(self.selected_downloader, link, title)
        if ok:
            self.used_link = link
            self.accept()
        else:
            msg_error(self, tr("msg_error"), msg)

    def get_choice(self):
        return self.selected_downloader, self.used_link


# ============================================================
# 【23】NodeEditDialog
# ============================================================
class NodeEditDialog(QDialog):
    def __init__(self, parent, node: Optional[dict] = None):
        super().__init__(parent)
        self.node = node
        self.is_edit = node is not None
        self.setWindowTitle("✏️ 编辑节点" if self.is_edit else "➕ 新建节点")
        self.setMinimumWidth(560)
        self.setMinimumHeight(500)
        self.init_ui()
        if self.is_edit:
            self.load_node()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        basic_group = QGroupBox("📋 基本信息")
        form = QFormLayout(basic_group)
        self.name_edit = QLineEdit()
        self.name_edit.setMinimumHeight(30)
        self.name_edit.setPlaceholderText("例如: 某字幕组")
        if self.is_edit:
            self.name_edit.setReadOnly(True)
            self.name_edit.setStyleSheet("color: #888;")
        form.addRow("名称:", self.name_edit)
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setMinimumHeight(30)
        self.base_url_edit.setPlaceholderText("例如: https://example.com")
        form.addRow("Base URL:", self.base_url_edit)
        self.search_url_edit = QLineEdit()
        self.search_url_edit.setMinimumHeight(30)
        self.search_url_edit.setPlaceholderText("例如: https://example.com/search?q={keyword}")
        form.addRow("搜索 URL 模板:", self.search_url_edit)
        hint = QLabel("💡 用 {keyword} 占位符表示关键词的位置")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow("", hint)
        layout.addWidget(basic_group)

        sniffer_group = QGroupBox("🔍 嗅探方式")
        sniffer_layout = QVBoxLayout(sniffer_group)
        self.sniffer_combo = QComboBox()
        self.sniffer_combo.setMinimumHeight(32)
        for key, info in SNIFFER_TYPES.items():
            self.sniffer_combo.addItem(info["label"], key)
        self.sniffer_combo.currentIndexChanged.connect(self.on_sniffer_changed)
        sniffer_layout.addWidget(self.sniffer_combo)
        self.sniffer_desc = QLabel("")
        self.sniffer_desc.setStyleSheet("color: #aaa; font-size: 11px; padding: 6px; background: #1a1a1a; border-radius: 6px;")
        self.sniffer_desc.setWordWrap(True)
        sniffer_layout.addWidget(self.sniffer_desc)

        self.brute_group = QGroupBox("🔥 暴力式参数")
        brute_form = QFormLayout(self.brute_group)
        self.brute_pages_spin = QSpinBox()
        self.brute_pages_spin.setRange(1, 100)
        self.brute_pages_spin.setValue(5)
        self.brute_pages_spin.setMinimumHeight(30)
        brute_form.addRow("最大翻页:", self.brute_pages_spin)
        self.brute_concurrency_spin = QSpinBox()
        self.brute_concurrency_spin.setRange(1, 8)
        self.brute_concurrency_spin.setValue(3)
        self.brute_concurrency_spin.setMinimumHeight(30)
        brute_form.addRow("并发进程数:", self.brute_concurrency_spin)
        brute_hint = QLabel("💡 并发越高越快，但内存占用越大\n   建议 2-4，最大 8")
        brute_hint.setStyleSheet("color: #888; font-size: 10px;")
        brute_form.addRow("", brute_hint)
        self.brute_group.setVisible(False)
        sniffer_layout.addWidget(self.brute_group)
        layout.addWidget(sniffer_group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton("💾 保存")
        save_btn.setMinimumHeight(36)
        save_btn.setMinimumWidth(100)
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; border-radius: 6px;")
        save_btn.clicked.connect(self.do_save)
        btn_layout.addWidget(save_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.on_sniffer_changed()

    def on_sniffer_changed(self):
        key = self.sniffer_combo.currentData()
        info = SNIFFER_TYPES.get(key, {})
        self.sniffer_desc.setText(info.get("desc", ""))
        self.brute_group.setVisible(key == "brute")

    def load_node(self):
        n = self.node
        self.name_edit.setText(n.get("name", ""))
        self.base_url_edit.setText(n.get("base_url", ""))
        self.search_url_edit.setText(n.get("search_url", ""))
        idx = self.sniffer_combo.findData(n.get("sniffer_type", "mikan"))
        if idx >= 0:
            self.sniffer_combo.setCurrentIndex(idx)
        self.brute_pages_spin.setValue(n.get("brute_max_pages", 5))
        self.brute_concurrency_spin.setValue(n.get("brute_concurrency", 3))

    def do_save(self):
        name = self.name_edit.text().strip()
        if not name:
            msg_warn(self, tr("msg_warning"), "请输入节点名称")
            return
        if not self.base_url_edit.text().strip() and not self.search_url_edit.text().strip():
            msg_warn(self, tr("msg_warning"), "请至少填写 Base URL 或搜索 URL")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "base_url": self.base_url_edit.text().strip(),
            "search_url": self.search_url_edit.text().strip(),
            "sniffer_type": self.sniffer_combo.currentData(),
            "brute_max_pages": self.brute_pages_spin.value(),
            "brute_concurrency": self.brute_concurrency_spin.value(),
            "enabled": True,
        }


# ============================================================
# 【24】HelpDialog
# ============================================================
class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("❓ 帮助")
        self.setMinimumSize(600, 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml(f"""
        <h2>Mikan Search Tool v{APP_VERSION}</h2>
        <p>一个动漫资源搜索工具。</p>
        <h3>🔍 搜索</h3>
        <ul>
        <li>选择源 → 输入关键词 → 点击搜索</li>
        <li>搜索到的关键词会<b>黄底高亮</b></li>
        <li><b>双击行</b> = 复制磁力链接</li>
        <li><b>右键</b> = 更多操作</li>
        </ul>
        <h3>📤 发送到下载器</h3>
        <ul>
        <li><b>浏览器 / 系统默认</b>：直接跳转</li>
        <li><b>Aria2 RPC</b>：任务会出现在「📥 下载」标签页</li>
        <li><b>Aria2 命令行</b>：独立窗口下载</li>
        <li><b>qBittorrent / Transmission</b>：通过 WebUI/RPC 发送</li>
        </ul>
        <h3>🌐 自定义节点</h3>
        <ul>
        <li>支持三种嗅探方式：蜜柑式 / 花园式 / 暴力式</li>
        <li>暴力式用 Playwright 渲染页面</li>
        </ul>
        <h3>⚙️ 设置</h3>
        <ul>
        <li>Aria2 若显示「未安装」，可一键自动安装</li>
        </ul>
        """)
        layout.addWidget(text)
        btn = QPushButton("关闭")
        btn.setMinimumHeight(34)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)


# ==== 接块 5 ====


# ============================================================
# 【25】MainWindow
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.node_manager = CustomNodeManager()
        self.history = HistoryManager()
        self.favorites = FavoriteManager()
        self.dl_config = DownloaderConfig()
        self.engine = SearchEngine(self.node_manager, log_func=self.log)
        self.sender = LinkSender(self.dl_config, log_func=self.log)
        self.translator = Translator()
        self.init_ui()
        self.apply_style()
        QTimer.singleShot(500, self._initial_detect)

    def _initial_detect(self):
        self.log("🔍 检测下载器...")
        downloaders = self.sender.detect_all()
        for d in downloaders:
            status = "✅" if d["available"] else "❌"
            self.log(f"  {status} {d['name']}")

    def init_ui(self):
        self.setWindowTitle(tr("app_title", APP_VERSION))
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.search_tab = SearchTab(self)
        self.tabs.addTab(self.search_tab, tr("tab_search"))
        self.downloads_tab = DownloadsTab(self)
        self.tabs.addTab(self.downloads_tab, tr("tab_downloads"))
        self.favorite_tab = FavoriteTab(self)
        self.tabs.addTab(self.favorite_tab, tr("tab_favorite"))
        self.history_tab = HistoryTab(self)
        self.tabs.addTab(self.history_tab, tr("tab_history"))
        self.nodes_tab = NodesTab(self)
        self.tabs.addTab(self.nodes_tab, tr("tab_nodes"))
        self.settings_tab = SettingsTab(self)
        self.tabs.addTab(self.settings_tab, tr("tab_settings"))
        self.tabs.currentChanged.connect(self.on_tab_changed)
        layout.addWidget(self.tabs)

        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件(&F)")
        act_refresh = QAction("🔄 刷新全部", self)
        act_refresh.setShortcut("F5")
        act_refresh.triggered.connect(self.refresh_all)
        file_menu.addAction(act_refresh)
        file_menu.addSeparator()
        act_exit = QAction("退出(&X)", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        lang_menu = menubar.addMenu(tr("menu_language"))
        for code, info in LANGUAGES.items():
            act = QAction(info["name"], self)
            act.setCheckable(True)
            act.setChecked(code == self.translator.get_language())
            act.triggered.connect(lambda checked, c=code: self.change_language(c))
            lang_menu.addAction(act)

        help_menu = menubar.addMenu(tr("menu_help"))
        act_help = QAction("📖 使用帮助", self)
        act_help.triggered.connect(self.show_help)
        help_menu.addAction(act_help)
        act_about = QAction(f"ℹ️ 关于 v{APP_VERSION}", self)
        act_about.triggered.connect(self.show_about)
        help_menu.addAction(act_about)

        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        act_search = QAction("🔍 搜索", self)
        act_search.setShortcut("Ctrl+F")
        act_search.triggered.connect(self.focus_search)
        toolbar.addAction(act_search)
        toolbar.addSeparator()
        act_settings = QAction("⚙️ 设置", self)
        act_settings.triggered.connect(lambda: self.tabs.setCurrentWidget(self.settings_tab))
        toolbar.addAction(act_settings)
        act_help2 = QAction("❓ 帮助", self)
        act_help2.triggered.connect(self.show_help)
        toolbar.addAction(act_help2)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(tr("status_ready"))

    def apply_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1a1a1a;
                color: #e0e0e0;
                font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
                font-size: 13px;
            }
            QMenuBar {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border-bottom: 1px solid #333;
            }
            QMenuBar::item:selected { background-color: #333; }
            QMenu {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #444;
            }
            QMenu::item:selected { background-color: #3a3a3a; }
            QToolBar {
                background-color: #1a1a1a;
                border: none;
                border-bottom: 1px solid #333;
                padding: 4px 8px;
                spacing: 4px;
            }
            QToolButton {
                background-color: transparent;
                color: #e0e0e0;
                border: none;
                padding: 6px 14px;
                border-radius: 4px;
            }
            QToolButton:hover { background-color: #333; }
            QTabWidget::pane {
                background-color: #1a1a1a;
                border: none;
            }
            QTabBar::tab {
                background-color: #1a1a1a;
                color: #aaa;
                padding: 10px 20px;
                border: 1px solid #333;
                border-bottom: none;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                color: #fff;
                background-color: #2b2b2b;
                border-bottom: 2px solid #4CAF50;
            }
            QTabBar::tab:hover:!selected { background-color: #252525; }
            QGroupBox {
                color: #e0e0e0;
                border: 1px solid #333;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                color: #aaa;
            }
            QLabel { color: #e0e0e0; }
            QLineEdit, QSpinBox, QComboBox, QTextEdit {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px 10px;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border-color: #4CAF50;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: #e0e0e0;
                selection-background-color: #3a3a3a;
                border: 1px solid #444;
            }
            QPushButton {
                background-color: #333;
                color: #e0e0e0;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #444; }
            QPushButton:disabled { background-color: #222; color: #666; }
            QRadioButton, QCheckBox { color: #e0e0e0; spacing: 8px; }

            /* ========== 表格：强制黑底白字 ========== */
            QTableWidget {
                background-color: #1e1e1e;
                alternate-background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #333;
                border-radius: 6px;
                gridline-color: #2a2a2a;
                selection-background-color: #0f3460;
            }
            QTableWidget::item {
                background-color: #1e1e1e;
                color: #ffffff;
                padding: 4px 6px;
            }
            QTableWidget::item:alternate {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QTableWidget::item:selected {
                background-color: #0f3460;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #252525;
                color: #aaaaaa;
                border: none;
                border-bottom: 1px solid #333;
                border-right: 1px solid #333;
                padding: 6px 8px;
                font-weight: bold;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #444;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background-color: #555; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                background: none;
                height: 0px;
            }
            QStatusBar {
                background-color: #1a1a1a;
                color: #888;
                border-top: 1px solid #333;
            }
            QProgressBar {
                background-color: #2b2b2b;
                border: 1px solid #444;
                border-radius: 4px;
                text-align: center;
                color: #e0e0e0;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)

    def log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}")

    def on_tab_changed(self, index):
        widget = self.tabs.widget(index)
        if widget is self.favorite_tab:
            widget.refresh()
        elif widget is self.history_tab:
            widget.refresh()
        elif widget is self.nodes_tab:
            widget.refresh()

    def refresh_all(self):
        self.node_manager.load()
        self.history.load()
        self.favorites.load()
        self.dl_config.load()
        self.search_tab.refresh_sources()
        self.favorite_tab.refresh()
        self.history_tab.refresh()
        self.nodes_tab.refresh()
        self.settings_tab.load()
        self.status_bar.showMessage("✅ 已刷新")
        self.log("✅ 已刷新全部")

    def change_language(self, lang_code: str):
        self.translator.set_language(lang_code)
        msg_info(self, "语言", f"已切换到 {LANGUAGES[lang_code]['name']}\n部分文本需重启后生效")

    def show_help(self):
        HelpDialog(self).exec()

    def show_about(self):
        msg_info(self, "关于",
                 f"<b>Mikan Search Tool</b><br>"
                 f"版本: v{APP_VERSION}<br>"
                 f"Python: {sys.version.split()[0]}<br>"
                 f"配置文件: {CONFIG_DIR}")

    def focus_search(self):
        self.tabs.setCurrentWidget(self.search_tab)
        self.search_tab.keyword_edit.setFocus()
        self.search_tab.keyword_edit.selectAll()

    def closeEvent(self, event):
        if hasattr(self, "downloads_tab"):
            self.downloads_tab.stop_polling()
        self.node_manager.save()
        self.history.save()
        self.favorites.save()
        self.dl_config.save()
        event.accept()


# ============================================================
# 【26】main()
# ============================================================
def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    try:
        lang_file = CONFIG_DIR / "lang.json"
        if lang_file.exists():
            with open(lang_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                lang = data.get("language", "zh_CN")
                if lang in LANGUAGES:
                    Translator().set_language(lang)
    except Exception:
        pass
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

# ============================================================
# 【全部结束】 mikan_search.py v6.2
# ============================================================