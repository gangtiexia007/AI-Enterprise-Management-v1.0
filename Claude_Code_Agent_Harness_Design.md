# Claude Code 的 Agent 设计思路（详细版）
**主题**：Claude Code 的核心架构为什么不是“一个更聪明的模型”，而是“一个 agent harness（代理运行框架 / scaffold）”  
**版本**：v1.0  
**更新时间**：2026-04-07  
**说明**：这份文档不把“泄露”当成事实前提。下面内容基于 Anthropic 公开文档、工程文章和 Claude Code/Agent SDK 说明做归纳。能确认的是：Anthropic 明确把 Claude Code/Agent SDK 描述为一个 **agent harness**，而不是单纯的模型能力展示。

---

# 一、先给结论

## 1. 核心判断
Claude Code 的真正价值，不在于“把一个模型 prompt 写得更聪明”，而在于它把一整套 **让模型持续工作、会用工具、会压缩上下文、会分工、会受约束、会恢复、会接入外部系统** 的运行框架打包好了。  
**模型只是大脑的一部分，harness 才是让这个大脑能持续干活的操作系统。**

## 2. 这句话翻译成人话
如果你只拿一个强模型，然后给它一个长 prompt，它顶多是：
- 会回答
- 会规划一点
- 会写一点代码
- 会试着调用工具

但它通常很快撞墙：
- 上下文爆掉
- 中间状态丢失
- 任务太大时容易一把梭哈
- 失败后不知道从哪里恢复
- 工具一多就乱
- 权限一放开就危险
- 同一个任务跨多轮后开始漂

**harness 的作用**，就是把这些“模型本身做不稳”的地方工程化补齐。

---

# 二、什么是 agent harness

Anthropic 在工程文章里给的定义很直接：  
**agent harness（或 scaffold）是让模型能够以 agent 方式行动的系统；它负责处理输入、编排工具调用、并返回结果。**

这句话非常关键。因为它把“agent”从“一个会思考的模型”改成了“一个由模型 + 运行控制系统共同组成的工作单元”。

## 1. harness 的本质职责
一个真正能落地的 harness，至少要负责这几件事：

1. **接收任务**：把用户目标转换成 agent 能执行的工作上下文。  
2. **分解任务**：让模型不要一次性一口吞掉大任务。  
3. **编排工具**：决定什么时候读文件、跑命令、编辑代码、搜网页、调 MCP。  
4. **管理上下文**：保留关键决策，丢弃噪音，避免窗口爆炸。  
5. **控制权限**：哪些动作直接做，哪些必须审批，哪些永远不能做。  
6. **处理失败**：任务中断、报错、半完成、上下文压缩后，如何继续。  
7. **支持协作**：主 agent、子 agent、后台任务、hook、技能之间如何协同。  
8. **保证可评估**：不是只看模型回答好不好，而是看整套系统完成任务的成功率、成本、稳定性、安全性。

## 2. 这也是为什么 Anthropic 说“评估 agent 时，评估的是 harness + model”
很多人做 agent 会犯的一个错，是把成败都归结为模型强不强。  
但 Anthropic 的公开说法很明确：**当我们评估一个 agent，本质上是在评估 harness 和模型一起工作的结果。**

这意味着：
- 同一个模型，换一个 harness，结果会差很多。
- 模型升级不是唯一增益来源。
- 很多所谓“agent 变强”，其实不是模型突然更聪明，而是 **任务拆分、上下文管理、权限设计、工具设计、恢复机制** 做对了。

---

# 三、为什么 Claude Code 不是“一个聪明模型”

## 1. 官方已经明确说了它是什么
Anthropic 在 Agent SDK 文档里写得很直接：  
Agent SDK 提供的是 **与 Claude Code 相同的工具、agent loop、context management**。  
这等于公开告诉你，Claude Code 的能力核心不是一个神秘 prompt，而是：

- 工具系统
- agent loop
- 上下文管理
- 权限与约束
- 可编程运行时

也就是说，Claude Code 更像：

```text
Claude Model
+ Tool Use
+ Agent Loop
+ Context Compaction
+ Memory / Rules
+ Permission Controls
+ Hooks / Skills / Subagents / MCP
= Claude Code 的实际工作能力
```

