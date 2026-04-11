"""POD 3.0 订单数据驱动的业务规则：SKU 分级、运营 KPI、选品命中率、每日上新、KPI 桥接。"""
import json
import logging
from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DEFAULT_KPI_TARGETS = {
    "有效链接数": 50,
    "S级爆款数": 5,
    "总出单量": 200,
    "销售额(CNY)": 50000,
    "取消率(%)": 5,
    "选品命中率(%)": 30,
}


def _load_kpi_targets(db: Session) -> dict:
    from models import Setting
    s = db.query(Setting).filter(Setting.key == "pod_kpi_targets").first()
    if s and s.value:
        try:
            return {**DEFAULT_KPI_TARGETS, **json.loads(s.value)}
        except (json.JSONDecodeError, TypeError):
            pass
    return dict(DEFAULT_KPI_TARGETS)


def run_sku_grading(db: Session) -> dict:
    """按 SKU（元素SKU）聚合订单数据，自动分级。仅统计 status_category='valid' 且 operator 非空。

    分级规则（POD 3.0）：
    - S级（爆款）：最近7天 >=3单 且 出单天数 >=2天
    - A级（潜力）：最近14天 >=2单 但 7天<3单
    - 有效链接：14天内 >=1单
    - C级（淘汰）：30天内 0单
    """
    from models import PodOrder

    today = date.today()
    d7 = today - timedelta(days=7)
    d14 = today - timedelta(days=14)
    d30 = today - timedelta(days=30)

    orders = (
        db.query(
            PodOrder.sku,
            PodOrder.operator,
            PodOrder.order_date,
            func.count(PodOrder.id).label("cnt"),
        )
        .filter(
            PodOrder.status_category == "valid",
            PodOrder.operator != "",
            PodOrder.sku != "",
            PodOrder.order_date >= d30,
        )
        .group_by(PodOrder.sku, PodOrder.operator, PodOrder.order_date)
        .all()
    )

    sku_data: dict[str, dict] = defaultdict(lambda: {
        "operator": "", "orders_7d": 0, "orders_14d": 0, "orders_30d": 0,
        "days_7d": set(), "days_14d": set(),
    })
    for sku, operator, order_dt, cnt in orders:
        d = sku_data[sku]
        d["operator"] = operator
        d["orders_30d"] += cnt
        if order_dt and order_dt >= d14:
            d["orders_14d"] += cnt
            d["days_14d"].add(order_dt)
        if order_dt and order_dt >= d7:
            d["orders_7d"] += cnt
            d["days_7d"].add(order_dt)

    grades: dict[str, list] = {"S": [], "A": [], "valid": [], "C": []}
    s_level_skus = []

    for sku, d in sku_data.items():
        info = {
            "sku": sku, "operator": d["operator"],
            "orders_7d": d["orders_7d"], "orders_14d": d["orders_14d"],
            "orders_30d": d["orders_30d"],
        }

        if d["orders_7d"] >= 3 and len(d["days_7d"]) >= 2:
            info["grade"] = "S"
            grades["S"].append(info)
            s_level_skus.append(info)
        elif d["orders_14d"] >= 2 and d["orders_7d"] < 3:
            info["grade"] = "A"
            grades["A"].append(info)
        elif d["orders_14d"] >= 1:
            info["grade"] = "valid"
            grades["valid"].append(info)
        elif d["orders_30d"] == 0:
            info["grade"] = "C"
            grades["C"].append(info)

    all_sku_count = (
        db.query(func.count(func.distinct(PodOrder.sku)))
        .filter(PodOrder.sku != "", PodOrder.operator != "")
        .scalar() or 0
    )
    c_count = max(0, all_sku_count - len(grades["S"]) - len(grades["A"]) - len(grades["valid"]) - len(sku_data))
    grades["C"].extend([])  # C 级还包括 30 天内完全没有出单的（不在 sku_data 中的）

    return {
        "total_skus": all_sku_count,
        "grades": {
            "S": len(grades["S"]),
            "A": len(grades["A"]),
            "valid": len(grades["valid"]),
            "C": len(grades["C"]) + c_count,
        },
        "s_level_skus": s_level_skus,
    }


