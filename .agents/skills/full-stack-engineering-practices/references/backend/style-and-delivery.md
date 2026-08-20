# 后端代码风格与交付规范

> 从仓库根目录 `coding-standards.md` 提取；仅省略前端专属小节，源文档是最终依据。

## 目录

- Java、SQL、文档与注释
- 新项目启动清单
- 后端开发、联调和完成清单
- Coding Agent 工作准则
- 后端目录与功能落地模板
- 反模式清单

## 代码风格规范

### Java / 后端

- 使用构造器注入，避免字段注入。
- 方法保持短小，一个方法只做一层抽象。
- 复杂判断提取成有业务语义的方法。
- 集合返回空集合而不是 null。
- Optional 只用于返回值或局部表达，不滥用于字段。
- 异常要有明确业务语义。
- 避免在 application 层写大量数据转换样板，使用 converter。
- DTO / VO / Command / Query / PO / Domain 等对象之间的转换必须优先使用 MapStruct 实现；`converter` 默认定义为 `@Mapper(componentModel = "spring")` 接口，字段名不一致时通过 `@Mapping` 显式声明，禁止手写大段 getter/setter / builder 式样板映射。只有当映射包含 MapStruct 难以表达的复杂上下文、循环依赖规避或框架限制时，才允许补充少量 `default` / 辅助方法，并在代码注释中说明原因。
- 避免在 domain 中引入框架注解。

Javadoc 规则：

- 每个 `public` 方法都必须编写 Javadoc。
- interface 中定义的方法必须编写完整 Javadoc，说明方法用途、参数、返回值和可能的业务异常。
- 实现 interface 的方法不重复完整说明，使用 `{@inheritDoc}` 继承接口文档即可。
- 如果实现方法相对接口契约有额外约束或副作用，可以在 `{@inheritDoc}` 后补充说明。
- 非接口的 public 方法，例如 Controller handler、executor 入口、工具类公开方法，也必须编写 Javadoc。
- Javadoc 应解释方法的业务语义和契约，不要只重复方法名。

推荐示例：

```java
public interface CourseService {

  /**
   * 创建课程。
   *
   * @param command 创建课程命令，包含课程名称、分类和操作者
   * @return 新创建课程的 ID
   */
  Long createCourse(CourseCreateCommand command);
}

public class CourseServiceImpl implements CourseService {

  /**
   * {@inheritDoc}
   */
  @Override
  public Long createCourse(CourseCreateCommand command) {
    // ...
  }
}
```

### SQL

- SQL 格式清晰，字段显式列出。
- 动态 SQL 处理 null 和空集合。
- 排序字段白名单。
- 大查询关注索引和分页。
- 删除优先软删除，物理删除需有明确理由。

### 文档与注释

注释用于解释“为什么”，不是重复“做什么”。

应写文档的场景：

- 新模块架构决策。
## 新项目启动清单

启动新项目时建议按顺序完成：

- [ ] 明确业务域、用户角色、核心流程。
- [ ] 设计模块分层和依赖方向。
- [ ] 定义统一错误响应、分页结构、认证方式。
- [ ] 定义代码目录规范和命名规范。
- [ ] 定义领域模型、状态机、错误码。
- [ ] 定义 API 契约和前端 service 类型。
- [ ] 设计数据库通用字段、软删除、乐观锁策略。
- [ ] 配置 lint、format、test、build。
- [ ] 建立本地开发环境和 docker compose。
- [ ] 建立 CI/CD 验证流程。
- [ ] 编写 README 和 coding guidelines。

## 新功能开发清单

### 开发前

- [ ] 明确业务目标和非目标。
- [ ] 找到所属业务域。
- [ ] 确认是否新增状态、枚举、角色、权限。
- [ ] 确认是否需要数据库变更。
- [ ] 确认 API 契约与前端页面影响。
- [ ] 阅读同类功能实现，复用现有模式。

### 后端开发

- [ ] 新增 / 修改 domain model、value object、error code。
- [ ] 新增 / 修改 Command、Query、DTO。
- [ ] 新增 / 修改 executor。
- [ ] 所有新增 / 修改的 Command Executor、Query Executor 都有对应单体测试。
- [ ] application service 只做事务和委托。
- [ ] infrastructure 实现 gateway 和数据转换。
- [ ] adapter 实现 Controller、VO、converter。
- [ ] 为所有新增或修改的 public 方法补充 Javadoc；interface 方法写完整 Javadoc，implement 接口的方法使用 `{@inheritDoc}`。
- [ ] 逐个检查新增或修改的 Java 单体测试：每个 `@Test` 方法前必须有专属 Javadoc，明确场景、核心断言，异常路径还必须写明预期异常；不得以类级注释、普通 `//` 注释或方法名代替。
- [ ] 每个 Controller 类和 HTTP handler 方法补充 OpenAPI 注解，例如 `@Tag`、`@Operation`，复杂参数和响应按需补充 `@Parameter`、`@ApiResponse`、`@Schema`。
- [ ] 每个 adapter VO 的类和字段补充 `@Schema`，请求体/响应体属性说明、示例、只读/只写、必填性和枚举范围清晰可生成文档。
- [ ] `@RequestBody` 对应的 Request VO 不使用 Bean Validation 注解；字段校验统一落在 Command / Query，并确保 Controller 在转换前不会因空值触发 NPE。
- [ ] 添加权限注解和操作者传递。
- [ ] 添加数据库 changelog / SQL。
- [ ] 添加测试。

### 联调前检查

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

### 完成前

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

## 可复用架构模板

### 后端目录模板

```text
backend/
  client/
    api/
    dto/
      command/
      query/
      data/
  domain/
    {aggregate}/
      model/
      gateway/
      ErrorCode
  application/
    {aggregate}/
      service/
      executor/
        command/
        query/
      converter/
  infrastructure/
    {aggregate}/
      gateway/
      database/
        dataobject/
        mapper/
      converter/
  adapter/
    web/
      {aggregate}/
        controller/
        vo/
        converter/
  bootstrap/
    resources/
```

### 单个功能落地模板

```text
1. Domain
   - Model
   - Value Object
   - ErrorCode
   - Gateway Interface

2. Client Contract
   - Command
   - Query
   - DTO
   - Service API

3. Application
   - Executor
   - ServiceImpl
   - DTO Converter

4. Infrastructure
   - PO / Doc
   - Mapper / Repository
   - GatewayImpl
   - PO Converter
   - DB migration

5. Adapter
   - Request / VO
   - Controller
   - VO Converter
   - Permission

6. Frontend
   - service type and function
   - route
   - page / component
   - access rule
   - tests
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
