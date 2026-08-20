# 前端工程、交互与代码风格规范

> 从仓库根目录 `coding-standards.md` 提取；源文档是最终依据。

## 目录

- 分层、页面、Service、权限、表单与 Ant Design Pro
- 前端错误处理
- TypeScript / 前端
- 文档与注释

## 前端工程规范

### 前端分层

推荐结构：

```text
src/
  pages/              页面
  components/         通用组件
  services/           API 封装
  models/ or stores/  全局状态
  utils/              纯工具函数
  locales/            国际化
  access/             权限规则
```

规则：

- 页面不直接写后端 URL。
- API 调用统一放 `services`。
- 通用请求拦截、错误处理、鉴权头注入统一配置。
- 可复用组件不要依赖具体页面业务。
- 页面内复杂逻辑抽成 hook 或纯函数。

### 页面职责

页面负责：

- 展示数据。
- 管理 UI 状态。
- 调用 service。
- 处理用户交互。
- 展示 loading、empty、error。

页面不应负责：

- 核心业务状态机。
- 权限最终判定。
- 拼装复杂 SQL 风格查询。
- 直接处理 token 底层逻辑。

### API Service

每个业务域维护一个 service 文件：

```text
course.ts
session.ts
evaluation.ts
user.ts
```

规范：

- 函数名使用业务动作：`createXxx`、`updateXxx`、`publishXxx`、`queryXxx`。
- 明确 request 和 response 类型。
- 状态迁移接口要包含版本号。
- 不要在组件中复制 API 路径。
- 类型要与后端 DTO / VO 保持同步。

### 权限与路由

前端权限用于提升体验，不是最终安全边界。

规则：

- 路由权限和按钮权限应使用统一 access 规则。
- 后端必须再次校验权限。
- 菜单文案走国际化或统一文案配置。
- 未授权页面、登录跳转、401 处理要统一。

### 表单与交互

- 表单字段名尽量与 API request 一致。
- 必填、长度、格式、时间区间在前端先校验。
- 提交成功后刷新数据或跳转要明确。
- 删除、归档、发布等危险操作需要确认。
- loading 状态防止重复提交。
- 错误消息使用统一错误处理，不在每个页面散落重复逻辑。

### Ant Design Pro UI 设计

前端页面默认遵循 Ant Design Pro 的 UI 设计最佳实践，优先使用项目已有的 Pro Components 和 Ant Design 组件体系承载页面结构、查询、表格、详情、表单、统计和操作反馈。

规则：

- 页面外层优先使用 `PageContainer`，复杂表单使用 `ProForm`，数据列表使用 `ProTable`，信息分组使用 `ProCard` / `Card` / `Descriptions`，履历、流程、审计记录优先使用 `Timeline`。
- 查询项、分页、排序、表格操作、空状态、loading、modal、drawer、message 等交互应使用 Ant Design Pro / Ant Design 的内建能力，不重复造自定义控件。
- 布局优先使用 `Space`、`Flex`、`Row`、`Col` 等 Ant Design 布局组件；避免大量裸 `div` 和临时 CSS 拼出组件已有能力。
- 颜色、圆角、边框、阴影、间距等视觉值优先使用 `theme.useToken()` 或组件 token，不硬编码主题色。
- 管理后台页面保持信息密度、对齐、搜索表单、操作列、按钮样式与 Ant Design Pro 一致；不要做营销页式 hero、装饰性渐变或脱离后台体系的视觉风格。
- 新增或修改页面时，应对照 Ant Design Pro 最佳实践检查页面结构、组件选择、主题 token、响应式布局和空 / 加载 / 错误状态。

### 前端错误处理

- 统一 request error handler。
- 401 统一清理登录态并跳转。
- 业务错误按 showType 展示 message / notification。
- 页面不重复实现通用错误处理。

### TypeScript / 前端

- API 类型要准确，避免无意义 `any`。
- 组件 props 明确定义类型。
- 枚举字段使用 union type。
- 请求函数返回 Promise 的明确泛型。
- hook 只处理可复用逻辑，不混入页面文案。
- 日期、金额、状态展示使用统一格式化函数。
- 不在组件中硬编码后端 host。

### 文档与注释

注释用于解释“为什么”，不是重复“做什么”。

应写文档的场景：

- 新模块架构决策。
- 复杂业务状态机。
- 重要接口契约。
- 数据库迁移说明。
- 安全和部署配置。

不要让文档与代码长期不一致；变更代码时同步更新文档。
