# GitHub 热门工作台

每日自动获取 GitHub Trending Top 10，入库并（后续）用 LLM 从 README 提炼中文简介。

## 第一步：数据库

已完成 SQLite 表 `trending_repos` 与初始化脚本。

### 初始化

```bash
# 建议先建虚拟环境（可选，本步无第三方依赖）
python -m venv .venv
# Windows:
.venv\Scripts\activate

# 在项目根目录执行
python -m app.db
```

成功会打印：`SQLite ready: ...\data\workbench.db`

### 表字段

| 字段 | 说明 |
|------|------|
| date | 榜单日期 YYYY-MM-DD |
| rank | 排名 1–10 |
| full_name | owner/repo |
| url | 仓库地址 |
| stars | 星数 |
| github_desc | GitHub 短描述 |
| readme_excerpt | README 截断（第二步后） |
| summary_zh | 中文提炼（第三步后） |
| fetched_at | 抓取时间 |

唯一约束：`(date, rank)`、`(date, full_name)`，同一天可重复跑脚本覆盖更新。

## 后续步骤

2. 拉取 Trending Top10 入库  
3. README + LLM 摘要  
4. FastAPI + 列表页  
5. 云服务器 cron 部署  
