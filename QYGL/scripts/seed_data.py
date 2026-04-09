"""Seed test data for 千帆海公司 (QianFanHai Corp).

Organizational structure:
- 总经理 (Boss): 陈总
- 中台: HR / 财务 / 总经理助理
- 业务团队: 跨境电商(Temu/TikTok/Shopee), ERP开发, ERP销售, 菲律宾POD工厂管理

Run: python scripts/seed_data.py
"""
import sys
sys.path.insert(0, ".")

import json
from datetime import date, datetime, timedelta

from app.core.database import Database, new_id
from app.core.config import get_config
from app.core.security import encrypt

cfg = get_config()
cfg.setup_logging()
db = Database.get_instance(cfg.db_path)
db.run_migrations()

print("=== 植入千帆海公司测试数据 ===\n")


# ── 1. 模型配置 ─────────────────────────────────────────────
print("1. 配置LLM模型...")

models_data = [
    {
        "id": "model_deepseek",
        "name": "deepseek-chat",
        "provider": "deepseek",
        "api_key_encrypted": encrypt("sk-fdfb1ba51a534d8da846abcfa547d426"),
        "capabilities_json": json.dumps(["chat", "function_calling"]),
        "cost_tier": 1,
        "daily_token_limit": 5000000,
        "monthly_token_limit": 100000000,
        "is_default": 1,
        "enabled": 1,
    },
    {
        "id": "model_ds_reasoner",
        "name": "deepseek-reasoner",
        "provider": "deepseek",
        "api_key_encrypted": encrypt("sk-fdfb1ba51a534d8da846abcfa547d426"),
        "capabilities_json": json.dumps(["chat", "reasoning"]),
        "cost_tier": 3,
        "daily_token_limit": 1000000,
        "monthly_token_limit": 20000000,
        "is_default": 0,
        "enabled": 1,
    },
]
for m in models_data:
    existing = db.query("models", {"id": m["id"]}, limit=1)
    if not existing:
        db.insert("models", m)
        print(f"   + 模型: {m['name']}")
    else:
        print(f"   = 模型已存在: {m['name']}")


# ── 2. Agent 团队 ───────────────────────────────────────────
print("\n2. 创建Agent团队...")