## 2. 只靠模型会发生什么
Anthropic 在 long-running harness 的文章里明确指出：  
即使是前沿模型，放进一个简单循环里，给它一个高层目标，例如“做一个某产品的 clone”，**也很难直接做出生产级结果**。

典型失败模式有两个：

### 失败模式 A：一把梭哈
模型会尝试一次性做太多事情。结果是：
- 任务范围太大
- 改动太散
- 中间没稳定 checkpoint
- 上下文中途爆掉
- 下一轮接手时变成残局

### 失败模式 B：半成品失忆
当上下文压缩或轮次切换发生时，如果没有好的结构化记录：
- 上一轮做了什么不清楚
- 哪些 bug 已知不清楚
- 哪些设计决策必须保留不清楚
- 下一轮只能“猜”

**这不是模型不够聪明，而是 harness 没把长期工作机制搭起来。**

---

# 四、Claude Code 的核心设计思路：把“智能”外包给结构

Claude Code 这套思路，核心不是“让模型记住一切”，而是：  
**让模型在合适的结构里工作。**

这个思路可以拆成 8 个核心层。

---

# 五、八层核心架构

## 第 1 层：Model 不是产品，Model 只是执行引擎

### 设计原则
不要把模型当成完整产品。模型只负责：
- 理解目标
- 进行局部推理
- 决定下一步调用什么工具
- 在局部上下文内产出动作或结论

### 为什么这样设计
因为模型本身不擅长长期状态管理。
它擅长的是：
- 看到当前上下文后做判断
- 基于规则和示例规划下一步
- 在工具反馈基础上继续推进

所以，**真正的系统设计重点不是“怎么让模型更像人”，而是“怎么把工作环境搭成一个模型能稳定发挥的流水线”。**

### 业务映射
你以后做任何业务 Agent，都不要想着：
- 写一个超级总 prompt
- 把所有经验塞进去
- 然后希望它自动变成运营主管/投流主管/客服主管

正确方向是：
- 模型只负责当前节点判断
- 规则、记忆、权限、流程、分工由 harness 管

---

## 第 2 层：Agent Loop 才是 agent 的骨架

Claude Code/Agent SDK 官方明确提到它提供 **agent loop**。  
这个 loop 才是 agent 能持续工作的根。

### 一个最小 agent loop 长这样

```text
1. 接收目标
2. 读取必要上下文
3. 决定下一步动作
4. 调用工具
5. 观察结果
6. 更新当前计划
7. 判断是否继续 / 是否结束 / 是否需要求助
8. 重复
```

### 为什么 loop 比 prompt 更重要
因为一次 prompt 只是“一次回答”。  
而真正的 agent 任务通常是：
- 多步
- 有工具调用
- 有反馈
- 有错误
- 有中断
- 有状态切换

没有 loop，模型只能“想”；  
有 loop，模型才开始“干活”。

### Claude Code 的关键点
它不是让模型只答一轮，而是允许模型：
- 读文件
- 改文件
- 跑命令
- 再看结果
- 再决定下一步

这就把“回答问题”变成了“执行任务”。

### 业务映射
你做 Temu 运营主管 Agent 时也是一样：
不要只问“今天怎么优化”。  
应该让系统跑成 loop：

```text
读最近 14 天链接数据
→ 判定哪些链接有信号
→ 调取对应优化动作卡
→ 生成今日动作
→ 收集结果
→ 更新有效/问题/淘汰状态
→ 输出明日动作
```

这就是 harness 逻辑，不是 prompt 逻辑。

---

## 第 3 层：Tool Use 不是外挂，是主工作面

Anthropic 的工具文档把机制讲得很清楚：  
模型会根据请求和工具描述，决定何时调用工具；然后由系统执行并把结果返回。

### 这意味着什么
真正强的 agent，不是靠“脑补”，而是靠：
- 去读真实文件
- 去跑真实命令
- 去搜真实网页
- 去接真实系统
- 去拿真实返回值

