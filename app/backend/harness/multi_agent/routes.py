"""Route chain definitions and task-type classification keywords.

Section 8 of the specification defines 6 route chains.
"""

ROUTE_CHAINS: dict[str, list[str]] = {
    "new_direction": [
        "a03_data_gate",
        "a01_risk",
        "a02_business",
        "a05_market",
        "a06_niche",
        "a04_platform",
        "a09_profit",
        "a10_listing",
        "a13_task_dispatch",
        "a14_review",
        "a16_memory",
    ],
    "link_analysis": [
        "a03_data_gate",
        "a01_risk",
        "a08_attribution",
        "a04_platform",
        "a09_profit",
        "a11_optimize",
        "a13_task_dispatch",
        "a14_review",
        "a16_memory",
    ],
    "market_expansion": [
        "a03_data_gate",
        "a02_business",
        "a05_market",
        "a06_niche",
        "a04_platform",
        "a09_profit",
        "a10_listing",
        "a13_task_dispatch",
        "a14_review",
        "a16_memory",
    ],
    "team_action": [
        "a03_data_gate",
        "a13_task_dispatch",
    ],
    "content_event": [
        "a03_data_gate",
        "a05_market",
        "a04_platform",
        "a12_content",
        "a13_task_dispatch",
        "a14_review",
        "a16_memory",
    ],
    "review": [
        "a03_data_gate",
        "a14_review",
        "a16_memory",
    ],
}

TASK_TYPE_KEYWORDS: dict[str, list[str]] = {
    "new_direction": [
        "新方向", "新赛道", "能不能做", "值不值得做", "新品", "新niche",
        "这个方向", "新设计", "要不要做", "选品", "赛道研究",
    ],
    "link_analysis": [
        "链接分析", "曝光没单", "有单没利润", "有单但不赚钱", "链接异常",
        "点击率低", "转化率低", "为什么没单", "链接问题", "不能放量",
        "有曝光", "CTR", "ctr",
    ],
    "market_expansion": [
        "市场扩张", "扩市场", "跨市场", "扩到欧美", "扩到东南亚",
        "菲律宾扩", "其他站点", "跨平台", "新市场",
    ],
    "team_action": [
        "团队", "下一步", "今天做什么", "本周推什么", "任务安排",
        "优先推什么", "工作安排", "动作安排",
    ],
    "content_event": [
        "内容", "活动", "节日", "节点", "TikTok内容", "达人",
        "活动安排", "活动节奏", "内容方向",
    ],
    "review": [
        "复盘", "沉淀", "经验", "SOP", "反例", "案例",
        "怎么复用", "写进SOP", "总结经验",
    ],
}

AGENT_PRIORITY_ORDER = [
    "a01_risk",
    "a03_data_gate",
    "a02_business",
    "a09_profit",
    "a08_attribution",
    "a04_platform",
    "a05_market",
    "a06_niche",
    "a07_design",
]
