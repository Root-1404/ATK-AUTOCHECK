import requests
import os
import jwt
import time
import datetime
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ========== 基础配置 ==========
token = os.getenv("ATK_TOKEN", "")
if not token:
    print("❌ 未读取到ATK_TOKEN，请检查环境变量配置")
    exit(1)

headers = {
    "Authorization": f"Bearer {token}",
    "Origin": "https://www.atkgear.com.cn",
    "Referer": "https://www.atkgear.com.cn/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "client-type": "atk",
    "env": "prod"
}

# ========== 工具函数 ==========
def parse_jwt_remain_time(jwt_token: str):
    """解析JWT剩余有效期"""
    try:
        payload = jwt.decode(jwt_token, options={"verify_signature": False})
        exp_ts = payload.get("exp")
        now_ts = int(time.time())
        remain_sec = exp_ts - now_ts
        if remain_sec <= 0:
            return 0, 0
        days = remain_sec // 86400
        hours = (remain_sec % 86400) // 3600
        return days, hours
    except Exception as e:
        print(f"⚠️ JWT解析异常: {str(e)}")
        return None, None

def send_alert_email(alert_title, alert_content):
    """邮件预警：仅GitHub Actions环境触发，失败不影响主流程"""
    if not os.getenv("GITHUB_ACTIONS"):
        print(f"📧 本地运行，跳过邮件发送: {alert_title}")
        return
    smtp_server = os.getenv("SMTP_SERVER", "smtp.qq.com")
    sender = os.getenv("SMTP_SENDER", "")
    auth_code = os.getenv("SMTP_AUTH_CODE", "")
    receiver = os.getenv("SMTP_RECEIVER", sender)
    if not sender or not auth_code:
        print("⚠️ 未配置SMTP参数，跳过邮件预警")
        return
    try:
        msg = MIMEText(
            f"ATK签到任务告警\n\n{alert_content}\n\n告警时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "plain", "utf-8"
        )
        msg["From"] = Header(f"ATK签到机器人 <{sender}>")
        msg["To"] = Header(receiver)
        msg["Subject"] = Header(f"【ATK签到预警】{alert_title}")
        smtp = smtplib.SMTP_SSL(smtp_server, 465)
        smtp.login(sender, auth_code)
        smtp.sendmail(sender, receiver, msg.as_string())
        smtp.quit()
        print(f"✅ 预警邮件已发送至 {receiver}")
    except Exception as e:
        print(f"⚠️ 邮件发送失败: {str(e)}")

def get_checkin_stats():
    """获取签到统计"""
    url = "https://api.vxe.com/v1/member/checkin/stats"
    resp = requests.get(url, headers=headers, timeout=20)
    return resp.json()

def get_member_profile():
    """获取用户积分信息"""
    url = "https://api.vxe.com/v1/member/profile"
    resp = requests.get(url, headers=headers, timeout=20)
    return resp.json()

def do_checkin():
    """提交签到请求"""
    url = "https://api.vxe.com/v1/member/checkin"
    resp = requests.post(url, headers=headers, timeout=20)
    return resp.json()

def clean_old_screenshots(save_dir="./screenshots", keep_count=1):
    """清理旧截图，只保留最新1组"""
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        return
    file_list = []
    for fname in os.listdir(save_dir):
        if fname.lower().endswith(".png"):
            full_path = os.path.join(save_dir, fname)
            mtime = os.path.getmtime(full_path)
            file_list.append((mtime, full_path))
    file_list.sort(key=lambda x: x[0])
    remove_num = len(file_list) - keep_count
    if remove_num > 0:
        for i in range(remove_num):
            _, path = file_list[i]
            os.remove(path)
            print(f"🧹 删除旧截图: {os.path.basename(path)}")