### Claude Code 的工具观非常重要
Agent SDK 文档里写得很清楚：它直接给你文件读取、命令执行、代码编辑等内置工具。  
所以 Claude Code 的工作方式不是：
- 我猜你项目长什么样

而是：
- 我读你的代码库
- 我看错误信息
- 我执行测试
- 我修改文件
- 我再验证

### 设计原则
工具不是附属品，工具是 agent 的主工作面。  
模型的任务是：
- 选择工具
- 组织工具使用顺序
- 解释工具结果
- 决定下一步

### 业务映射
你做运营 Agent 也一样。真正的运营 Agent 不应该只是聊天：
- 要能读 ERP 数据
- 要能读广告数据
- 要能拉店铺链接状态
- 要能触发动作流
- 要能把反馈写回系统

否则它不是 agent，只是会说话的报表解释器。

---

## 第 4 层：Context Management 决定 agent 能不能长期工作

这是 Claude Code 非常关键的一层。

Anthropic 在 context engineering 和 long-running harness 文章里反复强调：  
**compaction（压缩）不是可有可无，而是长期 agent 的生命线。**

### Claude Code 的做法
公开资料说明，Claude Code 会把消息历史进行总结与压缩，保留：
- 架构决策
- 未解决 bug
- 实现细节

同时丢掉：
- 重复消息
- 冗长工具输出
- 不关键中间噪音

并把压缩后的关键上下文与最近访问过的重要文件组合起来，继续工作。

### 为什么这层重要
因为 agent 真正失败的地方，不是第一轮，而是第 5 轮、第 15 轮、第 50 轮。

如果没有压缩和保留机制：
- 越跑越乱
- 越跑越贵
- 越跑越忘
- 越跑越偏

### 设计关键
上下文管理不是“尽量多塞信息”，而是“有选择地保留信息”。

#### 必须保留的内容
- 当前真实目标
- 已完成的关键步骤
- 未完成但已开始的步骤
- 已做出的架构/策略决策
- 已知问题与限制
- 接下来最重要的 pending action

#### 必须丢弃的内容
- 冗长日志
- 重复工具输出
- 已经失效的探索路径
- 不影响决策的细碎对话

### 业务映射
你做业务 Agent 的记忆设计时，也不能把“几百条历史内容”直接硬塞进去。  
要分层：
- 规则记忆
- 案例记忆
- 风格记忆
- 结果记忆

这本质上就是业务版的 context management。

---

## 第 5 层：Memory / Rules 不是“记住更多”，而是“在正确时机加载正确约束”

Claude Code 的记忆机制很值得抄。

### 公开机制里最重要的几个点
根据 Claude Code 的 memory 文档：
- `CLAUDE.md` 会沿目录树被发现和加载
- 不同层级的 `CLAUDE.md` 会被拼接进上下文
- 子目录规则是按需加载，不是全部启动时灌入
- Auto memory 是纯 markdown，可审计、可编辑、可删除
- `MEMORY.md` 启动时只加载一部分，其余按需读

### 这背后的设计思想
它不是追求“把所有记忆全塞给模型”，而是追求：

1. **分层**：全局规则、项目规则、目录规则、个人规则、自动记忆分开。  
2. **延迟加载**：相关时再加载，不相关不占上下文。  
3. **可审计**：记忆不是黑盒，用户可看、可改、可删。  
4. **可继承**：上层规则对子层生效，下层可增加更具体约束。  
5. **弱覆盖、强组合**：更多是拼接上下文，而不是神秘优先级黑箱。

### 这点为什么非常重要
很多人做企业 Agent，最容易做错两件事：

#### 错法 1：把全部知识库塞进系统提示词
结果：
- 上下文浪费
- 低遵循
- 冲突严重
- 成本高

#### 错法 2：把记忆做成不可解释黑盒
结果：
- 为什么这样决策说不清
- 规则冲突排查不了
- 错误会积累

Claude Code 的方向更对：  
**记忆是文件化、层级化、可调试、可延迟加载的。**

### 业务映射
你公司的 Agent 记忆，也应该按这套来：

```text
L1：老板级硬规则（战略、风险红线、利润底线）
L2：部门 SOP 规则（运营/投流/客服/设计）
L3：岗位动作卡（员工当天要怎么做）
L4：案例记忆（成功/失败案例）
L5：结果记忆（做过什么动作，结果如何）
```

