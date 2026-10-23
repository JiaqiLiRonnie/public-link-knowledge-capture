# 分享收件箱（inbox）· 可选模块

> **用途**：把抓取到的公开链接汇总成一个可浏览的看板（网页 + CSV + Excel），避免"转发了但没看"。
> 这是 `public-link-knowledge-capture` 的**可选配套**——不装也不影响抓取本身。

## 它解决什么

用户随手转发一堆链接（公众号 / 抖音 / 小红书 / X / 网页），散在各处；收件箱把它们**汇总成一张表 + 一个网页**，随时扫一眼，不遗漏。

## 组成

| 文件 | 作用 |
|---|---|
| **`inbox_add.py`** | **入库统一入口**：校验 source/status、按 URL 合并去重、原子写入、自动重建看板。**优先用它，别手写 JSON** |
| **`inbox_retry.py`** | 列出抓取失败 / 需浏览器的条目；`--run` 逐条重抓（抖音除外） |
| `build_inbox.py` | 合并三个来源 → 生成 `inbox.csv` / `inbox.xlsx` / `inbox.html` |
| `inbox_template.html` | 看板模板（暖白纸底 + teal 强调 + 卡片式，深浅色可切） |
| `refresh_inbox.sh` | 一键刷新（给 cron 调用） |

## 数据来源（三合一，按 URL 去重）

1. **知识包索引** `<PUBLIC_LINK_KNOWLEDGE_DIR>/index.jsonl` —— 每次 capture 自动追加
2. **手工补录** `<数据目录>/inbox_extra.jsonl` —— 抓到了但没建包、或用户发的是截图/tips
3. **待办台账** `<数据目录>/pending-reviews.md` —— 只有口令、缺链接的条目

`inbox_extra.jsonl` 优先级最高（中文标题、摘要、热度可人工补齐）。

## 用法

```bash
# 1) 入库一条（推荐：自动校验 + 去重 + 重建看板）
python3 inbox_add.py \
  --title "标题" --url "https://…" --source 公众号 \
  --author "作者" --type 文章 --status 已抓取 \
  --summary "2-5 句要点" --tags "标签1,标签2"

# 2) 看有哪些失败了，需要重抓
python3 inbox_retry.py            # 只列出
python3 inbox_retry.py --run      # 逐条重试（抖音除外）

# 3) 手动重建看板（inbox_add.py 已自动做，一般不需要）
python3 build_inbox.py

# 4) 定时或手动刷新；需要指定 Python 时设置 PYTHON
PYTHON=python3 ./refresh_inbox.sh

# 5) 起本地网页看板（可选）
python3 -m http.server 8787 --bind 127.0.0.1 --directory ~/.public-link-knowledge/inbox
# 打开 http://127.0.0.1:8787/inbox.html
```

`inbox_retry.py --run` 使用 `PUBLIC_LINK_PROXY`，或沿用进程已有的 `https_proxy` / `HTTPS_PROXY`；不预设某个本机代理地址。

## 字段说明

| 字段 | 取值 |
|---|---|
| `source` | 抖音 / 公众号 / 网页 / 小红书 / X |
| `type` | 视频 / 图文 / 文章 / Skill / 工具-开源 / 信息 |
| `status` | **已抓取**（拿到正文）/ **部分抓取**（只有标题描述）/ **待补链接**（只有分享口令）/ **提示词-要点**（截图或 tips） |
| `stats` | 热度，如 `赞11692 藏2738 转3015` |
| `summary` | 2–5 句，要求：**不点开原文也知道是什么** |

## 自动化（可选）

- **每晚刷新**：`cronjob` 调 `refresh_inbox.sh`（纯脚本、不耗 LLM）
- **常驻网页**：macOS 可用 launchd 托住 `http.server`，开机自启

## 设计参考

看板的视觉语言借鉴了 [AIHOT](https://github.com/KKKKhazix/AIHOT)：暖白纸底、单一 teal 强调色、发丝边框、极轻阴影、中文排版规范、深浅色双主题、卡片式条目（来源小字 → 大标题 → 灰摘要 → 标签）。

## 注意

- `inbox_extra.jsonl` 含**个人分享历史**，**不要提交到公开仓库**（`.gitignore` 已排除）。
- `inbox.csv/xlsx/html` 是产物，只由脚本生成，不要手改。
