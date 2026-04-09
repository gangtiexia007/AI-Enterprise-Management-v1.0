#!/bin/bash
cd /home/ubuntu/qfbj
source venv/bin/activate

export QFBJ_DB_PATH=data/qfbj.db
export QFBJ_HOST=0.0.0.0
export QFBJ_PORT=8000
export QFBJ_LOG_LEVEL=INFO
export DEEPSEEK_API_KEY=sk-fdfb1ba51a534d8da846abcfa547d426
export FEISHU_APP_ID=cli_a9348938ce395cb5
export FEISHU_APP_SECRET=WFC2cgTPU7WTdI9lXw2bwfj6kpTWvhQo

python scripts/init_db.py

exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
