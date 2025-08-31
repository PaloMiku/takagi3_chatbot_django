"""
Context processors for the chatbot app.
"""
import os
from pathlib import Path


def version_info(request):
    """
    Add version information to template context.
    """
    version = "0.2.1"  # 默认版本号
    
    try:
        # 尝试从 pyproject.toml 读取版本号
        base_dir = Path(__file__).resolve().parent.parent
        pyproject_path = base_dir / "pyproject.toml"
        
        if pyproject_path.exists():
            try:
                # Python 3.11+ 有内置的 tomllib
                import tomllib
                with open(pyproject_path, "rb") as f:
                    pyproject_data = tomllib.load(f)
                    version = pyproject_data.get("project", {}).get("version", version)
            except ImportError:
                # Python 3.10及以下版本，使用简单的文本解析
                with open(pyproject_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # 简单匹配 version = "x.x.x" 格式
                    import re
                    match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                    if match:
                        version = match.group(1)
    except Exception:
        # 如果读取失败，使用默认版本号
        pass
    
    return {
        'APP_VERSION': version
    }
