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


if __name__ == "__main__":
    unittest.main()
