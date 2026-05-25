"""全页面端到端自动化测试 - 使用Playwright"""
import pytest
import subprocess
import time
import sys
from pathlib import Path

# 测试输出目录
TEST_OUTPUT_DIR = Path(__file__).parent.parent / 'test_outputs'
TEST_OUTPUT_DIR.mkdir(exist_ok=True)

# 标记所有测试为E2E
pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def streamlit_server():
    """启动Streamlit服务器"""
    proc = subprocess.Popen(
        [sys.executable, '-m', 'streamlit', 'run', 'web/app.py',
         '--server.headless', 'true',
         '--server.port', '8503',
         '--server.enableCORS', 'false'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    # 等待服务器启动
    time.sleep(12)
    yield proc
    # 清理
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except:
        proc.kill()


@pytest.fixture(scope="module")
def browser_context():
    """创建浏览器上下文"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN'
        )
        yield context
        browser.close()


class TestHomePage:
    """首页测试"""

    def test_home_loads(self, streamlit_server, browser_context):
        """测试首页加载"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(2)

        # 截图
        page.screenshot(path=str(TEST_OUTPUT_DIR / '01_home_page.png'), full_page=True)

        # 检查标题
        title = page.title()
        assert title is not None and len(title) > 0

        # 检查关键内容
        content = page.locator('body').text_content()
        assert '股票工具' in content or '数据管理' in content

        page.close()

    def test_home_navigation_links(self, streamlit_server, browser_context):
        """测试首页导航链接"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(2)

        # 检查是否有导航链接
        links = page.locator('a').all()
        assert len(links) > 0, "应该有导航链接"

        page.close()


class TestDataManagementPage:
    """数据管理页面测试"""

    def test_data_management_loads(self, streamlit_server, browser_context):
        """测试数据管理页面加载"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503/%F0%9F%93%A5_%E6%95%B0%E6%8D%AE%E7%AE%A1%E7%90%86')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(3)

        # 截图
        page.screenshot(path=str(TEST_OUTPUT_DIR / '02_data_management.png'), full_page=True)

        # 检查Tab布局
        tabs = page.locator('[role="tab"]').all()
        assert len(tabs) >= 4, "应该有4个Tab"

        # 检查关键内容
        content = page.locator('body').text_content()
        assert '数据概览' in content or '同步管理' in content

        page.close()

    def test_data_management_tabs(self, streamlit_server, browser_context):
        """测试数据管理Tab切换"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503/%F0%9F%93%A5_%E6%95%B0%E6%8D%AE%E7%AE%A1%E7%90%86')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(3)

        # 点击不同的Tab
        tabs = page.locator('[role="tab"]').all()
        for i, tab in enumerate(tabs[:4]):
            try:
                tab.click()
                time.sleep(1)
                page.screenshot(
                    path=str(TEST_OUTPUT_DIR / f'02_data_tab_{i}.png'),
                    full_page=True
                )
            except:
                pass

        page.close()

    def test_data_management_metrics(self, streamlit_server, browser_context):
        """测试数据管理统计指标"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503/%F0%9F%93%A5_%E6%95%B0%E6%8D%AE%E7%AE%A1%E7%90%86')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(4)

        # 检查是否有统计指标
        metrics = page.locator('[data-testid="stMetric"]').all()
        print(f"Found {len(metrics)} metrics on data management page")

        # 截图
        page.screenshot(path=str(TEST_OUTPUT_DIR / '02_data_metrics.png'), full_page=True)

        page.close()


class TestPatternMatchingPage:
    """形态相似性选股页面测试"""

    def test_pattern_matching_loads(self, streamlit_server, browser_context):
        """测试形态匹配页面加载"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503/%F0%9F%94%8D_%E5%BD%A2%E6%80%81%E7%9B%B8%E4%BC%BC%E6%80%A7%E9%80%89%E8%82%A1')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(3)

        # 截图
        page.screenshot(path=str(TEST_OUTPUT_DIR / '03_pattern_matching.png'), full_page=True)

        # 检查关键内容
        content = page.locator('body').text_content()
        assert '形态' in content or '匹配' in content or '相似' in content

        page.close()

    def test_pattern_matching_controls(self, streamlit_server, browser_context):
        """测试形态匹配控制元素"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503/%F0%9F%94%8D_%E5%BD%A2%E6%80%81%E7%9B%B8%E4%BC%BC%E6%80%A7%E9%80%89%E8%82%A1')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(3)

        # 检查选择框
        selectboxes = page.locator('select').all()
        print(f"Found {len(selectboxes)} selectboxes on pattern matching page")

        # 检查按钮
        buttons = page.locator('button').all()
        print(f"Found {len(buttons)} buttons on pattern matching page")

        page.close()


class TestKLinePage:
    """K线图展示页面测试"""

    def test_kline_loads(self, streamlit_server, browser_context):
        """测试K线图页面加载"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503/%F0%9F%93%88_K%E7%BA%BF%E5%9B%BE%E5%B1%95%E7%A4%BA')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(3)

        # 截图
        page.screenshot(path=str(TEST_OUTPUT_DIR / '04_kline_page.png'), full_page=True)

        # 检查关键内容
        content = page.locator('body').text_content()
        assert 'K线' in content or '股票' in content

        page.close()

    def test_kline_stock_selector(self, streamlit_server, browser_context):
        """测试K线图股票选择器"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503/%F0%9F%93%88_K%E7%BA%BF%E5%9B%BE%E5%B1%95%E7%A4%BA')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(3)

        # 查找股票选择框
        selectboxes = page.locator('select').all()
        print(f"Found {len(selectboxes)} selectboxes on K-line page")

        # 如果有选择框，尝试检查选项
        if len(selectboxes) > 0:
            first_select = selectboxes[0]
            options = first_select.locator('option').all()
            print(f"First selectbox has {len(options)} options")

        page.screenshot(path=str(TEST_OUTPUT_DIR / '04_kline_selector.png'), full_page=True)

        page.close()

    def test_kline_chart_elements(self, streamlit_server, browser_context):
        """测试K线图图表元素"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503/%F0%9F%93%88_K%E7%BA%BF%E5%9B%BE%E5%B1%95%E7%A4%BA')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(4)

        # 检查是否有Plotly图表
        plotly_charts = page.locator('.js-plotly-plot').all()
        print(f"Found {len(plotly_charts)} Plotly charts on K-line page")

        # 截图
        page.screenshot(path=str(TEST_OUTPUT_DIR / '04_kline_chart.png'), full_page=True)

        page.close()


class TestLimitUpRankingPage:
    """连板梯队页面测试"""

    def test_limit_up_loads(self, streamlit_server, browser_context):
        """测试连板梯队页面加载"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503/%F0%9F%8F%86_%E8%BF%9E%E6%9D%BF%E6%A2%AF%E9%98%9F')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(3)

        # 截图
        page.screenshot(path=str(TEST_OUTPUT_DIR / '05_limit_up_page.png'), full_page=True)

        # 检查关键内容
        content = page.locator('body').text_content()
        assert '连板' in content or '涨停' in content or '梯队' in content

        page.close()

    def test_limit_up_date_selector(self, streamlit_server, browser_context):
        """测试连板梯队日期选择器"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503/%F0%9F%8F%86_%E8%BF%9E%E6%9D%BF%E6%A2%AF%E9%98%9F')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(3)

        # 检查日期输入框
        date_inputs = page.locator('input[type="date"]').all()
        print(f"Found {len(date_inputs)} date inputs on limit-up page")

        # 检查按钮
        buttons = page.locator('button').all()
        print(f"Found {len(buttons)} buttons on limit-up page")

        page.screenshot(path=str(TEST_OUTPUT_DIR / '05_limit_up_date.png'), full_page=True)

        page.close()

    def test_limit_up_filters(self, streamlit_server, browser_context):
        """测试连板梯队筛选功能"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503/%F0%9F%8F%86_%E8%BF%9E%E6%9D%BF%E6%A2%AF%E9%98%9F')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(3)

        # 检查多选框
        checkboxes = page.locator('input[type="checkbox"]').all()
        print(f"Found {len(checkboxes)} checkboxes on limit-up page")

        # 检查选择框
        selectboxes = page.locator('select').all()
        print(f"Found {len(selectboxes)} selectboxes on limit-up page")

        page.screenshot(path=str(TEST_OUTPUT_DIR / '05_limit_up_filters.png'), full_page=True)

        page.close()


class TestSystemConfigPage:
    """系统配置页面测试"""

    def test_system_config_loads(self, streamlit_server, browser_context):
        """测试系统配置页面加载"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503/%E2%9A%99%EF%B8%8F_%E7%B3%BB%E7%BB%9F%E9%85%8D%E7%BD%AE')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(3)

        # 截图
        page.screenshot(path=str(TEST_OUTPUT_DIR / '06_system_config.png'), full_page=True)

        # 检查关键内容
        content = page.locator('body').text_content()
        assert '配置' in content or 'Token' in content or '数据源' in content

        page.close()

    def test_system_config_inputs(self, streamlit_server, browser_context):
        """测试系统配置输入框"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503/%E2%9A%99%EF%B8%8F_%E7%B3%BB%E7%BB%9F%E9%85%8D%E7%BD%AE')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(3)

        # 检查文本输入框
        text_inputs = page.locator('input[type="text"], input[type="password"]').all()
        print(f"Found {len(text_inputs)} text inputs on config page")

        # 检查按钮
        buttons = page.locator('button').all()
        print(f"Found {len(buttons)} buttons on config page")

        page.close()


class TestNavigation:
    """页面导航测试"""

    def test_sidebar_navigation(self, streamlit_server, browser_context):
        """测试侧边栏导航"""
        page = browser_context.new_page()
        page.goto('http://localhost:8503')
        page.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(2)

        # 检查侧边栏
        sidebar = page.locator('[data-testid="stSidebar"]').first
        if sidebar:
            sidebar_content = sidebar.text_content()
            print(f"Sidebar content preview: {sidebar_content[:200] if sidebar_content else 'empty'}")

        page.screenshot(path=str(TEST_OUTPUT_DIR / '07_sidebar_nav.png'), full_page=True)

        page.close()

    def test_all_pages_accessible(self, streamlit_server, browser_context):
        """测试所有页面可访问"""
        pages_to_test = [
            ('http://localhost:8503', 'Home'),
            ('http://localhost:8503/%F0%9F%93%A5_%E6%95%B0%E6%8D%AE%E7%AE%A1%E7%90%86', 'Data Management'),
            ('http://localhost:8503/%F0%9F%94%8D_%E5%BD%A2%E6%80%81%E7%9B%B8%E4%BC%BC%E6%80%A7%E9%80%89%E8%82%A1', 'Pattern Matching'),
            ('http://localhost:8503/%F0%9F%93%88_K%E7%BA%BF%E5%9B%BE%E5%B1%95%E7%A4%BA', 'K-Line'),
            ('http://localhost:8503/%F0%9F%8F%86_%E8%BF%9E%E6%9D%BF%E6%A2%AF%E9%98%9F', 'Limit-Up Ranking'),
            ('http://localhost:8503/%E2%9A%99%EF%B8%8F_%E7%B3%BB%E7%BB%9F%E9%85%8D%E7%BD%AE', 'System Config'),
        ]

        results = []
        for url, name in pages_to_test:
            page = browser_context.new_page()
            try:
                page.goto(url, timeout=30000)
                page.wait_for_load_state('networkidle', timeout=30000)
                time.sleep(2)
                title = page.title()
                results.append((name, 'OK', title))
            except Exception as e:
                results.append((name, 'FAILED', str(e)))
            finally:
                page.close()

        # 打印结果
        print("\n=== Page Accessibility Test ===")
        for name, status, info in results:
            print(f"{name}: {status} - {info[:50]}")

        # 检查所有页面都应该可访问
        failed = [r for r in results if r[1] == 'FAILED']
        assert len(failed) == 0, f"以下页面无法访问: {failed}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