这才是可落地的记忆系统。

---

## 第 6 层：Subagents 说明它不是单线程聊天机器人，而是可分工的执行系统

Claude Code 文档公开支持 **subagents**，而且可以：
- 控制子 agent 用什么模型
- 限制子 agent 能用哪些工具
- 限制能不能写文件
- 限制它还能再拉起哪些子 agent

### 这意味着什么
这不是“一个模型更聪明”，而是一个 **可分工、可隔离、可并行** 的工作系统。

### 子 agent 的设计价值

#### 1. 专业分工
不同子 agent 负责不同工作：
- 研究
- 代码审查
- 测试
- 文档整理
- 数据分析

#### 2. 风险隔离
有些子 agent 只允许：
- Read
- Grep
- Glob
- Bash

不允许写文件，不允许危险 MCP。  
这样你可以做“只读研究员”“安全检查员”“差异分析员”。

#### 3. 上下文隔离
主 agent 不必把所有细节都自己扛。  
子 agent 处理完子任务，只返回结果摘要。

#### 4. 并行效率
Anthropic 公开文章里也提到，并行多个 Claude 可以解决单 agent 一次只能做一件事的问题，并带来专业化分工。

### 业务映射
你以后做管理型 Agent，至少应该拆成：
- 数据分析子 agent
- 动作建议子 agent
- 风险审计子 agent
- 文档归档子 agent

而不是让一个总 agent 什么都做。

---

## 第 7 层：Hooks / Skills / Commands 说明它是“流程框架”，不是“聊天技巧”

Claude Code 公开支持：
- hooks
- skills
- commands
- plugins
- MCP

这些东西加起来，本质上是在做一件事：  
**把高频、重复、可模板化的工作，从即时思考，转成可复用流程单元。**

### A. Skills 的本质
官方文档写得很清楚：skill 是 `SKILL.md` 驱动的扩展能力。  
Claude 可以按需调用，也可以手动触发；它甚至能结合工具与子 agent 完成工作。

这说明：
- Claude Code 的很多“能力”本质上不是模型原生天赋
- 而是把某类工作写成一套 playbook，再交给模型执行

换句话说：  
**skill = 可复用的工作方法模板**

这对你很重要，因为你做企业 Agent 时最值钱的资产不是 prompt，而是：
- 标准动作流
- 诊断框架
- 检查清单
- 升级处理规则
- 复盘模板

这些都应该 skill 化。

### B. Hooks 的本质
官方新闻稿提到 hooks 可以在特定节点自动触发动作，比如：
- 改完代码后跑测试
- 提交前做 lint

这意味着 agent harness 已经不是“每次都重新想一次”，而是：
- 到某个状态
- 自动执行固定检查
- 再把结果回灌给 agent

这就是流程控制。

### C. Commands 的本质
用户可直接触发预定义动作。  
也就是说，系统既支持 agent 自主，也支持人工指定工作模板。

### 业务映射
你公司的 Agent 未来也应该有：
- `/日清`：拉今天动作与结果
- `/复盘`：拉过去 7 天有效链接变化
- `/审计`：检查 SOP 是否执行到位
- `/上品诊断`：对单链接给出状态和下一步

这些都不是“聊天”，而是操作界面。

---

## 第 8 层：Permissions / Sandboxing / Auto Mode 说明 Claude Code 的目标是“安全自治”

这层极其关键，也是很多人做 Agent 时完全没意识到的。

Anthropic 在 auto mode 的文章里讲得很清楚：
- 默认情况下，Claude Code 对运行命令或修改文件会请求审批
- 直接全放开很危险
- 于是他们做了更细的自动权限决策机制，减少 approval fatigue

### 设计含义
一个真正能落地的 agent，不是“权限越大越牛”。  
而是：
- 低风险动作自动做
- 中风险动作按规则做
- 高风险动作强制审批
- 危险动作根本不给

### 权限控制为什么是核心架构，不是边角料
因为只要 agent 要干真活，就一定涉及：
- 改文件
- 跑命令
- 调系统
- 发请求
- 写数据

