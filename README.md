# GxP Guider

GxP Guider是一个轻量级的GMP指南管理与分发平台，目标用户为制药行业从业者和质量管理人员。网站提供 ISPE、PDA、WHO 等组织的GMP文档浏览、检索与下载服务，无需付费。

## 功能特性

- 文档管理：单条上传、PDF重命名、CSV批量导入、审核发布
- 前端展示：卡片式列表、详情页预览
- 用户系统：注册登录、个人资料管理
- 后台管理：文档、分类、用户管理
- 定时爬取：自动从ISPE、PDA、WHO等网站获取最新GMP文档
- 邮件推送：定时向用户推送最新文档信息

## 技术栈

- 后端：Python 3 + Flask + SQLAlchemy
- 数据库：SQLite（开发/测试默认）
- 模板/样式：Jinja2 + Tailwind CSS（CDN）+ Alpine.js + Font Awesome
- 文件存储：Cloudflare R2（S3 兼容，提供本地静态回退）
- 认证与安全：Flask-Login、WTForms/CSRF、Werkzeug 密码散列
- 管理界面：Flask-Admin（自定义视图与批量导出）
- 日志：`logging_config.py` 输出到 `logs/`
- 部署：Docker / Docker Compose（推荐）

## 安装与运行

### 本地开发环境

1. 克隆项目代码：
   ```
   git clone <repository-url>
   cd GMP-Seeker
   ```

2. 使用 uv 创建虚拟环境并安装依赖：
   ```
   uv venv
   source .venv/bin/activate
   uv pip install .
   ```

3. 设置环境变量：
   ```
   export FLASK_APP=run.py
   export FLASK_ENV=development
   ```

4. 初始化数据库：
   ```
   uv run python scripts/init_db.py
   ```

5. 运行应用：
   ```
   flask run
   ```

6. 访问应用：
   打开浏览器访问 `http://localhost:5000`

### 生产环境部署

生产环境请使用 Docker（见文末“生产环境部署（Docker Compose + SQLite）”章节）。

提示：也可使用 `uv run` 运行命令（如 `uv run flask run`），与上述效果一致。

## 环境配置

项目支持三种环境配置：

### 开发环境 (development)
- 启用调试模式
- 使用开发数据库 (data-dev.sqlite)
- 适用于本地开发和测试

### 测试环境 (testing)
- 用于运行单元测试
- 使用内存数据库
- 启用测试模式

### 生产环境 (production)
- 关闭调试模式
- 使用生产数据库 (data.sqlite)
- 适用于生产部署

可以通过设置 `FLASK_ENV` 环境变量来切换不同环境：
```
export FLASK_ENV=development  # 开发环境
export FLASK_ENV=testing      # 测试环境
export FLASK_ENV=production   # 生产环境
```

### 环境变量配置文件 (.env)

项目支持使用 `.env` 文件来配置环境变量，这对于管理敏感信息（如数据库密码、API 密钥等）非常有用。

#### .env.example 文件的作用

`.env.example` 文件是一个示例配置文件，展示了项目可能需要的所有环境变量及其格式。它不是实际的配置文件，而是作为模板供开发者参考。

#### 什么时候需要配置 .env 文件

1. **生产环境部署**：当部署到生产环境时，需要配置真实的数据库连接信息、邮件服务器配置、云存储密钥等敏感信息。

2. **自定义配置**：如果需要自定义项目的某些行为，比如修改默认的数据库路径、邮件服务器地址等。

3. **团队协作**：在团队开发中，`.env.example` 文件可以帮助新成员快速了解项目需要哪些环境变量。

#### 如何使用 .env 文件

1. 复制 `.env.example` 文件并重命名为 `.env`：
   ```
   cp .env.example .env
   ```

2. 编辑 `.env` 文件，填入实际的配置值：
   ```
   # 核心配置
   SECRET_KEY=your-real-secret-key
   FLASK_ENV=production
   DATABASE_URL=sqlite:////app/data/data.sqlite

   # 邮件配置
   MAIL_SERVER=smtp.your-company.com
   MAIL_PORT=587
   MAIL_USERNAME=your-production-email@company.com
   MAIL_PASSWORD=your-email-password

   # R2 / CDN
   R2_BUCKET_NAME=your-bucket
   R2_ACCESS_KEY_ID=your-access-key
   R2_SECRET_ACCESS_KEY=your-secret
   R2_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com
   CDN_URL=https://cdn.example.com
   ```

3. 确保 `.env` 文件不会被提交到版本控制系统中（已经在 `.gitignore` 中配置）。

