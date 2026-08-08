# SEMS — 半导体设备管理系统

Semiconductor Equipment Management System

一个面向半导体制造车间的轻量级设备管理平台，覆盖设备台账、实时状态看板、PM 维护计划、工单管理、点检巡检、备件管理、OEE 分析等功能。基于 FastAPI + Vue 3 构建，开箱即用。

---

## 版本 Highlights（最近一次主要更新）

- **设备 DOWN 触发工单**：操作员 / 设备 / 工艺人员都可在台账右上角切换设备状态到 `DOWN`，系统自动创建 `REPAIR` 类型工单（含故障现象 + 紧急度），自动派发。
- **工单持续时长可见**：列表 & 详情页显示工单从创建到关闭（或当前）的持续时长，便于跟踪。
- **关键词检索**：工单支持标题/描述/现象关键词检索（例：搜「漏真空」可命中所有包含该词的工单）。
- **局域网安全加固**：密码策略、账户锁定、JWT 访问+刷新令牌、敏感操作审计、强制首次改密、CSP/X-Frame 响应头（见「安全加固」章节）。
- **低成本灾备（3-2-1）**：备份加密、NAS/SMB 异地副本、烟雾还原测试、系统级旁路 cron/任务计划备份脚本（见「灾备方案」章节）。

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
| 工艺文件 | 文档版本管理 |
| OEE 分析 | 设备综合效率统计 |
| 品管工具 | 8D / FMEA |
| 环境核查 | 环境参数日志 |
| 人员管理 | 资质、培训、技能矩阵 |
| 资产管理 | 资产盘点、调拨报废 |
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

## 🔒 安全加固（面向局域网部署）

SEMS 运行在工厂内网时，依然有「临时接入电脑 / 运维共享账号 / 被嗅探 / 离职人员仍能登录」等风险。本系统内置以下安全能力（默认开启大部分）：

### 1) 身份认证

| 能力 | 说明 | 默认状态 |
|------|------|----------|
| 访问+刷新令牌双 JWT | `access_token` 2 小时 + `refresh_token` 7 天，前端到期前 5 分钟自动续期；降低长期有效密钥被窃取风险 | 启用 |
| 密码慢哈希 | bcrypt (rounds=12)，抗 GPU 暴力破解 | 启用 |
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

### 4) 敏感操作审计日志

所有敏感操作通过 `logger.warning("[SEC-AUDIT] ...")` 输出到后端 stdout（可再接入 logrotate / syslog / 文件日志采集器），包含：**操作类型、用户名、客户端 IP、User-Agent、时间戳**。当前覆盖的动作：

`LOGIN_OK` / `LOGIN_FAIL` / `LOGIN_LOCKED` / `PASSWORD_CHANGED_OK` / `PASSWORD_RESET` / `USER_CREATE` / `USER_UPDATE` / `USER_DELETE` / `USER_UNLOCK` / `LOGOUT` / `RESTORE_BACKUP`。

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

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| 前端页面显示 "service not running" | 后端未启动或已停止，请先启动后端服务 |
| `vite: not found` | 前端依赖未安装，执行 `cd frontend && npm install` |
| `No module named 'fastapi'` | 后端虚拟环境未激活或依赖未安装，执行 `source .venv/bin/activate && pip install -r requirements.txt` |
| 端口被占用 | 修改启动端口：后端 `--port 9000`，前端在 `vite.config.js` 中修改 `port` |
| Docker 构建失败 | 确认 Docker 服务已启动，磁盘空间充足，网络可访问镜像源 |
| 登录后提示 401 | Token 已过期，清除浏览器 localStorage 后重新登录 |

---

## 许可证

私有项目，未开源。