teams_data = [
    {
        "id": "team_ecom",
        "name": "cross_border_ecom",
        "display_name": "跨境电商运营团队",
        "tier": "T2",
        "status": "active",
        "department": "电商部",
        "system_prompt": "你是千帆海跨境电商运营AI助手。负责管理Temu、TikTok Shop、Shopee三个平台的店铺运营。\n你需要：\n1. 追踪每个运营人员的店铺销售数据和广告投放效果\n2. 催促运营按时提交日报和周报\n3. 分析销售趋势并给出优化建议\n4. 协助计算每个运营的利润和提成\n\n当前管理平台：{team.department}\n团队负责人：{employee.name}",
        "primary_model": "deepseek-chat",
        "fallback_model": "deepseek-reasoner",
        "automation_profile": "mid_manager",
        "data_scope_json": json.dumps({"platforms": ["temu", "tiktok", "shopee"]}),
        "escalation_json": json.dumps({"intervals_minutes": [30, 60, 120], "levels": ["employee", "manager", "boss"]}),
    },
    {
        "id": "team_erp_dev",
        "name": "erp_dev",
        "display_name": "ERP开发团队",
        "tier": "T2",
        "status": "active",
        "department": "技术部",
        "system_prompt": "你是千帆海ERP系统开发AI助手。负责管理ERP产品的需求、开发进度和Bug跟踪。\n你需要：\n1. 分配开发任务并追踪进度\n2. 评估代码质量和Bug修复速度\n3. 生成项目周报\n4. 协调与销售团队的需求对接",
        "primary_model": "deepseek-chat",
        "fallback_model": "",
        "automation_profile": "mid_manager",
        "escalation_json": json.dumps({"intervals_minutes": [60, 120, 240], "levels": ["employee", "manager", "boss"]}),
    },
    {
        "id": "team_erp_sales",
        "name": "erp_sales",
        "display_name": "ERP销售团队",
        "tier": "T2",
        "status": "active",
        "department": "销售部",
        "system_prompt": "你是千帆海ERP销售AI助手。负责管理客户跟进、合同签约和售后服务。\n你需要：\n1. 追踪销售人员的客户拜访和跟进情况\n2. 分析销售漏斗数据\n3. 催促提交客户拜访报告\n4. 生成销售业绩排行和预测",
        "primary_model": "deepseek-chat",
        "fallback_model": "",
        "automation_profile": "startup",
        "escalation_json": json.dumps({"intervals_minutes": [30, 60, 120], "levels": ["employee", "manager", "boss"]}),
    },
    {
        "id": "team_pod",
        "name": "pod_factory",
        "display_name": "菲律宾POD工厂管理团队",
        "tier": "T2",
        "status": "active",
        "department": "生产部",
        "system_prompt": "你是千帆海菲律宾POD(Print-on-Demand)工厂管理AI助手。负责管理工厂的生产排单、质检和交付。\n你需要：\n1. 跟踪每日生产订单完成情况\n2. 监控良品率和交付准时率\n3. 管理原材料库存预警\n4. 协助处理客诉和退货\n\n注意：与菲律宾团队沟通时需考虑时差(UTC+8 vs UTC+8，无时差)和文化差异。",
        "primary_model": "deepseek-chat",
        "fallback_model": "",
        "automation_profile": "process_driven",
        "escalation_json": json.dumps({"intervals_minutes": [20, 40, 90], "levels": ["employee", "manager", "boss"]}),
    },
    {
        "id": "team_hr",
        "name": "hr_admin",
        "display_name": "人力行政中台",
        "tier": "T2",
        "status": "active",
        "department": "中台",
        "system_prompt": "你是千帆海HR行政AI助手。负责招聘、考勤、薪酬、培训和员工关系管理。\n你需要：\n1. 追踪招聘进度和候选人状态\n2. 提醒合同到期、生日等关怀事项\n3. 协助统计考勤和加班数据\n4. 管理入职/离职流程",
        "primary_model": "deepseek-chat",
        "fallback_model": "",
        "automation_profile": "startup",
    },
    {
        "id": "team_finance",
        "name": "finance",
        "display_name": "财务中台",
        "tier": "T2",
        "status": "active",
        "department": "中台",
        "system_prompt": "你是千帆海财务AI助手。负责对账、利润核算、费用报销和财务报表生成。\n你需要：\n1. 匹配ERP发货订单和店铺回款订单\n2. 计算每个运营的利润和提成\n3. 汇总广告消耗、扣款和提现数据\n4. 生成月度财务报表\n5. 预警异常费用和超预算支出",
        "primary_model": "deepseek-chat",
        "fallback_model": "deepseek-reasoner",
        "automation_profile": "process_driven",
    },
]

for t in teams_data:
    existing = db.query("teams", {"id": t["id"]}, limit=1)
    if not existing:
        db.insert("teams", t)
        shadow_existing = db.query("team_shadow_config", {"team_id": t["id"]}, limit=1)
        if not shadow_existing:
            db.insert("team_shadow_config", {
                "id": new_id(),
                "team_id": t["id"],
                "mode": "live",
                "shadow_duration_days": 7,
            })
        print(f"   + 团队: {t['display_name']}")
    else:
        print(f"   = 团队已存在: {t['display_name']}")


# ── 3. 员工 ─────────────────────────────────────────────────
print("\n3. 创建员工...")

