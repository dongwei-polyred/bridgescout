# BridgeScout 出货报告

生成时间：2026-10-16 17:10 CST (UTC+8)

## 1. 公开 GitHub 仓库 ✅

- **URL**: https://github.com/dongwei-polyred/bridgescout
- 可见性：public
- 默认分支：`master`
- 推送账号：`dongwei-polyred`（本机 `gh`）
- 未提交：`.env`、`bridgescout/.env`（已在 `.gitignore`；远端 404 确认）
- LICENSE：MIT（仓内可见）

## 2. 外链托管 ✅

### 主演示（Render free，live 模式）

- **Demo URL**: https://bridgescout.onrender.com
- Dashboard: https://dashboard.render.com/web/srv-db8uhqei0phs7392o0h0
- Service ID: `srv-db8uhqei0phs7392o0h0`
- 健康检查：`GET /api/health` → `{"ok":true,"mode":"live",...}`（已验证 HTTP 200）
- 部署方式：Render API + 本机已有 `RENDER_API_KEY`，从公开仓 Docker 构建；`QLOO_API_KEY` / `QLOO_BASE_URL` 已设为服务环境变量（**未**写入公开文件）
- 说明：Free 实例休眠后首次访问可能需 30–60 秒唤醒

### 落地页（GitHub Pages，备用）

- **URL**: https://dongwei-polyred.github.io/bridgescout/
- 内容：项目简介、演示链接、本地一键跑、Render Blueprint 步骤
- 源：`docs/`（`master` 分支 Pages）

## 3. Devpost 交稿 ⚠️ 需浏览器（请父代理派 computerUse）

本执行者**没有** computerUse / 桌面，无法登录 Devpost 完成表单提交。

- 黑客松：https://qloo.devpost.com/
- 截止：约 2026-10-30 11:45pm EDT（≈ 2026-10-31 11:45 CST）
- 邮箱：`dw835496386@gmail.com` 已有 Devpost 活动邮件（账号存在）；验证码可读 Gmail `user-Gmail`
- 画廊页目前显示尚未正式发布，但官网仍显示接受提交至截止日
- **完整填表文案与步骤见** [`DEVPOST_BROWSER_STEPS.md`](./DEVPOST_BROWSER_STEPS.md)

建议 Devpost 项目 URL（提交成功后）：`https://devpost.com/software/bridgescout`（以实际 slug 为准）

## 4. 卡点

| 项 | 状态 | 说明 |
| --- | --- | --- |
| GitHub 公开仓 | 完成 | — |
| Render 演示 | 完成 | live + Qloo key |
| GitHub Pages | 完成 | 落地页 |
| Devpost 提交 | **未完成** | 无浏览器；需 computerUse 或 Wd 手工提交 |

## 5. Wd / 父代理还需做什么

1. **必须**：派 **computerUse**（或 Wd 本人）按 `DEVPOST_BROWSER_STEPS.md` 登录 Devpost → Register（若未注册）→ Start project → 填入链接与简介 → Submit。
2. 可选：在 Devpost 附上截图 `docs/screenshot-demo.png`。
3. 可选：若 Render 日后密钥丢失，在 Dashboard → bridgescout → Environment 重设 `QLOO_API_KEY`（本地仍在 `/workspace/hackathons/qloo/.env`，勿提交）。
4. 无需再登录 Render 才能「首次部署」——已部署完成。

## 6. 关键链接速查

| 用途 | URL |
| --- | --- |
| 仓库 | https://github.com/dongwei-polyred/bridgescout |
| 演示 | https://bridgescout.onrender.com |
| 落地页 | https://dongwei-polyred.github.io/bridgescout/ |
| 黑客松 | https://qloo.devpost.com/ |
| Devpost 交稿步骤 | 见本仓 `DEVPOST_BROWSER_STEPS.md` |