def run_operator_kpi(db: Session, period_start: date = None, period_end: date = None) -> list[dict]:
    """按运营聚合 KPI，生成排名表。仅统计 operator 非空的订单。"""
    from models import PodOrder

    if not period_end:
        period_end = date.today()
    if not period_start:
        period_start = period_end - timedelta(days=7)

    d7 = period_end - timedelta(days=7)
    d14 = period_end - timedelta(days=14)

    operators = (
        db.query(PodOrder.operator)
        .filter(PodOrder.operator != "", PodOrder.order_date.between(period_start, period_end))
        .distinct()
        .all()
    )

    results = []
    for (op_name,) in operators:
        base_q = db.query(PodOrder).filter(
            PodOrder.operator == op_name,
            PodOrder.order_date.between(period_start, period_end),
        )

        total_orders = base_q.filter(PodOrder.status_category == "valid").count()
        cancelled_orders = base_q.filter(PodOrder.status_category == "cancelled").count()
        refund_orders = base_q.filter(PodOrder.status_category == "refund").count()

        total_gmv_cny = db.query(func.sum(PodOrder.paid_amount_cny)).filter(
            PodOrder.operator == op_name,
            PodOrder.status_category == "valid",
            PodOrder.order_date.between(period_start, period_end),
        ).scalar() or 0

        denom = total_orders + cancelled_orders
        cancel_rate = round(cancelled_orders / denom * 100, 1) if denom > 0 else 0

        # 有效链接：14天内 >=1单 的 SKU 数
        valid_links = (
            db.query(func.count(func.distinct(PodOrder.sku)))
            .filter(
                PodOrder.operator == op_name,
                PodOrder.status_category == "valid",
                PodOrder.sku != "",
                PodOrder.order_date >= d14,
            )
            .scalar() or 0
        )

        # S级爆款数：7天 >=3单 且出单天数 >=2
        s_sku_rows = (
            db.query(PodOrder.sku)
            .filter(
                PodOrder.operator == op_name,
                PodOrder.status_category == "valid",
                PodOrder.sku != "",
                PodOrder.order_date >= d7,
            )
            .group_by(PodOrder.sku)
            .having(
                func.count(PodOrder.id) >= 3,
                func.count(func.distinct(PodOrder.order_date)) >= 2,
            )
            .all()
        )
        s_level_count = len(s_sku_rows)

        # 按国家分组
        by_country = {}
        country_rows = (
            db.query(PodOrder.country, func.count(PodOrder.id), func.sum(PodOrder.paid_amount_cny))
            .filter(
                PodOrder.operator == op_name,
                PodOrder.status_category == "valid",
                PodOrder.order_date.between(period_start, period_end),
            )
            .group_by(PodOrder.country)
            .all()
        )
        for country, cnt, gmv in country_rows:
            by_country[country or "unknown"] = {"orders": cnt, "gmv_cny": round(gmv or 0, 2)}

        # 按平台分组
        by_platform = {}
        platform_rows = (
            db.query(PodOrder.platform, func.count(PodOrder.id), func.sum(PodOrder.paid_amount_cny))
            .filter(
                PodOrder.operator == op_name,
                PodOrder.status_category == "valid",
                PodOrder.order_date.between(period_start, period_end),
            )
            .group_by(PodOrder.platform)
            .all()
        )
        for plat, cnt, gmv in platform_rows:
            by_platform[plat or "unknown"] = {"orders": cnt, "gmv_cny": round(gmv or 0, 2)}

        results.append({
            "operator": op_name,
            "valid_links": valid_links,
            "s_level_count": s_level_count,
            "total_orders": total_orders,
            "cancelled_orders": cancelled_orders,
            "cancel_rate": cancel_rate,
            "refund_orders": refund_orders,
            "total_gmv_cny": round(total_gmv_cny, 2),
            "by_country": by_country,
            "by_platform": by_platform,
        })

    results.sort(key=lambda x: x["valid_links"], reverse=True)
    return results


