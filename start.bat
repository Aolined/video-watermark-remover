@echo off
chcp 65001 >nul
cd /d %~dp0
echo ========================================
echo   视频去水印解析服务 启动器
echo ========================================
if not exist .venv (
    echo [1/3] 创建虚拟环境...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
echo [2/3] 安装依赖...
pip install -q -e ".[all]"
echo [3/3] 启动服务: http://127.0.0.1:8000
python main.py
pause