employees_data = [
    # 老板
    {"id": "emp_boss", "name": "陈志远", "team_id": "team_ecom", "role": "boss", "department": "总裁办", "join_date": "2020-01-01", "notes": "千帆海创始人/CEO"},
    # 跨境电商
    {"id": "emp_ecom_mgr", "name": "李明", "team_id": "team_ecom", "role": "manager", "department": "电商部", "direct_manager_id": "emp_boss", "join_date": "2021-03-15", "notes": "电商部经理"},
    {"id": "emp_temu_1", "name": "张小芳", "team_id": "team_ecom", "role": "employee", "department": "电商部", "direct_manager_id": "emp_ecom_mgr", "join_date": "2022-06-01", "notes": "Temu运营，负责3个店铺", "birthday": "1995-08-22"},
    {"id": "emp_temu_2", "name": "王浩", "team_id": "team_ecom", "role": "employee", "department": "电商部", "direct_manager_id": "emp_ecom_mgr", "join_date": "2023-01-10", "notes": "Temu运营，负责2个店铺"},
    {"id": "emp_tiktok_1", "name": "刘佳", "team_id": "team_ecom", "role": "employee", "department": "电商部", "direct_manager_id": "emp_ecom_mgr", "join_date": "2023-07-20", "notes": "TikTok Shop运营"},
    {"id": "emp_shopee_1", "name": "赵雨", "team_id": "team_ecom", "role": "employee", "department": "电商部", "direct_manager_id": "emp_ecom_mgr", "join_date": "2024-02-01", "notes": "Shopee运营，东南亚市场", "contract_end_date": "2026-05-15"},
    # ERP开发
    {"id": "emp_dev_mgr", "name": "周强", "team_id": "team_erp_dev", "role": "manager", "department": "技术部", "direct_manager_id": "emp_boss", "join_date": "2021-06-01", "notes": "技术总监"},
    {"id": "emp_dev_1", "name": "吴磊", "team_id": "team_erp_dev", "role": "employee", "department": "技术部", "direct_manager_id": "emp_dev_mgr", "join_date": "2022-03-01", "notes": "后端开发"},
    {"id": "emp_dev_2", "name": "郑雪", "team_id": "team_erp_dev", "role": "employee", "department": "技术部", "direct_manager_id": "emp_dev_mgr", "join_date": "2023-09-01", "notes": "前端开发", "birthday": "1997-12-05"},
    {"id": "emp_dev_3", "name": "孙涛", "team_id": "team_erp_dev", "role": "employee", "department": "技术部", "direct_manager_id": "emp_dev_mgr", "join_date": "2024-04-15", "notes": "全栈开发"},
    # ERP销售
    {"id": "emp_sales_mgr", "name": "杨丽", "team_id": "team_erp_sales", "role": "manager", "department": "销售部", "direct_manager_id": "emp_boss", "join_date": "2022-01-01", "notes": "销售经理"},
    {"id": "emp_sales_1", "name": "黄勇", "team_id": "team_erp_sales", "role": "employee", "department": "销售部", "direct_manager_id": "emp_sales_mgr", "join_date": "2022-08-01", "notes": "大客户销售"},
    {"id": "emp_sales_2", "name": "谢静", "team_id": "team_erp_sales", "role": "employee", "department": "销售部", "direct_manager_id": "emp_sales_mgr", "join_date": "2023-11-01", "notes": "渠道销售"},
    # POD工厂
    {"id": "emp_pod_mgr", "name": "林伟", "team_id": "team_pod", "role": "manager", "department": "生产部", "direct_manager_id": "emp_boss", "join_date": "2021-09-01", "notes": "菲律宾工厂厂长"},
    {"id": "emp_pod_1", "name": "Maria Santos", "team_id": "team_pod", "role": "employee", "department": "生产部", "direct_manager_id": "emp_pod_mgr", "join_date": "2022-11-01", "notes": "生产主管(菲方)"},
    {"id": "emp_pod_2", "name": "陈小军", "team_id": "team_pod", "role": "employee", "department": "生产部", "direct_manager_id": "emp_pod_mgr", "join_date": "2023-05-01", "notes": "质检专员"},
    # 中台
    {"id": "emp_hr", "name": "钱婷", "team_id": "team_hr", "role": "employee", "department": "中台", "direct_manager_id": "emp_boss", "join_date": "2021-04-01", "notes": "HR专员"},
    {"id": "emp_finance", "name": "冯敏", "team_id": "team_finance", "role": "employee", "department": "中台", "direct_manager_id": "emp_boss", "join_date": "2022-02-01", "notes": "财务主管"},
    {"id": "emp_assistant", "name": "何雅", "team_id": "team_hr", "role": "employee", "department": "中台", "direct_manager_id": "emp_boss", "join_date": "2023-06-01", "notes": "总经理助理"},
]

for e in employees_data:
    existing = db.query("employees", {"id": e["id"]}, limit=1)
    if not existing:
        db.insert("employees", e)
        print(f"   + 员工: {e['name']} ({e.get('notes', '')})")
    else:
        print(f"   = 员工已存在: {e['name']}")