def run_hit_rate(db: Session, days: int = 14) -> list[dict]:
    """选品命中率：有出单的产品数 / 总上架产品数（按运营统计）。
    同时更新 PodProduct 的 has_order, first_order_date, total_orders 字段。
    """
    from models import PodProduct, PodOrder

    cutoff = date.today() - timedelta(days=days)
    products = db.query(PodProduct).filter(
        PodProduct.upload_date >= cutoff,
        PodProduct.operator != "",
    ).all()

    if not products:
        return []

    sku_set = {p.platform_sku for p in products if p.platform_sku}
    order_stats = {}
    if sku_set:
        rows = (
            db.query(
                PodOrder.platform_sku,
                func.count(PodOrder.id).label("cnt"),
                func.min(PodOrder.order_date).label("first_date"),
            )
            .filter(
                PodOrder.platform_sku.in_(sku_set),
                PodOrder.status_category == "valid",
            )
            .group_by(PodOrder.platform_sku)
            .all()
        )
        order_stats = {r.platform_sku: (r.cnt, r.first_date) for r in rows}

    op_total: dict[str, dict] = defaultdict(lambda: {"total": 0, "hit": 0, "by_platform": defaultdict(lambda: {"total": 0, "hit": 0})})

    for p in products:
        op = p.operator
        plat = p.platform or "unknown"
        op_total[op]["total"] += 1
        op_total[op]["by_platform"][plat]["total"] += 1

        has_order = p.platform_sku and p.platform_sku in order_stats
        if has_order:
            cnt, first_dt = order_stats[p.platform_sku]
            p.has_order = 1
            p.first_order_date = first_dt
            p.total_orders = cnt
            op_total[op]["hit"] += 1
            op_total[op]["by_platform"][plat]["hit"] += 1
        else:
            p.has_order = 0
            p.total_orders = 0
            p.first_order_date = None

    db.commit()

    results = []
    for op, data in op_total.items():
        total = data["total"]
        hit = data["hit"]
        bp = {}
        for plat, pdata in data["by_platform"].items():
            bp[plat] = {
                "total": pdata["total"],
                "hit": pdata["hit"],
                "rate": round(pdata["hit"] / pdata["total"] * 100, 1) if pdata["total"] > 0 else 0,
            }
        results.append({
            "operator": op,
            "total_products": total,
            "hit_products": hit,
            "hit_rate": round(hit / total * 100, 1) if total > 0 else 0,
            "by_platform": bp,
        })

    results.sort(key=lambda x: x["hit_rate"], reverse=True)
    return results


def run_daily_upload_stats(db: Session, target_date: date = None) -> list[dict]:
    """每日上新数量统计（按运营）。"""
    from models import PodProduct

    if not target_date:
        target_date = date.today()

    rows = (
        db.query(PodProduct.operator, PodProduct.platform, func.count(PodProduct.id))
        .filter(
            PodProduct.upload_date == target_date,
            PodProduct.operator != "",
        )
        .group_by(PodProduct.operator, PodProduct.platform)
        .all()
    )

    op_data: dict[str, dict] = defaultdict(lambda: {"total_new": 0, "by_platform": {}})
    for op, plat, cnt in rows:
        op_data[op]["total_new"] += cnt
        op_data[op]["by_platform"][plat or "unknown"] = cnt

    return [
        {
            "operator": op,
            "date": target_date.isoformat(),
            "total_new": d["total_new"],
            "by_platform": d["by_platform"],
        }
        for op, d in sorted(op_data.items(), key=lambda x: x[1]["total_new"], reverse=True)
    ]


def sync_kpi_records(db: Session, period: str = None) -> int:
    """将聚合后的 KPI 写入 KPIRecord 表，激活评分/告警/辅导链路。

    1. 调用 run_operator_kpi 获取各运营 KPI
    2. 调用 run_hit_rate 获取命中率
    3. 对每个运营查找或创建 Employee
    4. 写入 KPIRecord（已存在则更新 actual_value）
    """
    from models import KPIRecord, Employee

    if not period:
        today = date.today()
        iso = today.isocalendar()
        period = f"{iso[0]}-W{iso[1]:02d}"

    targets = _load_kpi_targets(db)

    kpi_list = run_operator_kpi(db)
    hit_list = run_hit_rate(db)
    hit_map = {h["operator"]: h["hit_rate"] for h in hit_list}

    count = 0
    for r in kpi_list:
        op_name = r["operator"]
        employee = db.query(Employee).filter(Employee.name == op_name).first()
        if not employee:
            employee = Employee(name=op_name, department="POD运营", position="运营")
            db.add(employee)
            db.flush()

        hit_rate = hit_map.get(op_name, 0)

        metrics = [
            ("有效链接数", r["valid_links"], targets.get("有效链接数", 50)),
            ("S级爆款数", r["s_level_count"], targets.get("S级爆款数", 5)),
            ("总出单量", r["total_orders"], targets.get("总出单量", 200)),
            ("销售额(CNY)", r["total_gmv_cny"], targets.get("销售额(CNY)", 50000)),
            ("取消率(%)", r["cancel_rate"], targets.get("取消率(%)", 5)),
            ("选品命中率(%)", hit_rate, targets.get("选品命中率(%)", 30)),
        ]

        for metric_name, actual, target in metrics:
            if metric_name == "取消率(%)":
                score = max(0, round((target - actual) / target * 100 + 100, 1)) if target > 0 else 100
            else:
                score = round(actual / target * 100, 1) if target > 0 else 0

            grade = _calc_grade(score)

            existing = db.query(KPIRecord).filter(
                KPIRecord.employee_name == op_name,
                KPIRecord.metric_name == metric_name,
                KPIRecord.period == period,
            ).first()

            if existing:
                existing.actual_value = actual
                existing.target_value = target
                existing.score = score
                existing.grade = grade
            else:
                db.add(KPIRecord(
                    employee_id=employee.id,
                    employee_name=op_name,
                    metric_name=metric_name,
                    target_value=target,
                    actual_value=actual,
                    score=score,
                    grade=grade,
                    period=period,
                ))
            count += 1

    if kpi_list:
        db.commit()

    logger.info("KPI sync: %d records for %d operators, period=%s", count, len(kpi_list), period)
    return count


