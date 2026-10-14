# Russia Auto Price Monitor · 俄汽价格

中文、手机优先的俄罗斯官方新乘用车价格查询 H5/PWA。静态 HTML/CSS/ES Modules + Python 采集 + Git 持久化 + GitHub Actions + GitHub Pages；没有长期运行的后端、数据库、API Key 或收费采集服务。

**数字优先显示「官网公开优惠后参考价 / TP 参考」，绝不代表已证明的真实成交 TP。** 未核验价格为 `null`，不使用 0、Demo 或估算价格。默认展示所有已收录车型，包括待核验车型。

## 实际接入情况（2026-10-14）

本地实际联网采集成功的价格共 **2 个车型、9 条配置/口径报价**，收录目录共 **5 品牌、39 个车型**。这是部分覆盖，不是全品牌全车型价格库。`data/sources.json` 为来源登记；`data/state.json` 为唯一权威运行状态；`public/data/current.json` 为页面视图，包含逐品牌最近尝试、失败原因和当前有效覆盖。

| 品牌 | 实际报价接入 | 证据与限制 |
|---|---|---|
| HAVAL | **H3**，1 条官网公开优惠参考起价 | [官方价格目录](https://haval.ru/purchase/catalogues/)的独立 H3 配置卡与对应免责声明。2026 年款 / 2026 年生产，Оптимум 配置，2,549,000 RUB 起。要求 HAVAL/Great Wall 忠诚置换，旧车由本人或配偶持有并使用至少 3 个月；保留完整俄文条件。最高价、MSRP 未核验，不能从折扣反推 MSRP。 |
| TENET | **T7**，4 配置优惠参考价 + 4 配置 RRP | [官方车型页](https://tenet.ru/models/t7/)动态发现[官方关联 PDF](https://1.cdn.perxis.ru/originals/db7i1l4s5adg00dgqam0/original)。2026 年生产，PDF 标明价格截至 08.10.2026；逐列核验 Active/Prime × 2WD/4WD，并检查 HTML 与 PDF 金额一致、RRP − 置换优惠 = 表中优惠参考价。当前收录配置参考价 2,625,000–3,060,000 RUB，RRP 2,805,000–3,210,000 RUB。置换热门品牌旧车，品牌名单及细则须向经销商确认；未公布结束日。 |
| Geely | **待核验** | [Monjaro 官方页](https://www.geely-motors.com/model/monjaro/)已实际请求成功并发现价格文件链接；最初请求曾超时。尚未完成 PDF 的年款/配置/全部优惠条件映射，适配器主动拒绝将广告起价写为核验报价。 |
| Changan | **待核验 / 本地请求失败** | [官方车型目录](https://changanauto.ru/model)已通过公开网页检索确认；本地采集发生 SSL 握手超时。保留失败日志；没有采集到完整报价。首期目录只收录 Changan 主品牌 CS 系及轿车；UNI、AVATR、DEEPAL 单独列为未纳入子品牌，未合并价格。 |
| Hongqi | **待核验** | [官方价格目录](https://hongqi.ru/prices)可实际访问，发现 11 个价格文件候选。试读 HS3 PDF 发现缺少可核验生产年/年款且部分文本字体提取异常，未写入价格。不能因为能下载 PDF 就宣称价格接入成功。 |

上面金额是本次证据快照，不承诺未来仍有效。网页和 `monitor.publish` 会根据核验年龄与明确有效期自动降级。其他 37 个目录车型均无默认价格。中文别名只帮助检索，不证明跨市场车型完全等同。TENET 独立管理，不归入 Chery；HAVAL H5 与 Hongqi H5 保持不同 ID。

## 首次本地运行

需要 Python **3.12+**、Node.js **20+**（建议 24）、Git。前端运行和构建不需要 npm 包；Playwright 只用于浏览器测试。

```bash
git clone https://github.com/illusion2027/russia-auto-price-monitor.git
cd russia-auto-price-monitor
python -m venv .venv
```

macOS/Linux：

```bash
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m monitor.publish
node scripts/serve.mjs
```

Windows PowerShell（无需修改脚本执行策略）：

```powershell
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m monitor.publish
node scripts/serve.mjs
```

访问 **http://127.0.0.1:4173/russia-auto-price-monitor/**。不要用 `file://` 直接打开 HTML，因为浏览器需要通过 HTTP 读取 JSON。服务仅用于本地预览；部署后无服务器进程。没有 `data/state.json` 时，`monitor.publish` 会自动生成所有车型均待核验的可用页面。旧报价超过 3 天会显示旧数据，不伪造新核验时间。

```bash
# 独立测试不访问俄罗斯网站
python -m pytest -q
node --test tests/frontend.test.mjs
python -m monitor.audit

# 手工触发真实采集；可限定品牌
python -u -m monitor.collect
python -u -m monitor.collect --brands haval tenet

# 生成 /dist，可部署到 Pages 子路径
node scripts/build.mjs
```

PowerShell 中将上面的 `python` 换成 `.\.venv\Scripts\python.exe`。`requirements.txt` 列直接依赖，`requirements.lock` 固定本次已测试的完整依赖。脚本没有依赖用户电脑的绝对路径。

## 操作与 PWA

- 选择品牌后，车型下拉仅包含该品牌；关键词实时过滤候选。支持中英俄别名、大小写/空格规范化、部分词、前缀与编辑距离容错，例如 `mon`/`monjro` → Monjaro、`CS75` → 3 个候选。数字部分不做近似替换，避免 CS75 混入 CS95。
- 可按参考价格或名称排序。优惠参考价优先，缺少该口径时排序可使用已核验 MSRP，但不会把 MSRP 标为 TP；空值排最后。
- 点击「条件与来源」查看每条配置的完整俄文条件、生产年/年款、有效期、来源、原始金额、证据摘要哈希、核验时间与最后成功时间。
- 日志与历史趋势支持 7/30/90 天。至少两个不同日期、同口径的成功核验记录才画线；首次使用显示「历史数据积累中」。不同条件/年款/配置不连成一条趋势线。
- CSV 导出当前筛选车型及各报价，缺少价格的字段留空；UTF-8 BOM、正确引用换行和引号，并防止电子表格公式注入。
- Safari 分享 → 添加到主屏幕。PWA 图标、manifest 和 Service Worker 均使用相对路径。离线时显示「离线旧快照」，保留原核验时间；页面每分钟重新计算年龄和到期状态。联网后刷新数据。未在真实 iPhone Safari 上测试；已在 390×844 浏览器窗口验证交互与无横向溢出。

## 数据契约与准确性规则

| 文件/字段 | 意义 |
|---|---|
| `data/catalog.json` | 品牌、目录车型、中文/英文/俄文别名、来源、车身类型、子品牌排除配置。目录不表示有价格。 |
| `data/sources.json` | 各品牌允许的官方 HTTPS 主机、入口、解析版本、核验状态、原因、最后成功时间。当前运行状态以 `current.json.sources` 为准。 |
| `data/state.json` | 单一权威状态：`offers`、`observations`、`changes`、最近 450 条品牌运行记录。每品牌更新后通过临时文件原子替换。历史价格与变化不滚动删除。 |
| `data/evidence/` | 官方 PDF 原文件；HTML 只保留价格上下文、URL 和原始响应 SHA-256，不存页面脚本、表单或无关令牌。HTML 摘要文件不是原始响应字节的完整副本。 |
| `model_year` / `production_year` | 年款与生产年分开管理，未知值为 `null`。TENET 只证明生产年，不强行写成年款。 |
| `price_kind` | 支持的定义：`official_promotional_reference`、`msrp`、`dealer_offer`、`verified_transaction`；首期校验器只允许前两类，未来两类必须另建成交/经销商证据校验器。 |
| `price_basis` | `starting_at` 只证明起价/下限；`exact_trim` 是指定配置价。不会把起价作为车型最高价。 |
| `conditions` / `condition_labels` | 保留完整原文及可读摘要；原文与价格绑定，不把折扣金额/月供作为车辆价格。 |
| `source_type` | `official_html`、`official_pdf` 或 `manual_verified`；实际初始价格均由联网自动适配器采集。 |
| `verified_at` / `last_success_at` | 上次真实核验/成功时间。失败时绝不覆盖它们。 |
| `confidence` | 明确结构与跨来源校验规则通过的解析置信门槛，不是成交概率。至少 0.95。 |
| `effective_date` / `valid_until` | 官方明确的日期；没有公布时保留 `null` 并提示。有效日期按莫斯科 UTC+3 日历处理，结束日包含当天；采集核验时间戳仍保存为 UTC。 |
| `status` | `verified` 当前核验、`stale` 采集失败/缺失/年龄超过 3 天、`expired` 明确过期、`needs_review` 待核验。采集不可访问记录在品牌运行状态 `failed`，不写 0 元报价。 |
| `current_prices` 视图 | `public/data/current.json` 中每车型的 `promo`/`msrp` 最低最高、各端点完整 `min_offer`/`max_offer`。范围仅代表 **已收录配置**，不声称覆盖车型全市场。 |
| `price_history` | `public/data/history.json` 的每日成功 `observations` 与独立变动 `changes`。同日相同价/条件去重，失败不生成成功历史。 |

同口径 key 包括品牌、车型、年款、生产年、配置、价格类别、完整条件哈希、地区、有效期和金额口径。完全同口径才计算差额/百分比；新增配置或任意口径变化记录 `scope_change`，差额与百分比都是 `null`。到期变化也视为口径变更，不把不同促销活动直接比较。

`data/offer.schema.json`、`current.schema.json` 和 `history.schema.json` 定义机器可检查契约。`monitor.audit` 校验类型、报价证据存在、端点匹配、历史及口径变化空值规则。

采集设置：每主机至少间隔 1 秒、连接超时 10 秒/读取超时 25 秒，网络故障、429/5xx 最多 3 次尝试；403 不重试。检查 `robots.txt`，无法确认访问规则则保守停止；最多 4 次跟随跳转，每次校验官方主机，单文件上限 15 MB。无代理、无验证码绕过、无登录、无浏览器反爬规避。品牌解析/验证失败独立捕获，不影响其他品牌；同品牌任何新行校验失败时拒绝整批更新。未覆盖旧配置保留并标旧数据。

## 本地人工审核导入 CSV / JSON

适合官网动态结构尚未自动适配但已经人工逐项核对的公开报价。不是免审核入口。只有官方允许域名的来源、确定金额、至少一个明确年款/生产年、完整条件和真实核验时间才能通过。

1. 将 `data/manual-template.json` 复制到不提交的 `work/` 目录，填写全部真实字段。模板金额为空，不能直接导入；没有示例假价格。
2. 保存可检查的来源 PDF 或价格上下文到本地，核对车型/配置/年款、金额及条件。`verified_at` 填实际核验时间的带时区 ISO 8601 值（如 `YYYY-MM-DDTHH:mm:ss+00:00`），不是导入时间；过期、未来日期、错误域名、价款不符都会拒绝。
3. 执行：

```bash
python -m monitor.import_prices --file work/reviewed-prices.json --evidence work/official-price.pdf --reviewer "审核人姓名或标识" --reviewed
python -m monitor.audit
node scripts/build.mjs
```

CSV 的列名与模板字段完全相同：年款/生产年/金额为整数、未知日期留空，`condition_labels` 是引用正确的 JSON 数组，UTF-8 编码。可用 JSON 更简单。导入会自动设置 `source_type=manual_verified` 与证据文件 SHA-256；记录审核人/导入时间，只提交审核过的公开价格摘要，避免复制原人工证据中的私密内容。整份文件先校验，全部通过才改状态。人工报价也受有效期和 3 天核验年龄约束；重新人工核验或同配置的新自动核验可刷新数据。

人工导入后只提交这些公开文件：

```bash
git add data/state.json data/evidence public/data
git commit -m "data: add manually reviewed official prices"
git push
```

## GitHub Pages 部署

项目的 GitHub 仓库为 [illusion2027/russia-auto-price-monitor](https://github.com/illusion2027/russia-auto-price-monitor)。本地开发、价格采集及测试已完成；线上发布是否成功，以 Actions 的部署结果及 Settings → Pages 提供的地址为准。不需要任何 Secret、PAT 或 API Key。首次发布步骤如下：

1. 创建 **public** 仓库 `russia-auto-price-monitor`，默认分支 `main`，不要自动创建 README/License（避免与本地初始提交冲突）。公共仓库可使用 GitHub Free 的 Pages。若使用 ZIP 而不是现有 Git 目录，先 `git init -b main`、添加并提交全部文件。
2. 在交付仓库目录配置远程地址并推送；若已经配置 `origin`，可直接推送（或使用 `git remote set-url origin` 更新地址）：

```bash
git remote add origin https://github.com/illusion2027/russia-auto-price-monitor.git
git push -u origin main
```

3. **Settings → Pages → Build and deployment → Source → GitHub Actions**。已有工作流，无需再采用 GitHub 的模板。[GitHub 官方部署源说明](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)。
4. 在 **Actions** 中启用仓库工作流。如组织策略禁止写回默认分支，允许本工作流的 `contents: write` 权限及机器人数据提交；`main` 的保护规则也必须允许其更新公开数据。提交失败会停止部署，避免发布无法持久保存的历史。需要读写能力的只有采集 job；部署 job 只有 `pages: write` 和 `id-token: write`。没有用 PAT 绕过保护。
5. Actions → **Collect, validate and deploy Pages** → **Run workflow**，选择 `main`。查看 `collect-build` 的覆盖表/日志，再确认 `deploy` 成功。第一次推送如果早于 Pages 配置导致部署失败，配置后重新手动运行即可。
6. 成功后，工作流的部署输出/Settings → Pages 提供最终地址，通常为 `https://illusion2027.github.io/russia-auto-price-monitor/`。所有站内 URL、JSON、图标、PWA 缓存和 manifest 均适配该子路径。

定时为 UTC **06:17**，即莫斯科 **09:17**（北京时间 **14:17**），每天在默认分支执行。GitHub 调度可能延迟或在负载高时漏发，不承诺精准时刻；公开仓库长时间无活动时定时工作流可能自动禁用。[GitHub 计划事件说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

同一个工作流完成 **离线测试 → 真实采集 → 契约验证 → 数据/历史提交推送 → 静态构建 → Pages Artifact → 部署**。每次 checkout 读取默认分支已提交的 `data/state.json`，采集结果重新提交到 `main`，所以 Actions 临时环境不会丢失历史。`GITHUB_TOKEN` 推送一般不会再触发另一条 push 工作流，因此当前 run 自己构建部署，避免链式触发依赖。[GitHub Token 说明](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token)。工作流并发串行；遇到其他人同时推送使 Git push 失败则停止，可拉取最新分支后重跑，绝不 force push。

无须服务器/数据库/域名费用。公共仓库及平台权限/配额仍受 GitHub 规则约束；查看自己的 Actions 用量。网站只包含公开官方价格和代码，不能上传内部价格、账号令牌或私密交易材料。

## 浏览器测试与本次验证

```bash
npm ci
node scripts/build.mjs
npx playwright install chromium
npm run test:browser
```

Linux CI 用 `npx playwright install --with-deps chromium`。本地已有 Chrome 时可指定可执行路径：

```powershell
$env:PLAYWRIGHT_EXECUTABLE = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
npm run test:browser
```

浏览器测试启动并关闭专用 localhost 服务，实际访问构建后的 `dist/`、Pages 子路径，不请求俄罗斯官网。包括品牌/车型联动、前缀与拼写容错、真实已收录报价字段、CSV 下载、来源页面、7/30/90 天历史空状态、Service Worker 离线，以及单独拦截数据构造的 **无价格** 页面。测试中的金额变异只用于隔离的断言，不生成默认市场数据。

本地最终验证结果见 `VALIDATION.md`。`.github/workflows/ci.yml` 在 PR 上运行 Python/前端/浏览器检查，不发布 PR 内容。更新部署工作流在采集前运行离线 Python/前端检查，采集后验证生成数据与构建。

## 尚待完成的覆盖与二期

首期完整的静态查询、更新、持久化及发布流程已实现，但价格覆盖仅限表中实际接入车型。下一步应逐车型审核 Geely 最新 PDF、排查 Changan 可公开访问的来源，并为 Hongqi 建立可靠的 PDF 年款/配置提取；再扩展 HAVAL/TENET 其他车型。保持历史口径并评估 Git 历史增长后再引入压缩归档。经销商报价与真实成交数据需要独立来源可信度及授权管理，不能与官方优惠参考价混用。没有实施这些扩展，也没有宣称 5/5 可自动采集。

代码 MIT；官方原文件、摘录及品牌商标权利归原权利人。