#### Docker 环境中的 .env 文件

在使用 Docker 部署时，`.env` 文件会被传递给容器，使得容器内的应用可以读取这些配置。

注意：`.env` 文件中的配置会覆盖 `config.py` 中的默认配置。

## 使用 uv（命令速查）

项目使用 uv 管理虚拟环境与依赖。安装方法请参考 [uv 官方文档](https://docs.astral.sh/uv/)。

- 安装依赖：`uv venv && source .venv/bin/activate && uv pip install .`
- 运行应用：`flask run` 或 `uv run flask run`
- 初始化数据库：`uv run python scripts/init_db.py`（默认优先从 Excel 导入，见下文“文档导入”）
- 运维脚本示例：`uv run python scripts/manage.py list-users`

### 依赖管理

- 单一来源：依赖以 `pyproject.toml`（声明）+ `uv.lock`（锁定）为准。
- 不再维护 `requirements.txt`。如需兼容第三方平台，可临时生成：
  - `uv pip freeze > requirements.txt`
- Docker 构建已基于 `uv pip install .`，与本地保持一致。

## 文档导入

脚本支持从 `data/` 目录批量导入文档，默认“Excel 优先，CSV 回退”。

- Excel 首选：检测到 `data/documents_export.xlsx` 且安装了 `openpyxl` 时，优先使用该文件导入。
- CSV 回退：缺少 `documents_export.xlsx` 或未安装 `openpyxl` 时，回退为按组织的 `*_documents.csv` 导入（ISPE/PDA/WHO/FDA Guidance/APIC）。

Excel 列要求（严格匹配这些中文列名）：

ID、组织、分类、英文标题、中文标题、概述、中文概述、封面链接、出版日期、源链接、原版文档链接、中文版文档链接、原版预览链接、中文版预览链接、价格、创建时间、更新时间。

导入规则摘要：

- 组织/分类：从“组织/分类”列读取，按需创建；CSV 模式下亦会按数据动态创建分类。
- 去重：以“英文标题”作为唯一键。默认遇到重复标题跳过；可用 `--upsert` 更新非空字段。
- 价格：优先使用 Excel 中“价格”，否则回退 `data/price_list.xlsx`（按英文标题匹配），仍无则置 0。价格采用向下取整。
- 时间：出版日期尽力解析为 `YYYY-MM-DD`；“创建时间/更新时间”若为空或非法则忽略，走模型默认。

常用命令：

- 默认（自动选择来源，优先 Excel）：
  - `uv run python scripts/init_db.py`
- 强制使用 Excel：
  - `uv run python scripts/init_db.py --source excel`
- 仅导入某组织：
  - `uv run python scripts/init_db.py --org ISPE`
- 开启更新（重复标题时以非空值覆盖）：
  - `uv run python scripts/init_db.py --upsert`
- 仅校验不写库：
  - `uv run python scripts/init_db.py --dry-run --source excel --org PDA`
- 本地模式（用本地文件替换 R2 链接，并在导入时自动校验/下载缺失文件）：
  - `uv run python scripts/init_db.py --local-mode`
  - 可自定义本地根目录与 R2 域名：`uv run python scripts/init_db.py --local-mode --local-root ./app/static/uploads/documents --r2-base https://gmp-guidelines.wen817.com`
  - 运行时会统计需要下载/更新的文件数量，提示 `是否继续下载并完成初始化？[y/N]:`，输入 `y` 后才会从 R2 下载到本地并提交数据，否则中断且回滚。
  - 本地存储结构沿用上传回退路径：`app/static/uploads/documents/{org}/{file}` 与 `app/static/uploads/documents/preview/{org}/{yyyymmdd}/{uuid}.pdf`，请先从 R2 同步文件到对应目录结构。

增量导入：

- `uv run python scripts/import_new_documents.py`

## 定时爬取任务

项目包含定时爬取任务，用于从 ISPE、PDA、WHO、FDA Guidance、APIC 等站点获取最新 GMP 文档：

- ISPE 文档爬取：`uv run python crawler/ispe.py`
- PDA 文档爬取：`uv run python crawler/pda.py`
- WHO 文档爬取：`uv run python crawler/who.py`
- FDA Guidance 文档爬取：`uv run python crawler/fda-guidance.py`
- APIC 文档爬取：`uv run python crawler/apic.py`

可以通过cronjob或任务调度器定期运行这些脚本。

## 邮件推送服务

未来将提供邮件推送脚本（占位）。

## 管理后台

访问 `/admin` 进入管理后台，使用管理员账户登录后可以管理文档、分类、用户等。
另提供便捷上传页 `/admin/upload`（需管理员权限）。

## 命令行管理工具

项目提供命令行管理工具，用于管理用户和文档：

- 创建用户：`uv run python scripts/manage.py create-user <username> <email> <password> [--admin]`
- 删除用户：`uv run python scripts/manage.py delete-user <email>`
- 列出所有用户：`uv run python scripts/manage.py list-users`
- 设置用户为管理员：`uv run python scripts/manage.py set-admin <email>`
- 取消用户管理员权限：`uv run python scripts/manage.py remove-admin <email>`
- 列出所有文档：`uv run python scripts/manage.py list-documents`
- 删除文档：`uv run python scripts/manage.py delete-document <doc_id>`
- 设置文档状态：`uv run python scripts/manage.py set-document-status <doc_id> <status>`

## 数据库备份

项目提供数据库备份和恢复功能：

- 备份数据库：`uv run python scripts/backup.py backup`
- 列出备份文件：`uv run python scripts/backup.py list`
- 从备份恢复数据库：`uv run python scripts/backup.py restore <backup_file>`

## 配置

项目配置在 `config.py` 文件中，可以通过环境变量覆盖默认配置。
常用条目：
- `DEV_DATABASE_URL`、`TEST_DATABASE_URL`、`DATABASE_URL`
- `R2_*` 与 `CDN_URL`（文件存储/访问）
- `MAIL_*` 与 `GMP_SEEKER_ADMIN`

日志：默认写入 `logs/` 目录，请确保目录可写。
- 文件存储：`app/static/uploads/` 已在 `.gitignore`，无需提交（本地模式下载的文档也会落在此目录）。

## 使用 1Panel 部署（推荐给新手）

本项目提供专用的精简编排文件 `docker-compose.1panel.yml`，适配 1Panel 的网站与反向代理功能。

### 准备工作

- 域名与解析：将域名 A 记录指向服务器公网 IP。
- 放行端口：服务器需放行 80/443（1Panel 申请证书与对外访问需要）。
- 代码或镜像：
  - 方式 A：直接在服务器下载本仓库（包含 `docker-compose.1panel.yml`）。
  - 方式 B：使用预构建镜像，按需修改 compose 中的 `image`。

### 1Panel 中创建编排

1. 打开 1Panel → 容器 → 项目编排 → 新建编排。
2. 选择“从本地路径/粘贴 YAML”，指向/粘贴 `docker-compose.1panel.yml`。
3. 注意：1Panel 会把在界面上设置的环境变量写入同目录的 `1panel.env` 文件；本项目的 compose 已包含：

   ```yaml
   env_file:
     - 1panel.env
   ```

   因此只需在 1Panel 的“环境变量”里设置即可自动注入容器。

### 必填环境变量（在 1Panel 界面添加）

- 核心
  - `SECRET_KEY`：强随机串，用于会话/CSRF（生产必须设置）。
  - `FLASK_ENV=production`：已在 compose 预设。
  - `TZ=Asia/Shanghai`：可选，日志显示为东八区。
- 数据库（入门可用 SQLite）
  - `DATABASE_URL=sqlite:////app/data/data.sqlite`（compose 已预设）。
- Cloudflare R2（用于文件上传/访问）
  - `R2_BUCKET_NAME`
  - `R2_ACCESS_KEY_ID`
  - `R2_SECRET_ACCESS_KEY`
  - `R2_ENDPOINT_URL`（例如 `https://<account_id>.r2.cloudflarestorage.com`）
  - 可选：`CDN_URL`（如使用自定义域名分发）

保存并重新部署/重启编排后，这些变量会通过 `1panel.env` 注入容器。

### 端口与反向代理

- 本仓库的 `docker-compose.1panel.yml` 默认：

  ```yaml
  expose:
    - "5000"
  ports:
    - "127.0.0.1:7155:5000"
  ```

  说明：容器对外监听 5000；并把容器 5000 映射到宿主 `127.0.0.1:5001`，便于 1Panel 用“HTTP URL”反代。

- 在 1Panel → 网站 → 新建网站 → 反向代理：
  - 目标地址填：`http://127.0.0.1:7155`
  - 勾选/申请证书（Let’s Encrypt）并保存。

- 如果你的 1Panel 版本支持“目标类型：容器/服务”，可改为直连容器：
  - 删除 `ports:` 映射，仅保留 `expose: 5000`；
  - 在 1Panel 反代里选择“容器/服务: app:5000”。

### 首次启动与数据库初始化

- 镜像入口脚本 `start.sh` 会在启动时自动检查 SQLite：若 `DATABASE_URL` 指向的文件不存在或大小为 0，会自动执行 `python scripts/init_db.py`（建表、基础组织/分类、按 `/app/data` 下数据导入。导入阶段默认优先 `documents_export.xlsx`，否则回退 CSV）。
- 手动初始化/管理：
  - 初始化（可重复执行）：`python scripts/init_db.py`
  - 创建管理员：`python scripts/manage.py create-user <用户名> <邮箱> <密码> --admin`

### 常见问题

- 500 错误 “R2 configuration missing”
  - 未设置 R2 相关环境变量。到 1Panel 环境变量中补齐 `R2_*`，保存后重启容器。
- 网站打不开
  - 确认反代目标是否为 `http://127.0.0.1:5001`（或容器:5000）。
  - 容器日志包含 “Listening at: http://0.0.0.0:5000”。
- 权限问题（写入 `/app/data`/`/app/logs` 失败）
  - 先以 root 运行容器初始化一次，或在宿主/容器内 `chown -R` 修正卷权限。
- 时区不对
  - 在 1Panel 环境变量添加 `TZ=Asia/Shanghai` 并重启容器。

## 目录结构

```
app/
  admin/         # Flask-Admin 定制与上传
  api/           # JSON API 蓝图
  auth/          # 登录注册、个人中心
  main/          # 首页、文档检索与详情
  models/        # SQLAlchemy 模型
  utils/         # R2 上传、预览生成等工具
  templates/     # Jinja2 模板（Tailwind）
  static/        # 自定义样式与脚本
crawler/         # ISPE/PDA/WHO/FDA/APIC 爬虫脚本
scripts/         # 初始化、导入、备份、管理脚本
data/            # CSV/Excel 输入与备份输出
config.py        # 配置（多环境）
logging_config.py# 日志配置
run.py           # Flask 入口（使用 FLASK_ENV 切换配置）
Dockerfile, docker-compose.yml
```

## 测试

项目暂未提交正式测试用例，推荐使用 pytest：

```
pip install pytest
export FLASK_ENV=testing
pytest -q
```

测试环境使用内存 SQLite（见 `config.py`）。

## 部署

生产部署仅推荐使用 Docker/Compose，详见下文“生产环境部署（Docker Compose + SQLite）”。

## 许可证

MIT License

## 生产环境部署（Docker Compose + SQLite）

以下步骤适用于在一台 Linux 服务器上使用 Docker Compose 和 SQLite 快速上线本项目。

1. 前置条件
   - 已安装 Docker Engine 与 Compose 插件；开放 80/443（或仅 80）端口。
   - 域名已解析到服务器（如需 HTTPS，准备证书到 `./ssl`）。

2. 准备代码与环境
   ```bash
   git clone <repository-url> && cd GMP-Seeker
   cp .env.example .env  # 设置 SECRET_KEY、GMP_SEEKER_ADMIN、MAIL_*、R2_* 等
   docker compose build --pull
   ```

3. 初始化数据库（仅首次/更换环境时执行）
   - 本仓库的 `docker-compose.yml` 已将数据库指向容器内持久化路径：`DATABASE_URL=sqlite:////app/data/data.sqlite`
   - 执行一次初始化：
   ```bash
   docker compose run --rm app python scripts/init_db.py
   ```

4. 启动服务与查看日志
   ```bash
   docker compose up -d
   docker compose logs -f app
   ```

5. 反向代理（可选）
   - 使用内置 `nginx` 服务：在仓库根目录提供 `nginx.conf` 与 `./ssl` 证书文件，然后 `docker compose up -d`。
   - 或在宿主机/外部代理到 `app:5000`。

6. 备份与恢复
   ```bash
   docker compose exec app python scripts/backup.py backup   # 生成备份
   docker compose exec app python scripts/backup.py list     # 列出备份
   docker compose exec app python scripts/backup.py restore <file>  # 恢复
   ```

7. 维护与更新
   ```bash
   git pull && docker compose build && docker compose up -d
   ```

安全提示
- 不要提交 `.env`；确保 `SECRET_KEY` 复杂唯一。
- `./data` 与 `./logs` 挂载到宿主机目录，确认权限可写。
- 可在 `docker-compose.yml` 中为服务添加 `restart: unless-stopped` 以提高稳定性。
