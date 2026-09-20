# Mikan Search Tool v6.2

## 动漫资源搜索工具

[![GPL-3.0 License](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-green.svg)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-purple.svg)](https://www.pyside.org/)

---

## 项目介绍

Mikan Search Tool 是一款功能强大的动漫资源搜索工具，集成蜜柑计划、动漫花园等多种资源源的智能搜索与下载管理于一体。提供暗黑赛博朋克风格的图形界面，支持三种嗅探模式（蜜柑式表格解析、花园式 keepshare 解码、暴力式 Playwright 多进程渲染）、自定义节点扩展、搜索历史与收藏管理、多下载器对接（Aria2/qBittorrent/Transmission）等功能，是动漫资源检索与下载的综合利器。

---

## 功能特性

| 功能模块 | 说明 |
|---------|------|
| 三种嗅探引擎 | 蜜柑式（表格解析）、花园式（keepshare 解码）、暴力式（Playwright 多进程渲染），可自由切换 |
| 自定义节点管理 | 支持添加自定义搜索源节点，灵活扩展资源来源 |
| 关键词高亮 | 搜索结果中关键词黄底高亮显示，快速定位目标 |
| 蜜柑式通用解析 | 自动从标题提取字幕组、分辨率信息，从整行文本智能抠取大小/日期 |
| 花园式磁力解码 | 自动查找 keepshare.org 链接并解码磁力链接，支持去重 |
| 暴力式多进程嗅探 | 基于 Playwright Chromium 渲染页面，多进程并发暴力嗅探 magnet 和 .torrent 链接，支持智能翻页 |
| 下载器对接 | 支持浏览器/系统默认跳转、Aria2 RPC、Aria2 命令行、qBittorrent、Transmission 等多种下载方式 |
| Aria2 自动安装 | 内置 Aria2 一键自动安装功能，检测未安装时可直接下载安装 |
| 下载任务管理 | 实时进度监控、暂停/恢复/删除操作、任务状态轮询 |
| 搜索历史 | 自动记录搜索历史，支持查看、双击跳转、删除、清空 |
| 收藏管理 | 收藏感兴趣的结果，支持发送下载、复制磁力、移除、清空 |
| 多语言支持 | 内置简体中文和 English 两种语言，可自由切换 |
| 依赖自动安装 | 首次运行自动检测缺失依赖，多镜像源（清华/华为/阿里云）自动下载安装，自动安装 Playwright Chromium |
| 暗黑赛博朋克风格 UI | PySide6 构建的深色主题图形界面，自定义样式表 |
| 菜单栏/工具栏 | 支持文件菜单、语言切换、帮助、快捷键（F5 刷新、Ctrl+F 搜索、Ctrl+Q 退出） |

---

## 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.8+ | 编程语言 |
| PySide6 | GUI 框架 |
| requests | HTTP 请求库 |
| BeautifulSoup4 + lxml | HTML 解析 |
| Playwright | 浏览器自动化 / 动态渲染（暴力嗅探模式） |
| multiprocessing | 多进程并发（暴力嗅探） |
| threading + queue | 多线程并发 |
| JSON | 配置持久化（节点/历史/收藏/设置） |
| pathlib | 路径管理 |
| psutil | 进程检测（可选依赖） |

---

## 安装与运行

### 环境要求

- Python 3.8+
- Windows / Linux / macOS

### 运行步骤

1. 下载项目文件 `mikan_search.py`
2. 在终端中运行：

```
python mikan_search.py
```

3. 首次运行会自动安装所有依赖（包括 Playwright Chromium 浏览器驱动）
4. 配置文件目录 `config/` 自动生成，包含 `custom_nodes.json`、`history.json`、`favorites.json`、`downloaders_config.json`、`ui_settings.json`

### 注意事项

- 首次运行需联网以自动安装依赖
- Playwright 需下载 Chromium 浏览器驱动（约 150MB），请确保网络畅通
- 暴力嗅探模式需要 Playwright 已安装并配置 Chromium
- Aria2 功能需要系统已安装 Aria2（可通过内置一键安装功能安装）
- 建议合理设置暴力嗅探的最大页数和并发数，避免对目标网站造成过大压力
- 杀毒软件可能误报，可将程序加入白名单
- 配置文件可手动编辑以调整参数

---

## 项目结构

```
MikanSearchTool/
|-- mikan_search.py          # 主程序（单文件，包含所有逻辑）
|-- config/                  # 配置文件目录
|   |-- custom_nodes.json    # 自定义搜索源节点配置
|   |-- history.json         # 搜索历史记录
|   |-- favorites.json       # 收藏记录
|   |-- downloaders_config.json # 下载器配置
|   |-- ui_settings.json     # UI 设置
|   |-- lang.json            # 语言设置
```

---

## 模块说明

| 类/模块 | 功能说明 |
|---------|---------|
| Translator | 多语言翻译管理器，支持简体中文/English 切换 |
| SnifferBase | 嗅探器基类，封装会话、日志、URL 构建等公共逻辑 |
| MikanSniffer | 蜜柑式嗅探器，解析搜索结果表格，提取标题/大小/磁力/种子/字幕组/分辨率 |
| GardenSniffer | 花园式嗅探器，查找 keepshare.org 链接并解码磁力链接，支持去重 |
| BruteSniffer | 暴力式嗅探器，基于 Playwright Chromium 渲染页面，多进程并发嗅探 magnet 和 .torrent |
| _brute_worker | 暴力嗅探工作进程函数，独立 Chromium 实例执行页面抓取与链接提取 |
| CustomNodeManager | 自定义节点管理器，线程安全的 JSON 配置 CRUD 操作 |
| HistoryManager | 搜索历史管理器，记录搜索历史并支持查询/删除/清空 |
| FavoriteManager | 收藏管理器，支持添加/移除/查询收藏结果 |
| DownloaderConfig | 下载器配置管理器，管理 Aria2/qBittorrent/Transmission 等配置 |
| Aria2Installer | Aria2 自动安装器，检测系统并自动下载安装 Aria2 |
| LinkSender | 链接发送器，支持向多种下载器（浏览器/Aria2/qBit/Transmission）发送任务 |
| Aria2ProgressPoller | Aria2 进度轮询器，定时获取 Aria2 任务下载进度 |
| SearchEngine | 搜索引擎，编排搜索流程，管理源列表与嗅探器实例 |
| SearchWorker | 搜索工作线程，执行异步搜索并返回结果 |
| Aria2InstallWorker | Aria2 安装工作线程 |
| Aria2Poller | Aria2 轮询工作线程 |
| SearchTab | 搜索标签页 UI，包含源选择、关键词输入、结果表格、翻页控制 |
| HistoryTab | 历史记录标签页 UI |
| FavoriteTab | 收藏标签页 UI |
| NodesTab | 自定义节点标签页 UI，支持增删改查和启用/禁用 |
| DownloadsTab | 下载管理标签页 UI，显示 Aria2 任务进度 |
| SettingsTab | 设置标签页 UI，配置下载路径、Aria2 设置等 |
| DownloaderDialog | 发送到下载器对话框，选择目标下载器 |
| NodeEditDialog | 编辑节点对话框 |
| HelpDialog | 帮助对话框 |
| MainWindow | 主窗口 UI，完整的 PySide6 图形界面（含菜单栏/工具栏/状态栏） |

---

## 开发指南

### 代码风格

- 遵循 PEP 8 规范
- 使用中文注释
- 单文件架构，按功能区块用注释分隔（【1】~【26】）

### 添加自定义搜索源

在「🌐 节点」标签页中通过图形界面添加自定义节点，或手动编辑 `config/custom_nodes.json` 文件。每个节点需配置名称、基础 URL、搜索 URL 和嗅探器类型。

### 扩展嗅探器

继承 `SnifferBase` 类并实现 `sniff()` 方法，可在 `create_sniffer()` 函数中注册新的嗅探器类型。

### 扩展下载器支持

在 `LinkSender` 类中添加新的下载器检测与发送方法，并在 `DownloadsTab` 和 `SettingsTab` 中增加对应的 UI 支持。

---

## 许可证

本项目采用 [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0) 许可证开源。

---

## 致谢

本项目由 **DeepSeek AI** 辅助开发完成。