# ── 4. 子Agent ──────────────────────────────────────────────
print("\n4. 配置子Agent...")

sub_agents_data = [
    {"team_id": "team_ecom", "name": "director", "display_name": "电商总控", "role": "director", "system_prompt": "你是跨境电商团队的总控Agent，负责任务分配、进度协调和异常升级。", "sort_order": 0},
    {"team_id": "team_ecom", "name": "analyst", "display_name": "数据分析师", "role": "analyst", "system_prompt": "你是电商团队的数据分析师，负责分析各平台销售数据、广告ROI和利润率。只能读取数据，不能修改。", "sort_order": 1},
    {"team_id": "team_ecom", "name": "coach", "display_name": "运营教练", "role": "coach", "system_prompt": "你是电商运营教练，根据数据为运营人员提供优化建议：选品策略、广告调整、定价优化等。", "sort_order": 2},
    {"team_id": "team_ecom", "name": "executor", "display_name": "任务执行者", "role": "executor", "system_prompt": "你是执行者Agent，负责创建任务、发送催办通知、更新任务状态。", "sort_order": 3},
    {"team_id": "team_erp_dev", "name": "director", "display_name": "项目总控", "role": "director", "system_prompt": "你是ERP开发团队的项目经理Agent，管理Sprint任务和Bug分配。", "sort_order": 0},
    {"team_id": "team_erp_dev", "name": "analyst", "display_name": "代码审查员", "role": "analyst", "system_prompt": "你是代码审查Agent，分析开发进度、Bug密度和代码质量。", "sort_order": 1},
    {"team_id": "team_finance", "name": "director", "display_name": "财务总控", "role": "director", "system_prompt": "你是财务团队的总控Agent，负责对账流程协调和异常标记。", "sort_order": 0},
    {"team_id": "team_finance", "name": "analyst", "display_name": "对账分析师", "role": "analyst", "system_prompt": "你是对账分析Agent，负责匹配ERP发货订单和店铺回款，计算利润。", "sort_order": 1},
]

for sa in sub_agents_data:
    sa["id"] = new_id()
    existing = db.execute("SELECT id FROM sub_agents WHERE team_id=? AND name=?", (sa["team_id"], sa["name"]))
    if not existing:
        db.insert("sub_agents", sa)
        print(f"   + 子Agent: {sa['display_name']} → {sa['team_id']}")
    else:
        print(f"   = 子Agent已存在: {sa['display_name']}")


# ── 5. KPI定义 ──────────────────────────────────────────────
print("\n5. 配置KPI...")

