# SEMS — 半导体设备管理系统

Semiconductor Equipment Management System

一个面向半导体制造车间的轻量级设备管理平台，覆盖设备台账、实时状态看板、PM 维护计划、工单管理、点检巡检、备件管理、OEE 分析等功能。基于 FastAPI + Vue 3 构建，开箱即用。

---

## 版本 Highlights（最近一次主要更新）

- **📚 8D 报告一键归档知识库**：故障知识库支持从 **8D 报告**（D0 问题描述 + D2 问题定义 → 故障现象 / D4 → 根因 / D5 → 处置措施 / D7 → 预防措施）自动提取填充，关联 `source_d8_report_id` 溯源，同时保留原有「工单归档」入口，双路径沉淀经验。
- **📋 分级菜单（8 大分组）**：从一级平铺改为「设备管理 / 日常运维 / 工艺文控 / 品管工具 / 合规安全 / 数据价值 / 系统管理」8 组折叠式导航，**系统配置永远放在最末一组**，菜单层级一目了然。
- **🎯 角色定制看板**：不同角色（管理员/工程师/工艺/QA/操作员/查看者）登录后自动显示不同的看板卡片组合与排序优先级，例如 QA 优先看文控复审告警 + 8D 报告进度、操作员优先看设备状态 + 到期点检。
- **🧾 敏感操作审计日志入库**：`LOGIN_OK / LOGIN_FAIL / LOGIN_LOCKED / LOGOUT / PASSWORD_CHANGED / PASSWORD_RESET / USER_CREATE / USER_UPDATE / USER_DELETE / USER_UNLOCK` 等所有敏感操作从 stdout 改为持久化写入 `audit_logs` 表（含操作人 / 目标用户 / IP / User-Agent / 时间戳 / 详情），满足体系审核留痕要求。
- **🔐 密码 bcrypt 72 字节截断修复**：引入 SHA-256 预哈希 + bcrypt 二次哈希（旧算法透明回退 + 登录成功时自动升级重哈希），解决超长密码被静默截断导致熵损失的安全隐患。
- **🎨 B+C 双皮肤主题（一明一暗）可跟随系统**：引入"极简青绿（明色 B 方案）"+"暗色霓虹（暗色 C 方案）"两套配色；顶栏按钮一键切换明色 / 暗色 / 跟随系统（`prefers-color-scheme`），偏好写入 localStorage，刷新仍生效。
- **🌗 暗模式亮度统一补丁**：针对 Element Plus 组件（el-tag 实心/空心/浅色、el-button 实心、el-avatar、el-dropdown-menu、el-message、el-empty 等）在暗底上反白刺眼的问题做了增量修复，背景亮度统一压到 0.35 以下、文字对比度保持可读性，不再出现"白底淡蓝字"观感。
- **表单模板与结构化记录**：管理员定义模板（字段类型/必填/选项/单位/范围），操作员选模板动态生成电子表单并填写，数据结构化存储可导出 JSON/CSV，替代传统 PDF 上传模式。
- **作业记录新建电子表单**：在工艺文件→作业记录页面直接「新建电子表单」→选模板→填写→保存草稿/提交，自动归档为工艺文件条目；已有记录可点击「填写」按钮继续编辑。
- **设备 DOWN 触发工单**：操作员 / 设备 / 工艺人员都可在台账右上角切换设备状态到 `DOWN`，系统自动创建 `REPAIR` 类型工单（含故障现象 + 紧急度），自动派发。
- **工单持续时长可见**：列表 & 详情页显示工单从创建到关闭（或当前）的持续时长，便于跟踪。
- **关键词检索**：工单支持标题/描述/现象关键词检索（例：搜「漏真空」可命中所有包含该词的工单）。
- **局域网安全加固**：密码策略、账户锁定、JWT 访问+刷新令牌、敏感操作审计、强制首次改密、CSP/X-Frame 响应头（见「安全加固」章节）。
- **低成本灾备（3-2-1）**：备份加密、NAS/SMB 异地副本、烟雾还原测试、系统级旁路 cron/任务计划备份脚本（见「灾备方案」章节）。
- **📑 文控系统（符合体系标准）**：三级电子签名审批链（编制→审核→批准）+ SHA256 签名指纹、状态机白名单（草稿→审核中→生效→作废）、文档编号规则、修订记录（字段级 before/after）、分发收回台账、PDF 水印受控章、表单审核锁定 + 附加修正、复审周期告警、QA 角色权限矩阵（见「文控系统」章节）。
- **🛡 安全检查模块**：安全装置定期检查（防护罩/急停/联锁）、特种设备检验日历、证书到期告警、检查执行 + 整改措施跟踪（见「安全检查」章节）。
- **⏱ 工单 SLA / 升级**：SLA 目标响应/解决时长、实际响应/解决时长自动计算、SLA 违约标记、超时升级指派、SLA 达成率统计。
- **🔄 设备生命周期 T0-T3**：选型(T0)→采购(T1)→安装调试(T2,FAT/SAT)→量产移交(T3)全流程，含采购金额/验收结果/时间线展示。
- **🛢 润滑管理（五定）**：润滑点定义（定点/定人/定时/定质/定量）、润滑计划 + 到期告警、润滑执行记录、频次自动推算下次润滑日。
- **📚 故障知识库**：工单归档为知识条目（根因/处置/预防自动填充）、全文检索、相似案例推荐、复发次数追踪、浏览统计。
- **💰 设备成本 LCC**：单设备全生命周期成本汇总（采购/维护/备件/能耗/折旧/报废）、按类型统计 + 年度趋势 + Top10 高成本设备。

---

## 功能概览

| 模块 | 说明 |
|------|------|
| 看板总览 | 设备实时状态卡片（RUN / IDLE / DOWN / PM / ENGINEERING）、状态变更轨迹、超时预警 |
| 设备台账 | 设备档案管理，含厂区/区域分类、附件上传、**右上角状态切换（DOWN 自动派工单）** |
| 点检巡检 | 点检模板 + 检查项 + 历史记录 |
| 工单管理 | 工单创建与跟踪、**紧急度标签、持续时长、关键词检索**；REPAIR 工单可由 DOWN 状态自动触发 |
| PM 维护计划 | 周期性 PM 计划（周/双周/月/季度）、执行记录 |
| 备件管理 | 备件库存、出入库流水、设备易损件清单 |
| 工艺文件 | 指导性文件版本管理 + **作业记录结构化表单（模板定义→动态填写→归档→导出 JSON/CSV）** + **文控审批链 / 修订 / 分发 / 水印 / 复审** |
| **文控系统** | **三级电子签名审批链（编制→审核→批准）、状态机白名单、文档编号规则、修订记录、分发收回、PDF 水印受控章、表单审核锁定 + 附加修正、复审告警、QA 角色权限** |
| OEE 分析 | 设备综合效率统计 |
| 品管工具 | 8D / FMEA，**8D 报告可一键归档故障知识库**（D0+D2→现象 / D4→根因 / D5→处置 / D7→预防） |
| 环境核查 | 环境参数日志 |
| 人员管理 | 资质、培训、技能矩阵 |
| 资产管理 | 资产盘点、调拨报废 |
| **表单模板管理** | **管理员定义表单模板（字段/类型/选项/单位/范围）→ 上传参考文件 → 生成结构化记录（仅管理员）** |
| 系统配置 | 用户管理、角色权限、**IP 白名单**、系统设置、**一键备份/恢复/加密+异地副本**、定时备份计划 |

---

## 技术栈

- **后端**：Python 3.10+ / FastAPI / SQLAlchemy 2.0 / SQLite（零配置，开箱即用）
- **前端**：Vue 3 / Vite / Element Plus / ECharts / Pinia
- **数据库**：SQLite（默认，无需安装数据库服务）
- **部署**：支持本地开发、Docker Compose、Windows 单文件打包（PyInstaller）

---

## 安装与部署

提供三种安装方式，请根据使用场景选择：

