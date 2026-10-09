#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 BytePlus 信控额度监控 → 钉钉告警   (Playwright 持久化会话版 / 全功能单文件)
================================================================================

 功能：定时查询 BytePlus 费用中心的「信控额度 (Quota)」，
       低于阈值（默认 1500 USD）时推送钉钉群机器人告警。

 背景：信控额度没有公开 OpenAPI（GetQuotaAcctInfo 仅存在于控制台内部接口），
       AK/SK 方式调 open.byteplusapi.com 会 404。因此只能走登录态。
       本脚本用 Playwright 持久化会话，比裸 Cookie 更耐用：
         · 带完整浏览器指纹，不易被风控拦截
         · storage_state 会话信息比单条 Cookie 完整，通常活得更久
         · CSRF token 由浏览器自动处理，无需手动抓取

 ⚠️ 本质仍是登录态，终究会过期（预期数周一次）。过期时脚本会钉钉提醒你
    重跑 --login。脚本不保存、不读取、不输入你的账号密码——登录始终由你
    在浏览器里亲手完成，脚本只保存登录「之后」的会话状态。

--------------------------------------------------------------------------------
 一、安装依赖
--------------------------------------------------------------------------------
     pip install playwright requests
     playwright install chromium
     playwright install-deps          # Linux 缺系统库时执行（需 root）

     自检依赖是否齐全：
     python3 byteplus_quota_playwright.py --check

--------------------------------------------------------------------------------
 二、配置
--------------------------------------------------------------------------------
     修改下方 "配置区" 的 DINGTALK_WEBHOOK / DINGTALK_SECRET / THRESHOLD。
     （也可用同名环境变量覆盖，环境变量优先）

     钉钉机器人获取：钉钉群 → 群设置 → 智能群助手 → 添加自定义机器人
                     → 安全设置勾选「加签」→ 拿到 Webhook 和 SEC 开头的密钥

     配好后测试机器人是否通：
     python3 byteplus_quota_playwright.py --test-dingtalk

     ⚠️ 本文件含钉钉密钥，建议 chmod 600 byteplus_quota_playwright.py

--------------------------------------------------------------------------------
 三、首次登录（直接在服务器上执行）
--------------------------------------------------------------------------------
     python3 byteplus_quota_playwright.py --login

     脚本会：
       1. 让你输入 BytePlus 账号密码（密码不回显）
       2. 无头浏览器自动登录
       3. 成功 → 保存 auth.json，完成
       4. 遇验证码/二次验证 → 自动启动 VNC 远程桌面
          → 你 SSH 端口转发后用 VNC 客户端连上去，手动过验证码
          → 回终端按 Enter → 保存 auth.json

     也可用环境变量免交互输入：
     BYTEPLUS_ACCOUNT_ID=3000990276 BYTEPLUS_USER=vane BYTEPLUS_PASS=xxx python3 ... --login

     ⚠️ VNC 模式需要额外装两个包（无验证码时不需要）：
     dnf install -y xorg-x11-server-Xvfb x11vnc

--------------------------------------------------------------------------------
 四、部署到服务器（一台机器搞定）
--------------------------------------------------------------------------------
     # 装依赖
     pip install playwright requests
     playwright install chromium
     dnf install -y atk at-spi2-atk at-spi2-core cups-libs \
       libXcomposite libXdamage libXfixes libXrandr libxkbcommon \
       libdrm mesa-libgbm pango cairo alsa-lib nss nspr libX11 libXext libxcb

     # 登录获取会话
     python3 byteplus_quota_playwright.py --login

     # 验证能查到额度
     python3 byteplus_quota_playwright.py

--------------------------------------------------------------------------------
 五、挂定时任务
--------------------------------------------------------------------------------
     自动安装（每小时检查一次）：
     python3 byteplus_quota_playwright.py --install-cron

     或手动加到 crontab：
     0 * * * * cd /opt/monitor && /usr/bin/python3 byteplus_quota_playwright.py >> quota.log 2>&1

--------------------------------------------------------------------------------
 六、会话过期时怎么办
--------------------------------------------------------------------------------
     钉钉会收到「会话已过期」提醒，在服务器上重跑即可：
       python3 byteplus_quota_playwright.py --login
     下次定时任务自动恢复。

--------------------------------------------------------------------------------
 七、钉钉会收到的三类消息
--------------------------------------------------------------------------------
     🔴 额度不足        —— 额度低于阈值，需要充值/续额
     🟠 会话已过期      —— 需要你重跑 --login 更新 auth.json
     ⚠️ 查询异常        —— 其他错误（网络、依赖、页面结构变更等）

--------------------------------------------------------------------------------
 八、常见问题
--------------------------------------------------------------------------------
     Q: 报 libatk-1.0.so.0 / 其它 .so cannot open shared object file
        A: Chromium 缺系统依赖。playwright install-deps 只支持 Debian/Ubuntu，
           RHEL/CentOS/Rocky/Alma 需手动安装：

           dnf install -y atk at-spi2-atk at-spi2-core cups-libs \
             libXcomposite libXdamage libXfixes libXrandr libxkbcommon \
             libdrm mesa-libgbm pango cairo alsa-lib nss nspr libX11 \
             libXext libxcb

           实在装不齐可用发行版 chromium 拉全依赖：dnf install -y chromium
           （脚本遇到此错误会自动打印对症命令）

     Q: --login 在服务器上报 TargetClosedError / 起不来浏览器
        A: --login 是有头模式，需要图形界面，**只能在你的 Mac/Windows 上运行**。
           服务器无桌面环境，只负责无头跑监控。正确流程：
             本地 --login 生成 auth.json → scp 到服务器 → 服务器运行监控
           （脚本已内置检测，无图形界面时会直接提示而非报错）

     Q: 不想在服务器上折腾系统库
        A: 用官方 Playwright 镜像，依赖全预装：

           docker run --rm \
             -v /opt/monitor/QuotaAcctInfo:/app -w /app \
             mcr.microsoft.com/playwright/python:v1.49.0-jammy \
             python3 byteplus_quota_playwright.py

           cron 里直接调用上面这条 docker run 即可。

     Q: 报 "Running as root without --no-sandbox"
        A: 脚本已内置 --no-sandbox，若仍报错检查 Playwright 版本

     Q: 一直提示会话过期
        A: auth.json 可能没上传或路径不对；确认与脚本同目录，或用
           BYTEPLUS_AUTH_FILE 环境变量指定绝对路径

     Q: 想改检查频率
        A: 改 crontab 的时间表达式，例如每 30 分钟 → */30 * * * *