kpi_data = [
    {"team_id": "team_ecom", "name": "月销售额", "period": "monthly", "target_value": 500000, "weight": 0.4,
     "metrics_json": json.dumps({"unit": "USD", "source": "店铺后台"}),
     "scoring_json": json.dumps({">=100%": "A", ">=80%": "B", ">=60%": "C", "<60%": "D"}),
     "source_type": "manual", "responsible_role": "运营", "update_frequency": "daily", "dispute_resolver": "电商经理"},
    {"team_id": "team_ecom", "name": "广告ROAS", "period": "monthly", "target_value": 3.0, "weight": 0.3,
     "metrics_json": json.dumps({"unit": "倍", "source": "广告后台", "formula": "sales/ad_spend"}),
     "scoring_json": json.dumps({">=3.5": "A", ">=3.0": "B", ">=2.0": "C", "<2.0": "D"}),
     "source_type": "manual", "responsible_role": "运营", "update_frequency": "weekly"},
    {"team_id": "team_ecom", "name": "日报提交率", "period": "monthly", "target_value": 100, "weight": 0.15,
     "metrics_json": json.dumps({"unit": "%", "formula": "submitted_days/working_days*100"}),
     "scoring_json": json.dumps({">=95%": "A", ">=85%": "B", ">=70%": "C", "<70%": "D"}),
     "source_type": "system", "update_frequency": "daily"},
    {"team_id": "team_ecom", "name": "退货率", "period": "monthly", "target_value": 5, "weight": 0.15,
     "metrics_json": json.dumps({"unit": "%", "formula": "return_orders/total_orders*100", "lower_is_better": True}),
     "scoring_json": json.dumps({"<=3%": "A", "<=5%": "B", "<=8%": "C", ">8%": "D"}),
     "source_type": "manual", "update_frequency": "monthly"},
    {"team_id": "team_erp_dev", "name": "Sprint完成率", "period": "monthly", "target_value": 90, "weight": 0.4,
     "metrics_json": json.dumps({"unit": "%"}),
     "scoring_json": json.dumps({">=95%": "A", ">=85%": "B", ">=70%": "C", "<70%": "D"}),
     "source_type": "system", "update_frequency": "weekly"},
    {"team_id": "team_erp_dev", "name": "Bug修复速度", "period": "monthly", "target_value": 24, "weight": 0.3,
     "metrics_json": json.dumps({"unit": "小时", "description": "P1 Bug平均修复时间", "lower_is_better": True}),
     "scoring_json": json.dumps({"<=12h": "A", "<=24h": "B", "<=48h": "C", ">48h": "D"})},
    {"team_id": "team_erp_sales", "name": "月签约额", "period": "monthly", "target_value": 200000, "weight": 0.5,
     "metrics_json": json.dumps({"unit": "RMB"}),
     "scoring_json": json.dumps({">=120%": "A", ">=100%": "B", ">=80%": "C", "<80%": "D"}),
     "source_type": "manual", "update_frequency": "weekly"},
    {"team_id": "team_erp_sales", "name": "客户拜访量", "period": "monthly", "target_value": 20, "weight": 0.3,
     "metrics_json": json.dumps({"unit": "次"}),
     "scoring_json": json.dumps({">=25": "A", ">=20": "B", ">=15": "C", "<15": "D"})},
    {"team_id": "team_pod", "name": "日产能达成率", "period": "daily", "target_value": 95, "weight": 0.4,
     "metrics_json": json.dumps({"unit": "%"}),
     "scoring_json": json.dumps({">=98%": "A", ">=95%": "B", ">=85%": "C", "<85%": "D"})},
    {"team_id": "team_pod", "name": "良品率", "period": "monthly", "target_value": 98, "weight": 0.35,
     "metrics_json": json.dumps({"unit": "%"}),
     "scoring_json": json.dumps({">=99%": "A", ">=98%": "B", ">=95%": "C", "<95%": "D"})},
]

for kpi in kpi_data:
    kpi["id"] = new_id()
    existing = db.execute("SELECT id FROM kpi_definitions WHERE team_id=? AND name=?", (kpi["team_id"], kpi["name"]))
    if not existing:
        db.insert("kpi_definitions", kpi)
        print(f"   + KPI: {kpi['name']} → {kpi['team_id']}")
    else:
        print(f"   = KPI已存在: {kpi['name']}")


# ── 6. 奖惩规则 ─────────────────────────────────────────────
print("\n6. 配置奖惩规则...")

reward_rules = [
    {"team_id": "team_ecom", "name": "电商A级奖金", "kpi_grade": "A", "formula": "base_salary * 0.3", "description": "月度KPI A级：底薪30%奖金"},
    {"team_id": "team_ecom", "name": "电商B级奖金", "kpi_grade": "B", "formula": "base_salary * 0.15", "description": "月度KPI B级：底薪15%奖金"},
    {"team_id": "team_ecom", "name": "电商D级处罚", "kpi_grade": "D", "formula": "base_salary * -0.1", "description": "月度KPI D级：扣底薪10%"},
    {"team_id": "team_erp_sales", "name": "销售提成", "kpi_grade": "A", "formula": "signed_amount * 0.05", "description": "签约额5%提成"},
]

for rule in reward_rules:
    rule["id"] = new_id()
    db.insert("reward_rules", rule)
    print(f"   + 规则: {rule['name']}")


# ── 7. 任务样本 ─────────────────────────────────────────────
print("\n7. 创建样本任务...")