没有权限框架，agent 只能当演示。  
权限一旦胡乱放开，agent 就变事故源。

### Claude Code 的正确方向
它不是只让模型更敢做事，而是：
- 工具可限制
- 权限可审批
- 模式可切换
- 规则可配置
- 可在安全和效率之间调平衡

### 业务映射
你做企业内部 Agent 时，也必须分级：

```text
P0：只读分析（自动）
P1：生成建议（自动）
P2：写回草稿/待审核动作（自动）
P3：直接改系统数据（审批）
P4：批量删除/批量停推/批量发信（强审批）
```

这就是可落地的自治，不是空谈 AI 自动化。

---

# 六、Claude Code 为什么能比“单模型”更强：真正的增益来自哪里

下面是最重要的一段。

## 1. 增益并不主要来自 prompt 变花
真正的增益主要来自 6 个地方：

### （1）任务分解更稳
不要求模型一次做完整任务，而是通过 harness 让它逐步推进。

### （2）工具调用更真
不是凭空想，而是读取真实世界状态后再决策。

### （3）上下文压缩更准
把关键决策留下，把噪音扔掉，保证长期连续性。

### （4）记忆加载更合理
不是全量注入，而是按层、按路径、按需加载。

### （5）分工更清晰
主 agent 不做所有事，子 agent 和 skill 负责特定工作。

### （6）安全边界更清楚
权限和审批系统使 agent 可以真正进入生产环境。

## 2. 这也是为什么 Anthropic 一直在讲 harness design
Anthropic 近几篇工程文章反复强调一个主题：  
**前沿 agent 的上限，不只由模型决定，也由 harness design 决定。**

这件事你必须记住，因为它直接决定你以后做企业 Agent 的投入方向：

### 不该重投的地方
- 反复抠一版超级 prompt
- 指望模型自己长出稳定流程
- 把全部知识一股脑灌进上下文

### 应该重投的地方
- 工具定义
- 状态设计
- 上下文压缩
- 记忆结构
- 子 agent 分工
- hook 节点
- 权限分级
- eval 体系

---

# 七、Claude Code 的设计逻辑，可以抽象成一张总图

```text
                ┌──────────────────────────────┐
                │          User Goal           │
                └──────────────┬───────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │     Main Agent / Planner     │
                │  - 理解目标                   │
                │  - 决定下一步                 │
                │  - 选择工具/子Agent/技能      │
                └───────┬───────────┬──────────┘
                        │           │
            ┌───────────▼───┐   ┌──▼────────────────┐
            │ Context Layer │   │ Rules / Memory    │
            │ - 历史压缩     │   │ - CLAUDE.md       │
            │ - 状态摘要     │   │ - auto memory     │
            │ - 最近关键文件 │   │ - path rules      │
            └───────────┬───┘   └──┬────────────────┘
                        │           │
                        └─────┬─────┘
                              ▼
                ┌──────────────────────────────┐
                │         Agent Loop           │
                │ think → act → observe →     │
                │ update → continue/stop       │
                └───────┬───────────────┬──────┘
                        │               │
             ┌──────────▼───────┐   ┌──▼─────────────────┐
             │ Tooling Layer     │   │ Subagents / Skills │
             │ Read / Edit /     │   │ 专项任务、并行、隔离 │
             │ Bash / Web / MCP  │   │ playbook化能力      │
             └──────────┬───────┘   └──┬─────────────────┘
                        │               │
                        └─────┬─────────┘
                              ▼
                ┌──────────────────────────────┐
                │ Permissions / Hooks / Safety │
                │ 审批、自动化、限制、审计      │
                └──────────────┬───────────────┘
                               ▼
                ┌──────────────────────────────┐
                │      External Environment    │
                │ 文件系统 / 命令 / 浏览器 /   │
                │ MCP 服务 / 企业系统 / API    │
                └──────────────────────────────┘
```

---

# 八、如果你要复刻 Claude Code 思路，正确的设计顺序是什么

## 错误顺序
很多团队会这样做：
1. 先选模型
2. 写一个超长 prompt
3. 接很多工具
4. 发现 agent 不稳定
5. 再不断补 prompt

