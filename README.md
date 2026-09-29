# ATK 积分网站每日自动签到脚本 (GitHub‑Actions)
> 
> 功能清单
> 
> 
> - ✅ GitHub‑Actions 每日**随机时间窗口**执行签到，手动触发跳过随机延时
> - ✅ 解析 JWT Token 剩余有效期，输出运行日志，不足 3 天告警
> - ✅ 签到前后接口状态拉取，校验签到是否真正生效
> - ✅ 获取可用积分、即将过期积分，本地 HTML 生成截图
> - ✅ 自动清理旧截图，仅保留最新一张
> - ✅ Artifacts 上传截图，可在 Action 页面下载
> - ⚠️ 后端接口为 UTC 时区，和北京时间存在 8 小时时差
> - ## GitHub Secrets 配置

1. 仓库 → `Settings` → `Secrets and variables` → `Actions`
2. 点击 `New repository secret`

表格

| Name | Secret 值 |
| --- | --- |
| `ATK_TOKEN` | `Bearer` **后面**的完整 JWT 字符串，**不要填写 Bearer 前缀** |

> 
> 示例
> http 请求头：`Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxx`
> 填入 Secret：`eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxx`

## 获取 ATK_TOKEN (JWT)

1. 浏览器打开 `https://www.atkgear.com.cn`，登录账号
2. F12 开发者工具 →【网络】→筛选`Fetch/XHR`
3. 刷新页面，任意点开一个接口，找到请求头 `Authorization`
4. 复制 `Bearer `空格后面一长串字符

> 
> ⚠️ 禁止直接把 token 写在代码文件提交仓库，会泄露账号。

##  使用方法

1. **手动运行**：Actions → `ATK‑Gear 每日签到` → `Run workflow`，立即执行，**不随机延时**
2. **自动定时**：北京时间 7 点‑14 点之间随机时间自动运行
3. 运行结束，在任务页面 Artifacts 下载截图文件

## 重要注意事项

- 后端接口使用 **UTC 时间**，北京时间 0‑8 点会出现：现实到新一天，但接口判定还未签到。
- GitHub schedule 调度存在几分钟～十几分钟延迟，属于平台正常现象。
- Artifacts 截图文件 GitHub 仅保存 90 天。
- 强烈建议使用**私有仓库**部署。
- 日志出现 token 过期告警，需要重新抓取 JWT 更新 Secret。

## 关键日志标记

表格

| 日志内容 | 含义 |
| --- | --- |
| `🔐 Token有效期剩余：XX 天 XX 小时` | JWT 剩余有效时间 |
| `❗ 警告：Token剩余不足3天` | 提醒尽快更新 token |
| `✅ 校验通过：签到成功` | 签到执行完成，状态已更新 |
| `⚠️⚠️⚠️ 校验告警` | 调用签到接口，但状态未变化，优先排查 UTC 时区 |
<img width="1280" height="804" alt="atk_checkin_20260924_070226" src="https://github.com/user-attachments/assets/561bd31f-9b21-486e-a0e7-96553bfdfcf0" />
======================================================================================
/*
免责声明：
本脚本仅限个人学习研究，使用风险由使用者自行承担。
因使用本脚本造成的账号处罚、数据丢失等一切后果，作者概不负责。
使用即代表同意本声明，请遵守相关法规与网站协议。
*/