now = datetime.utcnow()
tasks_data = [
    {"team_id": "team_ecom", "employee_id": "emp_temu_1", "title": "提交Temu店铺3月销售日报", "description": "汇总3个店铺的销售额、订单数、退货数、广告花费", "status": "dispatched", "dispatched_at": (now - timedelta(hours=5)).isoformat(), "deadline_at": (now + timedelta(hours=3)).isoformat()},
    {"team_id": "team_ecom", "employee_id": "emp_temu_2", "title": "优化Temu新品Listing", "description": "重新拍摄主图，优化标题关键词，调整定价策略", "status": "in_progress", "dispatched_at": (now - timedelta(days=1)).isoformat(), "deadline_at": (now + timedelta(days=2)).isoformat()},
    {"team_id": "team_ecom", "employee_id": "emp_tiktok_1", "title": "TikTok Shop直播带货数据复盘", "description": "分析上周3场直播的GMV、观看人数、转化率，提出改进方案", "status": "submitted", "dispatched_at": (now - timedelta(days=2)).isoformat(), "deadline_at": (now - timedelta(hours=6)).isoformat(), "completed_at": (now - timedelta(hours=8)).isoformat()},
    {"team_id": "team_ecom", "employee_id": "emp_shopee_1", "title": "Shopee大促活动报名", "description": "报名Shopee 5月大促活动，提交选品和折扣方案", "status": "pending", "deadline_at": (now + timedelta(days=5)).isoformat()},
    {"team_id": "team_erp_dev", "employee_id": "emp_dev_1", "title": "修复订单导入异常Bug", "description": "ERP导入Temu订单时部分字段丢失，紧急修复。Bug #2024-0415", "status": "in_progress", "dispatched_at": (now - timedelta(hours=8)).isoformat(), "deadline_at": (now + timedelta(hours=4)).isoformat()},
    {"team_id": "team_erp_dev", "employee_id": "emp_dev_2", "title": "开发Shopee店铺数据对接模块", "description": "对接Shopee Open API，实现订单和产品数据同步", "status": "dispatched", "dispatched_at": (now - timedelta(days=3)).isoformat(), "deadline_at": (now + timedelta(days=7)).isoformat()},
    {"team_id": "team_erp_dev", "employee_id": "emp_dev_3", "title": "设计财务对账报表页面", "description": "按财务需求设计ERP中的对账报表模块前端界面", "status": "pending", "deadline_at": (now + timedelta(days=10)).isoformat()},
    {"team_id": "team_erp_sales", "employee_id": "emp_sales_1", "title": "跟进深圳XX电子签约", "description": "客户已试用30天，本周内完成合同签署。合同额预估¥80,000/年", "status": "in_progress", "dispatched_at": (now - timedelta(days=5)).isoformat(), "deadline_at": (now + timedelta(days=2)).isoformat()},
    {"team_id": "team_erp_sales", "employee_id": "emp_sales_2", "title": "新客户需求调研 - 广州YY贸易", "description": "了解客户现有系统、痛点和预算，输出需求调研报告", "status": "dispatched", "dispatched_at": (now - timedelta(days=1)).isoformat(), "deadline_at": (now + timedelta(days=3)).isoformat()},
    {"team_id": "team_pod", "employee_id": "emp_pod_1", "title": "完成今日500件T恤生产订单", "description": "订单号POD-20260408-001，500件定制T恤，要求16:00前完成", "status": "in_progress", "dispatched_at": now.isoformat(), "deadline_at": (now + timedelta(hours=6)).isoformat()},
    {"team_id": "team_pod", "employee_id": "emp_pod_2", "title": "本周质检报告", "description": "汇总本周生产良品率、不良品原因分析、改进措施", "status": "pending", "deadline_at": (now + timedelta(days=2)).isoformat()},
    {"team_id": "team_finance", "employee_id": "emp_finance", "title": "3月Temu店铺对账", "description": "匹配ERP发货订单和Temu回款数据，计算各运营利润", "status": "in_progress", "dispatched_at": (now - timedelta(days=3)).isoformat(), "deadline_at": (now + timedelta(days=1)).isoformat()},
]

for t in tasks_data:
    t["id"] = new_id()
    t["created_at"] = now.isoformat()
    db.insert("tasks", t)
    print(f"   + 任务: {t['title'][:30]}...")


# ── 8. 审批请求样本 ──────────────────────────────────────────
print("\n8. 创建审批请求样本...")