这个顺序基本会越做越乱。

## 正确顺序

### Step 1：先定义 agent 的“工作单位”
先回答：这个 agent 到底完成什么闭环？
不是“帮我做运营”，而是：
- 读取数据
- 判断链接状态
- 输出今日动作
- 写回记录
- 跟踪结果

### Step 2：定义状态机，不是只定义提示词
要清楚 agent 在哪些状态间切换：
- 初始化
- 收集上下文
- 分析
- 执行
- 验证
- 失败重试
- 升级审批
- 完成归档

### Step 3：定义工具，不要泛化
每个工具都要明确：
- 做什么
- 输入是什么
- 输出是什么
- 什么时候该调用
- 什么情况下禁止调用

### Step 4：定义记忆层次
至少拆成：
- 全局硬规则
- 项目规则
- 任务状态摘要
- 历史结果记忆
- 案例库

### Step 5：定义压缩策略
每轮压缩必须保留：
- 当前目标
- 已完成事项
- 未完成事项
- 当前阻塞
- 关键决策
- 下一步最优动作

### Step 6：定义权限分层
什么自动，什么审批，什么禁止。

### Step 7：定义子 agent 分工
主 agent 不要干所有事。  
把：
- 调研
- 审计
- 报告
- 数据检查
- 文档化
拆开。

### Step 8：定义 eval
没有 eval，就不知道问题在：
- 模型
- 工具
- 规则
- 压缩
- 权限
- 任务拆分

---

# 九、Claude Code 思路对企业 Agent 设计的真正启发

## 启发 1：不要造“全知全能 Agent”
一个大总管式 Agent，几乎一定会失控。  
正确做法是：主控 + 专项子 agent + 规则层 + 工具层。

## 启发 2：不要把知识库当上下文垃圾桶
知识越多不等于越强。  
要做的是：
- 分层
- 索引
- 按需加载
- 结果回写

## 启发 3：不要只做聊天入口
真正有价值的是：
- 能读真实数据
- 能执行真实动作
- 能把结果写回系统
- 能持续跟踪

## 启发 4：先做 harness，再谈 agent 自治
如果 harness 没搭起来，自治只会等于失控。  
所以顺序必须是：
- 先限制
- 再自动
- 再局部自治
- 最后才是更大范围自治

## 启发 5：业务 Agent 的核心资产不是 prompt，而是 SOP 结构化
你公司真正值钱的，不是“运营 prompt”。  
而是：
- 什么叫有效链接
- 什么叫问题链接
- 什么情况下必须停
- 什么情况下继续放量
- 谁可以决策
- 谁只能上报
- 哪些动作一定要做

这些东西一旦结构化，就能做成：
- skill
- rule
- action card
- hook
- eval case

这才是企业 Agent 的长期资产。

---

# 十、给你一个最实用的判断标准：什么算 Claude Code 式 Agent，什么不算

## 算 Claude Code 式 Agent 的特征
如果一个系统具备下面大部分特征，它就接近 Claude Code 的思路：

- 有明确 agent loop
- 能调用真实工具
- 有上下文压缩与状态延续
- 有规则 / 记忆分层
- 有子 agent 分工
- 有 hook / command / skill 机制
- 有权限控制与审批边界
- 能接外部系统（MCP / API / 文件 / 命令）
- 能评估的是“系统完成任务能力”，不是单次对话质量

## 不算的典型伪 Agent
下面这些，基本都不是真 agent，只是包装过的聊天：

- 一个长 prompt + 一个模型
- 接了很多工具，但没有状态机和权限层
- 能回答得很像专家，但不能持续执行
- 上下文一长就失忆
- 无法恢复半完成任务
- 没有明确的动作闭环和结果回写

---

# 十一、你做企业 Agent 时，最该照抄 Claude Code 的 10 条设计原则