def _calc_grade(score: float) -> str:
    if score >= 120:
        return "S"
    elif score >= 100:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 60:
        return "C"
    return "D"


# ─────────────────────────────────────────────────────────────────────────────
# P1: 月度 Goal 自动创建与更新
# ─────────────────────────────────────────────────────────────────────────────

def sync_monthly_goals(db: Session, year: int = None, month: int = None) -> int:
    """为每个运营按月创建或更新 Goal，并从 PodOrder 同步 current_value。
    
    Goal 维度（每人每月创建 3 个）:
    - 总出单量（目标从 pod_kpi_targets 读取）
    - 销售额 CNY（目标从 pod_kpi_targets 读取）
    - 有效链接数（目标从 pod_kpi_targets 读取）
    """
    from models import Goal, GoalLevel, GoalStatus, Employee
    from datetime import date as d_cls
    import calendar

    if not year or not month:
        today = d_cls.today()
        year, month = today.year, today.month

    month_start = d_cls(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    month_end = d_cls(year, month, last_day)
    period_label = f"{year}-{month:02d}"

    targets = _load_kpi_targets(db)
    kpi_list = run_operator_kpi(db, period_start=month_start, period_end=month_end)

    count = 0
    for kpi in kpi_list:
        op_name = kpi["operator"]
        employee = db.query(Employee).filter(Employee.name == op_name).first()
        if not employee:
            employee = Employee(name=op_name, department="POD运营", position="运营")
            db.add(employee)
            db.flush()

        goal_defs = [
            ("总出单量", kpi["total_orders"], targets.get("总出单量", 200), "单"),
            ("销售额(CNY)", kpi["total_gmv_cny"], targets.get("销售额(CNY)", 50000), "元"),
            ("有效链接数", kpi["valid_links"], targets.get("有效链接数", 50), "个"),
        ]

        for metric_name, current_val, target_val, unit in goal_defs:
            title = f"{op_name} {period_label} {metric_name}"
            existing = db.query(Goal).filter(
                Goal.title == title,
                Goal.owner == op_name,
            ).first()
            if existing:
                existing.current_value = current_val
                if current_val >= existing.target_value and existing.target_value > 0:
                    existing.status = GoalStatus.COMPLETED
            else:
                db.add(Goal(
                    title=title,
                    level=GoalLevel.INDIVIDUAL,
                    owner=op_name,
                    target_value=target_val,
                    current_value=current_val,
                    unit=unit,
                    deadline=month_end,
                    status=GoalStatus.ACTIVE,
                ))
            count += 1

    if kpi_list:
        db.commit()
    logger.info("Monthly goals sync: %d goals for %s-%02d", count, year, month)
    return count


# ─────────────────────────────────────────────────────────────────────────────
# P1: AI 补分类赛道
# ─────────────────────────────────────────────────────────────────────────────

def run_ai_niche_classification(db: Session, batch_size: int = 50) -> int:
    """对关键词未命中的标题批量调 AI 归类，写入 niche 字段。
    
    同时处理 PodOrder 和 PodProduct 表中 niche="" 的记录。
    每次最多处理 batch_size 条，避免 AI 调用超时。
    """
    from models import PodOrder, PodProduct
    import asyncio

    niche_names = [
        "潮牌街头", "复古怀旧", "宗教信仰", "情侣款", "车迷机车",
        "日系动漫", "运动健身", "宠物", "自然花卉", "旅行城市",
        "骷髅摇滚", "咖啡生活", "字母潮流",
    ]
    niche_list_str = "、".join(niche_names)

    # 收集需分类标题（orders + products）
    order_rows = (
        db.query(PodOrder.id, PodOrder.product_title)
        .filter(PodOrder.niche == "", PodOrder.product_title != "")
        .limit(batch_size)
        .all()
    )
    product_rows = (
        db.query(PodProduct.id, PodProduct.product_name)
        .filter(PodProduct.niche == "", PodProduct.product_name != "")
        .limit(batch_size)
        .all()
    )

    if not order_rows and not product_rows:
        logger.info("AI niche classification: no records to classify")
        return 0

    # 合并标题列表
    items = []
    for row_id, title in order_rows:
        items.append(("order", row_id, title))
    for row_id, title in product_rows:
        items.append(("product", row_id, title))

    # 构造 AI 提示
    titles_text = "\n".join(f"{i+1}. {item[2]}" for i, item in enumerate(items))
    prompt = f"""请为以下产品标题分类到对应赛道，赛道选项：{niche_list_str}、其他。
每行输出：序号|赛道名（例如：1|潮牌街头），如无法判断归类为"其他"。
只输出分类结果，不要解释。

{titles_text}"""

    try:
        from harness.ai_client import ai_client

        async def _call():
            return await ai_client.chat(
                [
                    {"role": "system", "content": "你是电商选品赛道分类专家，精通跨境T恤POD产品赛道划分。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=len(items) * 15 + 100,
            )

        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_call())
        loop.close()
    except Exception as e:
        logger.warning(f"AI niche classification failed: {e}")
        return 0

    # 解析结果
    classified = 0
    for line in (result or "").strip().split("\n"):
        line = line.strip()
        if "|" not in line:
            continue
        parts = line.split("|", 1)
        try:
            idx = int(parts[0].strip()) - 1
            niche = parts[1].strip()
            if niche == "其他":
                niche = ""
            if 0 <= idx < len(items):
                table_type, row_id, _ = items[idx]
                if table_type == "order":
                    obj = db.query(PodOrder).filter(PodOrder.id == row_id).first()
                else:
                    obj = db.query(PodProduct).filter(PodProduct.id == row_id).first()
                if obj and niche:
                    obj.niche = niche
                    classified += 1
        except (ValueError, IndexError):
            continue

    if classified > 0:
        db.commit()
    logger.info("AI niche classification: classified %d / %d records", classified, len(items))
    return classified


# ─────────────────────────────────────────────────────────────────────────────
# P2: 月度复盘
# ─────────────────────────────────────────────────────────────────────────────

def run_monthly_review(db: Session, year: int = None, month: int = None) -> dict:
    """每月 1 号聚合上月 KPI，与上上月对比，返回结构化复盘数据。"""
    from datetime import date as d_cls
    import calendar

    if not year or not month:
        today = d_cls.today()
        # 复盘上月
        if today.month == 1:
            year, month = today.year - 1, 12
        else:
            year, month = today.year, today.month - 1

    month_start = d_cls(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    month_end = d_cls(year, month, last_day)

    # 上上月
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    prev_start = d_cls(prev_year, prev_month, 1)
    prev_last = calendar.monthrange(prev_year, prev_month)[1]
    prev_end = d_cls(prev_year, prev_month, prev_last)

    current_kpi = run_operator_kpi(db, period_start=month_start, period_end=month_end)
    prev_kpi = run_operator_kpi(db, period_start=prev_start, period_end=prev_end)
    prev_map = {r["operator"]: r for r in prev_kpi}

    review_rows = []
    for r in current_kpi:
        op = r["operator"]
        prev = prev_map.get(op, {})
        review_rows.append({
            "operator": op,
            "this_month": {
                "valid_links": r["valid_links"],
                "s_level_count": r["s_level_count"],
                "total_orders": r["total_orders"],
                "total_gmv_cny": r["total_gmv_cny"],
                "cancel_rate": r["cancel_rate"],
            },
            "prev_month": {
                "valid_links": prev.get("valid_links", 0),
                "s_level_count": prev.get("s_level_count", 0),
                "total_orders": prev.get("total_orders", 0),
                "total_gmv_cny": prev.get("total_gmv_cny", 0),
                "cancel_rate": prev.get("cancel_rate", 0),
            },
            "order_growth": round(
                (r["total_orders"] - prev.get("total_orders", 0)) / prev.get("total_orders", 1) * 100, 1
            ) if prev.get("total_orders") else 0,
            "gmv_growth": round(
                (r["total_gmv_cny"] - prev.get("total_gmv_cny", 0)) / prev.get("total_gmv_cny", 1) * 100, 1
            ) if prev.get("total_gmv_cny") else 0,
        })

    # 排名：按本月出单量
    review_rows.sort(key=lambda x: x["this_month"]["total_orders"], reverse=True)

    return {
        "period": f"{year}-{month:02d}",
        "prev_period": f"{prev_year}-{prev_month:02d}",
        "operators": review_rows,
        "total_operators": len(review_rows),
        "top_operator": review_rows[0]["operator"] if review_rows else None,
        "bottom_operator": review_rows[-1]["operator"] if len(review_rows) > 1 else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# P2: 淘汰/奖励预警
# ─────────────────────────────────────────────────────────────────────────────

def check_elimination_and_rewards(db: Session) -> dict:
    """检查连续月度垫底/连续三问未提交/月度第一，返回需要处理的预警列表。
    
    返回结构：
    {
        "bottom_alerts": [{"operator": str, "consecutive_months": int}],  # 连续2月垫底
        "standup_missing": [{"operator": str, "missing_weeks": int}],     # 连续3周未提交三问
        "top_reward": {"operator": str, "period": str},                    # 月度第一
    }
    """
    from models import KPIRecord, Task, TaskStatus, Employee
    from datetime import date as d_cls
    import calendar

    today = d_cls.today()
    results = {"bottom_alerts": [], "standup_missing": [], "top_reward": None}

    # ── 1. 连续两月垫底 ──
    periods = []
    for delta in range(2):
        if today.month - delta < 1:
            y, m = today.year - 1, today.month - delta + 12
        else:
            y, m = today.year, today.month - delta
        periods.append(f"{y}-{m:02d}")

    # 用周期KPI聚合判断月度垫底
    monthly_rankings = {}
    for period in periods:
        try:
            y, m = int(period.split("-")[0]), int(period.split("-")[1])
        except Exception:
            continue
        m_start = d_cls(y, m, 1)
        m_end = d_cls(y, m, calendar.monthrange(y, m)[1])
        kpi_rows = run_operator_kpi(db, period_start=m_start, period_end=m_end)
        if kpi_rows:
            kpi_rows.sort(key=lambda x: x["total_orders"])
            monthly_rankings[period] = [r["operator"] for r in kpi_rows]

    if len(monthly_rankings) >= 2:
        all_periods = list(monthly_rankings.keys())
        bottom_this = monthly_rankings.get(all_periods[0], [])
        bottom_prev = monthly_rankings.get(all_periods[1], []) if len(all_periods) > 1 else []
        if bottom_this and bottom_prev:
            this_bottom = bottom_this[0]
            prev_bottom = bottom_prev[0]
            if this_bottom == prev_bottom:
                results["bottom_alerts"].append({
                    "operator": this_bottom,
                    "consecutive_months": 2,
                    "periods": all_periods,
                })

    # ── 2. 连续3周未提交三问周报 ──
    all_ops = db.query(Employee).filter(Employee.department == "POD运营").all()
    for emp in all_ops:
        missing_count = 0
        for week_delta in range(1, 4):
            check_date = today - __import__("datetime").timedelta(weeks=week_delta)
            iso = check_date.isocalendar()
            week_label = f"{iso[0]}-W{iso[1]:02d}"
            submitted = db.query(Task).filter(
                Task.assignee_name == emp.name,
                Task.task_type == "pod_weekly_standup",
                Task.status.in_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED]),
            ).filter(Task.created_at >= (check_date - __import__("datetime").timedelta(days=7)).isoformat()).count()
            if submitted == 0:
                missing_count += 1
        if missing_count >= 3:
            results["standup_missing"].append({
                "operator": emp.name,
                "feishu_id": emp.feishu_id,
                "missing_weeks": missing_count,
            })

    # ── 3. 月度第一 ──
    if today.day <= 3:  # 月初几天才检查上月第一
        if today.month == 1:
            cy, cm = today.year - 1, 12
        else:
            cy, cm = today.year, today.month - 1
        m_start = d_cls(cy, cm, 1)
        m_end = d_cls(cy, cm, calendar.monthrange(cy, cm)[1])
        kpi_rows = run_operator_kpi(db, period_start=m_start, period_end=m_end)
        if kpi_rows:
            kpi_rows.sort(key=lambda x: x["total_orders"], reverse=True)
            results["top_reward"] = {
                "operator": kpi_rows[0]["operator"],
                "total_orders": kpi_rows[0]["total_orders"],
                "total_gmv_cny": kpi_rows[0]["total_gmv_cny"],
                "period": f"{cy}-{cm:02d}",
            }

    return results