approvals_data = [
    {"type": "reward", "team_id": "team_ecom", "title": "张小芳3月KPI A级奖金审批", "detail_json": json.dumps({"employee": "张小芳", "grade": "A", "amount": 4500, "basis": "月销售额超目标120%"}), "suggestion": "建议批准，该员工连续2个月KPI达A级", "reasoning": "张小芳3月管理的3个Temu店铺总销售额达$62万，超目标24%，退货率仅2.8%", "priority": 2, "automation_level": "L2", "confidence": "A", "status": "pending", "source_agent": "team_ecom/director"},
    {"type": "task_dispatch", "team_id": "team_erp_dev", "title": "紧急：分配P1安全漏洞修复任务", "detail_json": json.dumps({"bug_id": "SEC-2026-003", "severity": "P1", "assignee": "吴磊", "deadline": "4小时内"}), "suggestion": "建议立即分配给吴磊，他是安全模块负责人", "reasoning": "发现SQL注入漏洞，影响生产环境", "priority": 1, "automation_level": "L3", "confidence": "A", "status": "pending", "source_agent": "team_erp_dev/director"},
    {"type": "escalation", "team_id": "team_ecom", "title": "赵雨连续3天未提交日报", "detail_json": json.dumps({"employee": "赵雨", "missed_days": 3, "last_submission": "2026-04-05"}), "suggestion": "建议约谈并扣除当月考勤分", "reasoning": "自动检测到连续缺交，已2次飞书提醒无响应", "priority": 2, "automation_level": "L2", "confidence": "B", "status": "pending", "source_agent": "team_ecom/executor"},
]

for a in approvals_data:
    a["id"] = new_id()
    a["created_at"] = now.isoformat()
    db.insert("approval_requests", a)
    print(f"   + 审批: {a['title'][:30]}...")


# ── 9. 客户样本 ─────────────────────────────────────────────
print("\n9. 创建客户样本...")

customers_data = [
    {"team_id": "team_erp_sales", "name": "深圳XX电子科技有限公司", "company": "XX电子", "assigned_employee_id": "emp_sales_1", "scope": "isolated", "profile_json": json.dumps({"industry": "3C电子", "scale": "50-100人", "current_erp": "用友U8", "budget": "8-10万/年", "stage": "试用中"})},
    {"team_id": "team_erp_sales", "name": "广州YY贸易有限公司", "company": "YY贸易", "assigned_employee_id": "emp_sales_2", "scope": "isolated", "profile_json": json.dumps({"industry": "服装外贸", "scale": "20-50人", "current_erp": "Excel", "budget": "5-8万/年", "stage": "需求调研"})},
    {"team_id": "team_erp_sales", "name": "东莞ZZ五金制品厂", "company": "ZZ五金", "assigned_employee_id": "emp_sales_1", "scope": "isolated", "profile_json": json.dumps({"industry": "五金制造", "scale": "100-200人", "current_erp": "金蝶K3", "budget": "15-20万/年", "stage": "报价中"})},
]

for c in customers_data:
    c["id"] = new_id()
    c["created_at"] = now.isoformat()
    db.insert("customers", c)
    print(f"   + 客户: {c['name']}")


# ── 10. 知识库样本 ───────────────────────────────────────────
print("\n10. 创建知识库样本...")