1. **模型不是系统，系统才是系统。**  
2. **先定义 loop，再写 prompt。**  
3. **工具是主工作面，不是附属插件。**  
4. **长任务必须靠压缩，不靠硬扛上下文。**  
5. **记忆必须分层、可审计、可按需加载。**  
6. **复杂任务必须拆给子 agent，不要总 agent 一把抓。**  
7. **把高频流程 skill 化、hook 化、command 化。**  
8. **权限分级是生产可用的前提。**  
9. **评估对象是 harness + model，不是模型单独表现。**  
10. **企业 Agent 的护城河是 SOP、规则、工具和反馈闭环，不是 prompt 文案。**

---

# 十二、最终判断

## 一个明确判断
**Claude Code 的核心设计思路，不是做出一个“超级聪明的 Claude”，而是把 Claude 放进一个工程化的 agent harness 中，让它具备：持续执行、工具使用、上下文压缩、规则继承、权限受控、分工协作、流程复用、长期恢复的能力。**

所以，Claude Code 的本质不是“模型增强”，而是：  
**模型 × 工具 × 上下文管理 × 记忆 × 权限 × 工作流 × 子 agent × 外部连接 = agent harness。**

这也是你后面做所有业务 Agent 时最该抄的底层逻辑。

---

# 十三、参考来源（公开资料）

> 下面是这份整理直接依赖的公开资料。为避免把“泄露”当成事实，我只列公开可核验来源。

1. Anthropic, **Agent SDK overview**  
   关键信息：Agent SDK 提供与 Claude Code 相同的 tools、agent loop、context management。  
   来源：https://platform.claude.com/docs/en/agent-sdk/overview

2. Anthropic Engineering, **Demystifying evals for AI agents**  
   关键信息：agent harness/scaffold 的定义；评估的是 harness + model。  
   来源：https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents

3. Anthropic Engineering, **Building Effective AI Agents**  
   关键信息：成功的 agent 通常建立在简单、可组合的模式上，而不是复杂框架幻想。  
   来源：https://www.anthropic.com/engineering/building-effective-agents

4. Anthropic Engineering, **Effective harnesses for long-running agents**  
   关键信息：只靠模型和简单循环，不足以完成长期高质量任务；需要 harness 设计。  
   来源：https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

5. Anthropic Engineering, **Harness design for long-running application development**  
   关键信息：在 agentic coding 前沿，harness design 是关键性能来源。  
   来源：https://www.anthropic.com/engineering/harness-design-long-running-apps

6. Anthropic Engineering, **Effective context engineering for AI agents**  
   关键信息：Claude Code 通过总结压缩历史，保留关键决策和最近关键文件以延续工作。  
   来源：https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

7. Claude Code Docs, **Memory**  
   关键信息：CLAUDE.md / CLAUDE.local.md / MEMORY.md / path-scoped rules / auditability。  
   来源：https://code.claude.com/docs/en/memory

8. Claude Code Docs, **Subagents**  
   关键信息：子 agent 的模型选择、工具限制、能力隔离。  
   来源：https://code.claude.com/docs/en/sub-agents

9. Claude Code Docs, **Skills**  
   关键信息：skill 作为 prompt-based playbook，可由 Claude 自动调用，也可人工触发。  
   来源：https://code.claude.com/docs/en/skills

10. Anthropic News, **Enabling Claude Code to work more autonomously**  
    关键信息：subagents、hooks、background tasks。  
    来源：https://www.anthropic.com/news/enabling-claude-code-to-work-more-autonomously

11. Anthropic Engineering, **Claude Code auto mode: a safer way to skip permissions**  
    关键信息：审批、权限、安全与效率平衡。  
    来源：https://www.anthropic.com/engineering/claude-code-auto-mode

12. Anthropic Docs, **Tool use with Claude**  
    关键信息：工具调用的工作机制。  
    来源：https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview

13. Model Context Protocol docs / Anthropic docs, **MCP**  
    关键信息：通过 MCP 把 agent 接到外部数据源和工具上。  
    来源：https://modelcontextprotocol.io/docs/getting-started/intro

---

# 十四、更新记录

## v1.0 - 2026-04-07
- 新建文档
- 以“agent harness”作为主线，重构 Claude Code 的设计思路
- 补齐：loop、tool use、context compaction、memory、subagents、skills、hooks、permissions、MCP、eval 视角
- 明确区分：公开可验证资料 vs “泄露”说法
