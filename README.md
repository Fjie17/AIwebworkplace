# GitHub 热门工作台

每日自动获取 GitHub Trending Top 10，入库并用 LLM 从 README 提炼中文简介。

## 密钥

```bash
copy .env.example .env
```

编辑 `.env`：至少填 `LLM_API_KEY`；推荐填 `GITHUB_TOKEN`。不要把密钥发到聊天或提交 Git。

## 日常命令

```bash
python -m jobs.fetch_trending    # 拉 Top10
python -m jobs.summarize         # README + 中文摘要
python -m jobs.peek_db           # 终端查看数据库
python -m app.web                # 启动 Web 工作台（推荐，无需额外依赖）
```

浏览器打开：http://127.0.0.1:8000

## 如何查看数据库

数据库文件：`data/workbench.db`

| 方式 | 做法 |
|------|------|
| **Web 页面（推荐）** | `python -m app.web` → 打开 http://127.0.0.1:8000 |
| **命令行** | `python -m jobs.peek_db` 或加 `--full` / `--date 2026-10-15` |
| **图形工具** | 用 [DB Browser for SQLite](https://sqlitebrowser.org/) 打开 `data/workbench.db` |
| **JSON API** | http://127.0.0.1:8000/api/trending |

终端里中文可能乱码（Windows GBK），**以网页或 DB Browser 为准**。

## API

| 路径 | 说明 |
|------|------|
| `GET /` | 列表页 |
| `GET /api/trending` | `?date=YYYY-MM-DD` 可选 |
| `GET /api/trending/latest` | 最新一天 |
| `GET /api/dates` | 已有日期 |

## 后续

5. 云服务器 cron / systemd 部署说明  
