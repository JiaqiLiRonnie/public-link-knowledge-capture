#!/usr/bin/env python3
"""把用户发来的文档（docx/pdf/txt/md）转成 md 存档并入库。

用法：
  python3 ingest_doc.py <文件路径> --agent codex [--channel manual] [--title "标题"]
  python3 ingest_doc.py <已下载文件> --url <链接> --agent codex [--title ...]

产物：
  ~/.public-link-knowledge/public-links/document/<hash>-<slug>/
      original.<ext>   原件（不转码，原样保存）
      article.md       转换后的 markdown
      meta.json        元数据
  追加 index.jsonl（platform=document）
  自动调用 inbox_add.py 入库
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys
from datetime import datetime, timezone, timedelta

ROOT = os.environ.get("PUBLIC_LINK_KNOWLEDGE_DIR") or os.path.expanduser(
    "~/.public-link-knowledge/public-links")
PLATFORM = "document"
INBOX_ADD = os.environ.get("PUBLIC_LINK_INBOX_ADD") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "inbox", "inbox_add.py")
CST = timezone(timedelta(hours=8))

DOC_EXTS = {".docx", ".doc", ".pdf", ".txt", ".md", ".rtf", ".odt", ".pptx", ".xlsx"}
CONVERTIBLE = {".docx", ".doc", ".odt", ".rtf", ".pptx"}   # pandoc 能转的


def slugify(text, limit=32):
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "-", (text or "").strip())
    text = re.sub(r"-+", "-", text).strip("-")
    return (text[:limit] or "doc")


def convert_to_md(src, dst_md):
    ext = os.path.splitext(src)[1].lower()
    if ext == ".md":
        shutil.copyfile(src, dst_md)
        return "copied"
    if ext in CONVERTIBLE:
        r = subprocess.run(
            ["pandoc", src, "-f", ext.lstrip("."), "-t", "gfm",
             f"--extract-media={os.path.dirname(dst_md)}/assets",
             "-o", dst_md, "--wrap=none"],
            capture_output=True, text=True)
        if r.returncode == 0:
            return "pandoc"
        return f"pandoc-failed: {r.stderr.strip()[:200]}"
    if ext == ".pdf":
        try:
            import fitz  # pymupdf
            doc = fitz.open(src)
            txt = "\n\n".join(p.get_text() for p in doc)
            doc.close()
            open(dst_md, "w", encoding="utf-8").write(txt)
            return "pymupdf"
        except Exception as e:
            pdftotext = shutil.which("pdftotext")
            if not pdftotext:
                return f"pdf-failed: {e}"
            r = subprocess.run([pdftotext, "-layout", "-enc", "UTF-8", src, dst_md],
                               capture_output=True, text=True)
            if r.returncode == 0 and os.path.getsize(dst_md) > 0:
                return "pdftotext"
            return f"pdf-failed: {r.stderr.strip()[:200] or e}"
    if ext == ".xlsx":
        try:
            import openpyxl
            wb = openpyxl.load_workbook(src, data_only=True)
            out = []
            for ws in wb.worksheets:
                out.append(f"## {ws.title}\n")
                for row in ws.iter_rows(values_only=True):
                    cells = ["" if c is None else str(c) for c in row]
                    if any(cells):
                        out.append("| " + " | ".join(cells) + " |")
                out.append("")
            open(dst_md, "w", encoding="utf-8").write("\n".join(out))
            return "openpyxl"
        except Exception as e:
            return f"xlsx-failed: {e}"
    # 兜底：按文本读
    try:
        open(dst_md, "w", encoding="utf-8").write(
            open(src, encoding="utf-8", errors="replace").read())
        return "text-fallback"
    except Exception as e:
        return f"failed: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--title", default="")
    ap.add_argument("--author", default="")
    ap.add_argument("--source", default="手工")
    ap.add_argument("--url", default="", help="原始链接（如果文档来自某个网页）")
    ap.add_argument("--no-inbox", action="store_true", help="只存档，不入收件箱")
    ap.add_argument("--agent", default=os.environ.get("PUBLIC_LINK_AGENT", ""),
                    help="谁在入库（入收件箱必填）：hermes/cc/codex/agy/grok/grokbot/muse/user")
    ap.add_argument("--channel", default=os.environ.get("PUBLIC_LINK_CHANNEL", ""),
                    help="来源渠道：wechat/manual/test/cron")
    a = ap.parse_args()
    if not a.no_inbox:
        if not os.path.isfile(INBOX_ADD):
            ap.error("inbox_add.py 不存在，请设置 PUBLIC_LINK_INBOX_ADD，或使用 --no-inbox")
        sys.path.insert(0, os.path.dirname(os.path.abspath(INBOX_ADD)))
        from inbox_add import AGENTS, AGENT_ALIASES
        a.agent = AGENT_ALIASES.get(a.agent.strip().lower(), a.agent.strip().lower())
        if a.agent not in AGENTS:
            ap.error("入收件箱必须指定有效 --agent（或 PUBLIC_LINK_AGENT）：" + "/".join(AGENTS))

    src = os.path.expanduser(a.file)
    if not os.path.isfile(src):
        sys.exit(f"文件不存在: {src}")

    ext = os.path.splitext(src)[1].lower()
    if ext not in DOC_EXTS:
        print(f"⚠️ 未识别的扩展名 {ext}，仍尝试处理", file=sys.stderr)

    title = a.title or os.path.splitext(os.path.basename(src))[0]
    digest = hashlib.sha1(src.encode() + str(os.path.getsize(src)).encode()).hexdigest()[:12]
    pkg_dir = os.path.join(ROOT, PLATFORM, f"{digest}-{slugify(title)}")
    os.makedirs(pkg_dir, exist_ok=True)

    # 1) 原件原样保存（改名但内容不动）
    original = os.path.join(pkg_dir, f"original{ext}")
    if not os.path.exists(original):
        shutil.copy2(src, original)

    # 2) 转 md
    md_path = os.path.join(pkg_dir, "article.md")
    method = convert_to_md(original, md_path)
    body = open(md_path, encoding="utf-8", errors="replace").read() if os.path.exists(md_path) else ""
    if not body.strip():
        sys.exit(f"⚠️ 转换结果为空（{method}），请检查原文件")

    # 3) 元数据
    now = datetime.now(CST).isoformat(timespec="seconds")
    meta = {"title": title, "author": a.author, "source": a.source,
            "url": a.url, "original_file": original, "markdown": md_path,
            "convert_method": method, "size_bytes": os.path.getsize(original),
            "converted_at": now}
    open(os.path.join(pkg_dir, "meta.json"), "w", encoding="utf-8").write(
        json.dumps(meta, ensure_ascii=False, indent=2))

    # 4) index.jsonl
    rec = {"url": a.url or f"file://{original}", "resolved_url": a.url or "",
           "platform": PLATFORM, "title": title, "author": a.author,
           "capture_status": "extracted", "package": pkg_dir, "captured_at": now}
    with open(os.path.join(ROOT, "index.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"✅ 存档完成\n  原件: {original}\n  正文: {md_path}（{len(body)} 字符，{method}）\n  知识包: {pkg_dir}")

    # 5) 入收件箱
    if not a.no_inbox and os.path.exists(INBOX_ADD):
        excerpt = re.sub(r"\s+", " ", body)[:400]
        cmd = [sys.executable, INBOX_ADD,
               "--title", title, "--source", a.source[:20],
               "--type", "文档", "--status", "已抓取",
               "--summary", excerpt]
        if a.agent:
            cmd += ["--agent", a.agent]
        if a.channel:
            cmd += ["--channel", a.channel]
        # 始终带 url：无外部链接时用 file:// 原件路径，和 index.jsonl 里的记录同键，
        # 否则看板会出现「index 一行 + extra 一行」的重复条目。
        cmd += ["--url", a.url or f"file://{original}"]
        if a.author:
            cmd += ["--author", a.author]
        r = subprocess.run(cmd, capture_output=True, text=True)
        print("📥 入库:", (r.stdout or r.stderr).strip()[:200])
        if r.returncode:
            sys.exit(r.returncode)


if __name__ == "__main__":
    main()