| 方式 | 适用场景 | 需要安装 | 说明 |
|------|----------|----------|------|
| [方式一：本地开发](#方式一本地开发) | 开发调试 | Python + Node.js | 前后端分离启动，支持热更新 |
| [方式二：Docker Compose](#方式二docker-compose-部署) | 生产部署 / 快速体验 | Docker | 一键构建，Nginx 反向代理 |
| [方式三：Windows 单文件打包](#方式三windows-单文件打包) | Windows 离线部署 | 无（打包后） | 生成 sems.exe，双击运行 |

---

### 方式一：本地开发

#### 环境要求

- Python ≥ 3.10
- Node.js ≥ 18
- npm ≥ 9

#### 第 1 步：克隆项目

```bash
git clone <repository-url>
cd sems
```

#### 第 2 步：启动后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动后端开发服务器（默认 8000 端口）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> 后端首次启动时会自动完成以下操作：
> - 创建 SQLite 数据库（`backend/data/app.db`）
> - 初始化默认管理员账号（admin / admin123）
> - 生成演示数据（10 台半导体设备、PM 计划、备件、点检记录等）

#### 第 3 步：启动前端

打开一个新的终端窗口：

```bash
cd frontend

# 安装前端依赖
npm install

# 启动前端开发服务器（默认 5173 端口）
npm run dev
```

> 前端开发服务器运行在 `http://localhost:5173`，API 请求会自动代理到 `http://127.0.0.1:8000`（配置在 `frontend/vite.config.js`）。

#### 第 4 步：访问系统

- 浏览器打开 `http://localhost:5173`
- 默认账号：`admin`
- 默认密码：`admin123`

> ⚠️ **首次登录**：系统检测到 `admin` 仍使用弱密码 `admin123` 会自动**强制跳转修改密码**；请按密码策略（≥8 位 + 大小写/数字/特殊符号至少 3 类）修改后才可进入主界面。其它用户如果被管理员标记了「必须改密」，也会走同样流程。

#### 验证安装

后端启动成功后，可访问以下地址确认：
- 健康检查：`http://localhost:8000/health` → 返回 `{"status": "ok"}`
- API 文档：`http://localhost:8000/docs` → Swagger UI 界面
- 安全配置自检：登录后「系统配置 → 备份」→ 点 **备份安全性状态**，检查 `encryption/secondary` 是否配置。

---

### 方式二：Docker Compose 部署

适合生产环境或快速体验，无需本地安装 Python / Node.js。

#### 环境要求

- Docker ≥ 20.10
- Docker Compose ≥ 2.0

#### 第 1 步：配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，按需修改：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FRONTEND_PORT` | `8080` | 前端对外访问端口 |
| `BACKEND_PORT` | `8000` | 后端对外端口（一般无需修改） |
| `SECRET_KEY` | （需修改） | JWT 签名密钥，**生产环境务必改为随机长字符串（≥48 位）**，首次启动未填会自动写 `.env` |
| `BACKUP_ENCRYPTION_PASSWORD` | 空 | 备份加密专用密码（32 位以上随机字符串最佳）；不填则退化用 `SECRET_KEY` 派生 |
| `BACKUP_SECONDARY_DIR` | 空 | 第二备份目录（绝对路径），例如 `/mnt/nas/sems_backups` / `\\fileserver\share\sems_backups` |
| `BACKEND_CORS_ORIGINS` | 见下 | CORS 白名单（生产必须明确域名/局域网 IP，不要留 `*`） |
| `LOGIN_FAILURE_LOCK_THRESHOLD` | `5` | 连续登录失败次数阈值，达到则锁定账户 |
| `LOGIN_FAILURE_LOCK_MINUTES` | `15` | 失败锁定时长（分钟） |
| `PASSWORD_MIN_LENGTH` | `8` | 密码最小长度 |

#### 第 2 步：构建并启动

```bash
docker compose up -d --build
```

首次构建需要下载镜像和安装依赖，耐心等待。

#### 第 3 步：访问系统

- 浏览器打开 `http://localhost:8080`（端口由 `FRONTEND_PORT` 决定）
- 默认账号：`admin` / `admin123`

#### 常用命令

```bash
# 查看日志
docker compose logs -f

# 停止服务
docker compose down

# 重新构建（代码更新后）
docker compose up -d --build
```

> 数据库持久化在 Docker volume `sems-data` 中，停止容器不会丢失数据。如需彻底清除数据：`docker compose down -v`

---

### 方式三：Windows 单文件打包

使用 PyInstaller 将前后端打包为单个 `sems.exe`，双击即可运行，适合 Windows 离线部署。

#### 打包环境要求

- Windows 操作系统
- Python 3.10+
- Node.js 18+

#### 打包步骤

在项目根目录依次执行：

```bash
# 1. 安装后端依赖
cd backend
pip install -r requirements.txt
pip install pyinstaller
cd ..

# 2. 构建前端静态资源
cd frontend
npm install
npm run build
cd ..

# 3. 执行打包脚本
python build_win.py
```

#### 运行打包产物

| 操作 | 说明 |
|------|------|
| 产物路径 | `dist/sems.exe` |
| 启动 | 双击 `sems.exe`，自动打开浏览器访问 `http://localhost:8000` |
| 默认账号 | `admin` / `admin123` |
| 数据库位置 | exe 同级 `data/` 目录下自动创建 |
| 修改端口 | 设置环境变量 `PORT=9000` 后再启动 |

---

## 配置说明

### 后端环境变量

通过环境变量或 `.env` 文件配置（基于 pydantic-settings）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SQLALCHEMY_DATABASE_URI` | `sqlite:///./data/app.db` | 数据库连接串 |
| `SECRET_KEY` | 启动时自动生成 | JWT 签名密钥，**生产建议 48 位以上随机字符串**。首次启动检测到默认值会自动用 `secrets.token_urlsafe(48)` 写入 `.env` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `120`（2 小时） | 访问令牌过期时间（短） |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | 刷新令牌过期时间（长，用于自动续期） |
| `BACKEND_CORS_ORIGINS` | 仅 `localhost` 开发地址 | CORS 白名单（生产必须改为部署机器的局域网 IP/域名，不能用 `*`） |
| `PORT` | `8000` | 后端监听端口 |
| `HOST` | `0.0.0.0` | 后端监听地址 |
| `LOGIN_FAILURE_LOCK_THRESHOLD` | `5` | 登录失败次数阈值 |
| `LOGIN_FAILURE_LOCK_MINUTES` | `15` | 失败锁定时长（分钟） |
| `PASSWORD_MIN_LENGTH` | `8` | 密码最小长度；另外还有"3/4 类字符 + 弱密码字典"规则（见安全加固） |
| `BACKUP_ENCRYPTION_PASSWORD` | 空 | 备份加密密码（AES-256 Fernet PBKDF2 派生 key，20 万轮迭代） |
| `BACKUP_SECONDARY_DIR` | 空 | 第二备份目录（绝对路径，NAS/SMB/U盘 挂载点；要求已存在且进程可写） |

### 前端 API 代理

开发模式下在 `frontend/vite.config.js` 中配置：

```js
proxy: {
  '/api': {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
  },
}
```

生产模式下由 Nginx 反向代理 `/api/` 到后端（见 `docker/nginx/default.conf`）。

---

## 项目结构

```
sems/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API 路由（dashboard, equipment, work_order 等）
│   │   ├── core/             # 配置、数据库、安全（密码哈希、JWT、响应头中间件）
│   │   ├── models/           # SQLAlchemy 数据模型（含 failed_login_count / locked_until 等安全字段）
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   ├── services/         # 业务逻辑层（user_service=认证；backup_service=加密+异地副本+烟雾测试；backup_scheduler=定时）
│   │   ├── constants.py      # 常量定义
│   │   └── main.py           # FastAPI 应用入口 + SecurityHeadersMiddleware
│   ├── scripts/             # **系统级旁路备份**（sems_standalone_backup.sh / .bat，不依赖后端进程）
│   ├── requirements.txt
│   ├── run_server.py         # PyInstaller 打包入口
│   ├── seed_full_demo.py     # 全量演示数据脚本
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/              # Axios API 封装（auth 自动 refresh、token 失效跳登录）
│   │   ├── layouts/          # 布局组件
│   │   ├── router/           # Vue Router 路由（must_change_password 守卫）
│   │   ├── stores/           # Pinia 状态管理（user: access/refresh token、自动续期）
│   │   ├── views/            # 页面组件（ChangePassword.vue = 强制改密页）
│   │   ├── App.vue
│   │   └── main.js
│   ├── vite.config.js        # Vite 配置（含 API 代理）
│   ├── package.json
│   └── Dockerfile
├── docker/
│   └── nginx/default.conf    # Nginx 反向代理配置
├── .env.example              # 环境变量模板
├── docker-compose.yml        # Docker Compose 编排
├── build_win.py              # Windows 打包脚本
└── .gitignore
```

---

## API 文档

后端启动后访问：
- Swagger UI：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`

---

## 演示数据

系统首次启动会自动生成演示数据：

- **10 台半导体设备**：离子注入机、刻蚀机、光刻机、PVD 溅射机、湿法清洗机、涂胶显影、CMP 抛光机、退火炉、扩散炉、量测机
- **设备状态日志**：每台设备有完整的状态变更历史（RUN / IDLE / DOWN / PM / ENGINEERING）
- **PM 维护计划**：周/双周/月度周期性 PM 计划及执行记录
- **备件库存**：备件信息、出入库流水
- **点检记录**：点检模板与历史记录
- **默认管理员**：admin / admin123

---

## 🎨 UI 主题：B 极简青绿（明） + C 暗色霓虹（暗） + 跟随系统

系统内置两套主题，并支持一键跟随操作系统配色偏好。

### 三套模式（顶栏右侧按钮切换）

| 模式 | 说明 | 何时亮 / 暗 |
|------|------|-------------|
| **明色青绿（B 方案）** | 强制使用明色主题 | 始终 `:root` 变量 |
| **暗色霓虹（C 方案）** | 强制使用暗色主题 | 始终 `html.dark` 变量 |
| **跟随系统** | 跟随浏览器/OS 的 `prefers-color-scheme` 媒体查询 | 系统亮 → B；系统暗 → C |

> 选择会写入 `localStorage.sems_theme_mode`，下次访问自动恢复；跟随系统时还会实时监听媒体查询变化（例如 macOS 从浅切换到深，页面立刻跟着切）。

### 两套方案色板

| 变量 | 方案 B（明色青绿） | 方案 C（暗色霓虹） |
|------|-------------------|-------------------|
| 主色 `--app-primary` | `#10B981` 翠绿 | `#22D3EE` 霓虹青 |
| 侧栏背景 `--app-sidebar-bg` | `#FFFFFF` | `#0B1220` |
| 页面背景 `--app-page-bg` | `#F8FAFC` | `#0F172A` |
| 卡片背景 `--app-card-bg` | `#FFFFFF` | `#1E293B` |
| 主文字 `--app-text-primary` | `#1E293B` | `#F1F5F9` |
| 登录页渐变 | `青绿斜切 → 灰白` | `深蓝 斜切 → 深青` |

### 暗模式"过亮"专项修复

原 Element Plus 在自定义暗色变量后，`el-tag effect="dark"`、`el-button 实心`、`el-avatar`、`el-dropdown-menu` 等组件仍会使用明色逻辑的高亮度背景，产生"白底淡蓝字"刺眼观感。当前版本内置了增量补丁（**只在 `html.dark` 下追加覆盖规则，不影响明色**）：

- `el-tag effect="dark"`：语义色背景改为 `14~18%` 半透明 + 同色系描边，背景亮度从 `0.60~0.75` 降到 `≈0.12`。
- `el-tag effect="light" / plain`：空心/浅色标签统一压到 `10%` 半透明底。
- `el-button 实心`：primary/success/warning/danger/info 使用更深色阶（`#0891B2 / #059669 / #D97706 / #DC2626 / #475569`），不再反白。
- `el-avatar`：主色背景改为半透明 + 内描边。
- `el-dropdown-menu / el-message / el-empty 描述`：统一落 `#1E293B` 暗底。

### 技术实现 & 如何自定义主题

- 主题变量集中在 [frontend/src/styles/theme.css](file:///workspace/frontend/src/styles/theme.css)：
  - `:root` 块 = 明色方案（B）
  - `html.dark` 块 = 暗色方案（C）
  - `html.dark .xxx` 追加选择器 = 暗模式补丁
- 主题切换逻辑封装在 composable 里：[frontend/src/composables/useTheme.js](file:///workspace/frontend/src/composables/useTheme.js)
  - 三态：`light / dark / auto`；`auto` 模式下监听 `window.matchMedia('(prefers-color-scheme: dark)')`。
  - 持久化 key：`sems_theme_mode`（localStorage）。
  - 生效方式：在 `<html>` 根元素上增删 `.dark` 类，配合 `color-scheme: dark` 让原生控件也跟随。
- 在顶栏 [MainLayout.vue](file:///workspace/frontend/src/layouts/MainLayout.vue) 接入下拉切换按钮：图标 + 标签（"明色青绿 / 暗色霓虹 / 跟随系统"），并对所有组件移除硬编码颜色，改用 `var(--app-xxx)` / `var(--el-color-xxx)` 变量。

**想改配色？只需三步**：
1. 编辑 `theme.css` 的 `:root`（明色）或 `html.dark`（暗色）变量；
2. 对应改 `--app-primary / --app-page-bg / --app-card-bg` 及 Element Plus 覆盖变量；
3. 刷新即可（如果是跟随系统模式，要注意 OS 配色再验证一下暗色部分）。

相关代码：[theme.css](file:///workspace/frontend/src/styles/theme.css) · [useTheme.js](file:///workspace/frontend/src/composables/useTheme.js) · [MainLayout.vue](file:///workspace/frontend/src/layouts/MainLayout.vue) · [Dashboard.vue](file:///workspace/frontend/src/views/Dashboard.vue)

---

## 🔒 安全加固（面向局域网部署）

SEMS 运行在工厂内网时，依然有「临时接入电脑 / 运维共享账号 / 被嗅探 / 离职人员仍能登录」等风险。本系统内置以下安全能力（默认开启大部分）：

### 1) 身份认证

| 能力 | 说明 | 默认状态 |
|------|------|----------|
| 访问+刷新令牌双 JWT | `access_token` 2 小时 + `refresh_token` 7 天，前端到期前 5 分钟自动续期；降低长期有效密钥被窃取风险 | 启用 |
| 密码慢哈希（修复 72 字节截断） | bcrypt (rounds=12) 前先做 **SHA-256 预哈希** → 固定 32 字节摘要喂给 bcrypt，规避原生 bcrypt 对超长密码静默截断前 72 字节的熵损失漏洞；旧哈希值透明回退验证，且登录成功时**自动升级**为新算法 | 启用 |
| 密码复杂度 | 最小 8 位 + 大写/小写/数字/特殊符号 ≥3 类 + 内置弱密码字典 16 条拦截 | 启用 |
| 登录失败锁定 | 连续失败 5 次 → 账户锁定 15 分钟（阈值可配置） | 启用 |
| 用户名枚举防护 | 即使账号不存在也走一次 bcrypt 验证耗时，避免攻击者用耗时判断账号是否存在 | 启用 |
| 首次登录强制改密 | admin 默认密码 `admin123` 或管理员新创建账号打 `must_change_password=True` → 强制跳改密页 | 启用 |
| 管理员重置密码 | 重置后自动打「必须改密」标记 + 清零失败计数 + 解锁账户 | 启用 |
| 账户解锁 UI | 用户管理面板新增锁定状态列 + 一键解锁按钮 | 启用 |

### 2) 传输 & 响应头（浏览器侧防御）

- **CORS 收紧**：不再接受 `*`，生产需明确局域网 IP/域名加入白名单。
- **安全响应头**（`main.py` 中间件自动注入）：
  - `X-Content-Type-Options: nosniff`（防止 MIME 嗅探）
  - `X-Frame-Options: DENY`（防点击劫持）
  - `Content-Security-Policy`：默认禁止 `unsafe-inline` 脚本 & data: 图片以外的协议；生产部署建议根据实际域名进一步收紧。
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=()`（禁浏览器敏感硬件 API）

### 3) 会话安全（前端）

- localStorage 统一前缀 `sems_*`，避免与其它系统或老版本冲突；登出时连同 sessionStorage 一并清理。
- **Token 失效双保险**：
  - 主动：`setTimeout` 提前 5 分钟 refresh。
  - 被动：任何请求返回 401 时自动带着"刷新锁"重试一次；刷新失败再跳登录。
- **路由守卫**：`must_change_password=True` 的用户除 `/change-password`、`/login` 外，所有受保护页面都会被拦截，避免绕过。
- `api/request.js` 中对 401 做了请求级防抖，避免同时发 N 个刷新请求。

### 4) 敏感操作审计日志（入库持久化）

所有敏感操作持久化写入 `audit_logs` 表（`AuditLog` 模型，可按 `action / actor / target / ip / created_at` 条件查询，满足体系审核留痕要求），同时也会 `logger.warning` 输出到 stdout，便于实时监控。每条日志包含：

- `action`：操作类型
- `actor`：操作者用户名
- `target`：被操作对象用户名（如被改密/被删除的用户）
- `ip`：客户端 IP
- `user_agent`：浏览器 User-Agent
- `detail`：补充信息（如旧密码/新密码哈希标记、失败原因）
- `created_at`：时间戳（UTC）

当前覆盖的动作：

`LOGIN_OK` / `LOGIN_FAIL` / `LOGIN_LOCKED` / `LOGOUT` / `PASSWORD_CHANGED` / `PASSWORD_RESET` / `USER_CREATE` / `USER_UPDATE` / `USER_DELETE` / `USER_UNLOCK` / `RESTORE_BACKUP`。

相关代码：[audit_service.py](file:///workspace/backend/app/services/audit_service.py) · [models/__init__.py](file:///workspace/backend/app/models/__init__.py)（`AuditLog`）· [auth.py](file:///workspace/backend/app/api/v1/auth.py)

### 5) 管理员快速自检清单（上线前必做）

1. 改 `.env` 里 `SECRET_KEY`（推荐 `python -c "import secrets; print(secrets.token_urlsafe(48))"` 生成）；
2. 设置 `BACKUP_ENCRYPTION_PASSWORD`（32 位以上）；
3. 设置 `BACKUP_SECONDARY_DIR`（指向 NAS/SMB/U盘挂载点）；
4. 配置 `BACKEND_CORS_ORIGINS` 列出实际局域网访问地址（例如 `http://192.168.1.50:8080`）；
5. 登录 `admin` 后强制改密；
6. 每季度做一次「恢复演练」（见灾备方案第 5 节）。

相关代码：[user_service.py](file:///workspace/backend/app/services/user_service.py) · [security.py](file:///workspace/backend/app/core/security.py) · [main.py](file:///workspace/backend/app/main.py) · [auth.py](file:///workspace/backend/app/api/v1/auth.py) · [stores/user.js](file:///workspace/frontend/src/stores/user.js) · [ChangePassword.vue](file:///workspace/frontend/src/views/ChangePassword.vue)

---

## 🛡 灾备方案（局域网低成本 3-2-1 策略）

**3-2-1 原则** = 至少 **3** 份数据副本、用 **2** 种不同介质、其中 **1** 份离线（异地 / 拔走 U 盘 / 另一机房）。本系统按该策略在应用内 + 系统层都提供了实现，总成本几乎为 0。

### 方案总览（4 层防护）

| 层级 | 作用 | 实现 | 触发时机 |
|------|------|------|----------|
| ① 应用内定时备份 | 业务运行时自动打包 | 后台「系统配置 → 备份计划」+ APScheduler | cron（如每天 02:00） |
| ② SQLite 一致性快照 + ZIP + AES-256 加密 | SQLite 热备份不丢数据；加密后放共享盘也不怕被直接打开 | `backup_service.py`（Fernet AES-128-CBC+HMAC-SHA256 + PBKDF2 20 万轮） | 每次备份自动执行 |
| ③ 异地副本（NAS / SMB 共享 / 第 2 台服务器目录 / U 盘） | 防本机硬盘坏；局域网内几乎零成本 | `.env` 中 `BACKUP_SECONDARY_DIR`（绝对路径 + 路径越权校验 + 写后大小校验） | 每次备份后自动复制 |
| ④ 系统级旁路备份脚本 | **不依赖后端进程**；代码崩了 / 服务起不来也照样能备 | `backend/scripts/sems_standalone_backup.sh`（Linux）/ `.bat`（Windows） | crontab / 任务计划程序（建议每天 02:15，错开应用内 02:00） |

每次备份都会自动做**还原烟雾测试**（解压到临时目录→打开 sqlite→查 users/equipment 表行数→数 uploads 成员数），你**永远知道手上这份备份能不能真的还原**（可通过 `POST /api/v1/system/backup/health-check` 手动触发）。

### 快速启用（3 步）

#### 步骤 1：编辑 `backend/.env`，追加 2~3 行

```bash
# ① 备份加密密码（强烈建议单独设置；32 位以上随机）
BACKUP_ENCRYPTION_PASSWORD=这里填一串随机长字符串（可用 openssl rand -hex 16）
# ② 第二备份目录（绝对路径；必须提前建好并赋予本进程读写权限）
#    Linux:   /mnt/nas/sems_backups
#    Windows: Z:\\sems_backups 或 \\fileserver\share\sems_backups
BACKUP_SECONDARY_DIR=/mnt/nas/sems_backups
```

#### 步骤 2：系统设置打开 3 个开关

- ✅ **备份后加密**（应用内：encrypt）
- ✅ **复制到第二目录**（应用内：copy_to_secondary）
- ✅ **备份后还原烟雾测试**（应用内：run_smoke_check，默认打开）

建议：本地保留 **30** 份（1 个月每日一份）、异地保留 **14** 份。

#### 步骤 3：在操作系统层再加一条旁路任务（强烈推荐，防服务挂掉）

**Linux（crontab -e）**
```bash
# 1. 凭据配置文件：
sudo tee /opt/sems/backup.env <<'EOF'
SEMS_BACKEND_DIR=/opt/sems/backend
SEMS_SECONDARY_DIR=/mnt/nas/sems_backups
SEMS_ENC_PASSWORD=和.env中BACKUP_ENCRYPTION_PASSWORD一致或单独更复杂
SEMS_KEEP_LOCAL=30
SEMS_KEEP_SECONDARY=14
SEMS_INCLUDE_UPLOADS=1
SEMS_INCLUDE_ENV=1
EOF
sudo chmod 600 /opt/sems/backup.env
# 2. crontab 追加（每天 02:15，与应用内 02:00 错开）：
15 2 * * * /opt/sems/backend/scripts/sems_standalone_backup.sh /opt/sems/backup.env >> /var/log/sems_backup.log 2>&1
```
脚本优先走 `sqlite3 .backup` 官方热备份 API，确保 SQLite 快照一致性；`zip` + `manifest` 与应用内完全兼容，将来可直接通过后台「恢复备份」上传还原；如果填了 `SEMS_ENC_PASSWORD` 还会用 `openssl aes-256-cbc -pbkdf2 -iter 200000` 做加密（即使 SEMS 崩了，运维离线也能用 openssl 命令解开）。

**Windows（任务计划程序）**
1. 新建任务 → 触发器：每天 02:15；
2. 操作：启动程序 `D:\sems\backend\scripts\sems_standalone_backup.bat`，参数 `D:\sems\backup.conf`；
3. "不管用户是否登录都要运行"+"使用最高权限"打勾。

`backup.conf` 示例（用 `set KEY=VAL` 即可，脚本会 call 它）：
```bat
set SEMS_BACKEND_DIR=D:\sems\backend
set SEMS_SECONDARY_DIR=\\fileserver\share\sems_backups
set SEMS_ENC_PASSWORD=xxxxxxxx
set SEMS_KEEP_LOCAL=30
set SEMS_KEEP_SECONDARY=14
```

### 局域网挂载异地目录的 3 种常见方式（零成本）

#### A. Windows SMB 共享 / 公司文件服务器（最常见）
Linux 端：
```bash
sudo apt install -y cifs-utils
sudo mkdir -p /mnt/nas/sems_backups
sudo tee /etc/smbcredentials_sems <<'EOF'
username=共享账号
password=共享密码
EOF
sudo chmod 600 /etc/smbcredentials_sems
# /etc/fstab 追加（开机自动挂载）:
# //fileserver/ShareName/sems_backups /mnt/nas/sems_backups cifs nofail,vers=3.0,credentials=/etc/smbcredentials_sems,uid=1000,gid=1000,file_mode=0660,dir_mode=0770 0 0
sudo mount /mnt/nas/sems_backups
```

#### B. 旧办公机装 TrueNAS / OpenMediaVault 当 NAS（硬盘成本≈400 元 2TB）
Linux NFS 挂载：
```bash
# /etc/fstab:
# 192.168.1.50:/volume1/sems_backups /mnt/nas/sems_backups nfs _netdev,noatime,rsize=1048576,wsize=1048576 0 0
```

#### C. U 盘冷备（离线 1 份，每周轮换）
64G USB3.0 U 盘插服务器 USB 口，挂载到 `/mnt/usb_drive`，作为 `BACKUP_SECONDARY_DIR`；每周五 IT 人员拔走放入保险柜、插回新盘。  
> 注意：**务必打开加密开关**，避免 U 盘遗失后数据库被直接读取。

### 离线解密（极端情况下 SEMS 后端不可用也能还原）
备份被加密后的文件名形如 `sems_backup_xxx.zip.aes256`：
- **应用内加密版本（Fernet）**：用 `backend/scripts/decrypt_backup_standalone.py` 或直接走 Python:
  ```python
  from app.services.backup_service import decrypt_to_tempfile
  # 配置好 .env 中同一个 BACKUP_ENCRYPTION_PASSWORD 后执行即可
  tmp = decrypt_to_tempfile(Path('/path/to/file.zip.aes256'))
  print(tmp)
  ```
- **旁路脚本 openssl 加密版本（.enc 后缀）**：
  ```bash
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in sems_standalone_xxx.zip.enc -out out.zip -pass pass:你的密码
  ```

### 恢复演练 SOP（建议每季度 1 次）
1. 准备一台同网段空机器，部署一套 SEMS（空 db 也行）；
2. 用上述"离线解密"拿到 `out.zip`；
3. 进入系统管理 → 恢复备份 → 上传 zip；
4. 校验：设备台账条数、工单条数、用户列表与生产一致；抽查 2~3 份上传附件是否能正常打开。

相关代码：[backup_service.py](file:///workspace/backend/app/services/backup_service.py) · [backup_scheduler.py](file:///workspace/backend/app/services/backup_scheduler.py) · [system.py /backup/* API](file:///workspace/backend/app/api/v1/system.py) · [独立脚本 sh](file:///workspace/backend/scripts/sems_standalone_backup.sh) · [独立脚本 bat](file:///workspace/backend/scripts/sems_standalone_backup.bat)

---

## 🔌 服务守护与自启动（健壮性 / 开机自启 / 崩溃自重启）

SEMS 服务一旦跑在产线（工厂/实验室局域网服务器），最怕的是：
- 机器重启后服务没起来 → 车间工人登录不上；
- 后端因为未捕获异常/OOM/系统杀进程 → 服务挂了没人知道；
- 端口被旧的残留进程占用 → 新进程起不来、错误日志晦涩；
- SQLite WAL 异常残留 → 恢复慢/数据文件损坏概率上升。

本系统按"多路径兜底"思想，给出 **4 套部署 + 守护方案**（Linux/Windows/Docker/受限环境）。你按实际操作系统任选一套即可；同时主启动入口 `run_server.py` 也做了**入口级加固**。

### 一、入口级加固（所有方案都自动生效，无需配置）

由 [run_server.py](file:///workspace/backend/run_server.py) + [main.py](file:///workspace/backend/app/main.py) 共同提供：

| 能力 | 说明 |
|------|------|
| **端口占用友好提示** | `sys.exit(2)` 前输出「3 条解决选项 + ss/netstat 定位占用 PID」，**不会再抛一大段 OSError 堆栈**；systemd/NSSM 看到 exit 2 会标记为"配置错误"避免无限重启 |
| **SQLite WAL checkpoint 钩子** | 启动前 `PRAGMA journal_mode=WAL; synchronous=NORMAL; optimize; wal_checkpoint(TRUNCATE);`；停服前再 checkpoint 一次；显著降低「-wal 几 MB 没 checkpoint、下次启动恢复慢/损坏」概率 |
| **应用级预热 _bootstrap_once()** | 监听端口前就跑：建表 + 默认用户 + 默认设置 + 演示数据回填 + 重启标记清理 + 启动安全检查。端口打开了就说明 DB 一定就绪 |
| **uvicorn 优雅退出** | `timeout_keep_alive=75`（对齐 Nginx）、`timeout_graceful_shutdown=30`（给在途请求 30s 收尾）。配合 systemd `TimeoutStopSec=60` / docker `stop_grace_period: 45s` |
| **日志双写** | 控制台 + journald / NSSM 文件 + 内部 `TimedRotatingFileHandler` 按天滚动：`sems.log`（14 天）、`sems.error.log`（30 天 WARNING+）。**断电后仍能定位最后几分钟在干嘛** |
| **启动横幅自检入口** | 打印 `/health`、`/docs`、`日志目录`、`停止命令`，运维扫一眼就能跑自检 |

### 二、方案 A — Linux（最推荐，systemd + 看门狗 + 健康检查 crontab）

**核心文件**：
- Unit 模板：[sems.service](file:///workspace/backend/scripts/sems.service)
- 安装脚本：[install_service.sh](file:///workspace/backend/scripts/install_service.sh)
- 卸载脚本：[uninstall_service.sh](file:///workspace/backend/scripts/uninstall_service.sh)
- 健康检查脚本：[sems_healthcheck.sh](file:///workspace/backend/scripts/sems_healthcheck.sh)（连续失败 3 次自动 `systemctl restart sems`）

一键安装（推荐给 root 管理员在服务器上执行，不需要动代码）：
```bash
cd /opt/sems/backend/scripts

# ① 标准：服务名 sems，端口 8000，系统用户 sems，并追加 root crontab 健康检查
sudo bash ./install_service.sh \
  --backend-dir=/opt/sems/backend \
  --user=sems --group=sems \
  --port=8000 \
  --with-healthcheck-cron

# ② 如果不能给 root：用户级 systemd（同样开机自启，前提是管理员启用 linger）
bash ./install_service.sh --user-level --backend-dir=$HOME/sems/backend --port=8000
sudo loginctl enable-linger $USER   # 管理员执行一次；否则退出登录后服务也停
```

**得到的保障（开箱即用）**：
- ✅ `WantedBy=multi-user.target`：**开机自动启动**
- ✅ `Restart=on-failure` + `RestartPreventExitStatus=2`：崩了 / OOM / kill -9 自动重启；端口占用/配置错不再"无限重启刷日志"
- ✅ `StartLimitBurst=5 / 120s`：连续 2 分钟内启动失败 5 次 → systemd 标记 failed，人工介入（防雪崩）
- ✅ `WatchdogSec=5min`：systemd 原生看门狗兜底
- ✅ 沙箱硬ening：`ProtectSystem=strict + ReadWritePaths` 只允许写 `data/.env/scripts/`、`PrivateTmp=true`、`NoNewPrivileges=true`、`SystemCallArchitectures=native`、`MemoryMax=2G`、`TasksMax=256`
- ✅ root crontab 每 2 分钟 curl /health；连续 3 次 NG 就 `systemctl restart sems`（**极端假死（端口在但不响应）也能兜住**）

常用运维命令：
```bash
sudo systemctl status sems -l
sudo systemctl restart sems
sudo journalctl -u sems -f --since today              # 实时看 systemd 日志
sudo tail -f /var/log/sems/sems.log /var/log/sems/sems.error.log  # 看应用轮转日志
curl -fsS http://127.0.0.1:8000/health                 # 健康检查
tail -f /var/log/sems/healthcheck.log                  # 健康检查独立日志
```

卸载：
```bash
sudo bash /opt/sems/backend/scripts/uninstall_service.sh            # 停+删服务，保留日志
sudo bash /opt/sems/backend/scripts/uninstall_service.sh --purge-data   # 连日志/健康计数一起删
```

### 三、方案 B — 无 root / 受限 Linux（不能写 systemd、没有 sudo）

用看门狗 + cron `@reboot` 做**纯用户态兜底**，不用提权、不用写系统目录：

```bash
bash ./backend/scripts/watchdog_user.sh install --backend-dir=/home/john/sems/backend --port=8000
```

它会：
1. 写 `~/.sems_watchdog.conf` 保存配置（mode 600）；
2. 往当前用户 crontab 加 2 条：
   - `@reboot ... watchdog_user.sh tick ...`  开机后马上拉起一次
   - `* * * * * ... watchdog_user.sh tick ...` 每分钟跑 health 检查
3. tick 逻辑：/health ok → 清零；连续失败 3 次 → kill 旧 PID + 必要时 `fuser -k 8000/tcp` → `nohup setsid python run_server.py ...` 拉起新进程，写 pidfile 给下一轮识别。

卸载：
```bash
bash ./backend/scripts/watchdog_user.sh uninstall
```

> 适合场景：工厂小服务器是共享账号、只能用普通用户、不能装 systemd unit。稳健性略逊于 A，但比"屏幕里 tmux 挂着"强太多（tmux 杀不掉用户误关终端）。

### 四、方案 C — Windows（工厂常见，NSSM + 任务计划程序健康检查）

**核心文件**：
- 安装脚本：[install_service.bat](file:///workspace/backend/scripts/install_service.bat)
- 健康检查脚本：[sems_healthcheck.bat](file:///workspace/backend/scripts/sems_healthcheck.bat)
- 主入口仍然是 [run_server.py](file:///workspace/backend/run_server.py)

**先装 NSSM（Non-Sucking Service Manager）**：https://nssm.cc/download ，下载 64 位 `nssm.exe` 放到：
```
D:\sems\backend\scripts\nssm.exe
```
（或加入 PATH；本脚本会自动探测 `%~dp0nssm.exe` 再回退 PATH 找）

**然后管理员身份打开 cmd，执行**：
```bat
cd /d D:\sems\backend\scripts
install_service.bat /PORT 8000 /SERVICE sems
```

**得到的保障（开箱即用）**：
- ✅ **开机自启（延迟启动）**：`sc config sems start= delayed-auto`
- ✅ **崩溃自重启**：
  - NSSM 层：`AppExit Default Restart` + `AppRestartDelay 0 + AppThrottle 1500ms`（连续崩不刷 CPU）
  - SCM 层：`sc failure` 三次失败全 restart / 3s / 失败计数 24h 重置
- ✅ **健康检查计划任务**：每 2 分钟 `PowerShell Invoke-WebRequest /health`，连续失败 3 次 → `net stop && net start` 兜底
- ✅ 应用 stderr/stdout 通过 NSSM 也会写 `data/logs/nssm.out.log`，10MB 自动轮转

**Windows 运维命令**：
```bat
net start sems
net stop  sems
nssm edit sems          :: 图形化改参数、看 stderr/stdout 路径
schtasks /Run /TN "SEMS健康检查_sems"
schtasks /Query /TN "SEMS健康检查_sems" /V
curl -fsS http://127.0.0.1:8000/health
```

> 如工厂策略禁止装 NSSM，也可用 `sc.exe` + PyInstaller 打包的 `SEMS-Server.exe`（`run_server.py` 是官方 PyInstaller 入口），不过重启策略、stdout 重定向都要自己写，复杂度高，优先 NSSM。

### 五、方案 D — Docker Compose（容器化部署最快）

`docker-compose.yml` 已经按健壮性重配（[docker-compose.yml](file:///workspace/docker-compose.yml)）：

| 字段 | 作用 |
|------|------|
| `restart: unless-stopped` | 崩溃/重启 Docker/宿主机都启动；只有 `docker compose down` 才停 |
| `depends_on.condition: service_healthy` | **前端必须等后端 `/health` 通过才起来**（避免白屏 "can't reach api"） |
| backend `healthcheck` | 每 30s curl 容器内 8000/health，失败 3 次标记 unhealthy，compose 重启策略才生效 |
| frontend `healthcheck` | 每 45s 看 Nginx 能不能回首页 |
| `stop_grace_period: 45s` | 对齐 uvicorn `timeout_graceful_shutdown=30`，留 15s 缓冲 |
| `sems-logs` 独立卷 | `/var/log/sems` 单独卷，方便 Filebeat/ELK 采集，即使容器重建日志也保留 |
| `BACKEND_CORS_ORIGINS` | 默认不开放 `*`，改为仅 localhost |

常用：
```bash
docker compose up -d --build          # 首次构建启动
docker compose ps                     # 查 healthy 状态
docker compose logs -f backend        # 只看后端容器日志
docker inspect --format='{{.State.Health.Log}}' sems-backend | jq .  # 看最近 5 次健康检查详情
```

### 六、上线前自检验收清单（每一条都做到，基本不会意外停机）

| # | 验证项 | 命令 / 方法 | 期望 |
|---|--------|-------------|------|
| 1 | 守护方案已启用 | `systemctl is-enabled sems` / `nssm get sems Start` / `docker compose ps` | `enabled` / `AUTO` / 显示 running + healthy |
| 2 | 端口占用提示正确 | 占住 8000 再启后端 | 给出"占用 PID + 3 条出路"并 `echo $? = 2` |
| 3 | 崩溃自重启有效 | 手动 `kill -9 <uvicorn-PID>`（Linux） / 任务管理器结束 python.exe（Win） | 10s 内 process 再次出现，PID 不同，`/health = ok` |
| 4 | 优雅停服有效 | 传一个长请求，再 `systemctl restart sems` | 长请求未被截断，日志出现 `[SEMS] 退出前 SQLite checkpoint 完成。` |
| 5 | 开机自启有效 | `sudo reboot`（Linux） / 服务器重启（Win） | 重启完无需登录，`curl /health` 本地能通 |
| 6 | 日志双写有效 | 发请求 / 登登录几次，`journalctl -u sems` 与 `tail /var/log/sems/sems.log` 都有记录 | 两边都看得到同样请求 |
| 7 | 健康检查兜底 | 手动把 8000 iptables drop 掉（仅测试）或改健康端点临时返回非 ok | 3 次失败后 systemctl/服务被重启 |

### 七、4 套方案选型速查表

| 你的部署场景 | 推荐方案 | 额外需要 | 自启 | 崩溃重启 | 健康检查兜底 |
|-------------|----------|---------|-----|---------|---------|
| 工厂 Linux 服务器，有 root | **A. systemd** | N/A | ✅ | ✅ | ✅ (cron + 重启) |
| 只有普通用户，无 sudo | **B. watchdog_user.sh** | cron 可用 | ✅ (@reboot) | ✅ | ✅ (每分钟 tick) |
| Windows Server / Win10 工控机 | **C. NSSM + 任务计划** | 装 nssm.exe | ✅ | ✅ | ✅ (每 2 分钟) |
| 习惯 Docker 部署 | **D. Compose** | docker + compose | ✅ | ✅ | ✅ (compose healthcheck) |

---

## 表单模板与结构化记录

传统模式下，作业记录（批次记录、参数记录、检验记录、交接班记录等）通过上传 PDF/Excel 附件归档。本功能允许管理员**定义表单模板**（字段、类型、选项、单位、范围），操作员**选模板动态生成电子表单并填写**，数据结构化存储，支持导出 JSON/CSV，便于后续检索和分析。

### 工作流程

```
① 管理员定义模板                    ② 操作员填写                      ③ 归档与导出
┌─────────────────────┐     ┌─────────────────────────┐     ┌───────────────────┐
│ 表单模板管理页面      │     │ 工艺文件→作业记录页面     │     │ 自动归档为工艺文件   │
│ - 创建模板            │ ──→ │ - 新建电子表单→选模板    │ ──→ │ - 查看填写详情      │
│ - 定义字段（9种类型） │     │ - 动态渲染表单            │     │ - 导出 JSON / CSV   │
│ - 上传参考文件        │     │ - 保存草稿 / 提交         │     │ - 可继续编辑修改     │
│ - 启用 / 停用         │     │ - 已有记录可点击「填写」   │     │                   │
└─────────────────────┘     └─────────────────────────┘     └───────────────────┘
```

### 支持的字段类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `text` | 单行文本 | 操作员姓名 |
| `textarea` | 多行文本 | 异常描述 |
| `number` | 数字（可设 min/max/单位） | 腔体温度 (℃) |
| `select` | 下拉选择 | 班次 = A/B/C |
| `radio` | 单选 | 合格 / 不合格 |
| `date` | 日期 | 生产日期 |
| `datetime` | 日期时间 | 开机时间 |
| `time` | 时间 | 交接时间 |
| `boolean` | 是/否开关 | 是否完成清洁 |

### 权限说明

| 功能 | 权限 Key | 默认允许角色 |
|------|----------|-------------|
| 模板管理（创建/编辑/删除/停用） | `form_template.manage` | admin, process_engineer |
| 记录填写（新建/编辑/提交） | `form_record.fill` | admin, engineer, process_engineer, operator |
| 记录删除 | `form_record.delete` | admin |

> **注意**：表单模板管理页面（创建/编辑模板）仅管理员可访问。工艺文件页面中的「新建电子表单」和「填写」按钮对所有有 `form_record.fill` 权限的角色可见。

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/form-templates` | 模板列表（支持分类/机台/状态过滤） |
| POST | `/api/v1/form-templates` | 创建模板 |
| PUT | `/api/v1/form-templates/{id}` | 更新模板 |
| DELETE | `/api/v1/form-templates/{id}` | 删除模板 |
| POST | `/api/v1/form-templates/{id}/ref-file` | 上传参考模板文件 |
| GET | `/api/v1/form-templates/{id}/ref-file` | 下载参考模板文件 |
| GET | `/api/v1/form-records` | 记录列表 |
| POST | `/api/v1/form-records` | 创建记录（含 auto_submit + link_process_doc） |
| GET | `/api/v1/form-records/{id}` | 记录详情（含字段值） |
| PUT | `/api/v1/form-records/{id}` | 更新记录（元数据 + 字段值） |
| PATCH | `/api/v1/form-records/{id}/submit` | 提交草稿 |
| PATCH | `/api/v1/form-records/{id}/void` | 作废记录 |
| GET | `/api/v1/form-records/{id}/export/{format}` | 导出 JSON / CSV |

相关代码：[models/__init__.py](file:///workspace/backend/app/models/__init__.py)（FormTemplate / FormRecord / FormRecordValue）· [api/v1/form_templates.py](file:///workspace/backend/app/api/v1/form_templates.py) · [api/v1/form_records.py](file:///workspace/backend/app/api/v1/form_records.py) · [views/FormTemplates.vue](file:///workspace/frontend/src/views/FormTemplates.vue) · [views/ProcessDocuments.vue](file:///workspace/frontend/src/views/ProcessDocuments.vue)

---

## 📑 文控系统（符合体系标准）

基于现有工艺文件 + 表单模板模块扩展，实现符合质量体系标准的文档控制能力。核心设计原则：**文档编码由用户在系统中手动编辑**（非系统自动生成），系统负责审批链、修订记录、分发收回、受控章等合规控制。

### 审批流程（三级电子签名）

```
草稿 ──prepare──→ 审核中 ──review──→ 审核通过 ──approve──→ 生效
  ↑                  │                  │                    │
  │                  │                  ├──reject──→ 草稿     │
  └──reject──────────┘                  └──reject──→ 草稿     │
                                                          生效→作废 (终态)
```

| 阶段 | stage | 权限点 | 允许角色 | 状态变更 |
|------|-------|--------|---------|---------|
| ① 编制提交 | `prepare` | `process_doc.submit_review` | admin、process_engineer | 草稿 → 审核中 |
| ② 审核通过 | `review` | `process_doc.approve` | admin、qa | 不变（仅记录通过） |
| ③ 批准生效 | `approve` | `process_doc.approve` | admin、qa | 审核中 → 生效 |

**电子签名机制**：每次签署需二次密码校验 → 生成 SHA256 签名指纹（含 doc_id / stage / signer_id / signed_at / comment / password_validated）→ 前端展示签名后 8 位。

**状态机白名单**：

| 流转 | 合法 |
|------|:---:|
| 草稿 → 审核中 | ✅ |
| 草稿 → 生效 | ✅ |
| 草稿 → 作废 | ✅ |
| 审核中 → 生效 | ✅ |
| 审核中 → 作废 | ✅ |
| 审核中 → 草稿 | ✅ |
| 生效 → 作废 | ✅ |
| 作废 → 生效 | ❌ 拦截 |

**生效副作用**：自动写入 `effective_date`，按 `review_cycle_month`（月）计算 `next_review_date`，同组旧生效版自动作废。

### 权限矩阵

| 权限点 | admin | process_engineer | qa | engineer | operator |
|--------|:---:|:---:|:---:|:---:|:---:|
| 上传/创建草稿 (`process_doc.create`) | ✅ | ✅ | - | - | - |
| 提交审核 (`process_doc.submit_review`) | ✅ | ✅ | - | - | - |
| 审核/批准 (`process_doc.approve`) | ✅ | - | ✅ | - | - |
| 作废 (`process_doc.void`) | ✅ | - | ✅ | - | - |
| 只看生效版 (`process_doc.view_effective`) | ✅ | ✅ | ✅ | ✅ | ✅ |
| 查看全部版本 (`process_doc.view_all_versions`) | ✅ | ✅ | ✅ | ✅ | - |
| 表单审核 (`form_record.audit`) | ✅ | - | ✅ | - | - |
| 附加修正 (`form_record.amend`) | ✅ | - | ✅ | - | - |

### 功能模块

| 模块 | 说明 |
|------|------|
| **文档编号规则** | `DocNoRule` 模型定义各分类编号格式（前缀/分隔符/年份/序号位数）；管理员在系统中编辑文档编码 |
| **审批链** | 三级签署（prepare/review/approve）+ 驳回路径（reject_prepare/reject_review）；防重复审核；批准前置条件校验 |
| **修订记录** | 记录变更原因、摘要、明细项（字段级 before/after 对比） |
| **分发收回** | 批量创建分发记录（USER/DEPT），支持批量收回 + 备注；分发台账可追溯 |
| **PDF 水印受控章** | 下载 PDF 自动加盖受控章（文档编号 + 状态 + 用户信息 + 日期） |
| **表单审核锁定** | 已审核表单禁止原地修改，返回 400 提示走附加修正 |
| **附加修正** | PENDING → APPROVED 流转；需密码二次校验；记录原值/修正值/原因 |
| **复审告警** | 按 `next_review_date` 查询 30 天内到期 / 已过期文档；前端 Badge 红色告警 |

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/process-doc-qc/approvals/sign` | 电子签名签署（prepare/review/approve/reject_*） |
| GET | `/api/v1/process-doc-qc/documents/{id}/approvals` | 审批链列表 |
| GET | `/api/v1/process-doc-qc/documents/{id}/change-logs` | 修订记录列表 |
| POST | `/api/v1/process-doc-qc/documents/{id}/change-logs` | 创建修订记录 |
| GET | `/api/v1/process-doc-qc/documents/{id}/distributions` | 分发记录列表 |
| POST | `/api/v1/process-doc-qc/documents/{id}/distributions` | 创建分发记录 |
| POST | `/api/v1/process-doc-qc/distributions/revoke` | 批量收回分发 |
| GET | `/api/v1/process-doc-qc/review-alerts` | 复审告警统计 |
| POST | `/api/v1/form-record-qc/records/{id}/audit` | 表单审核 |
| GET | `/api/v1/form-record-qc/records/{id}/amendments` | 附加修正列表 |
| POST | `/api/v1/form-record-qc/records/{id}/amendments` | 创建附加修正 |
| POST | `/api/v1/form-record-qc/amendments/{id}/approve` | 审批附加修正 |
| GET/POST/PUT/DELETE | `/api/v1/doc-no-rules` | 文档编号规则 CRUD |

相关代码：[models/__init__.py](file:///workspace/backend/app/models/__init__.py)（DocNoRule / DocumentApproval / DocumentChangeLog / DocumentDistribution / FormRecordAmendment）· [api/v1/process_doc_qc.py](file:///workspace/backend/app/api/v1/process_doc_qc.py) · [api/v1/form_record_qc.py](file:///workspace/backend/app/api/v1/form_record_qc.py) · [services/pdf_watermark.py](file:///workspace/backend/app/services/pdf_watermark.py) · [views/ProcessDocuments.vue](file:///workspace/frontend/src/views/ProcessDocuments.vue)

---

## 🚀 设备管理扩展模块（合规 / 全生命周期 / 数据价值）

基于晶名设备部门现状摸底，补齐以下三大侧、六个模块。所有模块已在后端注册路由、前端注册页面与菜单，随启动数据库自动建表，开箱即用。

### 路由与页面总览

| 模块 | 后端路由前缀 | 前端页面 | 菜单位置 |
|------|-------------|----------|----------|
| 安全检查（P0） | `/api/v1/safety-inspections` | [SafetyInspection.vue](file:///workspace/frontend/src/views/SafetyInspection.vue) | 合规安全 |
| 工单 SLA / 升级（P1） | `/api/v1/work-order-sla` + `/api/v1/work-orders`（SLA 字段扩展） | [WorkOrderSLA.vue](file:///workspace/frontend/src/views/WorkOrderSLA.vue) | 日常运维 |
| 设备生命周期 T0-T3（P2） | `/api/v1/equipment-lifecycle` | [EquipmentLifecycle.vue](file:///workspace/frontend/src/views/EquipmentLifecycle.vue) | 设备全生命周期 |
| 润滑管理五定（P3） | `/api/v1/lubrication` | [Lubrication.vue](file:///workspace/frontend/src/views/Lubrication.vue) | 设备全生命周期 |
| 故障知识库（P6） | `/api/v1/knowledge` | [KnowledgeBase.vue](file:///workspace/frontend/src/views/KnowledgeBase.vue) | 数据价值 |
| 设备成本 LCC（P7） | `/api/v1/equipment-costs` | [EquipmentCost.vue](file:///workspace/frontend/src/views/EquipmentCost.vue) | 数据价值 |

相关代码：[models/__init__.py](file:///workspace/backend/app/models/__init__.py)（`SafetyInspection` / `WorkOrder` SLA 字段 / `EquipmentLifecycle` / `LubricationPoint` / `LubricationRecord` / `KnowledgeEntry` / `EquipmentCost`）· [api/v1/safety_inspection.py](file:///workspace/backend/app/api/v1/safety_inspection.py) · [api/v1/work_order_sla.py](file:///workspace/backend/app/api/v1/work_order_sla.py) · [api/v1/equipment_lifecycle.py](file:///workspace/backend/app/api/v1/equipment_lifecycle.py) · [api/v1/lubrication.py](file:///workspace/backend/app/api/v1/lubrication.py) · [api/v1/knowledge_base.py](file:///workspace/backend/app/api/v1/knowledge_base.py) · [api/v1/equipment_cost.py](file:///workspace/backend/app/api/v1/equipment_cost.py)

---

### 🛡 安全检查（P0 合规安全侧 · 风险最高）

针对 EHS 合规风险最高的一项单独建模，覆盖安全装置、特种设备、环保、消防四类检查。

#### 数据模型

- `SafetyInspection`：检查项主表
  - `check_type`：检查类型（`safety_device` / `special_equipment` / `environmental` / `fire_protection`）
  - `frequency`：检查频次（`daily` / `weekly` / `monthly` / `quarterly` / `yearly`），用于自动推算下次检查日
  - `last_check_date` / `next_check_date`：上次检查 / 下次检查日
  - `result`：检查结果（`pending` / `pass` / `fail` / `n_a`）
  - `findings` / `corrective_action`：检查发现 / 整改措施
  - `certificate_no` / `certificate_expiry`：特种设备检验证书编号 / 到期日（仅特种设备类）

#### 功能

| 操作 | 路径 | 说明 |
|------|------|------|
| 列表查询 | `GET /api/v1/safety-inspections` | 支持按设备/类型/结果筛选，支持 `upcoming_days`（默认 30 天）筛选即将到期/已过期项 |
| 新建/编辑/删除 | `POST/PUT/DELETE /api/v1/safety-inspections[/{id}]` | 维护检查项主数据 |
| 执行检查 | `POST /api/v1/safety-inspections/{id}/check` | 提交结果/发现/整改，自动按频次推算下次检查日 |
| 告警列表 | `GET /api/v1/safety-inspections/alerts` | 拉取 30 天内到期或已逾期项，前端 Badge 计数 |

> 前端表格对「下次检查」与「证书到期」日期自动高亮：30 天内黄底、已逾期红字；告警按钮显示待办数量徽标。

---

### ⏱ 工单 SLA / 升级（P1 合规安全侧）

在 `WorkOrder` 模型上扩展 SLA 字段，避免单独立表带来的维护负担。

#### 数据字段（扩展 `WorkOrder`）

- `sla_response_target_min` / `sla_resolution_target_min`：目标响应时长 / 目标解决时长（分钟）
- `responded_at` / `resolved_at`：实际响应 / 实际解决时间
- `sla_response_min` / `sla_resolution_min`：实际响应 / 实际解决时长（自动计算）
- `sla_breached`：是否违约（布尔）
- `escalated_to_id`：超时升级指派人 ID
- `priority`：紧急度（与原有紧急度一致，用于 SLA 模板预设）

#### 功能

| 操作 | 路径 | 说明 |
|------|------|------|
| 设置/更新 SLA 目标 | `PUT /api/v1/work-orders/{id}` 或 `PUT /api/v1/work-order-sla/{id}/targets` | 设定响应/解决时长目标 |
| 标记响应 | `POST /api/v1/work-order-sla/{id}/respond` | 记录实际响应时间，自动计算 `sla_response_min` |
| 标记解决 | `POST /api/v1/work-order-sla/{id}/resolve` | 记录实际解决时间，自动计算 `sla_resolution_min` 与 `sla_breached` |
| 超时升级 | `POST /api/v1/work-order-sla/{id}/escalate` | 标记超时并指派升级人 |
| SLA 统计 | `GET /api/v1/work-order-sla/stats` | SLA 达成率、平均响应/解决时长、违约数 |

---

### 🔄 设备生命周期 T0-T3（P2 全生命周期侧 · 体系完整性）

按选型 → 采购 → 安装调试 → 量产移交四阶段建模，一个阶段一条记录，便于时间线展示。

#### 数据模型

- `EquipmentLifecycle`：阶段记录表
  - `stage`：`T0`（选型）/ `T1`（采购）/ `T2`（安装调试）/ `T3`（量产移交）
  - **T0 选型**：`vendor_candidates`（JSON 候选供应商列表）/ `selected_vendor` / `ur_summary`（URS 用户需求摘要）
  - **T1 采购**：`po_no` / `po_amount` / `delivery_date`
  - **T2 安装调试**：`fat_date` / `fat_result` / `fat_notes`、`sat_date` / `sat_result` / `sat_notes`、`commissioning_date` / `commissioning_notes`
  - **T3 量产移交**：`handover_date` / `handover_to` / `acceptance_result` / `acceptance_notes`
  - `attachment_path`：附件路径（FAT/SAT 报告等）
  - `status`：`in_progress` / `completed` / `aborted`

#### 功能

| 操作 | 路径 | 说明 |
|------|------|------|
| 阶段列表 | `GET /api/v1/equipment-lifecycle` | 支持按设备/阶段筛选 |
| 新建阶段 | `POST /api/v1/equipment-lifecycle` | 新建任意阶段（建议按 T0→T3 顺序补齐） |
| 编辑/删除 | `PUT/DELETE /api/v1/equipment-lifecycle/{id}` | 修改或删除阶段 |
| 标记完成 | `POST /api/v1/equipment-lifecycle/{id}/complete` | 阶段流转到 `completed` |

> 前端页面按时间倒序展示各阶段卡片，并以时间线串联 T0→T3，便于设备主管一眼看全流程进度。

---

### 🛢 润滑管理（五定）（P3 全生命周期侧）

落实"定点、定人、定时、定质、定量"五定原则。

#### 数据模型

- `LubricationPoint`：润滑点定义（五定）
  - `equipment_id` / `point_name` / `position`（定点）
  - `responsible_person`（定人）
  - `frequency` / `interval_days`（定时）
  - `oil_type` / `oil_grade`（定质）
  - `quantity` / `unit`（定量）
  - `last_lubricated_date` / `next_lubricated_date`：上次/下次润滑日
- `LubricationRecord`：润滑执行记录
  - 关联 `LubricationPoint`，记录执行人、实际用量、备注

#### 功能

| 操作 | 路径 | 说明 |
|------|------|------|
| 润滑点 CRUD | `/api/v1/lubrication/points[/{id}]` | 维护润滑点主数据 |
| 执行润滑 | `POST /api/v1/lubrication/points/{id}/record` | 提交执行记录，自动按 `interval_days` 推算下次润滑日 |
| 到期告警 | `GET /api/v1/lubrication/due` | 拉取即将到期/已逾期润滑点 |

---

### 📚 故障知识库（P6 数据价值侧 · 精益化阶段）

将历史故障工单 + 8D 报告沉淀为可检索的故障知识，支持双路径归档、相似案例推荐、复发次数追踪。

#### 数据模型

- `KnowledgeEntry`：知识条目
  - `title` / `fault_category` / `symptom`（故障现象）
  - `root_cause`（根因）/ `solution`（处置）/ `prevention`（预防）
  - `equipment_id`：关联设备（可空，表示通用知识）
  - `equipment_model`：设备型号（跨设备复用检索）
  - `source_work_order_id`：来源工单 ID（可空）
  - `source_d8_report_id`：来源 8D 报告 ID（可空）
  - `tags`（标签，CSV）
  - `views`：浏览次数（GET 详情时自动 +1）
  - `recurrence_count`：复发次数
  - `status`：`active` / `archived`

#### 功能

| 操作 | 路径 | 说明 |
|------|------|------|
| 知识列表 | `GET /api/v1/knowledge` | 支持按设备/分类/关键词全文检索（title / symptom / root_cause / solution） |
| 从工单归档 | `POST /api/v1/knowledge/from-work-order/{wo_id}` | 把工单的描述/根因/处置/预防 + fault_category 自动填充为知识条目；payload 可覆盖 title / tags / equipment_model / fault_category |
| **从 8D 报告归档** | **`POST /api/v1/knowledge/from-d8/{d8_id}`** | 自动提取 D0（problem）+ D2（problem_desc）→ symptom / D4 → root_cause / D5 → solution / D7 → prevention；默认标签 `8D,{报告编号}`；payload 可覆盖 title / tags / equipment_model / fault_category |
| 知识 CRUD | `POST/PUT/DELETE /api/v1/knowledge[/{id}]` | 手动维护知识 |
| 相似案例 | `GET /api/v1/knowledge/similar` | 按 `equipment_id` + `fault_category` 双维匹配推荐（同设备同分类优先，退化同设备或同分类） |
| 标记复发 | `POST /api/v1/knowledge/{id}/recurrence` | `recurrence_count + 1`，追踪同根因复发 |

---

### 💰 设备成本 LCC（P7 数据价值侧 · 精益化阶段）

单设备全生命周期成本汇总与统计分析。

#### 数据模型

- `EquipmentCost`：成本记录
  - `equipment_id`：关联设备
  - `cost_type`：成本类型（`purchase` 采购 / `maintenance` 维护 / `spare_part` 备件 / `energy` 能耗 / `depreciation` 折旧 / `disposal` 报废）
  - `amount`：金额
  - `occurred_date`：发生日期
  - `remark` / `ref_type` / `ref_id`：备注与来源类型（如工单/PM 计划）

#### 功能

| 操作 | 路径 | 说明 |
|------|------|------|
| 成本记录 CRUD | `/api/v1/equipment-costs[/{id}]` | 按设备维护成本明细 |
| 单设备汇总 | `GET /api/v1/equipment-costs/equipment/{eq_id}/summary` | 单设备各类成本汇总 + 总成本 |
| 按类型统计 | `GET /api/v1/equipment-costs/stats/by-type` | 按成本类型汇总（饼图） |
| 年度趋势 | `GET /api/v1/equipment-costs/stats/yearly-trend` | 按年汇总（折线图） |
| Top10 高成本设备 | `GET /api/v1/equipment-costs/stats/top-equipment` | 排名前 10 的高成本设备 |

---

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| 前端页面显示 "service not running" | 后端未启动或已停止，请先启动后端服务 |
| `vite: not found` | 前端依赖未安装，执行 `cd frontend && npm install` |
| `No module named 'fastapi'` | 后端虚拟环境未激活或依赖未安装，执行 `source .venv/bin/activate && pip install -r requirements.txt` |
| 端口被占用 | 修改启动端口：后端 `--port 9000`，前端在 `vite.config.js` 中修改 `port` |
| Docker 构建失败 | 确认 Docker 服务已启动，磁盘空间充足，网络可访问镜像源 |
| 登录后提示 401 | Token 已过期，清除浏览器 localStorage 后重新登录 |
| 页面反复提示"登录已过期，请重新登录" | **两种常见原因：** ① 浏览器缓存了旧 token（改密后旧 token 已失效），清除方法：F12 → Application → Local Storage → 删除 `sems_` 前缀的条目，或直接用无痕窗口打开；② 密码已被修改但仍在用旧密码登录——默认初始密码为弱密码 `admin123`，系统会在启动时自动标记 `must_change_password=True` 强制改密，改密后需使用新密码登录。若忘记密码，可在后端执行重置脚本：`python -c "from app.core.database import SessionLocal; from app.models import User; from app.core.security import get_password_hash; db=SessionLocal(); u=db.query(User).filter(User.username=='admin').first(); u.hashed_password=get_password_hash('新密码'); u.must_change_password=False; u.failed_login_count=0; u.locked_until=None; db.commit(); print('OK')"` |

---

## 许可证

私有项目，未开源。
