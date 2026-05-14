"""Web端到端自动化测试 - 使用Playwright"""
import pytest
import subprocess
import time
import sys
from pathlib import Path

# 测试输出目录 - 统一管理所有测试输出
TEST_OUTPUT_DIR = Path(__file__).parent.parent / 'test_outputs'
TEST_OUTPUT_DIR.mkdir(exist_ok=True)

# 标记需要手动运行的测试（需要Streamlit服务器）
pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def streamlit_server():
    """启动Streamlit服务器作为fixture"""
    proc = subprocess.Popen(
        [sys.executable, '-m', 'streamlit', 'run', 'web/app.py',
         '--server.headless', 'true',
         '--server.port', '8502',
         '--server.enableCORS', 'false'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    # 等待服务器启动
    time.sleep(10)
    yield proc
    # 清理
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except:
        proc.kill()


@pytest.mark.skipif(not sys.platform.startswith('win'), reason="Only test on Windows")
def test_home_page_loads(streamlit_server):
    """测试首页加载成功"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('http://localhost:8502')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(2)

        # 检查页面标题
        title = page.title()
        assert title is not None
        assert len(title) > 0

        # 检查页面包含关键元素
        content = page.locator('body').text_content()
        assert content is not None
        # 应该有"K线"或"形态"或"股票"等关键词
        has_keyword = any(k in content for k in ['股票', '形态', 'K线', '数据'])
        assert has_keyword, "页面应该包含中文关键词"

        browser.close()


@pytest.mark.skipif(not sys.platform.startswith('win'), reason="Only test on Windows")
def test_kline_page_navigation(streamlit_server):
    """测试K线图页面导航和功能"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('http://localhost:8502/K%E7%BA%BF%E5%9B%BE%E5%B1%95%E7%A4%BA')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(3)

        # 截图用于调试
        screenshot_path = TEST_OUTPUT_DIR / 'test_kline_page.png'
        page.screenshot(path=str(screenshot_path), full_page=True)

        # 检查页面内容
        content = page.locator('body').text_content()
        print(f"Page content preview: {content[:200]}")

        # 检查是否有选择器
        select_count = page.locator('select').count()
        print(f"Found {select_count} select elements")

        # 检查是否有按钮
        button_count = page.locator('button').count()
        print(f"Found {button_count} button elements")

        browser.close()


if __name__ == '__main__':
    # 直接运行测试
    print("Starting E2E web test...")
    from playwright.sync_api import sync_playwright

    # 先启动服务器
    proc = subprocess.Popen(
        [sys.executable, '-m', 'streamlit', 'run', 'web/app.py',
         '--server.headless', 'true',
         '--server.port', '8502'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        print("Waiting for server to start (10s)...")
        time.sleep(10)

        print("Running Playwright test...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 测试首页
            print("\n=== Testing Home Page ===")
            page.goto('http://localhost:8502')
            page.wait_for_load_state('networkidle', timeout=30000)
            time.sleep(2)
            print(f"Page title: {page.title()}")

            # 测试K线图页面
            print("\n=== Testing K-Line Page ===")
            page.goto('http://localhost:8502/K%E7%BA%BF%E5%9B%BE%E5%B1%95%E7%A4%BA')
            page.wait_for_load_state('networkidle', timeout=30000)
            time.sleep(3)

            # 截图
            screenshot_path = TEST_OUTPUT_DIR / 'e2e_test_kline.png'
            page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"Screenshot saved to test_outputs/e2e_test_kline.png")

            # 检查股票下拉选择框
            selectboxes = page.locator('select').all()
            print(f"Found {len(selectboxes)} selectboxes on page")

            # 检查页面文本
            text = page.locator('body').text_content()
            has_sh = '.SH' in text
            has_sz = '.SZ' in text
            print(f"Page contains .SH codes: {has_sh}")
            print(f"Page contains .SZ codes: {has_sz}")

            browser.close()

        print("\n=== E2E TEST COMPLETED ===")
        print("[OK] Streamlit server started")
        print("[OK] Home page loaded")
        print("[OK] K-line page navigated")
        print("[OK] Screenshot captured")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except:
            proc.kill()
