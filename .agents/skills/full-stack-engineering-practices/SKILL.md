---
name: full-stack-engineering-practices
description: 统一指导本仓库前端、后端及跨端功能的设计、实现、重构、审查、测试、联调和交付。用于任何涉及 Java/Spring 后端、TypeScript/React 前端、API 契约或前后端协同的编码变更；先判断实际范围，再按需加载对应规范。不用于与仓库开发无关的纯概念问答。
---

# 全栈工程实践

先理解需求和仓库事实，再判断变更是后端、前端还是跨端。只加载实际需要的引用，不因使用本 skill 擅自扩大用户要求的修改范围。

## 路由规范

始终读取 [shared/engineering-workflow.md](references/shared/engineering-workflow.md)。随后按范围读取：

- **后端变更**：读取 [backend/architecture-and-api.md](references/backend/architecture-and-api.md)。涉及认证、授权、配置、错误或日志时再读 [backend/security-and-observability.md](references/backend/security-and-observability.md)；涉及测试时读 [backend/testing.md](references/backend/testing.md)；涉及 Java/SQL/Javadoc、开发清单或交付时读 [backend/style-and-delivery.md](references/backend/style-and-delivery.md)。
- **前端变更**：读取 [frontend/engineering.md](references/frontend/engineering.md)。涉及测试时读 [frontend/testing.md](references/frontend/testing.md)；涉及开发清单、目录、联调或交付时读 [frontend/delivery-and-antipatterns.md](references/frontend/delivery-and-antipatterns.md)。
- **跨端变更**：读取前后端所有与变更相关的引用，并额外读取 [integration.md](references/integration.md)。

不要仅因需求名称像“功能开发”就默认修改前后端。根据实际契约、数据、页面和验收范围判断；只涉及一侧时，另一侧仅做必要的只读契约核对。

执行代码审查，或完成任何代码修改后，必须读取 [shared/review-loop.md](references/shared/review-loop.md)，并以本节选出的全部适用规范作为审查依据。不得只依赖通用编程经验进行泛化审查。

## 执行流程

1. 明确业务目标、非目标、用户角色、状态变化、权限、数据影响、外部契约和验收行为。
2. 搜索同类实现，确认技术栈、模块边界、命名、公共类型、错误模型、分页结构、权限规则、迁移链路和验证命令；不猜测字段、路径或框架行为。
3. 声明变更范围和适用规范主题，列出前端、后端、契约、数据与测试影响。
4. 跨端功能先稳定 API 契约，再实现后端能力和前端消费；任何契约变化都同步请求、响应、枚举、时间、分页、权限、错误和版本控制。
5. 在行为发生的层直接测试。前后端各自完成单元或集成验证，跨端功能再完成契约核对和联调检查。
6. 运行与风险相称的类型检查、lint、测试、编译或构建，记录实际命令与结果。失败或未完成必要验证时不得声明完成。
7. 按 [shared/review-loop.md](references/shared/review-loop.md) 对完整变更执行规范驱动的审查、修复、回归验证和重新审查，直到满足退出条件。

## 审查与交付

审查必须覆盖所有适用规范。每个问题都应包含严重程度、代码位置、证据与风险、对应规范文件及章节标题、期望修复；修复后重新审查完整变更，不得只检查最后一次补丁。无法验证的规范项必须明确说明，不得视为通过。

交付说明必须包含：前端和后端分别修改了什么、契约或数据是否变化、实际验证命令与结果、适用规范及审查结果、未执行项及原因、残余风险。只有最新一轮完整审查没有未解决的规范问题，且代码、类型、契约、迁移、权限、测试和必要文档一致时才声明完成。
