# 前端开发、联调与交付规范

> 从仓库根目录 `coding-standards.md` 提取；省略后端专属实现清单，源文档是最终依据。

## 目录

- 开发前
- 前端开发、联调与完成检查
- Coding Agent 工作准则
- 前端目录模板
- 反模式清单
- 工程交付路径

## 开发前

- [ ] 明确业务目标和非目标。
- [ ] 找到所属业务域。
- [ ] 确认是否新增状态、枚举、角色、权限。
- [ ] 确认是否需要数据库变更。
- [ ] 确认 API 契约与前端页面影响。
- [ ] 阅读同类功能实现，复用现有模式。

## 前端开发

- [ ] 在 service 层新增 API 函数和类型。
- [ ] 新增页面或组件。
- [ ] 配置路由、菜单、权限。
- [ ] 页面 UI 符合 Ant Design Pro 最佳实践，优先使用 Pro Components / Ant Design 组件和主题 token。
- [ ] 处理 loading、empty、error。
- [ ] 添加表单校验和危险操作确认。
- [ ] 同步枚举、状态文案、国际化文案。
- [ ] 添加必要测试。

## 联调前检查

- [ ] HTTP method 和路径一致。
- [ ] 前端 URL 前缀与网关 / 后端前缀一致。
- [ ] Request body 字段一致。
- [ ] Response 类型一致。
- [ ] 分页查询统一返回 `PageableDTO<T>`，且 Controller 返回类型、builder 和 HTTP 响应体都设置明确泛型。
- [ ] OpenAPI 注解与真实 HTTP 方法、路径、请求体、响应体、分页结构、权限说明保持一致。
- [ ] 请求体和响应体 VO 属性均有 `@Schema` 标注，且只读字段、服务端生成字段不会被写接口信任。
- [ ] 枚举 code 一致。
- [ ] 时间格式一致。
- [ ] 分页结构一致。
- [ ] 权限前后端一致。
- [ ] 写操作包含版本号和操作者。

## 完成前

- [ ] 运行后端测试或最小模块编译。
- [ ] 运行前端类型检查、lint、测试。
- [ ] 检查是否引入敏感信息。
- [ ] 检查是否有临时代码、console、mock 数据残留。
- [ ] 更新相关文档。
- [ ] 总结验证结果和风险。

## Coding Agent 工作准则

Coding agent 在本类项目中工作时应遵循：

1. 先理解架构，再修改代码。
2. 先搜索同类实现，再生成新实现。
3. 先定位业务域，再确定文件位置。
4. 不猜测接口和字段，必须从代码或契约确认。
5. 不跨层调用，不把快速实现凌驾于架构边界之上。
6. 修改后必须做最小验证。
7. 如果同时影响前后端，必须同步类型、路径、枚举、权限。
8. 如果影响数据库，必须同步迁移脚本、PO、Mapper、测试。
9. 如果影响认证和权限，必须同时检查前端体验和后端强校验。
10. 输出总结时说明改了什么、如何验证、还有什么风险。

## 前端目录模板

```text
frontend/
  config/
    routes
    proxy
  src/
    app
    access
    requestErrorConfig
    services/
      {domain}.ts
      common.ts
    pages/
      {domain}/
        {Page}/index.tsx
        components/
    components/
    utils/
    locales/
```

## 反模式清单

应避免：

- Controller 里写大量业务 if/else。
- 前端页面复制后端状态机。
- Domain model 只是 getter/setter 数据袋。
- Application service 同时做事务、SQL、HTTP、状态判断。
- 把同一业务对象的多个 command / query 操作塞进一个聚合式 `XxxExecutor`，而不是按操作拆成独立 executor。
- Infrastructure 对象泄漏到接口层。
- DTO、VO、PO 混用。
- 已经明确可由 MapStruct 表达的对象转换仍手写 `new` / `builder` / `setXxx` 样板代码，而不是定义 `@Mapper` converter。
- 在 client 模块中定义 HTTP Request / Response / VO、Domain Model 或 PO。
- 创建 / 更新接口直接复用资源 Response VO 作为请求体，导致客户端在 OpenAPI 文档中看到或误传只读字段、服务端生成字段。
- Request VO 暴露当前用例不允许客户端写入的字段，或 converter 将请求体无脑透传到 Command。
- HTTP 接口缺少 OpenAPI 注解，或注解中的路径、方法、请求体、响应体与真实代码不一致。
- `@Operation.description` 只写 HTTP 方法和路径，没有描述接口功能、业务行为、关键约束或副作用。
- 请求体/响应体 VO 没有 `@Schema` 字段说明，导致生成的接口文档无法理解字段含义、示例、必填性或只读属性。
- 在 HTTP 请求体 Request VO 上标注 `@NotBlank`、`@NotNull`、`@Size`、`@Valid` 等 validation 注解，而不是把校验放到 Command / Query。
- public 方法缺少 Javadoc；interface 方法没有完整 Javadoc；实现接口的方法重复粘贴接口文档而不是使用 `{@inheritDoc}`。
- 没有错误码，只返回字符串错误消息。
- 写接口不做权限校验。
- 更新接口不带版本号。
- 查询不处理软删除。
- 在已启用 MyBatis-Plus 逻辑删除自动条件的 PO 查询中，又手动追加 `.eq(XxxPO::getIsDeleted, 0)` 或 `is_deleted = 0`，导致 SQL 出现重复逻辑删除条件。
- 复杂查询无分页上限。
- 分页查询返回裸 `PageableDTO`、裸 `Map`、未设置泛型，或重复定义分页响应结构。
- 前端组件里硬编码后端地址。
- 新增配置时提交真实密钥。
- 修改接口后不同步前端类型。
- 改数据库后不同步迁移脚本。
- 不运行任何验证就结束任务。

## 一句话总结

好的工程代码应该让新功能沿着固定路径自然落位：

```text
业务意图 → 用例 → 领域规则 → 契约 → 适配器 → 持久化 → 页面 → 测试 → 交付
```

只要持续保持清晰边界、稳定契约、集中转换、可测试规则和可验证交付，新项目和新功能就能在复杂度增长时仍然保持可维护。
