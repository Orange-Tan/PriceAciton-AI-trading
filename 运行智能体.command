#!/bin/bash
cd "$(dirname "$0")"

# 自动选择已安装项目依赖的 Python 解释器
# （系统自带 /usr/bin/python3 未安装 PyQt6 等依赖，必须显式指定）
PA_PY=""
for cand in "$HOME"/.workbuddy/binaries/python/versions/*/bin/python3 \
            /opt/homebrew/bin/python3 \
            /usr/local/bin/python3 \
            "$(command -v python3 2>/dev/null)"; do
    if [ -n "$cand" ] && [ -x "$cand" ] && "$cand" -c "import PyQt6" >/dev/null 2>&1; then
        PA_PY="$cand"
        break
    fi
done

if [ -z "$PA_PY" ]; then
    echo "[错误] 未找到装有 PyQt6 的 Python 解释器。"
    echo "请先安装依赖：在终端执行  pip3 install -e /Users/orange/AI/PA_agent/PA_Agent"
    echo "按回车键关闭窗口..."
    read
    exit 1
fi
echo "[提示] 使用 Python: $PA_PY"

# TradingView 数据源代理自动探测
if [ -z "$PA_TV_PROXY" ]; then
    for proxy_port in 7890 7897 1087 8118 10809; do
        if nc -z -w 1 127.0.0.1 ${proxy_port} 2>/dev/null; then
            export PA_TV_PROXY=127.0.0.1:${proxy_port}
            echo "[提示] 检测到本地代理端口 ${proxy_port}，TradingView 数据将通过代理获取。"
            break
        fi
    done
fi

"$PA_PY" run.py
if [ $? -ne 0 ]; then
    echo ""
    echo "[错误] 程序异常退出，请查看上方错误信息。"
    echo "按回车键关闭窗口..."
    read
fi