# ========== 截图函数 ==========
def take_status_screenshot_by_html(stats_data, profile_data, remain_days, remain_hours, note_text="", save_dir="./screenshots"):
    """本地生成清晰状态卡片截图（不受网页加载影响）"""
    os.makedirs(save_dir, exist_ok=True)
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    save_file = os.path.join(save_dir, f"atk_status_{now_str}.png")
    html_path = os.path.join(save_dir, "temp.html")

    d = stats_data.get("data", {})
    p_data = profile_data.get("data", {})
    available_point = p_data.get("quantity", "获取失败")
    expire_point = p_data.get("aboutExpireQuantity", 0)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <title>ATK签到状态</title>
        <style>
            body {{font-family:system-ui;background:#1a1a1a;color:#fff;padding:30px;font-size:18px;}}
            .box {{border:1px solid #444;border-radius:12px;padding:24px;max-width:600px;margin:0 auto;}}
            .ok {{color:#4cd964;}}
            .no {{color:#ff3b30;}}
            .info {{color:#74b9ff;}}
            .card {{border:1px solid #EEE;border-radius:8px;padding:16px;margin-bottom:20px;background:#222;}}
            .card-title {{font-size:16px;color:#aaa;margin-bottom:8px;}}
            .card-value {{font-size:32px;font-weight:bold;}}
            .note {{padding:8px;border-radius:6px;background:#333;margin:10px 0;color:#ffd166;}}
        </style>
    </head>
    <body>
        <div class="box">
            <h2>ATK Gear 签到状态</h2>
            {f'<div class="note">执行备注：{note_text}</div>' if note_text else ''}
            <div class="card">
                <div class="card-title">可用积分</div>
                <div class="card-value">{available_point}</div>
            </div>
            <p>即将过期积分：{expire_point}</p>
            <p>今日已签到：<span class="{'ok' if d.get('isCheckedInToday') else 'no'}">{d.get('isCheckedInToday')}</span></p>
            <p>累计签到天数：{d.get('totalDays')}</p>
            <p>当前连续签到：{d.get('currentConsecutiveDays')}</p>
            <p>最大连续签到：{d.get('maxConsecutiveDays')}</p>
            <p>总积分：{d.get('totalPoints')}</p>
            <p>上次签到日期：{d.get('lastCheckinDate')}</p>
            <p>下次奖励：{d.get('nextRewardDays')}天后，+{d.get('nextRewardPoints')}积分</p>
            <p class="info">Token有效期剩余：{remain_days} 天 {remain_hours} 小时</p>
            <p>截图时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </body>
    </html>
    """
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"file://{os.path.abspath(html_path)}")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=save_file, full_page=True)
        browser.close()
    os.remove(html_path)
    print(f"📊 状态卡片截图已保存: {save_file}")
    return save_file

def take_sign_popup_screenshot(save_dir="./screenshots"):
    """精准截取签到日历弹窗（优化超时+拦截无关请求+自动点击按钮）"""
    os.makedirs(save_dir, exist_ok=True)
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    save_file = os.path.join(save_dir, f"atk_sign_popup_{now_str}.png")
    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=headers["User-Agent"],
                locale="zh-CN"
            )

            # 拦截请求：注入鉴权头，阻断第三方统计加速加载
            def intercept_request(route):
                req_headers = route.request.headers
                if "api.vxe.com" in route.request.url:
                    req_headers["Authorization"] = f"Bearer {token}"
                    req_headers["client-type"] = "atk"
                    req_headers["env"] = "prod"
                if any(block in route.request.url for block in ["hm.baidu", "google-analytics", "doubleclick", "cnzz"]):
                    return route.abort()
                route.continue_(headers=req_headers)
            context.route("**/*", intercept_request)

            page = context.new_page()
            # 只等DOM加载，不等待所有静态资源
            try:
                page.goto(
                    "https://www.atkgear.com.cn/pointmall/mallcenter",
                    wait_until="domcontentloaded",
                    timeout=30000
                )
            except PlaywrightTimeout:
                print("⚠️ 页面加载超时，DOM已就绪，继续尝试截图")
            page.wait_for_timeout(5000)  # 等Vue组件渲染

            # 点击「签到日历」按钮弹出弹窗
            try:
                sign_btn = page.locator("div:has-text('签到日历'):visible").first
                sign_btn.click(timeout=8000)
                print("✅ 成功点击签到日历按钮")
                page.wait_for_timeout(3000)
            except Exception as e:
                print(f"ℹ️ 未找到签到日历按钮: {str(e)}")

            # 定位精准弹窗元素截图
            try:
                popup = page.locator("div[data-v-22e9525c].relative.bg-white.shadow-lg").first
                popup.wait_for(state="visible", timeout=10000)
                popup.screenshot(path=save_file)
                print("✅ 成功截取签到日历弹窗")
            except PlaywrightTimeout:
                print("⚠️ 弹窗未加载，截取当前页面兜底")
                page.screenshot(path=save_file, full_page=False)

            browser.close()
        print(f"🌐 签到弹窗截图已保存: {save_file}")
        return save_file
    except Exception as e:
        print(f"⚠️ 签到弹窗截图失败（不影响签到主流程）: {str(e)}")
        if browser:
            try:
                browser.close()
            except:
                pass
        return None

# ========== 主流程 ==========
if __name__ == "__main__":
    alert_messages = []  # 收集所有异常，最后汇总发邮件

    # 1. Token有效期检查
    remain_days, remain_hours = parse_jwt_remain_time(token)
    if remain_days is not None:
        if remain_days <=0 and remain_hours <=0:
            warn = "⚠️ JWT Token已经过期！请立刻更新Token！"
            print(warn)
            alert_messages.append(warn)
        else:
            print(f"🔐 Token有效期剩余：{remain_days} 天 {remain_hours} 小时")
            if remain_days < 3:
                warn = f"❗ 警告：Token剩余{remain_days}天{remain_hours}小时，不足3天，请尽快更换！"
                print(warn)
                alert_messages.append(warn)

    # 2. 签到前状态查询
    stats_before = get_checkin_stats()
    print("\n📊【签到前】签到统计接口返回：")
    print(stats_before)
    profile_before = get_member_profile()
    print("\n👤【签到前】用户资料接口返回：")
    print(profile_before)

    if stats_before.get("statusCode") == 401:
        warn = "❌ Token鉴权失败(401)，请重新获取最新JWT更新Secret！"
        print(warn)
        alert_messages.append(warn)

    data_before = stats_before.get("data", {})
    note_text = ""
    stats_final = stats_before
    profile_final = profile_before

    # 3. 执行签到逻辑
    if data_before.get("isCheckedInToday"):
        print("\nℹ️ 今日已经完成签到，无需重复执行")
        note_text = "无需签到，今日已签"
    else:
        print("\n🚀 开始执行签到...")
        sign_result = do_checkin()
        print("✅ 签到接口返回结果：")
        print(sign_result)
        time.sleep(2)
        stats_final = get_checkin_stats()
        profile_final = get_member_profile()
        print("\n📊【签到后】签到统计接口返回：")
        print(stats_final)
        print("\n👤【签到后】用户资料接口返回：")
        print(profile_final)

        data_after = stats_final.get("data", {})
        if data_after.get("isCheckedInToday") is True:
            print("\n✅ 校验通过：签到成功，isCheckedInToday已更新为true")
            note_text = "已执行一次签到请求，校验签到成功"
        else:
            warn = "⚠️ 校验告警：已经调用签到接口，但isCheckedInToday仍然为false！可能受UTC时区限制/接口异常！"
            print(warn)
            alert_messages.append(warn)
            note_text = "⚠️校验告警：调用签到后状态未变更，注意UTC时区问题"

    # 4. 生成截图
    clean_old_screenshots("./screenshots", keep_count=1)
    take_status_screenshot_by_html(stats_final, profile_final, remain_days, remain_hours, note_text=note_text)
    snap_result = take_sign_popup_screenshot()
    if not snap_result:
        alert_messages.append("ℹ️ 签到弹窗截图失败（不影响签到结果）")

    # 5. 汇总发送预警邮件
    if alert_messages:
        send_alert_email("签到任务异常提醒", "\n".join(alert_messages))