knowledge_data = [
    {"title": "Temu店铺运营SOP", "content": "1. 每日9:00检查店铺数据\n2. 10:00调整广告出价\n3. 14:00处理退货退款\n4. 16:00更新Listing\n5. 17:30提交日报\n\n广告ROAS低于2.0时立即暂停广告组并通知经理。", "scope": "department", "department": "电商部", "category": "运营SOP", "source": "manual"},
    {"title": "ERP客户签约流程", "content": "1. 需求调研(3-5天)\n2. 系统演示(1天)\n3. 试用开通(14-30天)\n4. 商务谈判(3-7天)\n5. 合同签署\n6. 实施部署(15-30天)\n7. 验收上线\n\n合同金额>10万需总经理审批。", "scope": "department", "department": "销售部", "category": "业务流程", "source": "manual"},
    {"title": "POD工厂质检标准", "content": "A级品：无明显瑕疵，印刷清晰，色差<5%\nB级品：轻微瑕疵，不影响使用\nC级品：返工处理\nD级品：报废\n\n日良品率(A+B)需>=98%，低于95%触发停线检查。", "scope": "department", "department": "生产部", "category": "质量标准", "source": "manual"},
    {"title": "财务对账操作指南", "content": "1. 从ERP导出发货订单(含运费、成本)\n2. 从店铺后台导出回款订单(含平台佣金、广告费)\n3. 按订单号匹配\n4. 计算利润 = 回款 - 成本 - 运费 - 佣金 - 广告费\n5. 按运营分组汇总\n6. 生成利润报表交总经理审批", "scope": "department", "department": "中台", "category": "操作指南", "source": "manual"},
    {"title": "千帆海员工手册(摘要)", "content": "工作时间：9:00-18:00，午休12:00-13:30\n考勤：迟到3次扣1天工资\n请假：提前1天飞书审批\n试用期：3个月\n转正考核：直属上级+HR评估\n\n保密协议：客户数据、销售数据、供应商信息严禁外泄。", "scope": "company", "category": "公司制度", "source": "manual"},
]

for k in knowledge_data:
    k["id"] = new_id()
    k["status"] = "active"
    k["created_at"] = now.isoformat()
    db.insert("knowledge", k)
    print(f"   + 知识: {k['title']}")


# ── 11. 目标样本 ─────────────────────────────────────────────
print("\n11. 创建目标...")

goals_data = [
    {"level": "company", "owner_id": "emp_boss", "title": "2026年Q2总营收目标", "target_value": 3000000, "current_value": 800000, "unit": "USD", "period": "2026-Q2", "status": "active"},
    {"level": "department", "team_id": "team_ecom", "owner_id": "emp_ecom_mgr", "title": "电商部Q2销售额", "target_value": 2000000, "current_value": 550000, "unit": "USD", "period": "2026-Q2", "status": "active"},
    {"level": "personal", "team_id": "team_ecom", "employee_id": "emp_temu_1", "owner_id": "emp_temu_1", "title": "张小芳4月Temu销售目标", "target_value": 180000, "current_value": 45000, "unit": "USD", "period": "2026-04", "status": "tracking"},
]

for g in goals_data:
    g["id"] = new_id()
    g["created_at"] = now.isoformat()
    db.insert("goals", g)
    print(f"   + 目标: {g['title']}")


# ── 12. 内置技能分配 ─────────────────────────────────────────
print("\n12. 分配技能到团队...")

builtin_skills = db.query("skills", {"source": "builtin"})
if not builtin_skills:
    skill_names = ["sqlite_data", "knowledge", "file_parser", "calc_engine", "notification", "feishu_im"]
    for sn in skill_names:
        db.insert("skills", {"id": f"skill_{sn}", "name": sn, "display_name": sn, "source": "builtin", "is_global": 1})
    builtin_skills = db.query("skills", {"source": "builtin"})

for team in teams_data:
    for skill in builtin_skills:
        existing = db.execute(
            "SELECT id FROM team_skills WHERE team_id=? AND skill_id=?",
            (team["id"], skill["id"])
        )
        if not existing:
            db.insert("team_skills", {"id": new_id(), "team_id": team["id"], "skill_id": skill["id"], "assigned_to": "main"})

print(f"   = {len(builtin_skills)} 个技能已分配给 {len(teams_data)} 个团队")


# ── Summary ──────────────────────────────────────────────────
print("\n" + "=" * 50)
team_count = db.count("teams")
emp_count = db.count("employees")
task_count = db.count("tasks")
kpi_count = db.count("kpi_definitions")
approval_count = db.count("approval_requests")
customer_count = db.count("customers")
knowledge_count = db.count("knowledge")
goal_count = db.count("goals")

print(f"""
千帆海公司测试数据植入完成!

  团队:   {team_count}
  员工:   {emp_count}
  任务:   {task_count}
  KPI:    {kpi_count}
  审批:   {approval_count}
  客户:   {customer_count}
  知识:   {knowledge_count}
  目标:   {goal_count}
  模型:   {db.count('models')}

登录信息: admin / admin123
访问地址: http://159.75.48.163:8000
""")
