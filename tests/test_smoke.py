import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import capture_public_link as capture  # noqa: E402


class CaptureSmokeTests(unittest.TestCase):
    def test_platform_routing(self):
        cases = {
            "https://mp.weixin.qq.com/s/example": "wechat",
            "https://xhslink.cn/o/example": "xiaohongshu",
            "https://www.douyin.com/video/123": "douyin",
            "https://x.com/example/status/123": "x",
            "https://www.reddit.com/r/MachineLearning/comments/123/": "reddit",
            "https://redd.it/123": "reddit",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ": "youtube",
            "https://youtu.be/dQw4w9WgXcQ": "youtube",
            "https://github.com/openai/codex": "github",
            "https://news.ycombinator.com/item?id=123": "hackernews",
            "https://www.bilibili.com/video/BV1abc": "bilibili",
            "https://example.org/page": "web",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(capture.platform_for(url), expected)

    def test_normalize_url_removes_fragment(self):
        self.assertEqual(
            capture.normalize_url("example.org/a#comments"),
            "https://example.org/a",
        )

    def test_private_host_is_rejected(self):
        with self.assertRaises(capture.CaptureError) as context:
            capture.ensure_public_host("http://127.0.0.1:8080/")
        self.assertEqual(context.exception.status, "rejected")

    def test_partial_media_response_is_rejected(self):
        self.assertFalse(
            capture.media_body_is_complete(b"123", "bytes 0-2/100")
        )
        self.assertTrue(
            capture.media_body_is_complete(b"x" * 100, "bytes 0-99/100")
        )
        self.assertTrue(capture.media_body_is_complete(b"123", ""))


    def test_platform_parsers(self):
        reddit = capture.parse_page(
            "https://www.reddit.com/r/test/comments/1/hello/",
            '<html><head><title>ignored</title></head><body>'
            '<shreddit-post post-title="Hello world" author="alice" subreddit-name="test">'
            "<p>This is the post body, long enough to count as real content for testing.</p>"
            "</shreddit-post>"
            '<shreddit-comment author="bob"><p>Great post, thanks for sharing it here.</p></shreddit-comment>'
            "</body></html>",
            "reddit",
        )
        self.assertEqual(reddit["title"], "Hello world")
        self.assertIn("This is the post body", reddit["text"])
        self.assertIn("bob: Great post", reddit["text"])

        youtube = capture.parse_page(
            "https://www.youtube.com/watch?v=abc123",
            '<html><head><title>ignored</title></head><body><script>'
            'var ytInitialPlayerResponse = {"videoDetails": {"title": "Demo video", '
            '"author": "SomeChannel", "shortDescription": "A demo description that is long enough.", '
            '"lengthSeconds": "42", "viewCount": "1000", '
            '"thumbnail": {"thumbnails": [{"url": "https://i.ytimg.com/vi/abc123/hqdefault.jpg"}]}}};'
            "</script></body></html>",
            "youtube",
        )
        self.assertEqual(youtube["title"], "Demo video")
        self.assertEqual(youtube["author"], "SomeChannel")
        self.assertIn("A demo description", youtube["text"])
        self.assertTrue(any("i.ytimg.com" in str(item.get("url")) for item in youtube["media"]["images"]))

        github = capture.parse_page(
            "https://github.com/someone/somerepo",
            '<html><head><meta property="og:title" content="someone/somerepo"></head><body>'
            '<article class="markdown-body"><h1>Readme</h1>'
            "<p>This readme explains the project in enough detail to be real content.</p>"
            "</article></body></html>",
            "github",
        )
        self.assertEqual(github["author"], "someone")
        self.assertIn("This readme explains", github["text"])

        hn = capture.parse_page(
            "https://news.ycombinator.com/item?id=123",
            '<html><body><span class="titleline"><a href="https://example.com">HN story</a></span>'
            '<span class="hnuser">dave</span>'
            '<tr class="athing comtr"><td><span class="hnuser">erin</span>'
            '<div class="comment"><p>Interesting discussion point here for testing.</p></div></td></tr>'
            "</body></html>",
            "hackernews",
        )
        self.assertEqual(hn["title"], "HN story")
        self.assertIn("erin: Interesting discussion", hn["text"])

    def test_youtube_ytdlp_gate_is_open(self):
        # Previously yt-dlp was gated to bilibili/x only, so the README's
        # YouTube-audio claim was false. With no URL the function must
        # now reach the "no source" branch, not the "platform not enabled"
        # branch.
        result = capture.download_audio_with_ytdlp(
            {"platform": "youtube", "url": ""}, Path("/tmp/plc-nope")
        )
        self.assertNotIn("未启用", str(result.get("error")))

    def test_platform_parser_falls_back_to_generic(self):
        # A Reddit shell with no post markup must not crash and must not
        # invent content: it stays partial, which is what triggers the
        # browser retry for reddit.
        shell = capture.parse_page(
            "https://www.reddit.com/r/test/comments/1/hello/",
            "<html><head><title>Reddit</title></head><body><p>Loading</p></body></html>",
            "reddit",
        )
        self.assertEqual(shell["capture_status"], "partial")


if __name__ == "__main__":
    unittest.main()
