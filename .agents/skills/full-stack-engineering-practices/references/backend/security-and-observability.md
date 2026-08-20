# 安全、错误与可观测性规范

> 从仓库根目录 `coding-standards.md` 提取；源文档是最终依据。

## 认证、授权与安全规范

### 认证

推荐：

- 企业应用优先使用标准 OIDC / OAuth2 / SSO。
- SPA 使用 Authorization Code + PKCE。
- 后端作为 Resource Server 校验 token。
- 内部系统调用使用明确的服务身份。

规则：

- 不在代码中硬编码 token、密码、私钥。
- token 存储和刷新策略必须统一。
- 登录态失效统一跳转登录。
- 用户身份由认证上下文获得，不由请求 body 传入。

### 授权

权限应分层：

- 前端：控制菜单、按钮、路由可见性。
- 后端：强制校验接口访问权限。
- 领域 / 应用层：校验业务归属、操作者是否允许执行该业务动作。

规则：

- 角色码或权限码使用稳定常量。
- 高危操作必须后端校验。
- 不能只靠前端隐藏按钮。
- 审计日志记录操作者和关键动作。

### 配置与密钥

- 所有环境差异通过配置或环境变量注入。
- 不提交真实密钥、个人账号密码、生产连接串。
- 默认配置只能用于本地开发。
- CI/CD 中使用 secret manager 或受保护变量。
- 文档中的示例密钥必须明显标注为示例。
- 调用外部 HTTP 接口必须使用 Spring HTTP Interface，即使用 `@HttpExchange`、`@GetExchange`、`@PostExchange` 等注解标注 interface，并通过 Spring `HttpServiceProxyFactory` 创建代理；禁止在业务代码中直接使用 OkHttp、Apache HttpClient、JDK `HttpClient`、`RestTemplate` 或手写 HTTP 请求样板调用外部服务。
- 外部 HTTP interface 的 API Key、Token、Base URL、超时等必须由服务端配置注入；密钥只能作为请求头或认证配置在服务端使用，不得返回给前端、写入日志或进入 DTO / VO。

## 错误处理与可观测性

### 后端错误处理

推荐统一错误响应：

```text
success: false
errorCode: string | number
errorMessage: string
showType?: number
data?: object
```

规则：

- 业务错误和系统错误区分处理。
- 业务错误可预期，返回稳定错误码。
- 系统错误记录日志，不暴露敏感堆栈。
- 参数校验错误返回可读信息。

### 前端错误处理

- 统一 request error handler。
- 401 统一清理登录态并跳转。
- 业务错误按 showType 展示 message / notification。
- 页面不重复实现通用错误处理。

### 日志与监控

- 关键业务动作记录 info 日志。
- 异常记录 error 日志并包含上下文 ID。
- 不打印密码、token、身份证、个人隐私等敏感信息。
- 暴露健康检查和指标端点。
- 对外部依赖调用记录耗时和失败情况。
