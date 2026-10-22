#!/bin/bash
# 刷新「分享收件箱」看板（CSV/XLSX/HTML）。每晚由 cron 调用，也可手动跑。
cd ~/.public-link-knowledge/inbox || exit 1
python3 ~/.public-link-knowledge/inbox/build_inbox.py
