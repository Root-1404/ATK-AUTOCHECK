import requests
import os
import jwt
import time
import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

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

def parse_jwt_remain_time(jwt_token: str):
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

def get_checkin_stats():
    url = "https://api.vxe.com/v1/member/checkin/stats"
    resp = requests.get(url, headers=headers, timeout=20)
    return resp.json()

def get_member_profile():
    url = "https://api.vxe.com/v1/member/profile"
    resp = requests.get(url, headers=headers, timeout=20)
    return resp.json()

def do_checkin():
    url = "https://api.vxe.com/v1/member/checkin"
    resp = requests.post(url, headers=headers, timeout=20)
    return resp.json()

def clean_old_screenshots(save_dir="./screenshots", keep_count=1):
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

def take_status_screenshot_by_html(stats_data, profile_data, remain_days, remain_hours, note_text="", save_dir="./screenshots"):
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
    """修复超时版：海外服务器访问国内网站，只等DOM不等待静态资源"""
    os.makedirs(save_dir, exist_ok=True)
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    save_file = os.path.join(save_dir, f"atk_sign_popup_{now_str}.png")
    page = None
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

            # 拦截API请求，注入鉴权头
            def intercept_request(route):
                req_headers = route.request.headers
                if "api.vxe.com" in route.request.url:
                    req_headers["Authorization"] = f"Bearer {token}"
                    req_headers["client-type"] = "atk"
                    req_headers["env"] = "prod"
                # 阻断不必要的第三方统计、追踪请求，加速页面加载
                if any(block_url in route.request.url for block_url in ["hm.baidu", "google-analytics", "doubleclick", "cnzz"]):
                    return route.abort()
                route.continue_(headers=req_headers)
            context.route("**/*", intercept_request)

            page = context.new_page()
            # 核心修复：只等DOM结构出现就继续，不等所有图片/静态资源加载
            try:
                page.goto(
                    "https://www.atkgear.com.cn/pointmall/mallcenter",
                    wait_until="domcontentloaded",  # 不等待load事件，不等所有资源
                    timeout=30000
                )
            except PlaywrightTimeout:
                print("⚠️ 页面加载超时，DOM已就绪，继续尝试截图")

            # 只等核心交互元素出现，不等网络空闲
            page.wait_for_timeout(5000)  # 给前端JS5秒时间渲染Vue组件

            # 尝试点击签到日历按钮
            try:
                sign_calendar_btn = page.locator("div:has-text('签到日历'):visible").first
                sign_calendar_btn.click(timeout=8000)
                print("✅ 成功点击签到日历按钮")
                page.wait_for_timeout(3000)  # 等弹窗弹出动画
            except Exception as e:
                print(f"ℹ️ 未找到签到日历按钮: {str(e)}")

            # 尝试定位签到弹窗，找不到就截当前页面
            try:
                popup_locator = page.locator("div[data-v-22e9525c].relative.bg-white.shadow-lg").first
                popup_locator.wait_for(state="visible", timeout=10000)
                popup_locator.screenshot(path=save_file)
                print("✅ 成功截取签到日历弹窗")
            except PlaywrightTimeout:
                print("⚠️ 弹窗未加载，截取当前页面兜底")
                page.screenshot(path=save_file, full_page=False)

            browser.close()
        print(f"🌐 签到弹窗截图已保存: {save_file}")
        return save_file
    except Exception as e:
        print(f"⚠️ 签到弹窗截图失败（不影响签到主流程）: {str(e)}")
        # 清理残留浏览器进程，避免影响后续步骤
        if browser:
            try:
                browser.close()
            except:
                pass
        return None

if __name__ == "__main__":
    remain_days, remain_hours = parse_jwt_remain_time(token)
    if remain_days is not None:
        if remain_days <=0 and remain_hours <=0:
            print("⚠️ JWT Token已经过期！请立刻更新Token！")
        else:
            print(f"🔐 Token有效期剩余：{remain_days} 天 {remain_hours} 小时")
            if remain_days < 3:
                print("❗ 警告：Token剩余不足3天，请尽快更换！")

    stats_before = get_checkin_stats()
    profile_before = get_member_profile()
    print("\n📊【签到前】签到统计接口返回：")
    print(stats_before)
    print("\n👤【签到前】用户资料接口返回：")
    print(profile_before)

    data_before = stats_before.get("data", {})
    note_text = ""
    stats_final = stats_before
    profile_final = profile_before

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
            print("\n⚠️⚠️⚠️ 校验告警：已经调用签到接口，但isCheckedInToday仍然为false！可能受UTC时区限制/接口异常！")
            note_text = "⚠️校验告警：调用签到后状态未变更，注意UTC时区问题"

    clean_old_screenshots("./screenshots", keep_count=1)
    take_status_screenshot_by_html(stats_final, profile_final, remain_days, remain_hours, note_text=note_text)
    take_sign_popup_screenshot()
