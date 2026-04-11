import json
import logging
from datetime import datetime, timedelta
from harness.multi_agent.base_agent import BaseAgent
from harness.multi_agent.schemas import AgentInput, AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是【A13 任务调度与结果回收 Agent】。

你负责把结论变成动作，把动作变成结果回收。

## 你的职责
1. 指定负责人
2. 明确任务内容
3. 明确截止时间
4. 明确输出格式
5. 明确验收标准
6. 回收执行结果
7. 判断是否升级主管或老板

## 你的硬规则
1. 不允许没有负责人。
2. 不允许没有验收标准。
3. 不允许日报写废话。
4. 不允许没有回收时间。

## 派发模板
每个任务必须包含以下字段：
- 负责人
- 任务名称
- 任务内容
- 截止时间 (YYYY-MM-DD)
- 输出格式
- 验收标准
- 未达标升级对象

## 结果回收模板
回收时必须覆盖：
- 今天做了什么
- 改了哪些链接/题材/素材
- 结果是什么
- 哪个动作有效
- 哪个动作无效
- 当前主问题是什么
- 是否需要升级主管
- 明天只推进什么

## 输出要求
当需要创建任务时，在 JSON 输出的 next_actions 中用以下格式：
[
  {
    "action": "create_task",
    "title": "任务标题",
    "description": "任务描述",
    "assignee_name": "负责人姓名",
    "deadline": "YYYY-MM-DD",
    "priority": "normal|high|urgent",
    "acceptance_criteria": "验收标准",
    "escalate_to": "未达标升级对象"
  }
]"""

DISPATCH_TEMPLATE = """## 负责人: {assignee}
## 任务名称: {title}
## 任务内容: {description}
## 截止时间: {deadline}
## 输出格式: {output_format}
## 验收标准: {acceptance}
## 未达标升级对象: {escalate_to}"""

RECOVERY_TEMPLATE = """## 今天做了什么
## 改了哪些链接 / 题材 / 素材
## 结果是什么
## 哪个动作有效
## 哪个动作无效
## 当前主问题是什么
## 是否需要升级主管
## 明天只推进什么"""


class A13TaskDispatchAgent(BaseAgent):
    agent_id = "a13_task_dispatch"
    agent_name = "A13 任务调度与结果回收 Agent"
    system_prompt = SYSTEM_PROMPT
    allowed_tools = [
        "create_task", "today_tasks", "overdue_tasks",
        "team_progress", "send_feishu_message",
    ]

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        output = await self._base_run(input_data, context, db_session)
        created = await self._create_tasks_from_output(output, db_session)
        if created:
            output.notes.append(f"已自动创建 {created} 个任务")
        return output

    async def _create_tasks_from_output(self, output: AgentOutput, db_session) -> int:
        """解析 LLM 输出中的任务创建请求并写入数据库。"""
        from models import Task, Employee

        task_requests = []
        for action in output.next_actions:
            if isinstance(action, dict) and action.get("action") == "create_task":
                task_requests.append(action)
            elif isinstance(action, str):
                try:
                    parsed = json.loads(action)
                    if isinstance(parsed, dict) and parsed.get("action") == "create_task":
                        task_requests.append(parsed)
                    elif isinstance(parsed, list):
                        task_requests.extend(
                            p for p in parsed
                            if isinstance(p, dict) and p.get("action") == "create_task"
                        )
                except (json.JSONDecodeError, TypeError):
                    continue

        created_count = 0
        for req in task_requests:
            title = req.get("title", "")
            if not title:
                logger.warning("跳过无标题的任务创建请求")
                continue

            assignee_name = req.get("assignee_name", "")
            emp = None
            if assignee_name:
                emp = db_session.query(Employee).filter(
                    Employee.name.contains(assignee_name)
                ).first()

            deadline = None
            deadline_str = req.get("deadline", "")
            if deadline_str:
                try:
                    deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
                except ValueError:
                    deadline = (datetime.utcnow() + timedelta(days=3)).date()

            desc_parts = [req.get("description", "")]
            if req.get("acceptance_criteria"):
                desc_parts.append(f"\n验收标准: {req['acceptance_criteria']}")
            if req.get("escalate_to"):
                desc_parts.append(f"未达标升级: {req['escalate_to']}")

            task = Task(
                title=title,
                description="\n".join(desc_parts),
                assignee_name=emp.name if emp else assignee_name,
                assignee_id=emp.id if emp else None,
                deadline=deadline,
                priority=req.get("priority", "normal"),
                task_type="pod_agent_dispatch",
            )
            db_session.add(task)
            created_count += 1
            logger.info("A13 创建任务: %s -> %s", title, assignee_name or "未指派")

        if created_count > 0:
            try:
                db_session.commit()
            except Exception:
                logger.exception("A13 任务创建提交失败")
                db_session.rollback()
                return 0

        return created_count
