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
