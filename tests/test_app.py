import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# --- 1. 环境准备：把上一级目录加入路径，以便导入 app.py ---
# 这一步是因为 app.py 在 tests 文件夹的外面
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, format_duration, clean_path, find_free_port


# --- 2. 单元测试：测试纯逻辑函数 (不涉及界面) ---

def test_format_duration():
    """测试秒数转时间格式是否准确"""
    assert format_duration(0) == "00:00:00"
    assert format_duration(65) == "00:01:05"
    assert format_duration(3661) == "01:01:01"
    # 测试异常输入
    assert format_duration(None) == "00:00:00"


def test_clean_path():
    """测试路径清洗功能 (去除多余的引号)"""
    # Windows 风格引号
    assert clean_path('"C:/Users/Test"') == os.path.normpath("C:/Users/Test")
    # 单引号
    assert clean_path("'D:/Videos'") == os.path.normpath("D:/Videos")
    # 正常路径
    assert clean_path("/home/user/video") == os.path.normpath("/home/user/video")


def test_find_free_port():
    """测试端口寻找功能"""
    port = find_free_port(5000)
    assert isinstance(port, int)
    assert 1024 < port < 65535


# --- 3. 集成测试：测试 Flask 网页流程 ---

@pytest.fixture
def client():
    """创建一个虚拟的 Flask 测试客户端"""
    app.config['TESTING'] = True
    # 设置密钥以免 session 报错
    app.secret_key = 'test_key_for_ci'
    with app.test_client() as client:
        yield client


def test_homepage_redirect(client):
    """测试：未登录时访问首页，应该重定向到登录页"""
    response = client.get('/', follow_redirects=True)
    # 检查网页内容里是否包含 '系统登录' 字样
    assert "系统登录" in response.get_data(as_text=True)


def test_login_process(client):
    """测试：登录功能是否正常"""
    # 1. 模拟发送登录 POST 请求
    response = client.post('/login', data={'username': 'TestUser_CI'}, follow_redirects=True)

    # 2. 验证登录后是否看到了控制台
    page_content = response.get_data(as_text=True)
    assert "检测控制台" in page_content
    assert "TestUser_CI" in page_content  # 确认用户名显示了


def test_logout(client):
    """测试：退出登录"""
    # 先登录
    client.post('/login', data={'username': 'User'}, follow_redirects=True)
    # 再退出
    response = client.get('/logout', follow_redirects=True)
    # 应该回到登录页
    assert "系统登录" in response.get_data(as_text=True)


# --- 4. 高级测试：Mock 掉 GUI 弹窗 ---

def test_browse_api_mocked(client):
    """
    测试 /api/browse_folder 接口。
    关键：这里我们要 Mock 掉 tkinter 的弹窗，
    否则在 GitHub Actions 无显示器环境下会报错崩溃。
    """
    # 模拟 open_folder_dialog 函数
    # patch 的路径必须是 'app.open_folder_dialog'
    with patch('app.open_folder_dialog') as mock_dialog:
        # 设定：假如用户选了 "/tmp/videos"
        mock_dialog.return_value = "/tmp/videos"

        # 触发 API
        response = client.get('/api/browse_folder')

        # 验证结果
        data = response.get_json()
        assert data['path'] == "/tmp/videos"  # 路径被正确返回
        assert mock_dialog.called  # 确认程序确实试图去打开弹窗（被我们拦截了）


def test_scan_api_no_path(client):
    """测试扫描接口：如果不传路径应该报错"""
    # 先登录
    with client.session_transaction() as sess:
        sess['user'] = 'TestBot'

    response = client.post('/api/scan', json={'path': ''})
    assert response.status_code == 400
    assert "路径不存在" in response.get_json()['error']