================================================================================
"""
import argparse
import base64
import hashlib
import hmac
import os
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime

# ==============================================================================
#                                  配置区
#                     （同名环境变量存在时优先使用环境变量）
# ==============================================================================

# ---- 钉钉机器人（加签模式）----
DINGTALK_WEBHOOK = os.environ.get(
    "DINGTALK_WEBHOOK",
    "https://oapi.dingtalk.com/robot/send?access_token=2a05bfe78955a0ad43e61c022c6eacf15443aa355b25bb4e6310882097d23dffv"
)
DINGTALK_SECRET = os.environ.get(
    "DINGTALK_SECRET",
    "SECc1305aa535576bdf7e501223c57ca9992dfe1c6fd65f897dabb01fd097a03a4bv"
)
# ---- 告警冷却（小时）——避免重复轰炸 ----
ALERT_COOLDOWN_HOURS = float(os.environ.get("ALERT_COOLDOWN_HOURS", "6"))

# ---- 连续失败多少次才告警（避免验证码等瞬时故障误报）----
MAX_RELOGIN_FAILURES = int(os.environ.get("MAX_RELOGIN_FAILURES", "3"))

# ---- 失败类钉钉告警总开关（调试期间可临时关闭，避免修好之前被轰炸）----
# 设为 False 时：自动重登失败 / 查询异常不再推送钉钉，只打日志。
# 额度不足告警不受影响。修复完成后改回 True。
ENABLE_FAILURE_ALERT = os.environ.get("ENABLE_FAILURE_ALERT", "0") == "1"

# ---- 告警阈值（USD）----
THRESHOLD = float(os.environ.get("QUOTA_THRESHOLD", "1500"))

# ---- 会话文件路径 ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTH_FILE = os.environ.get("BYTEPLUS_AUTH_FILE", os.path.join(BASE_DIR, "auth.json"))
CRED_FILE = os.environ.get("BYTEPLUS_CRED_FILE", os.path.join(BASE_DIR, ".credentials"))
ALERT_STATE_FILE = os.path.join(BASE_DIR, ".last_alert")
FAIL_COUNT_FILE = os.path.join(BASE_DIR, ".relogin_fails")
SESSION_ALERTED_FILE = os.path.join(BASE_DIR, ".session_alerted")

# ---- 定时任务频率（--install-cron 使用）----
CRON_SCHEDULE = os.environ.get("CRON_SCHEDULE", "0 * * * *")   # 默认每小时

# ---- BytePlus 控制台 ----
CONSOLE_HOST = "console.byteplus.com"
FINANCE_URL = f"https://{CONSOLE_HOST}/finance/overview"
IAM_LOGIN_URL = "https://signin.byteplus.com/auth/login/user/?redirectURI=https%3A%2F%2Fconsole.byteplus.com%2Ffinance%2Foverview"
ACTION_KEYWORD = "GetQuotaAcctInfo"
REGION = os.environ.get("BYTEPLUS_REGION", "ap-singapore-1")
VERSION = os.environ.get("BYTEPLUS_VERSION", "2020-01-01")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)

# 接口等待与超时（秒）
API_WAIT_SECONDS = 20
PAGE_TIMEOUT_MS = 60000
# ==============================================================================


class SessionExpired(Exception):
    """会话失效，需要重新 --login"""
    pass


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


# ------------------------------------------------------------------------------
#                        环境问题诊断（缺库 / 无图形界面）
# ------------------------------------------------------------------------------
RHEL_PKGS = (
    "atk at-spi2-atk at-spi2-core cups-libs libXcomposite libXdamage "
    "libXfixes libXrandr libxkbcommon libdrm mesa-libgbm pango cairo "
    "alsa-lib nss nspr libX11 libXext libxcb"
)
DEBIAN_HINT = "playwright install-deps    # 或: apt-get install -y libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 libnss3"


def _print_missing_lib_help(err_text):
    """Chromium 缺系统库时打印对症的安装命令"""
    m = re.search(r"(lib[\w\.\-\+]+\.so[\.\d]*)", str(err_text))
    missing = m.group(1) if m else "系统图形库"

    print("\n" + "=" * 70, file=sys.stderr)
    print(f"❌ Chromium 启动失败：缺少系统库 {missing}", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print("\n请在本机安装 Chromium 运行所需的系统依赖：\n", file=sys.stderr)

    if os.path.exists("/etc/redhat-release") or os.path.exists("/etc/rocky-release"):
        mgr = "dnf" if os.path.exists("/usr/bin/dnf") else "yum"
        print(f"  # RHEL / CentOS / Rocky / Alma （检测到当前系统）", file=sys.stderr)
        print(f"  {mgr} install -y {RHEL_PKGS}\n", file=sys.stderr)
        print(f"  # 若上面仍缺库，可用发行版 chromium 拉齐全部依赖：", file=sys.stderr)
        print(f"  {mgr} install -y chromium\n", file=sys.stderr)
    else:
        print(f"  # Debian / Ubuntu", file=sys.stderr)
        print(f"  {DEBIAN_HINT}\n", file=sys.stderr)
        print(f"  # RHEL / CentOS / Rocky / Alma", file=sys.stderr)
        print(f"  dnf install -y {RHEL_PKGS}\n", file=sys.stderr)

    print("装完后重新执行本脚本即可。", file=sys.stderr)
    print("（也可改用官方 Docker 镜像，免去装库：见文件开头「常见问题」）\n", file=sys.stderr)


def _has_display():
    """判断当前环境是否有图形界面（有头模式必需）"""
    if sys.platform in ("darwin", "win32"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _print_no_display_help():
    """无图形界面时，指引用户改用服务器可行的方案"""
    script = os.path.basename(__file__)
    workdir = os.path.dirname(os.path.abspath(__file__))

    print("\n" + "=" * 70, file=sys.stderr)
    print("❌ 当前机器没有可用的图形界面（X server），--login 无法运行。", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print("\n--login 需要弹出真实浏览器让你手动登录，必须有桌面环境。", file=sys.stderr)
    print("服务器通常没有，因此请改用下面任一方案：\n", file=sys.stderr)

    print("  ✅ A) 从 Cookie 生成 auth.json —— 推荐，完全不需要图形界面", file=sys.stderr)
    print(f"        python3 {script} --import-cookie", file=sys.stderr)
    print("        （浏览器 F12 抓 Cookie → 粘贴进去 → 自动生成）\n", file=sys.stderr)

    print("     B) X11 转发，把浏览器窗口显示到你的 Mac", file=sys.stderr)
    print("        Mac: brew install --cask xquartz   （装完注销重登一次）", file=sys.stderr)
    print("        服务器: dnf install -y gtk3 libXScrnSaver libXtst xorg-x11-xauth", file=sys.stderr)
    print(f"        然后: ssh -X root@服务器 → cd {workdir} → python3 {script} --login\n", file=sys.stderr)

    print("     C) 在你的 Mac 上生成后上传", file=sys.stderr)
    print(f"        Mac: pip install playwright && playwright install chromium", file=sys.stderr)
    print(f"             python3 {script} --login", file=sys.stderr)
    print(f"        再: scp auth.json root@服务器:{workdir}/\n", file=sys.stderr)

    print("说明：服务器跑「监控」用无头模式，不需要图形界面；", file=sys.stderr)
    print("      只有「登录」这一步需要真人看着浏览器操作。\n", file=sys.stderr)


# ------------------------------------------------------------------------------
#                              依赖自检
# ------------------------------------------------------------------------------
def check_deps(verbose=True):
    """检查 requests / playwright / chromium 是否就绪"""
    ok = True

    try:
        import requests  # noqa: F401
        if verbose:
            print("✅ requests 已安装")
    except ImportError:
        ok = False
        print("❌ 缺少 requests   →  pip install requests", file=sys.stderr)

    try:
        from playwright.sync_api import sync_playwright
        if verbose:
            print("✅ playwright 已安装")
        try:
            with sync_playwright() as p:
                path = p.chromium.executable_path
                if path and os.path.exists(path):
                    if verbose:
                        print(f"✅ Chromium 已就绪  ({path})")
                else:
                    ok = False
                    print("❌ Chromium 未安装  →  playwright install chromium", file=sys.stderr)
        except Exception as e:
            ok = False
            print(f"❌ Chromium 检查失败: {e}", file=sys.stderr)
            print("   →  playwright install chromium", file=sys.stderr)
            print("   →  Linux 若缺系统库再执行: playwright install-deps", file=sys.stderr)
    except ImportError:
        ok = False
        print("❌ 缺少 playwright →  pip install playwright && playwright install chromium",
              file=sys.stderr)

    if verbose:
        print(f"\n配置检查:")
        print(f"  阈值      : ${THRESHOLD:,.0f} USD")
        print(f"  会话文件  : {AUTH_FILE} {'(存在)' if os.path.exists(AUTH_FILE) else '(不存在，需 --login)'}")
        cred_ok = os.path.exists(CRED_FILE)
        print(f"  凭据文件  : {CRED_FILE} {'(存在，过期可自动重登)' if cred_ok else '(不存在，过期需手动 --login)'}")
        dt_ok = "填写待确认" not in DINGTALK_WEBHOOK and "在这里填" not in DINGTALK_WEBHOOK
        print(f"  钉钉配置  : {'已填写' if dt_ok else '❌ 未填写，请修改配置区'}")

    return ok


# ------------------------------------------------------------------------------
#                              钉钉推送
# ------------------------------------------------------------------------------
def send_dingtalk(text, title="BytePlus 信控额度告警"):
    import requests

    if "在这里填" in DINGTALK_WEBHOOK or "在这里填" in DINGTALK_SECRET:
        print("[钉钉未配置，跳过推送] 消息内容:\n" + text, file=sys.stderr)
        return

    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{DINGTALK_SECRET}"
    hmac_code = hmac.new(
        DINGTALK_SECRET.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

    url = f"{DINGTALK_WEBHOOK}&timestamp={timestamp}&sign={sign}"
    body = {"msgtype": "markdown", "markdown": {"title": title, "text": text}}

    try:
        resp = requests.post(url, json=body, timeout=10)
        data = resp.json()
        if data.get("errcode") == 0:
            log("钉钉推送成功")
        else:
            log(f"钉钉推送失败: {data}")
    except Exception as e:
        print(f"钉钉推送异常: {e}", file=sys.stderr)


def notify_quota_low(balance, account_id):
    send_dingtalk(
        f"### 🔴 BytePlus 信控额度不足\n\n"
        f"当前可用信控额度：**${balance:,.2f} USD**\n\n"
        f"已低于预警阈值 **${THRESHOLD:,.0f} USD**，请及时充值或联系上游续额。\n\n"
        f"> 账户ID：{account_id}\n"
        f"> 检查时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        title="BytePlus 信控额度不足",
    )


def notify_quota_recovered(balance, account_id):
    send_dingtalk(
        f"### ✅ BytePlus 信控额度已恢复\n\n"
        f"当前可用信控额度：**${balance:,.2f} USD**\n\n"
        f"已回升至预警阈值 **${THRESHOLD:,.0f} USD** 以上，恢复正常。\n\n"
        f"> 账户ID：{account_id}\n"
        f"> 恢复时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        title="BytePlus 信控额度已恢复",
    )


def notify_session_recovered(balance, account_id):
    send_dingtalk(
        f"### ✅ BytePlus 监控已恢复\n\n"
        f"**此前连续登录失败已告警，现在自动重登成功，监控恢复正常。**\n\n"
        f"当前信控额度：**${balance:,.2f} USD**\n\n"
        f"> 账户ID：{account_id}\n"
        f"> 恢复时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        title="BytePlus 监控已恢复",
    )


def notify_session_expired(reason, fail_count=None):
    count_line = f"连续失败 **{fail_count}** 次后仍无法恢复。\n\n" if fail_count else ""
    send_dingtalk(
        f"### 🟠 BytePlus 监控需要手动介入\n\n"
        f"**会话过期后自动重登失败，信控额度暂时查不到了。**\n\n"
        f"{count_line}"
        f"可能原因：密码已修改、登录页出现验证码、账号被锁定、网络异常\n\n"
        f"登录成功后监控自动恢复，无需其他操作。\n\n"
        f"> 失败原因：{str(reason)[:200]}\n"
        f"> 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        title="BytePlus 自动重登失败",
    )


def notify_error(err):
    send_dingtalk(
        f"### ⚠️ BytePlus 额度查询异常\n\n"
        f"> 非会话过期的其他错误，请检查服务器环境或脚本。\n\n"
        f"错误：`{str(err)[:300]}`\n\n"
        f"> 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        title="BytePlus 监控异常",
    )


# ------------------------------------------------------------------------------
#                          登录模式（有头，手动登录）
# ------------------------------------------------------------------------------
def _cookie_string_to_storage_state(cookie_str, domain=".byteplus.com"):
    """把浏览器 Cookie 请求头字符串转成 Playwright storage_state 结构"""
    cookies = []
    for part in cookie_str.strip().rstrip(";").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name, value = name.strip(), value.strip()
        if not name:
            continue
        cookies.append({
            "name": name,
            "value": value,
            "domain": domain,
            "path": "/",
            "expires": -1,          # 会话 cookie
            "httpOnly": False,
            "secure": True,
            "sameSite": "Lax",
        })
    return {"cookies": cookies, "origins": []}


def import_cookie(cookie_file=None):
    """从 Cookie 字符串生成 auth.json —— 无需图形界面，可直接在服务器执行

    三种输入方式（便于自动化，无需交互）：
      1. 交互粘贴：  --import-cookie
      2. 从文件读：  --import-cookie --cookie-file cookie.txt
      3. 从管道读：  echo "$COOKIE" | --import-cookie
                     ssh server 'cd /opt/... && python3 x.py --import-cookie' <<< "$COOKIE"
    """
    import json as _json

    cookie_str = None

    # 方式 2：指定文件
    if cookie_file:
        if not os.path.exists(cookie_file):
            print(f"❌ 找不到文件: {cookie_file}", file=sys.stderr)
            sys.exit(1)
        with open(cookie_file, encoding="utf-8") as f:
            cookie_str = f.read().strip()
        print(f"已从文件读取 Cookie: {cookie_file}")

    # 方式 3：管道 / 重定向输入（非 tty）
    elif not sys.stdin.isatty():
        cookie_str = sys.stdin.read().strip()
        print("已从标准输入读取 Cookie")

    # 方式 1：交互粘贴
    else:
        print("=" * 70)
        print(" 从 Cookie 生成 auth.json（无需图形界面）")
        print("=" * 70)
        print("\n获取 Cookie 的步骤：")
        print("  1. 浏览器登录 console.byteplus.com，打开费用中心")
        print("  2. F12 → Network → 刷新页面 → 找到 GetQuotaAcctInfo 请求")
        print("  3. Request Headers 里复制 Cookie 那一整行的值")
        print("\n把 Cookie 粘贴到下面（一整行，粘完直接回车）：\n")
        try:
            cookie_str = input("Cookie> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消。", file=sys.stderr)
            sys.exit(1)

    if not cookie_str or "=" not in cookie_str:
        print("\n❌ Cookie 内容看起来不对（应该是 a=b; c=d 这种格式）。", file=sys.stderr)
        sys.exit(1)

    state = _cookie_string_to_storage_state(cookie_str)
    n = len(state["cookies"])
    if n == 0:
        print("\n❌ 没解析出任何 cookie，请检查粘贴内容。", file=sys.stderr)
        sys.exit(1)

    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        _json.dump(state, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(AUTH_FILE, 0o600)
    except Exception:
        pass

    print(f"\n✅ 已解析 {n} 个 cookie，写入：{AUTH_FILE}（权限 600）")
    print(f"\n下一步验证是否可用：")
    print(f"  python3 {os.path.basename(__file__)}")
    print("\n若提示会话过期，说明 Cookie 抓得不完整或已失效，重新抓一次即可。")


# ------------------------------------------------------------------------------
#                          登录模式（有头，手动登录）
# ------------------------------------------------------------------------------
def _start_virtual_display():
    """在无显示器的服务器上启动 Xvfb 虚拟显示 + x11vnc，返回 (xvfb_proc, vnc_proc, display)"""
    import shutil

    xvfb_bin = shutil.which("Xvfb")
    vnc_bin = shutil.which("x11vnc")

    if not xvfb_bin or not vnc_bin:
        missing = []
        if not xvfb_bin:
            missing.append("Xvfb")
        if not vnc_bin:
            missing.append("x11vnc")
        mgr = "dnf" if os.path.exists("/usr/bin/dnf") else "yum"
        print(f"\n❌ 缺少: {', '.join(missing)}", file=sys.stderr)
        print(f"   安装: {mgr} install -y xorg-x11-server-Xvfb x11vnc\n", file=sys.stderr)
        return None, None, None

    display = ":99"
    vnc_port = "5999"

    xvfb = subprocess.Popen(
        [xvfb_bin, display, "-screen", "0", "1440x900x24", "-ac"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1)

    vnc = subprocess.Popen(
        [vnc_bin, "-display", display, "-localhost", "-nopw",
         "-rfbport", vnc_port, "-shared", "-forever"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1)

    return xvfb, vnc, display


def _stop_virtual_display(xvfb, vnc):
    for proc in (vnc, xvfb):
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()


def _get_login_credentials():
    """从环境变量、已保存文件、或终端交互获取 IAM 登录凭据"""
    import getpass as _getpass

    account_id = os.environ.get("BYTEPLUS_ACCOUNT_ID", "").strip()
    username = os.environ.get("BYTEPLUS_USER", "").strip()
    password = os.environ.get("BYTEPLUS_PASS", "").strip()

    if account_id and username and password:
        print("已从环境变量读取 IAM 登录凭据。")
        return account_id, username, password

    # 尝试从已保存的凭据文件读取
    saved = _load_saved_credentials()
    if saved:
        print("已从保存的凭据文件读取 IAM 登录信息。")
        return saved

    print("\n请输入 BytePlus IAM 登录凭据（密码不会回显）：\n")
    if not account_id:
        account_id = input("  主账号用户名 (Account ID): ").strip()
    if not username:
        username = input("  子账号用户名 (IAM User):   ").strip()
    if not password:
        password = _getpass.getpass("  密码:                      ").strip()

    if not account_id or not username or not password:
        print("❌ 凭据不完整，已取消。", file=sys.stderr)
        sys.exit(1)

    return account_id, username, password


def _derive_key():
    """v2 密钥：只绑定机器，不绑定脚本文件名。
    （老版本把 __file__ 写进密钥材料，重命名脚本会导致已保存凭据无法解密，
    这正是“没有保存的凭据”的根因之一。）"""
    import platform
    material = f"{platform.node()}|byteplus-quota-monitor|cred-v2"
    return hashlib.sha256(material.encode()).digest()


def _derive_key_legacy():
    """v1 兼容密钥：老版本密钥材料含脚本绝对路径（byteplus_quota_playwright.py）。
    仅用于读取老版本保存的 .credentials，读到后会自动迁移到 v2。"""
    import platform
    legacy_path = os.path.join(BASE_DIR, "byteplus_quota_playwright.py")
    material = f"{platform.node()}|{os.path.abspath(legacy_path)}|byteplus-quota-monitor"
    return hashlib.sha256(material.encode()).digest()


def _xor_bytes(data, key):
    """XOR 加密/解密"""
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _save_credentials(account_id, username, password):
    """加密保存凭据到隐藏文件 .credentials"""
    import json as _json
    plaintext = _json.dumps({
        "account_id": account_id, "username": username, "password": password
    }).encode("utf-8")
    encrypted = base64.b64encode(_xor_bytes(plaintext, _derive_key()))
    with open(CRED_FILE, "wb") as f:
        f.write(encrypted)
    try:
        os.chmod(CRED_FILE, 0o600)
    except Exception:
        pass
    log(f"凭据已加密保存：{CRED_FILE}（权限 600）")


def _load_saved_credentials():
    """从加密文件加载凭据，返回 (account_id, username, password) 或 None。
    先试 v2 密钥，再兼容 v1 老密钥（读到后自动迁移到 v2）。"""
    import json as _json
    if not os.path.exists(CRED_FILE):
        return None
    try:
        with open(CRED_FILE, "rb") as f:
            encrypted = f.read()
    except Exception:
        return None
    for key, is_legacy in ((_derive_key(), False), (_derive_key_legacy(), True)):
        try:
            plaintext = _xor_bytes(base64.b64decode(encrypted), key)
            data = _json.loads(plaintext.decode("utf-8"))
            acct = data.get("account_id", "").strip()
            user = data.get("username", "").strip()
            pwd = data.get("password", "").strip()
            if acct and user and pwd:
                if is_legacy:
                    try:
                        _save_credentials(acct, user, pwd)  # 迁移到 v2，下次直接读
                        log("已将老版本凭据迁移到新密钥")
                    except Exception:
                        pass
                return acct, user, pwd
        except Exception:
            continue
    return None



# ==========================================================================
# 滑块验证码自动破解模块（内联版，2026-10-09）
# 原 slider_solver.py 内容，原样内联于此，无需额外文件。
# 依赖：pip install opencv-python-headless numpy（缺依赖时自动跳过，不影响主流程）
# slider_solver.py — 拼图滑块验证码自动破解（尽力而为版）
# 
# 原理（GitHub 主流方案的通用做法）：
#   1. 截取验证码背景图
#   2. OpenCV 识别缺口位置（暗部列统计为主，Canny 边缘轮廓为辅）
#   3. 按「缺口左边缘 - 拼图块左边缘」算出图内拖动距离，映射到滑块轨道像素
#   4. 用「先加速后减速 + 抖动 + 轻微过冲回拉」的人类轨迹拖动
#      （匀速直线拖动会被行为检测直接判定为机器人）
#   5. 失败则点 Refresh 换一张，最多重试 max_attempts 次
# 
# 成功返回 True；任何一步失败返回 False，调用方继续走原有的人工/VNC/告警流程。
# 本模块是可选的：缺依赖（opencv/numpy）时自动跳过，不影响主脚本。
# 
# 依赖（服务器上装 headless 版，不需要图形库）：
#     pip install opencv-python-headless numpy
# 
# 调试：每次尝试会把带缺口标记的截图存为 slider_debug_attempt{N}.png（当前目录），
#      破解失败时把这张图发给开发者即可针对性调阈值。
import io
import math
import random
import re
import time

DEBUG_PREFIX = "slider_debug"


def _log(msg):
    print(f"[滑块破解] {msg}", flush=True)


def _try_import_cv():
    try:
        import cv2
        import numpy as np
        return cv2, np
    except ImportError:
        return None, None


# ------------------------------------------------------------------------------
# 元素定位（尽量通用，找不到就返回 None，不抛异常）
#
# 策略：先定位弹窗容器（role=dialog 或提示文字的祖先），再在容器内找元素。
# 字节第一方验证码是动态渲染的，背景图可能是 img / canvas / 带背景图的 div，
# 也可能整个弹窗在 iframe 里——逐层降级。
# ------------------------------------------------------------------------------
def _visible(el):
    try:
        return el.is_visible()
    except Exception:
        return False


def _find_modal(ctx):
    """定位验证码弹窗容器，找不到返回 None"""
    try:
        d = ctx.locator('[role="dialog"]').first
        if d.count() and _visible(d):
            return d
    except Exception:
        pass
    try:
        hint = ctx.get_by_text(
            re.compile(r"Drag the puzzle piece|Verify to continue", re.I)).first
        if hint.count():
            for xp in ("xpath=ancestor::*[@role='dialog'][1]",
                       "xpath=ancestor::div[6]",
                       "xpath=ancestor::div[5]",
                       "xpath=ancestor::div[4]"):
                try:
                    anc = hint.locator(xp).first
                    if anc.count() and _visible(anc):
                        return anc
                except Exception:
                    continue
    except Exception:
        pass
    return None


def _largest_img_canvas(scope):
    """scope 内最大的 img / canvas（宽>=200，高>=100），找不到返回 None"""
    try:
        cands = scope.locator("img, canvas")
        best, best_area = None, 0
        for i in range(min(cands.count(), 80)):
            el = cands.nth(i)
            try:
                if not el.is_visible():
                    continue
                b = el.bounding_box()
                if not b or b["width"] < 200 or b["height"] < 100:
                    continue
                a = b["width"] * b["height"]
                if a > best_area:
                    best, best_area = el, a
            except Exception:
                continue
        return best
    except Exception:
        return None


def _bg_div_clip(scope):
    """兜底：scope 内带背景图的最大 div，返回截图用的 clip 矩形（或 None）"""
    try:
        box = scope.evaluate("""(root) => {
          const els = root.querySelectorAll('div');
          let best = null, bestArea = 0;
          for (const el of els) {
            const r = el.getBoundingClientRect();
            if (r.width < 200 || r.height < 100 || r.width > 1200) continue;
            const cs = window.getComputedStyle(el);
            if (!cs.backgroundImage || cs.backgroundImage === 'none') continue;
            const area = r.width * r.height;
            if (area > bestArea) { best = el; bestArea = area; }
          }
          if (!best) return null;
          const r = best.getBoundingClientRect();
          return {x: r.x, y: r.y, width: r.width, height: r.height};
        }""")
        return box
    except Exception:
        return None


def _find_in_scope(ctx, scope):
    els = {"bg": None, "bg_clip": None, "track": None, "handle": None, "refresh": None}

    els["bg"] = _largest_img_canvas(scope)
    if not els["bg"]:
        els["bg_clip"] = _bg_div_clip(scope)

    # 轨道：包含提示文字的元素
    try:
        t = scope.get_by_text(re.compile(r"Drag the puzzle piece", re.I)).first
        if t.count() and _visible(t):
            els["track"] = t
    except Exception:
        pass

    # 手柄：常见类名 / role
    for sel in ("[role='slider']",
                "[class*='slider-button']",
                "[class*='move-block']",
                "[class*='slider-handle']",
                "[class*='drag-button']",
                "[class*='captcha-slider']"):
        try:
            h = scope.locator(sel).first
            if h.count() and _visible(h):
                b = h.bounding_box()
                if b and b["width"] < 140 and b["height"] < 140:
                    els["handle"] = h
                    break
        except Exception:
            continue

    # Refresh 换图按钮
    try:
        r = scope.get_by_text("Refresh", exact=False).first
        if r.count() and _visible(r):
            els["refresh"] = r
    except Exception:
        pass

    return els


def _find_elements(page):
    """返回 (els, 生效的 ctx)。
    顺序：主页面弹窗内 → 主页面全局 → 各 iframe 弹窗内 → iframe 全局。"""
    try:
        frames = [page] + [f for f in page.frames if f != page.main_frame]
    except Exception:
        frames = [page]
    for ctx in frames:
        modal = _find_modal(ctx)
        if modal is not None:
            els = _find_in_scope(ctx, modal)
            if els["bg"] or els.get("bg_clip"):
                if ctx is not page:
                    _log("验证码位于 iframe 内，已切换上下文")
                return els, ctx
        els = _find_in_scope(ctx, ctx)
        if els["bg"] or els.get("bg_clip"):
            if ctx is not page:
                _log("验证码位于 iframe 内，已切换上下文")
            return els, ctx
    return _find_in_scope(page, page), page


# ------------------------------------------------------------------------------
# 缺口 / 拼图块识别
# ------------------------------------------------------------------------------
def _detect_gap_x(img_bgr, cv2, np):
    """返回 (缺口左边缘 x（截图像素）, (方法名, bbox))。
    bbox=(x,y,w,h) 仅 contour 方法提供，供拼图块定位复用 y 高度带；失败返回 (None, (None, None))。

    优先级：白边轮廓 > 暗部列统计。真实验证码（字节 Turing）的缺口有白色描边，
    这是最可靠的特征；暗部列统计在风景图上容易被阴影/物体误报，只能做兜底。
    """
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    # 方法1（优先）：白边轮廓
    edges = cv2.Canny(gray, 80, 180)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if x < w * 0.12:
            continue  # 跳过左侧拼图块
        if x < 5 or y < 5 or x + cw > w - 5 or y + ch > h - 5:
            continue  # 贴着图片边缘的通常是背景轮廓，不是缺口
        area = cw * ch
        if area < (w * h) * 0.004 or area > (w * h) * 0.12:
            continue
        if cw < 15 or ch < 15:
            continue
        aspect = cw / max(ch, 1)
        if aspect < 0.6 or aspect > 1.6:
            continue  # 缺口接近正方形，过滤细长条背景
        if best is None or area > best[4]:
            best = (x, y, cw, ch, area)
    if best:
        return best[0], ("contour", best[:4])

    # 方法2（兜底）：暗部列统计 —— 取最宽的暗带（而非第一条），避开零星阴影误报
    dark = (gray < 55).astype(np.uint8)
    y0, y1 = int(h * 0.15), int(h * 0.85)   # 只看中间垂直带，避开装饰条
    col_dark = dark[y0:y1, :].sum(axis=0)
    start = int(w * 0.12)                    # 拼图块在最左侧，从 12% 处开始找
    peak = int(col_dark[start:].max())
    if peak >= 12:
        thresh = max(peak * 0.5, 12)
        best_run = None  # (width, start_x)
        rs, rl = None, 0
        for x in range(start, w + 1):
            if x < w and col_dark[x] >= thresh:
                if rs is None:
                    rs = x
                rl += 1
            else:
                if rl >= 8 and (best_run is None or rl > best_run[0]):
                    best_run = (rl, rs)
                rs, rl = None, 0
        if best_run and best_run[0] >= 20:   # 缺口应有一定宽度，过滤细条误报
            return best_run[1], ("darkcol", None)
    return None, (None, None)


def _detect_piece_left(img_bgr, cv2, np, y_band=None):
    """拼图块左边缘 x（截图像素）。

    方法1（优先）：白边框检测 —— 真实验证码的拼图块有白色描边；
    在缺口的 y 高度带内（两者等高），从左找第一列"白色像素密集"的列。
    方法2（兜底）：Canny 边缘列统计。
    找不到返回 0（块贴着左边缘是常见布局）。
    """
    h, w = img_bgr.shape[:2]

    # 方法1：白边框列检测
    if y_band:
        y0 = max(0, y_band[0] - 8)
        y1 = min(h, y_band[1] + 8)
        band = img_bgr[y0:y1, :int(w * 0.30)]
        white = ((band[:, :, 0] > 235) & (band[:, :, 1] > 235)
                 & (band[:, :, 2] > 235)).astype(np.uint8)
        col_white = white.sum(axis=0)
        need = int((y1 - y0) * 0.35)
        for x in range(col_white.shape[0]):
            if col_white[x] >= need:
                return x

    # 方法2：Canny 边缘列统计（兜底）
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 180)
    strip = edges[:, :int(w * 0.30)]
    col_edge = (strip > 0).sum(axis=0)
    need = int(h * 0.10)
    for x in range(strip.shape[1]):
        if col_edge[x] >= need:
            return x
    return 0


# ------------------------------------------------------------------------------
# 拟人拖动轨迹
# ------------------------------------------------------------------------------
def _human_drag(page, start_x, start_y, distance):
    """先加速后减速 + 抖动 + 轻微过冲回拉。"""
    overshoot = random.uniform(4, 9)
    target = distance + overshoot

    steps = random.randint(45, 75)
    raw = []
    for i in range(steps):
        t = i / steps
        v = math.sin(math.pi * t) ** 0.8      # 中间快、两头慢
        raw.append(v + random.uniform(0, 0.35))
    s = sum(raw)
    xs, acc = [], 0.0
    for v in raw:
        acc += target * v / s
        xs.append(acc)

    page.mouse.move(start_x, start_y)
    page.mouse.down()
    page.wait_for_timeout(random.randint(120, 260))   # 人手"抓住"后的短暂停顿
    for x in xs:
        page.mouse.move(start_x + x, start_y + random.uniform(-2, 2))
        page.wait_for_timeout(random.randint(8, 22))
    for back in (overshoot * 0.6, overshoot * 0.3, 0):  # 过冲回拉
        page.mouse.move(start_x + distance + back, start_y + random.uniform(-1.5, 1.5))
        page.wait_for_timeout(random.randint(60, 140))
    page.wait_for_timeout(random.randint(150, 350))
    page.mouse.up()


# ------------------------------------------------------------------------------
# 主入口
# ------------------------------------------------------------------------------
def _is_solved(page):
    """验证码是否已消失 / 已跳转"""
    try:
        url = page.url
        if "console.byteplus.com" in url and "signin" not in url and "login" not in url:
            return True
    except Exception:
        pass
    try:
        t = page.get_by_text(re.compile(r"Verify to continue|Drag the puzzle piece", re.I))
        if t.count() == 0:
            return True
        for i in range(t.count()):
            try:
                if t.nth(i).is_visible():
                    return False
            except Exception:
                continue
        return True
    except Exception:
        return False


def _click_refresh(page):
    try:
        r = page.get_by_text("Refresh", exact=False).first
        if r.count() and r.is_visible():
            r.click(timeout=3000)
            _log("已点击 Refresh 换图")
            return True
    except Exception as e:
        _log(f"点击 Refresh 失败：{e}")
    return False


def _save_debug(debug_dir, attempt, cv2, img_bgr, gap_x):
    try:
        import os
        dbg = img_bgr.copy()
        if gap_x is not None:
            cv2.line(dbg, (int(gap_x), 0), (int(gap_x), dbg.shape[0]), (0, 0, 255), 2)
        path = os.path.join(debug_dir, f"{DEBUG_PREFIX}_attempt{attempt}.png")
        cv2.imwrite(path, dbg)
        _log(f"调试截图已保存：{path}")
    except Exception:
        pass


def _attempt_once(page, cv2, np, attempt, debug_dir):
    els, ctx = _find_elements(page)
    if els["bg"]:
        box = els["bg"].bounding_box()
        png = els["bg"].screenshot()
        _log("背景图来源：img/canvas 元素截图")
    elif els.get("bg_clip"):
        box = els["bg_clip"]
        png = page.screenshot(clip=box)
        _log("背景图来源：div 背景图区域截图")
    else:
        _log("找不到验证码背景图（img/canvas/div 背景图均未命中）")
        return False
    if not box or box["width"] < 10:
        _log("背景图区域无效")
        return False
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        _log("背景图截图解码失败")
        return False
    sh, sw = img.shape[:2]
    _log(f"背景图：截图 {sw}x{sh}px，页面 {box['width']:.0f}x{box['height']:.0f}px")

    gap_x, method = _detect_gap_x(img, cv2, np)
    if gap_x is None:
        _log("缺口识别失败（两种方法都没找到）")
        _save_debug(debug_dir, attempt, cv2, img, None)
        return False
    gap_bbox = method[1]  # contour 方法提供 (x,y,w,h)，用于拼图块定位的 y 高度带
    y_band = (gap_bbox[1], gap_bbox[1] + gap_bbox[3]) if gap_bbox else None
    piece_left = _detect_piece_left(img, cv2, np, y_band)
    _log(f"缺口左边缘 x={gap_x}px（方法={method[0]}），拼图块左边缘 x={piece_left}px")
    _save_debug(debug_dir, attempt, cv2, img, gap_x)

    # 截图像素 → CSS 像素 → 轨道像素
    scale = sw / box["width"]
    dist_img_css = (gap_x - piece_left) / scale

    track_box = els["track"].bounding_box() if els["track"] else None
    track_w = track_box["width"] if track_box else box["width"]
    if not els["track"]:
        _log("找不到轨道元素，用背景图宽度估算")
    dist_track = dist_img_css * (track_w / box["width"])
    # 第一次之后加随机缩放抖动，避免系统性偏差导致连续失败
    jitter = random.uniform(0.97, 1.03) if attempt > 1 else 1.0
    dist_track *= jitter
    _log(f"拖动距离：图内 {dist_img_css:.1f}px → 轨道 {dist_track:.1f}px（抖动系数 {jitter:.3f}）")
    if dist_track < 20 or dist_track > track_w * 1.2:
        _log(f"拖动距离不合理（{dist_track:.1f}px），放弃本次")
        return False

    # 起点：手柄中心；找不到手柄就用轨道左侧
    if els["handle"]:
        hb = els["handle"].bounding_box()
        sx, sy = hb["x"] + hb["width"] / 2, hb["y"] + hb["height"] / 2
    elif track_box:
        sx, sy = track_box["x"] + 30, track_box["y"] + track_box["height"] / 2
    else:
        sx, sy = box["x"] + 30, box["y"] + box["height"] + 25
    _log(f"拖动起点 ({sx:.0f}, {sy:.0f})，开始拖动...")
    _human_drag(page, sx, sy, dist_track)

    page.wait_for_timeout(2500)
    if _is_solved(page):
        _log("验证通过！")
        return True
    _log("本次未通过")
    return False


def try_solve_slider(page, max_attempts=3, debug_dir=None):
    """尝试自动破解滑块验证码。成功返回 True，失败返回 False。

    page: Playwright 同步 Page 对象（验证码弹窗已出现时调用）
    max_attempts: 最多换图重试次数
    debug_dir: 调试截图保存目录，默认当前目录
    """
    import os
    cv2, np = _try_import_cv()
    if cv2 is None:
        _log("缺少 opencv/numpy，跳过自动破解（pip install opencv-python-headless numpy）")
        return False
    if debug_dir is None:
        debug_dir = os.getcwd()

    for attempt in range(1, max_attempts + 1):
        _log(f"第 {attempt}/{max_attempts} 次尝试...")
        try:
            if _attempt_once(page, cv2, np, attempt, debug_dir):
                return True
        except Exception as e:
            _log(f"本次尝试异常：{str(e)[:150]}")
        if attempt < max_attempts:
            if not _click_refresh(page):
                _log("找不到 Refresh 按钮，无法换图，停止重试")
                break
            page.wait_for_timeout(2000)
    _log("自动破解失败，交回上层处理（人工/VNC/告警）")
    return False
# ==========================================================================

def auto_relogin():
    """会话过期时自动重新登录，返回是否成功"""
    from playwright.sync_api import sync_playwright

    saved = _load_saved_credentials()
    if not saved:
        log("没有保存的凭据，无法自动重登")
        return False

    account_id, username, password = saved
    log("尝试自动重新登录...")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
        except Exception as e:
            log(f"浏览器启动失败: {e}")
            return False

        ctx = browser.new_context(
            user_agent=USER_AGENT, locale="zh-CN",
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()

        try:
            page.goto(FINANCE_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        except Exception:
            pass

        success, reason = _try_auto_login(page, account_id, username, password)

        if success:
            # 验证登录
            try:
                page.goto(FINANCE_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                page.wait_for_timeout(3000)
            except Exception:
                pass

            if "signin" not in page.url and "login" not in page.url:
                ctx.storage_state(path=AUTH_FILE)
                browser.close()
                try:
                    os.chmod(AUTH_FILE, 0o600)
                except Exception:
                    pass
                log("✅ 自动重登成功，auth.json 已刷新")
                return True

        browser.close()
        log(f"自动重登失败：{reason}")
        return False


def _try_auto_login(page, account_id, username, password):
    """尝试自动完成 IAM 登录（主账号 + 子账号 + 密码）。返回 (成功, 失败原因)"""

    # 等页面加载
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(2000)

    # 已经登录了（不在登录页）
    if "signin" not in page.url and "login" not in page.url:
        return True, None

    # 直接导航到 IAM 登录页（比从主登录页跳转更稳）
    # 判断依据：IAM 登录页有 #AccountInfo_input（主账号框），"欢迎回来"页没有
    on_iam_page = False
    try:
        on_iam_page = page.query_selector("#AccountInfo_input") is not None
    except Exception:
        pass

    if not on_iam_page:
        log("  跳转到 IAM 登录页...")
        # 优先点页面上的「IAM 子用户登录 / IAM user」链接
        try:
            iam_link_sel = ('a:has-text("IAM子用户登录"), a:has-text("IAM 子用户登录"), '
                            'a:has-text("IAM user"), a:has-text("IAM用户"), a:has-text("子用户")')
            iam_link = page.query_selector(iam_link_sel)
            if iam_link:
                iam_link.click()
                page.wait_for_timeout(2500)
        except Exception:
            pass
        # 点了还没到 IAM 页，或没找到链接 → 直接导航
        try:
            if page.query_selector("#AccountInfo_input") is None:
                page.goto(IAM_LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2500)
        except Exception:
            pass

    # ---- 关闭 Cookie 同意弹窗（会挡住登录按钮）----
    try:
        page.evaluate("""
            // 方法1：直接移除 cookiebanner
            const banner = document.getElementById('cookiebanner');
            if (banner) banner.remove();
            // 方法2：移除所有可能的遮罩
            document.querySelectorAll('[id*="cookie"], [class*="cookie-banner"], [class*="consent"]')
                .forEach(el => el.remove());
        """)
        page.wait_for_timeout(500)
        log("  ↳ 已清除 Cookie 弹窗")
    except Exception:
        pass

    # 再试一次点击弹窗上的按钮（有些弹窗移除不掉）
    try:
        consent_btns = [
            'button:has-text("Accept All")', 'button:has-text("Accept")',
            'button:has-text("同意")', 'button:has-text("Agree")',
            'button:has-text("OK")', 'button:has-text("Got it")',
            'button:has-text("Decline")', 'button:has-text("拒绝")',
        ]
        for sel in consent_btns:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                page.wait_for_timeout(500)
                log("  ↳ 已点击弹窗按钮")
                break
    except Exception:
        pass

    # ---- 填写三个字段 ----
    # IAM 登录页三个输入框有稳定的 id（从页面 HTML 确认）：
    #   主账号: #AccountInfo_input
    #   子账号: #UserIdentity_input
    #   密码:   #UserPassword_input
    # 优先按 id 精准定位；找不到再退回"按可见顺序"的兜底方案。
    log("  [1/4] 等待登录表单出现...")

    ACCT_SEL = "#AccountInfo_input"
    USER_SEL = "#UserIdentity_input"
    PASS_SEL = "#UserPassword_input"

    # 等主账号框出现，最多 25 秒（IAM 页面是 SPA，首次渲染较慢）
    form_ready = False
    for _ in range(50):
        try:
            if page.query_selector(ACCT_SEL) and page.query_selector(PASS_SEL):
                form_ready = True
                break
        except Exception:
            pass
        page.wait_for_timeout(500)

    def _set_value_by_sel(sel, val):
        el = page.query_selector(sel)
        if not el:
            return False
        try:
            el.click(timeout=3000)
            el.fill("", timeout=3000)
            el.type(val, delay=20, timeout=5000)
            if (el.input_value() or "") == val:
                return True
        except Exception:
            pass
        try:
            el.evaluate("""(el, val) => {
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, val);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""", val)
            return True
        except Exception:
            return False

    # 优先走 id 精准定位
    if form_ready:
        log("  [2/4] 填写主账号 / 子账号（按 id 定位）...")
        ok_acct = _set_value_by_sel(ACCT_SEL, account_id)
        page.wait_for_timeout(300)
        ok_user = _set_value_by_sel(USER_SEL, username)
        page.wait_for_timeout(300)
        log("  [3/4] 填写密码（按 id 定位）...")
        ok_pass = _set_value_by_sel(PASS_SEL, password)

        if ok_acct and ok_user and ok_pass:
            # id 定位成功，跳过下面的兜底逻辑
            pass_el = page.query_selector(PASS_SEL)
        else:
            log("  按 id 定位未完全成功，回退到顺序兜底...")
            form_ready = False  # 触发兜底

    # ---- 兜底：按可见顺序填（页面结构变化时用）----
    if not form_ready:
        def _visible_password_input():
            for el in page.query_selector_all('input[type="password"]'):
                try:
                    name = (el.get_attribute("name") or "").lower()
                    if "fake" in name or "remember" in name:
                        continue
                    try:
                        hidden = el.evaluate("""el => {
                            const s = window.getComputedStyle(el);
                            return s.display === 'none' || s.visibility === 'hidden';
                        }""")
                    except Exception:
                        hidden = False
                    if not hidden:
                        return el
                except Exception:
                    continue
            return None

        pass_el = None
        for _ in range(30):
            pass_el = _visible_password_input()
            if pass_el:
                break
            page.wait_for_timeout(500)

        if not pass_el:
            try:
                page.screenshot(path=os.path.join(BASE_DIR, "login_debug.png"), full_page=True)
                log(f"  已保存登录调试截图：{os.path.join(BASE_DIR, 'login_debug.png')}")
            except Exception:
                pass
            return False, "登录表单未出现（找不到可见的密码框，可能页面没加载出来）"

        page.wait_for_timeout(1000)

        def _visible_text_inputs():
            out = []
            for el in page.query_selector_all("input"):
                try:
                    itype = (el.get_attribute("type") or "text").lower()
                    if itype in ("password", "hidden", "checkbox", "radio", "submit", "button"):
                        continue
                    name = (el.get_attribute("name") or "").lower()
                    if "fake" in name or "remember" in name:
                        continue
                    try:
                        hidden = el.evaluate("""el => {
                            const s = window.getComputedStyle(el);
                            return s.display === 'none' || s.visibility === 'hidden'
                                   || el.offsetParent === null && s.position !== 'fixed';
                        }""")
                    except Exception:
                        hidden = False
                    if not hidden:
                        out.append(el)
                except Exception:
                    continue
            return out

        def _set_value(el, val):
            try:
                el.click(timeout=3000)
                el.fill("", timeout=3000)
                el.type(val, delay=20, timeout=5000)
                if (el.input_value() or "") == val:
                    return
            except Exception:
                pass
            el.evaluate("""(el, val) => {
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, val);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""", val)

        log("  [2/4] 填写主账号 / 子账号（顺序兜底）...")
        text_inputs = _visible_text_inputs()
        all_inputs = page.query_selector_all("input")
        log(f"  找到账号输入框 {len(text_inputs)} 个（页面 input 总数 {len(all_inputs)}）")
        if len(text_inputs) < 2:
            try:
                page.screenshot(path=os.path.join(BASE_DIR, "login_debug.png"), full_page=True)
                log(f"  已保存登录调试截图：{os.path.join(BASE_DIR, 'login_debug.png')}")
            except Exception:
                pass
            return False, f"登录页可见输入框不足 2 个（找到 {len(text_inputs)} 个），页面结构可能已变"

        _set_value(text_inputs[0], account_id)
        page.wait_for_timeout(300)
        _set_value(text_inputs[1], username)
        page.wait_for_timeout(300)
        log("  [3/4] 填写密码（顺序兜底）...")
        try:
            pass_el.click(timeout=3000)
            pass_el.fill("", timeout=3000)
            pass_el.type(password, delay=20, timeout=5000)
            if (pass_el.input_value() or "") != password:
                raise Exception("值未填入")
        except Exception:
            pass_el.evaluate("""(el, val) => {
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, val);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""", password)

    page.wait_for_timeout(300)

    # 勾选"记住我"（如果有且未勾选）
    try:
        remember = page.query_selector('input[type="checkbox"]')
        if remember and not remember.is_checked():
            remember.click()
    except Exception:
        pass

    page.wait_for_timeout(300)
    log("  [4/4] 点击登录按钮...")

    # 点登录按钮（force=True 绕过残留遮罩）
    try:
        btn_sel = 'button:has-text("登录"), button:has-text("Sign in"), button:has-text("Log in"), button[type="submit"]'
        page.click(btn_sel, timeout=5000, force=True)
    except Exception as e:
        return False, f"找不到登录按钮: {e}"

    log("  等待跳转到控制台...")

    # 等待跳转（最多 20 秒）
    for _ in range(40):
        page.wait_for_timeout(500)
        url = page.url
        if "console.byteplus.com" in url and "signin" not in url and "login" not in url:
            return True, None

    # 20 秒后仍在登录页 — 先看是不是弹了滑块验证码
    def _has_slider_captcha():
        try:
            body = page.inner_text("body")
        except Exception:
            body = ""
        kws = ["拖动", "滑动", "puzzle", "drag the puzzle", "verify to continue",
               "captcha", "验证码", "slider"]
        if any(k.lower() in body.lower() for k in kws):
            return True
        # 结构判断：常见滑块容器
        try:
            for sel in ('[class*="captcha"]', '[class*="slide"]', '[class*="puzzle"]',
                        '[id*="captcha"]', '[id*="slide"]'):
                el = page.query_selector(sel)
                if el and el.is_visible():
                    return True
        except Exception:
            pass
        return False

    # ================= 补丁：滑块验证码自动破解（新增） =================
    if _has_slider_captcha():
        # 先尝试自动破解滑块（OpenCV 识别缺口 + 拟人拖动）。
        # 尽力而为：成功则继续等待跳转；失败则走原有的关闭重试 / 人工逻辑。
        # 需要 pip install opencv-python-headless numpy；缺依赖时自动跳过。
        solved = False
        try:
            log("  检测到滑块验证码，尝试自动破解...")
            # try_solve_slider 已内联在本文件（滑块验证码自动破解模块）；
            # 缺 opencv/numpy 依赖时它内部会自动跳过并返回 False。
            solved = try_solve_slider(page, max_attempts=3)
        except Exception as e:
            log(f"  自动破解异常，跳过：{str(e)[:150]}")

        if solved:
            log("  滑块破解成功，继续等待跳转...")
            for _ in range(40):
                page.wait_for_timeout(500)
                url = page.url
                if "console.byteplus.com" in url and "signin" not in url and "login" not in url:
                    return True, None
            log("  破解后仍未跳转，继续分析页面状态...")
        elif not getattr(page, "_captcha_retried", False):
            log("  自动破解未成功，关闭弹窗并重新走 IAM 登录...")
            # 关闭滑块弹窗（点关闭图标 / 按 Esc / 移除遮罩）
            try:
                close_sel = ('.arco-modal-close-icon, [aria-label="Close"], '
                             'button:has-text("关闭"), .close, [class*="close-icon"]')
                btn = page.query_selector(close_sel)
                if btn:
                    btn.click(timeout=2000)
            except Exception:
                pass
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            page.wait_for_timeout(1000)

            # 重新导航到 IAM 登录页，重试一次登录
            try:
                page.goto(IAM_LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2500)
            except Exception:
                pass

            # 标记已重试，避免无限递归
            try:
                page._captcha_retried = True
            except Exception:
                pass
            return _try_auto_login(page, account_id, username, password)
        # else: 已重试过 → 落到下方正文分析，返回"需要人工操作"
    # =============== 补丁结束 ===============

    # 分析原因
    try:
        body = page.inner_text("body")
    except Exception:
        body = ""

    # 出错时存一张截图，方便排查（服务器上也能 scp 下来看）
    try:
        shot = os.path.join(BASE_DIR, "login_debug.png")
        page.screenshot(path=shot, full_page=True)
        log(f"  已保存登录调试截图：{shot}")
    except Exception:
        pass

    captcha_keywords = ["captcha", "验证码", "verify", "滑动", "拖动", "puzzle",
                        "recaptcha", "geetest", "human", "robot"]
    for kw in captcha_keywords:
        if kw.lower() in body.lower():
            return False, "检测到验证码（重试后仍出现），需要人工操作"

    error_keywords = ["incorrect", "wrong", "invalid", "错误", "失败", "不正确",
                      "not found", "不存在", "密码错误", "用户名"]
    for kw in error_keywords:
        if kw.lower() in body.lower():
            return False, "账号、用户名或密码错误"

    return False, "登录后未跳转到控制台（可能有验证码/二次验证，见 login_debug.png）"


def do_login():
    """登录并保存会话。自动登录优先，遇验证码/2FA 回退到 VNC 让用户手动过。"""
    from playwright.sync_api import sync_playwright

    account_id, username, password = _get_login_credentials()
    print("\n正在启动浏览器...")

    # 判断是否需要虚拟显示
    need_virtual = not _has_display()
    xvfb = vnc = None

    if need_virtual:
        # 先尝试纯无头自动登录（不需要 Xvfb）
        print("服务器环境（无图形界面），先尝试无头自动登录...")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
        except Exception as e:
            msg = str(e)
            if "shared libraries" in msg or "cannot open shared object" in msg:
                _print_missing_lib_help(e)
                sys.exit(1)
            raise

        ctx = browser.new_context(
            user_agent=USER_AGENT, locale="zh-CN",
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()

        try:
            page.goto(FINANCE_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        except Exception as e:
            print(f"打开页面失败: {e}", file=sys.stderr)

        # 尝试自动登录
        success, reason = _try_auto_login(page, account_id, username, password)

        if success:
            print("✅ 自动登录成功！")
        else:
            print(f"\n⚠️  自动登录未成功：{reason}")
            browser.close()

            # 回退到 VNC 模式
            if need_virtual:
                print("正在启动 VNC 远程桌面，让你手动完成登录...\n")
                xvfb, vnc_proc, display = _start_virtual_display()
                if not xvfb:
                    print("\n也可以改用 --import-cookie：", file=sys.stderr)
                    print(f"  python3 {os.path.basename(__file__)} --import-cookie\n", file=sys.stderr)
                    sys.exit(1)
                os.environ["DISPLAY"] = display

                try:
                    browser = p.chromium.launch(headless=False)
                except Exception as e:
                    _stop_virtual_display(xvfb, vnc_proc)
                    msg = str(e)
                    if "shared libraries" in msg or "cannot open shared object" in msg:
                        _print_missing_lib_help(e)
                    sys.exit(1)

                ctx = browser.new_context(
                    user_agent=USER_AGENT, locale="zh-CN",
                    viewport={"width": 1440, "height": 900},
                )
                page = ctx.new_page()
                page.goto(FINANCE_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)

                # 先自动填好账号密码，用户只需过验证码
                _try_auto_login(page, account_id, username, password)

                print("=" * 70)
                print(" VNC 远程桌面已就绪")
                print("=" * 70)
                print(f"\n 在你的电脑上执行 SSH 端口转发（新开一个终端）：")
                print(f"   ssh -L 5999:localhost:5999 root@<服务器IP>\n")
                print(f" 然后用 VNC 客户端连接：")
                print(f"   地址: localhost:5999")
                print(f"   Mac 自带: 打开 Finder → 前往 → 连接服务器 → vnc://localhost:5999\n")
                print(" 在 VNC 里完成验证码/二次验证，看到费用中心页面后")
                input(" 回到这里按 Enter 保存会话...")

            else:
                # 有图形界面（Mac）才重开有头浏览器让用户手动完成
                if _has_display():
                    print("重新打开浏览器，请手动完成登录...\n")
                    browser = p.chromium.launch(headless=False)
                    ctx = browser.new_context(
                        user_agent=USER_AGENT, locale="zh-CN",
                        viewport={"width": 1440, "height": 900},
                    )
                    page = ctx.new_page()
                    page.goto(FINANCE_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                    _try_auto_login(page, account_id, username, password)

                    print(">>> 请在浏览器中完成验证码/二次验证。")
                    input(">>> 登录完成后按 Enter 保存会话...")
                else:
                    # 服务器无图形界面，且 Xvfb/x11vnc 也没装 → 直接退出，不要崩
                    print("\n❌ 自动登录失败，且当前无图形界面、未装 VNC 组件。", file=sys.stderr)
                    print("   排查建议：", file=sys.stderr)
                    print(f"   1. 查看登录调试截图：{os.path.join(BASE_DIR, 'login_debug.png')}", file=sys.stderr)
                    print("      scp 到本地打开看卡在哪一步", file=sys.stderr)
                    print("   2. 若是验证码，装 VNC 组件后重试：", file=sys.stderr)
                    print("      dnf install -y xorg-x11-server-Xvfb x11vnc", file=sys.stderr)
                    print("   3. 或改用 --import-cookie 从浏览器抓 Cookie 生成会话", file=sys.stderr)
                    sys.exit(1)

        # 验证登录状态
        try:
            page.goto(FINANCE_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
            page.wait_for_timeout(3000)
        except Exception:
            pass

        if "signin" in page.url or "login" in page.url:
            print("\n❌ 登录未成功（仍在登录页），会话未保存。", file=sys.stderr)
            browser.close()
            if need_virtual:
                _stop_virtual_display(xvfb, vnc)
            sys.exit(1)

        ctx.storage_state(path=AUTH_FILE)
        browser.close()

    if need_virtual:
        _stop_virtual_display(xvfb, vnc)

    try:
        os.chmod(AUTH_FILE, 0o600)
    except Exception:
        pass

    # 保存凭据，会话过期时自动重登用
    _save_credentials(account_id, username, password)

    print(f"\n✅ 会话已保存：{AUTH_FILE}（权限 600）")
    print(f"\n   下一步验证：python3 {os.path.basename(__file__)}")
    print(f"   挂定时任务：python3 {os.path.basename(__file__)} --install-cron")


# ------------------------------------------------------------------------------
#                        取额度（无头，加载持久化会话）
# ------------------------------------------------------------------------------
def _parse_from_payload(data):
    """从 GetQuotaAcctInfo 响应 JSON 取额度"""
    result = (data or {}).get("Result") or {}
    raw = result.get("AvailableBalance") or result.get("Balance")
    if raw is None:
        return None, None
    try:
        return float(raw), result.get("AccountID", "未知")
    except (TypeError, ValueError):
        return None, None


def _parse_from_dom(page):
    """兜底：接口未拦截到时，从页面文本正则提取 Quota 金额（中英文界面均支持）"""
    try:
        text = page.inner_text("body")
    except Exception:
        return None, None
    m = re.search(r"(?:Quota|信控额度)[\s\S]{0,120}?\$\s*([\d,]+\.\d{2})", text)
    if not m:
        return None, None
    return float(m.group(1).replace(",", "")), "未知(DOM解析)"


def _extract_cookies_for_requests():
    """从 auth.json 提取 cookies,供 requests 轻量查询用"""
    import json as _json
    if not os.path.exists(AUTH_FILE):
        return None
    try:
        with open(AUTH_FILE, encoding="utf-8") as f:
            state = _json.load(f)
        cookies = {}
        for c in state.get("cookies", []):
            cookies[c["name"]] = c["value"]
        if not cookies:
            return None
        return cookies
    except Exception:
        return None


def _extract_csrf_from_cookies(cookies):
    """从 cookies 里找 CSRF token（BytePlus 通常叫 volc_oauth_security_token_v2）"""
    for name in ("volc_oauth_security_token_v2", "csrf_token", "x-csrf-token"):
        if name in cookies:
            return cookies[name]
    return ""


def fetch_quota_light():
    """轻量查询：用 requests 直接调内部接口,不启动浏览器。
    成功返回 (balance, account_id)，失败返回 None。"""
    import requests as _req

    cookies = _extract_cookies_for_requests()
    if not cookies:
        return None

    csrf = _extract_csrf_from_cookies(cookies)
    url = f"https://{CONSOLE_HOST}/api/top/bill/{REGION}/{VERSION}/{ACTION_KEYWORD}"
    headers = {
        "Accept": "application/json",
        "X-Csrf-Token": csrf,
        "X-Language": "zh",
        "Referer": FINANCE_URL,
        "User-Agent": USER_AGENT,
    }

    try:
        resp = _req.get(url, headers=headers, cookies=cookies,
                        timeout=15, allow_redirects=False)

        if resp.status_code in (301, 302, 303, 307, 308, 401, 403):
            return None  # 会话过期
        if "application/json" not in resp.headers.get("Content-Type", ""):
            return None

        data = resp.json()
        result = data.get("Result")
        if not result:
            return None

        raw = result.get("AvailableBalance") or result.get("Balance")
        if raw is None:
            return None
        return float(raw), result.get("AccountID", "未知")
    except Exception:
        return None


def fetch_quota():
    """返回 (balance, account_id)；会话失效抛 SessionExpired。
    优先用轻量 requests，失败才启动 Playwright。"""

    # ---- 第一层：轻量 requests（毫秒级，无浏览器）----
    result = fetch_quota_light()
    if result is not None:
        log("额度来源：轻量接口查询（requests）")
        return result

    log("轻量查询未成功，启动浏览器验证...")

    # ---- 第二层：Playwright（确认是否真的过期）----
    from playwright.sync_api import sync_playwright

    if not os.path.exists(AUTH_FILE):
        raise SessionExpired(f"找不到会话文件 {AUTH_FILE}，请先在本地执行 --login")

    captured = {}

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
        except Exception as e:
            if "shared libraries" in str(e) or "cannot open shared object" in str(e):
                _print_missing_lib_help(e)
                raise RuntimeError(f"Chromium 缺少系统库，无法启动: {str(e)[:150]}")
            raise
        try:
            ctx = browser.new_context(
                storage_state=AUTH_FILE,
                user_agent=USER_AGENT,
                locale="zh-CN",
                viewport={"width": 1440, "height": 900},
            )
        except Exception as e:
            browser.close()
            raise SessionExpired(f"会话文件无法加载（可能损坏，请重新 --login）: {e}")

        page = ctx.new_page()

        def on_response(resp):
            if ACTION_KEYWORD in resp.url:
                try:
                    captured["data"] = resp.json()
                except Exception:
                    pass

        page.on("response", on_response)

        try:
            page.goto(FINANCE_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        except Exception as e:
            browser.close()
            raise RuntimeError(f"打开费用中心失败: {e}")

        # 等接口返回（最多 API_WAIT_SECONDS 秒）
        deadline = time.time() + API_WAIT_SECONDS
        while time.time() < deadline:
            if "data" in captured:
                break
            if "signin" in page.url or "login" in page.url:
                break
            page.wait_for_timeout(500)

        # 被踢回登录页 = 会话过期
        if "signin" in page.url or "login" in page.url:
            browser.close()
            raise SessionExpired("被重定向到登录页，storage_state 已过期")

        balance = account_id = None

        # 主路径：拦截到的接口响应
        if "data" in captured:
            balance, account_id = _parse_from_payload(captured["data"])
            if balance is not None:
                log("额度来源：接口响应")

        # 兜底路径：页面 DOM
        if balance is None:
            page.wait_for_timeout(3000)
            balance, account_id = _parse_from_dom(page)
            if balance is not None:
                log("额度来源：页面 DOM 兜底解析")

        browser.close()

    if balance is None:
        raise SessionExpired(
            "未能获取额度（接口无响应且页面无法解析），可能会话已失效或页面结构变更"
        )

    return balance, account_id


# ------------------------------------------------------------------------------
#                            告警冷却控制
# ------------------------------------------------------------------------------
def _should_alert():
    """检查是否应该发送告警（冷却期内不重复发）"""
    if not os.path.exists(ALERT_STATE_FILE):
        return True
    try:
        mtime = os.path.getmtime(ALERT_STATE_FILE)
        elapsed_hours = (time.time() - mtime) / 3600
        return elapsed_hours >= ALERT_COOLDOWN_HOURS
    except Exception:
        return True


def _record_alert():
    """记录本次告警时间"""
    try:
        with open(ALERT_STATE_FILE, "w") as f:
            f.write(datetime.now().isoformat())
    except Exception:
        pass


def _clear_alert():
    """额度恢复正常时清除告警状态（下次再低于阈值立刻告警）"""
    try:
        if os.path.exists(ALERT_STATE_FILE):
            os.remove(ALERT_STATE_FILE)
    except Exception:
        pass


# ---- 连续重登失败计数 ----
def _get_fail_count():
    """读取当前连续失败次数"""
    if not os.path.exists(FAIL_COUNT_FILE):
        return 0
    try:
        with open(FAIL_COUNT_FILE) as f:
            return int(f.read().strip() or "0")
    except Exception:
        return 0


def _incr_fail_count():
    """失败次数 +1，返回累计值"""
    n = _get_fail_count() + 1
    try:
        with open(FAIL_COUNT_FILE, "w") as f:
            f.write(str(n))
    except Exception:
        pass
    return n


def _reset_fail_count():
    """重登成功后清零"""
    try:
        if os.path.exists(FAIL_COUNT_FILE):
            os.remove(FAIL_COUNT_FILE)
    except Exception:
        pass


# ---- 会话告警状态：标记是否已发过"需人工介入"告警，用于发恢复通知 ----
def _mark_session_alerted():
    try:
        with open(SESSION_ALERTED_FILE, "w") as f:
            f.write(datetime.now().isoformat())
    except Exception:
        pass


def _was_session_alerted():
    return os.path.exists(SESSION_ALERTED_FILE)


def _clear_session_alerted():
    try:
        if os.path.exists(SESSION_ALERTED_FILE):
            os.remove(SESSION_ALERTED_FILE)
    except Exception:
        pass


# ---- 额度告警"是否处于低额状态"标记，用于恢复通知 ----
def _is_in_low_state():
    return os.path.exists(ALERT_STATE_FILE)


# ------------------------------------------------------------------------------
#                                主监控流程
# ------------------------------------------------------------------------------
def run_monitor():
    import random

    # 随机延迟 0~120 秒，避免每次精确整点请求（降低风控风险）
    if not sys.stdin.isatty():  # cron 环境才延迟，手动执行不等
        delay = random.randint(0, 120)
        log(f"随机延迟 {delay} 秒...")
        time.sleep(delay)

    log("开始检查 BytePlus 信控额度...")

    try:
        balance, account_id = fetch_quota()
    except SessionExpired as e:
        log(f"会话已过期: {e}")
        log("自动重新登录中（使用保存的凭据）...")

        # 尝试自动重登
        if auto_relogin():
            _reset_fail_count()   # 重登成功，清零失败计数
            try:
                balance, account_id = fetch_quota()
                # 如果此前发过"需人工介入"告警，现在恢复了 → 发恢复通知
                if _was_session_alerted():
                    log("此前已告警，现已恢复，发送恢复通知")
                    notify_session_recovered(balance, account_id)
                    _clear_session_alerted()
                _evaluate_quota(balance, account_id)
                return
            except Exception as e2:
                log(f"重登后查询仍失败: {e2}")

        # 自动重登失败 → 累加失败次数，达到阈值才告警
        fails = _incr_fail_count()
        log(f"自动重登失败（连续第 {fails}/{MAX_RELOGIN_FAILURES} 次）")
        if fails >= MAX_RELOGIN_FAILURES:
            if ENABLE_FAILURE_ALERT:
                log("连续失败达到阈值，通知人工介入")
                notify_session_expired(e, fails)
                _mark_session_alerted()   # 记录已告警，恢复时好发通知
            else:
                log("连续失败达到阈值（失败告警已临时关闭，只记录不推送）")
        else:
            log(f"未达告警阈值（{MAX_RELOGIN_FAILURES} 次），暂不打扰（多为验证码等瞬时故障，下次大概率自愈）")
        sys.exit(2)
    except Exception as e:
        log(f"查询异常: {e}")
        if ENABLE_FAILURE_ALERT:
            notify_error(e)
        else:
            log("查询异常告警已临时关闭，只记录不推送")
        sys.exit(1)

    # 查询成功 → 清零失败计数
    _reset_fail_count()
    # 若此前发过"需人工介入"告警（例如上次滑块过不去），现在直接查通了 → 发恢复通知
    if _was_session_alerted():
        log("此前已告警，现已恢复，发送恢复通知")
        notify_session_recovered(balance, account_id)
        _clear_session_alerted()
    _evaluate_quota(balance, account_id)


def _evaluate_quota(balance, account_id):
    """判断额度是否告警 / 恢复"""
    log(f"当前信控额度: ${balance:,.2f} USD  (账户 {account_id})")

    if balance < THRESHOLD:
        if _should_alert():
            log(f"低于阈值 ${THRESHOLD:,.0f}，触发告警")
            notify_quota_low(balance, account_id)
            _record_alert()
        else:
            log(f"低于阈值但在 {ALERT_COOLDOWN_HOURS}h 冷却期内，跳过重复告警")
    else:
        # 如果之前处于低额告警状态，现在恢复了 → 发恢复通知
        if _is_in_low_state():
            log("额度已从低于阈值恢复正常，发送恢复通知")
            notify_quota_recovered(balance, account_id)
        _clear_alert()
        log(f"额度充足，未触发告警（阈值 ${THRESHOLD:,.0f}）")


# ------------------------------------------------------------------------------
#                              辅助命令
# ------------------------------------------------------------------------------
def report_quota():
    """手动查一次额度并推送钉钉（干净版，不含测试排查内容）"""
    log("查询当前信控额度...")
    try:
        balance, account_id = fetch_quota()
    except SessionExpired as e:
        log(f"会话已过期，尝试自动重登: {e}")
        if auto_relogin():
            balance, account_id = fetch_quota()
        else:
            log("自动重登失败，请在服务器执行 --login")
            send_dingtalk(
                f"### ⚠️ 手动查询失败\n\n无法获取额度（会话过期且自动重登失败）。\n\n"
                f"> 错误：{str(e)[:150]}\n"
                f"> 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                title="BytePlus 手动查询失败",
            )
            return
    except Exception as e:
        log(f"查询失败: {e}")
        send_dingtalk(
            f"### ⚠️ 手动查询失败\n\n错误：`{str(e)[:200]}`\n\n"
            f"> 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            title="BytePlus 手动查询失败",
        )
        return

    status = "🟢 充足" if balance >= THRESHOLD else "🔴 不足"
    send_dingtalk(
        f"### 📊 BytePlus 信控额度\n\n"
        f"当前可用额度：**${balance:,.2f} USD**\n\n"
        f"预警阈值：${THRESHOLD:,.0f} USD　|　状态：{status}\n\n"
        f"> 账户ID：{account_id}\n"
        f"> 查询时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        title="BytePlus 信控额度",
    )
    log(f"已推送钉钉：${balance:,.2f} USD（{status}）")


def test_dingtalk():
    """完整测试：查额度 + 发钉钉，任何一步失败都说明原因"""

    # 1. 检查钉钉配置
    log("=" * 50)
    log("步骤 1/3：检查钉钉配置")
    if "在这里填" in DINGTALK_WEBHOOK or "在这里填" in DINGTALK_SECRET:
        log("❌ 钉钉未配置！")
        log("")
        log("请修改脚本顶部配置区的两个值：")
        log(f"  文件：{os.path.abspath(__file__)}")
        log("")
        log('  DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=你的token"')
        log('  DINGTALK_SECRET  = "SEC开头的加签密钥"')
        log("")
        log("获取方式：钉钉群 → 群设置 → 智能群助手 → 添加自定义机器人")
        log("         安全设置选「加签」→ 拿到 Webhook 和 SEC 密钥")
        return

    log("✅ 钉钉 Webhook 和密钥已填写")

    # 2. 查询额度
    log("")
    log("步骤 2/3：查询 BytePlus 信控额度")
    balance = None
    account_id = None
    try:
        balance, account_id = fetch_quota()
        log(f"✅ 查询成功：${balance:,.2f} USD（账户 {account_id}）")
    except SessionExpired as e:
        log(f"❌ 会话已过期：{e}")
        log("   请先执行：python3 byteplus_quota_playwright.py --login")
        return
    except Exception as e:
        log(f"❌ 查询失败：{e}")
        return

    # 3. 发送钉钉
    log("")
    log("步骤 3/3：发送钉钉消息")
    status = "🟢 充足" if balance >= THRESHOLD else "🔴 不足"
    send_dingtalk(
        f"### ✅ BytePlus 监控测试 + 额度报告\n\n"
        f"当前信控额度：**${balance:,.2f} USD**\n\n"
        f"告警阈值：**${THRESHOLD:,.0f} USD**\n\n"
        f"状态：{status}\n\n"
        f"> 账户ID：{account_id}\n"
        f"> 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"---\n"
        f"如果你在钉钉看到这条消息，说明整条链路（登录→查额度→推钉钉）全部正常。",
        title="BytePlus 监控测试",
    )
    log("完成！如果钉钉没收到消息，请检查：")
    log("  1. 机器人安全设置是否选了「加签」（不是关键词/IP）")
    log("  2. SEC 密钥是否复制完整")
    log("  3. 服务器能否访问 oapi.dingtalk.com")


def install_cron():
    """把定时任务写入当前用户的 crontab"""
    script_path = os.path.abspath(__file__)
    workdir = os.path.dirname(script_path)
    python_bin = sys.executable or "/usr/bin/python3"
    log_path = os.path.join(workdir, "quota.log")

    entry = (f"{CRON_SCHEDULE} cd {workdir} && {python_bin} {script_path} "
             f">> {log_path} 2>&1")

    print("将要添加的 crontab 条目：\n")
    print(f"  {entry}\n")

    try:
        existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        current = existing.stdout if existing.returncode == 0 else ""
    except FileNotFoundError:
        print("❌ 找不到 crontab 命令，请手动添加上面这行。", file=sys.stderr)
        return

    if script_path in current:
        print("⚠️  crontab 中已存在本脚本的任务，未重复添加。")
        print("   如需修改请手动执行: crontab -e")
        return

    answer = input("确认添加到 crontab？[y/N] ").strip().lower()
    if answer != "y":
        print("已取消。你可以手动执行 crontab -e 添加上面那行。")
        return

    new_content = (current.rstrip("\n") + "\n" + entry + "\n") if current.strip() else entry + "\n"
    proc = subprocess.run(["crontab", "-"], input=new_content, text=True)
    if proc.returncode == 0:
        print("✅ 定时任务已添加。查看：crontab -l")
        print(f"   日志输出：{log_path}")
    else:
        print("❌ 添加失败，请手动执行 crontab -e", file=sys.stderr)


# ------------------------------------------------------------------------------
#                                  入口
# ------------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="BytePlus 信控额度监控 → 钉钉告警 (Playwright 持久化会话版)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "常用流程:\n"
            "  1. python3 %(prog)s --check           检查依赖和配置\n"
            "  2. python3 %(prog)s --test-dingtalk   测试钉钉机器人\n"
            "  3. python3 %(prog)s --login           本地手动登录，生成 auth.json\n"
            "  4. python3 %(prog)s                   运行一次监控\n"
            "  5. python3 %(prog)s --install-cron    安装定时任务\n"
        ),
    )
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--login", action="store_true",
                   help="自动登录获取会话（输入账号密码，遇验证码自动回退 VNC）")
    g.add_argument("--import-cookie", action="store_true",
                   help="从 Cookie 生成 auth.json（无需图形界面；支持交互/文件/管道输入）")
    g.add_argument("--check", action="store_true",
                   help="检查依赖是否安装、配置是否填写")
    g.add_argument("--test-dingtalk", action="store_true",
                   help="发送一条钉钉测试消息")
    g.add_argument("--report", action="store_true",
                   help="立即查询当前额度并推送钉钉（干净版）")
    g.add_argument("--install-cron", action="store_true",
                   help="把定时任务写入 crontab")
    parser.add_argument("--cookie-file", metavar="PATH", default=None,
                        help="配合 --import-cookie：从指定文件读取 Cookie，免交互")
    args = parser.parse_args()

    if args.check:
        sys.exit(0 if check_deps() else 1)
    if args.test_dingtalk:
        test_dingtalk()
    elif args.report:
        report_quota()
    elif args.login:
        do_login()
    elif args.import_cookie:
        import_cookie(cookie_file=args.cookie_file)
    elif args.install_cron:
        install_cron()
    else:
        run_monitor()


if __name__ == "__main__":
    main()
