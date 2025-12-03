#!/bin/bash
# 启动脚本

# 设置环境变量
export FLASK_APP=${FLASK_APP:-run.py}
export FLASK_ENV=${FLASK_ENV:-production}

# 创建必要的目录
mkdir -p logs data

# 若使用 SQLite，首启时自动初始化（建表 + 基础数据 + 可用的 CSV 导入）
# 判断依据：DATABASE_URL 以 sqlite:// 开头，且目标文件不存在或为空
db_url="${DATABASE_URL:-}"
maybe_sqlite_init=false
db_path=""

if [[ -n "$db_url" && "$db_url" == sqlite:* ]]; then
  # 去掉 sqlite:/// 前缀，保留绝对路径
  db_path="${db_url#sqlite:///}"
  maybe_sqlite_init=true
elif [[ -z "$db_url" ]]; then
  # 未显式配置 DATABASE_URL：生产/默认会回落到 SQLite
  # 生产默认：/app/data/data.sqlite；默认配置：/app/data-dev.sqlite 或 /app/data.sqlite
  # 按最常见的生产路径处理
  db_path="/app/data/data.sqlite"
  maybe_sqlite_init=true
fi

if [[ "$maybe_sqlite_init" == true ]]; then
  if [[ ! -s "$db_path" ]]; then
    echo "[startup] SQLite 数据库不存在或为空，执行初始化: $db_path"
    python scripts/init_db.py || {
      echo "[startup] 初始化失败" >&2
      exit 1
    }
  else
    echo "[startup] 检测到已存在的 SQLite 数据库: $db_path"
  fi
else
  echo "[startup] 检测到非 SQLite 数据库或已显式配置，跳过自动初始化"
fi

# 启动应用
exec gunicorn run:app \
  --bind 0.0.0.0:${PORT:-5000} \
  --workers ${WORKERS:-1} \
  --worker-class ${WORKER_CLASS:-sync} \
  --threads ${THREADS:-1} \
  --max-requests ${MAX_REQUESTS:-1000} \
  --max-requests-jitter ${MAX_REQUESTS_JITTER:-100} \
  --timeout ${TIMEOUT:-30} \
  --graceful-timeout ${GRACEFUL_TIMEOUT:-30} \
  --keep-alive ${KEEP_ALIVE:-5} \
  --log-level ${LOG_LEVEL:-info} \
  --access-logfile '-' \
  --error-logfile '-'
