# 通用编码规范指导

> 本文档从既有项目的编码实践中提炼的通用规范，用于指导新项目启动、新功能开发、重构和 coding agent 协作。  
> 它不是某个仓库的目录说明，而是一套可迁移的工程化开发准则。

## 1. 核心原则

### 1.1 先分层，再编码

任何新项目或新功能都应先明确边界，再落代码：

- 对外接口边界：HTTP API、RPC API、SDK API、前端 service API。
- 应用用例边界：一个业务动作对应一个明确用例。
- 领域模型边界：核心业务规则、状态、约束不应散落在 Controller 或页面里。
- 基础设施边界：数据库、缓存、消息、文件存储、第三方系统应通过接口隔离。
- 展示边界：前端页面只负责交互、状态展示和调用服务，不承载后端业务规则。

目标是让代码具备：

- 可理解性：从入口能追踪到用例、领域、持久化。
- 可测试性：核心规则可以脱离 Web 和数据库测试。
- 可替换性：数据库、认证、对象存储、外部系统可以替换适配。
- 可演进性：新增功能遵循同样路径，不破坏已有边界。

### 1.2 业务规则优先于技术实现

开发时优先回答：

1. 这个功能属于哪个业务域？
2. 它改变哪个业务对象的状态？
3. 有哪些不变量和状态流转限制？
4. 谁有权限执行？
5. 是否需要审计、版本、幂等、并发控制？
6. 对外契约是什么？

不要先从数据库表、Controller 或页面按钮开始设计。

### 1.3 小步提交、可验证交付

每次变更应满足：

- 只解决一个清晰目标。
- 修改范围可解释。
- 有最小验证方式。
- 不引入无关格式化。
- 不跨层偷懒调用。
- 不把临时代码、mock、测试凭据带入生产路径。

## 2. 推荐后端架构

### 2.1 分层模型

推荐采用类似六边形架构 / DDD 的分层方式：

```text
adapter / interfaces
  → application
  → domain
  ← infrastructure
```

更完整的模块职责可抽象为：

| 层 / 模块 | 职责 | 不应包含 |
|---|---|---|
| client / api-contract | App Service 对外契约，以及 App Service 使用的 DTO、Command、Query 等对象 | Controller、HTTP 请求/响应体、VO、数据库对象、领域模型、业务实现 |
| domain | 领域模型、值对象、领域服务、网关接口、错误码 | Web 注解、SQL、ORM、外部系统 SDK |
| application | 用例编排、事务边界、权限外的业务流程控制 | HTTP 细节、数据库 SQL、页面逻辑 |
| infrastructure | 网关实现、数据库、缓存、消息、对象存储、第三方系统适配 | Controller、前端展示逻辑 |
| adapter / interfaces | REST/RPC Controller、VO、请求转换、安全入口；HTTP 请求体和响应体只能定义在该层的 `vo` 命名空间 | 核心业务规则、持久化细节 |
| bootstrap / start | 应用启动、配置装配、运行时配置 | 业务逻辑 |

### 2.2 依赖方向

推荐依赖方向：

```text
adapter → application → domain
application → client/api-contract
infrastructure → domain
bootstrap → adapter/application/infrastructure
```

约束：

- `domain` 不依赖 `application`、`adapter`、`infrastructure`。
- `application` 不依赖 Web Controller 或 ORM PO。
- `adapter` 不直接访问数据库。
- `infrastructure` 通过实现 domain gateway 被 application 使用。
- `client` 模块只定义 App Service 使用的对象，包括 Service API、Command、Query、DTO；不得定义 HTTP Request / Response / VO、Domain Model、PO / Entity / Doc。
- 对外契约 DTO 不要混入 HTTP 协议字段、数据库字段或前端展示字段。
- HTTP 接口的请求体、响应体、Request、Response、VO 只能定义在 `adapter` 模块的 `vo` 命名空间中，不能定义在 `client`、`application`、`domain` 或 `infrastructure` 中。

### 2.3 请求处理链路

推荐链路：

```text
HTTP/RPC Request
  → Controller / Adapter
  → Request/VO 转 Command/Query
  → Application Service
  → Use Case Executor / Handler
  → Domain Model / Domain Service
  → Gateway Interface
  → Infrastructure Gateway Implementation
  → Database / Cache / External System
```

每层职责：

- Controller：协议适配、认证信息读取、参数转换、协议级校验。
- Application Service：事务边界、用例入口、委托 executor。
- Executor / Handler：单个用例的业务编排。
- Domain Model：业务不变量、状态机、领域行为。
- Gateway Interface：领域需要的持久化或外部能力。
- Infrastructure：技术实现与数据转换。

其中“协议级校验”只包含 Web 边界必须处理的检查，例如路径参数与请求体资源名一致性、必填请求头读取、`updateMask` 解析、HTTP 协议格式约束等；不要在 `@RequestBody` 对应的 Request VO 上堆放 Bean Validation 注解。

## 3. 用例与 CQRS 规范

### 3.1 一个用例一个执行器

复杂系统建议把每个业务动作拆成独立执行器：

```text
executor/command/CreateOrderExecutor
executor/command/SubmitEvaluationExecutor
executor/query/QueryOrderByIdExecutor
executor/query/ListAvailableSessionsExecutor
```

规则：

- 写操作放 `command`。
- 读操作放 `query`。
- 一个 executor 只处理一个业务意图。
- 不要创建聚合式 `XxxExecutor` 同时承载 `create`、`get`、`list`、`update`、`delete`、`submit` 等多个操作；每个操作必须拆成独立 executor，并放入 `executor/command` 或 `executor/query` 子目录。
- executor 名称使用“业务对象 + 动作 + Executor”。
- 每个 Command Executor 和 Query Executor 类都必须编写类级 Javadoc，说明该 executor 实现的业务功能；说明应聚焦业务动作、处理对象和关键结果，不能只保留空模板、作者信息或泛泛的“处理 execute”。
- application service 只负责事务和委托，不堆积业务逻辑。

### 3.2 Command / Query 设计

Command 用于表达“我要改变系统状态”：

```text
CreateCourseCommand
PublishCourseCommand
UpdateSessionCommand
SubmitEvaluationCommand
```

Query 用于表达“我要查询数据”：

```text
CourseQuery
SessionQuery
UserSearchQuery
```

规范：

- Command 必须包含执行动作所需的最小字段。
- 修改类 Command 应包含业务对象 ID、版本号、操作者。
- Query 应表达过滤条件、排序、分页，不混入写操作字段。
- Command / Query 应承载字段级 Bean Validation 约束；跨字段、状态、资源存在性等业务规则在 application / domain 中显式校验。HTTP Request VO 不承载 Bean Validation 注解。
- 不要把 HTTP Request 直接传入 application 层。

### 3.2.1 Validation 职责边界

后端校验按“协议契约、应用契约、业务规则”分层处理，避免同一个规则散落在 Controller、Executor 和领域对象中重复实现。

**1. HTTP Request VO 只描述 HTTP 契约**

- `adapter` 层的 Request VO 只表达 HTTP JSON 入参结构和 OpenAPI 文档。
- Request VO 不使用 `@NotBlank`、`@NotNull`、`@Size`、`@Valid` 等 `jakarta.validation` / `javax.validation` 注解。
- 字段必填性、长度、枚举、嵌套对象等校验应放在转换后的 Command / Query 上。
- Request VO 可以使用 `@Schema(requiredMode = REQUIRED)`、`example`、`description` 等 OpenAPI 注解描述接口契约，但这些注解不等同于运行时校验。
- Controller 不在 `@RequestBody` 参数上添加 `@Valid` 来触发 Request VO 校验。

**2. App Service API 是 Bean Validation 入口**

- `client` 模块的 App Service 接口使用 `@Validated` 标注类或接口。
- App Service 方法参数使用 `@NotNull @Valid` 标注 Command / Query，例如：

```java
@Validated
public interface LessonKnowledgeService {
  LessonEntryDTO createLessonEntry(@NotNull @Valid LessonEntryCreateCommand command);
}
```

- Command / Query 字段使用 Bean Validation 注解表达字段级约束，例如 `@NotBlank`、`@NotNull`、`@Size`、`@Min`、`@Max`。
- Controller 将 Request VO 转换为 Command / Query 后调用 App Service，由 Spring 方法级 validation 在 App Service 边界统一触发校验。
- Service Facade 实现类只负责事务和委托，不重复手写字段必填判断。

**3. Executor 只处理用例业务规则**

- Executor 不重复实现 Command / Query 上已有的 JSR-303 字段校验，例如不再手写 `StringUtils.isBlank(command.getProjectId())` 来兜底 `@NotBlank`。
- Executor 应显式校验 Bean Validation 无法表达或不适合表达的业务规则，例如资源名解析、`updateMask` 白名单、状态流转、版本一致性、资源存在性、操作者角色、跨字段业务约束。
- 业务显式校验应抛稳定业务错误码；字段级 Bean Validation 失败由统一异常处理转换为接口错误响应。

**4. 测试职责**

- 不在 client 模块为 Command / Query 的 JSR-303 注解编写独立 `Validator` 单测。
- Executor 单测不验证 JSR-303 注解是否生效，只覆盖 Executor 内部显式业务校验、转换、gateway 调用和返回结果。
- 如果需要证明方法级 Bean Validation 生效，应通过 Spring 集成测试覆盖 App Service 边界，而不是在 Executor 测试中重复实现 validation 框架行为。

### 3.3 事务边界

事务应放在 application service 层：

- 写操作：开启事务，异常回滚。
- 查询操作：只读事务。
- 跨聚合写操作：明确一致性要求，必要时使用事件或补偿。
- 外部系统调用：避免长事务包裹远程调用；必要时拆分流程。

## 4. 领域模型规范

### 4.1 领域对象承载核心规则

领域模型不只是数据容器，应承载：

- 状态流转。
- 不变量检查。
- 核心计算逻辑。
- 业务语义明确的方法。

示例抽象：

```text
course.publish()
session.start()
evaluation.submit(scores, comments)
order.cancel(reason)
```

不要把这些规则散落在：

- Controller if/else。
- 前端按钮逻辑。
- SQL update 语句。
- application service 的过程式脚本。

### 4.2 创建与状态流转

推荐：

- 构造器私有或受保护。
- 使用静态工厂表达创建语义。
- 状态迁移使用领域方法。
- 非法迁移抛业务异常。

示例原则：

```text
create() → DRAFT
publish(): DRAFT → PUBLISHED
start(): PUBLISHED → IN_PROGRESS
complete(): IN_PROGRESS → COMPLETED
archive(): COMPLETED → ARCHIVED
```

规范：

- 状态枚举应同时有稳定的外部 code 和稳定的数据库 value，不要只依赖展示文案或枚举声明顺序。
- Java domain enum 的常量名作为外部 code，使用 `UPPER_SNAKE_CASE`，并提供 `fromCode(String)`；HTTP API、DTO、前端类型和接口文档均使用该 code。
- Java domain enum 必须显式定义 `Integer value`，提供 `getValue()` 和 `fromValue(Integer)`；数据库枚举字段统一存储该 value，禁止直接存储 `Enum.name()` 或 `ordinal()`。
- 持久化对象中的枚举字段使用 `Integer`；infra converter 写库时使用 `getValue()`，读库时使用 `fromValue()`，查询条件也必须转换为 value 后再访问数据库。
- 新增、删除、调整状态或业务枚举时，必须同步 domain enum、转换器、数据库字段注释、接口文档、前端类型和测试。已发布 value 不得复用或改义。
- 每个状态迁移都应有测试覆盖。

### 4.3 值对象

当一组字段有共同业务含义时，应抽成值对象：

- 时间区间：`startTime` + `endTime`
- 金额：`amount` + `currency`
- 用户引用：`userId` + `name`
- 文件引用：`fileId` + `fileName` + `url`

值对象应：

- 表达业务语义。
- 在创建时校验自身合法性。
- 尽量不可变。
- 避免被当成任意 Map 使用。

### 4.4 错误码

推荐按业务域维护错误码：

```text
CourseErrorCode
SessionErrorCode
EvaluationErrorCode
UserErrorCode
```

规则：

- 业务异常必须带稳定错误码。
- 错误码不应直接使用临时字符串。
- 错误消息可以国际化，但错误码应稳定。
- 前端不应依赖错误消息文本做逻辑判断。

## 5. 数据模型与持久化规范

### 5.1 区分领域模型与持久化对象

不要把 ORM 对象当领域模型使用。推荐区分：

| 类型 | 用途 |
|---|---|
| Domain Model | 业务规则与领域行为 |
| DTO | App Service 契约中的数据传输对象，只定义在 client / application 边界需要的位置 |
| VO / Request | Web 层入参与出参 |
| PO / Entity | 数据库持久化 |
| Doc | 文档数据库持久化 |

规则：

- Controller 不直接返回 PO。
- Controller 的 `@RequestBody`、HTTP response body 只能使用 `adapter` 模块 `vo` 命名空间下的类型。
- HTTP Request / Response / VO 不得放入 `client`、`application`、`domain`、`infrastructure`，这些层只能使用各自边界内的 Command、Query、DTO、Domain Model、PO / Doc。
- 创建 / 更新接口必须显式定义专用 Request VO，例如 `CreateXxxRequest`、`UpdateXxxRequest`，即使请求字段是资源响应 VO 的子集，也不要直接复用资源响应 VO 作为请求体。
- 专用 Request VO 只暴露当前用例允许客户端写入的字段，避免客户端在接口文档中看到或误传 `id`、`name`、`createTime`、`updateTime`、服务端统计字段等只读或服务端生成字段。
- Response VO 用于表达服务端返回的资源表示；Request VO 用于表达客户端提交的写入意图。二者即使字段相似，也应按语义隔离。
- Request VO 只描述 HTTP 契约和 OpenAPI 文档，不使用 `jakarta.validation` / `javax.validation` 注解；字段必填性、长度、枚举、嵌套对象校验统一放在转换后的 Command / Query 中。
- `client` 模块中的 DTO、Command、Query 只能服务于 App Service API，不得为了复用而承载 HTTP 表单结构、页面展示结构、数据库结构或领域行为。
- Domain 不依赖 PO。
- Infrastructure 负责 Domain ↔ PO / Doc 转换。
- 字段名不一致时显式映射，不要依赖隐式猜测。

### 5.2 数据库通用字段

业务表建议包含：

- `id`：主键。
- `revision` 或 `version`：乐观锁版本。
- `is_deleted`：软删除标记。
- `created_by`、`created_time`：创建审计。
- `updated_by`、`updated_time`：更新审计。

规则：

- 查询默认过滤软删除数据。
- 如果项目使用 MyBatis-Plus 逻辑删除（例如 PO 继承的基础实体已通过 `@TableLogic` 或全局配置处理 `is_deleted`），普通 `selectById`、`selectOne`、`selectList`、`selectCount` 等由 MyBatis-Plus 生成的查询会自动追加逻辑删除条件；QueryWrapper / LambdaQueryWrapper 中不要再手动添加 `.eq(XxxPO::getIsDeleted, 0)` 或 SQL 片段 `is_deleted = 0`，否则会生成重复条件，例如 `WHERE is_deleted=0 AND (is_deleted = ? ...)`。
- 只有在自定义 XML SQL、原生 SQL、跨表 join、统计历史删除数据等 MyBatis-Plus 逻辑删除插件无法自动覆盖或明确需要绕过默认行为的场景，才允许显式处理 `is_deleted`；这类 SQL 必须在代码注释或 mapper 方法 Javadoc 中说明原因。
- 更新必须考虑乐观锁。
- 操作者来自认证上下文，不来自前端 body。
- 批量操作也要维护审计字段。
- 数据库字段禁止创建外键约束。表之间通过业务 ID 或关联 ID 建立逻辑关系，关联字段应按查询场景建立必要索引，并由 application / domain 层负责关联数据的存在性与一致性校验。

### 5.3 SQL 与 Mapper

推荐：

- 简单 CRUD 可用 ORM / Mapper 方法。
- 复杂查询放 XML 或清晰的 Query Builder。
- 多表查询必须明确分页策略，避免 join 后分页错误。
- 模糊查询、动态条件、集合条件要做空值处理。
- 重要查询要考虑索引。

注意事项：

- 不拼接未校验的用户输入，防止 SQL 注入。
- `IN` 条件集合为空时应返回空结果或跳过条件，不能生成非法 SQL。
- 分页查询应同时提供 count 和 data query。
- 复杂 result map 要写清楚一对多关系。
- 使用 ORM / QueryWrapper 生成 SQL 时，要先确认框架是否已自动追加租户、逻辑删除、数据权限等全局条件，避免手动重复添加导致 SQL 冗余、参数错位或执行计划异常。

#### 5.3.1 列表查询中的关联数据回填

列表查询返回多条业务记录时，如果每条记录都需要补充用户、分类、标签、组织、统计值等关联展示数据，禁止在循环中按单条记录逐次查询关联对象，避免形成 N+1 查询。

推荐处理流程：

1. 先完成主资源分页查询，拿到当前页主记录列表。
2. 从当前页主记录中提取关联键集合，例如 `createdBy`、`categoryId`、`ownerId`，并去重、过滤空值。
3. 使用批量查询接口一次取回关联对象，例如按 `Set<String> userIds` 查询用户信息。
4. 将批量结果转换为 `Map<关联键, 关联对象>`。
5. 在 DTO / VO 转换阶段按 map 回填每条记录的展示字段或引用对象。
6. 对缺失的关联对象提供稳定兜底，例如保留原账号 ID、资源名或显示 `-`，列表接口不得因单个关联对象缺失而整体失败。

示例：

```java
List<LessonEntry> entries = gateway.query(criteria, orderBy, offset, size);
Set<String> userIds = entries.stream()
    .map(LessonEntry::getCreatedBy)
    .filter(StringUtils::isNotBlank)
    .collect(Collectors.toSet());
Map<String, User> usersByUserId = userGateway.getUsersByUserIds(userIds);

return entries.stream()
    .map(entry -> converter.fromModel(entry, usersByUserId))
    .toList();
```

测试要求：

- 列表查询执行器测试应覆盖“多条记录、重复关联键”的场景，验证批量查询只调用一次，并且每条记录按关联键正确回填。
- 转换器测试应覆盖关联对象存在、关联对象缺失、关联键为空的兜底行为。
- 如果已有批量查询能力，应优先复用；如果没有，应在 application / gateway 层补充明确的批量查询方法，不让前端通过逐条请求承担回填。

### 5.4 Liquibase 数据库迁移

所有数据库结构和基础数据变更必须通过 Liquibase 管理，禁止只修改数据库、PO 或 Mapper 而不提供迁移脚本。

#### 5.4.1 版本与目录组织

- 每次迁移必须归属一个明确的发布版本，例如 `release-1.1.0`；同一需求产生的全部 SQL 都必须落入该版本目录，不得散落到旧版本或其他发布版本中。
- 版本入口采用两级 changelog：根 `master.xml` include 顶层 `release-x.y.z.xml`，顶层版本文件再 include `release-x.y.z/release-x.y.z.xml`，最后由版本文件 include 具体 SQL。
- 新版本只能追加到 changelog 链路中，不得把新版本 SQL include 到历史版本入口。
- 版本内 SQL 统一放在 `db/changelog/release-x.y.z/schema/` 下，并在该版本的 `release-x.y.z.xml` 中显式 include。
- include 顺序必须满足数据库依赖：建表先于对应的 `ALTER TABLE`、索引或初始化数据；存在跨表初始化数据时，被引用数据应先写入。

目录示例：

```text
db/changelog/
├── master.xml
├── release-1.1.0.xml
└── release-1.1.0/
    ├── release-1.1.0.xml
    └── schema/
        ├── tb_lesson_entry_revision.sql
        ├── tb_lesson_review.sql
        └── tb_lesson_review_assignment.sql
```

#### 5.4.2 SQL 文件拆分与命名

- 每个表的变更对应一个 SQL 文件；同一发布版本内，同一张表的建表、加列、索引、约束等变更集中在该表文件中。
- SQL 文件名必须直接使用表名并采用小写下划线形式，例如 `tb_lesson_review.sql`。
- 文件名不得添加动作前缀或描述性后缀，例如不得使用 `alter_tb_lesson_review.sql`、`create_lesson_review_table.sql`。
- 一个 SQL 文件只允许修改其文件名对应的主表，不得在同一文件中顺带修改其他表。

#### 5.4.3 changeset 规范

- SQL 使用 Liquibase formatted SQL，文件首行统一为 `--liquibase formatted sql`。
- changeset 的 author 使用项目名，id 只使用发布版本，统一格式为：

```sql
--changeset training-mgmt:release-1.1.0 dbms:h2,mysql
```

- changeset id 不得包含表名、SQL 文件名或动作描述，例如不得使用 `training-mgmt:release-1.1.0-alter-tb-lesson-review-assignment`。
- 同一版本不同表文件允许使用相同的 author 和 id；Liquibase 通过 changelog 文件路径、author 和 id 共同标识 changeset。因此文件一旦在共享环境执行，不得重命名、移动或修改已有 changeset，应通过新发布版本追加迁移。
- 必须显式声明目标 `dbms`。SQL 同时支持多个目标数据库时，应在本地或测试环境验证各方言均可执行；无法兼容时按数据库方言拆分 changeset，禁止依赖未声明的隐式兼容。
- 每个 changeset 必须提供准确、可执行的 `--rollback`。建表对应删表；加列和索引的 rollback 应按依赖逆序删除。
- 使用 `--comment` 简要说明迁移目的，描述业务意图，不重复文件名。

#### 5.4.4 迁移设计与审查

- 新增表应同步设计主键、业务唯一约束、必要索引、逻辑关联字段、乐观锁、逻辑删除和审计字段，并与项目通用字段规范保持一致；禁止创建外键约束。
- 索引和约束必须显式命名，名称应稳定且能表达表内用途，避免数据库自动生成不可预测名称。
- 新增非空字段必须评估历史数据；需要回填时，应先提供兼容默认值或分阶段迁移，禁止直接导致存量数据迁移失败。
- 删除列、修改类型、收紧约束等破坏性变更必须说明数据迁移和回滚策略，并验证应用版本的前后向兼容窗口。
- 提交前至少检查：changelog include 链完整、版本归属正确、每表一文件、文件名等于表名、changeset 格式正确、执行顺序合理、rollback 可用、目标数据库方言兼容。

### 5.5 多存储一致性

当同时使用 MySQL、MongoDB、Redis、对象存储时：

- 明确哪个存储是主数据源。
- 明确快照、缓存、索引数据的更新时机。
- 对文件上传、对象存储写入要考虑失败清理。
- 对缓存使用要有失效策略。
- 对发布版本、历史版本建议使用不可变快照。

## 6. 接口设计规范

### 6.1 REST API

接口设计优先采用资源导向风格：API 以资源为核心，而不是以操作为核心。优先使用标准方法 `List`、`Get`、`Create`、`Update`、`Delete`；只有当业务动作无法表达为标准资源操作时，才使用自定义方法。

资源与路径命名规则：

- 资源集合使用复数名词，例如 `lessonEntries`、`lessonCategories`、`actionItems`。
- 路径中的资源集合使用 `lowerCamelCase`。
- JSON 字段使用 `lowerCamelCase`。
- 枚举值使用 `UPPER_SNAKE_CASE`。
- 时间字段使用 RFC 3339 / ISO 8601 格式，例如 `2026-06-01T10:00:00+08:00`。
- 资源对象建议统一包含稳定资源名字段 `name`，格式如 `lessonEntries/1001`、`lessonCategories/1001`。
- `name` 用于跨接口引用资源；数据库主键、内部 ID 不应成为前端必须理解的唯一资源语义。

标准方法路径风格：

```text
GET    /resources                         # List
GET    /{name=resources/*}                # Get
POST   /resources                         # Create
PATCH  /{resource.name=resources/*}       # Update
DELETE /{name=resources/*}                # Delete
POST   /{name=resources/*}:publish        # Custom method
POST   /{name=resources/*}:archive        # Custom method
```

标准方法说明：

| 标准方法 | HTTP 方法 | 说明 |
|---|---|---|
| List | `GET /resources` | 查询资源列表，支持分页、过滤、排序和视图参数 |
| Get | `GET /{name=resources/*}` | 查询单个资源 |
| Create | `POST /resources` | 创建资源 |
| Update | `PATCH /{resource.name=resources/*}` | 更新资源，必须支持 `updateMask` |
| Delete | `DELETE /{name=resources/*}` | 删除资源；业务上优先逻辑删除 |

自定义方法规则：

- URL 中不要为标准 CRUD 操作使用动词路径，例如避免 `/submit`、`/approve`、`/reject`。
- 确实属于业务动作、状态迁移或非 CRUD 语义的操作，使用 Google 风格自定义方法：`POST /{name=resources/*}:verb`。
- 自定义方法的请求体按业务动作定义，例如审核通过可以使用 `{ "comment": "..." }`。
- 自定义方法仍应返回 adapter 层 VO 或明确的动作结果 VO，不返回 domain model、client DTO 或 PO。

规范：

- 名词表示资源，动词动作仅用于无法用标准方法表达的业务动作或状态迁移。
- 查询参数用于过滤、分页、排序。
- Request body 用于复杂创建 / 更新命令。
- API 前缀统一由网关、框架或路由配置处理，避免前后端重复。
- 响应结构应统一，包含业务错误码和错误消息。
- HTTP 接口暴露的请求体和响应体类型必须来自 adapter 层 `vo` 命名空间；Controller 负责将 VO 转换为 application 层 Command / Query / DTO，不允许直接暴露 application DTO、domain model 或 persistence PO。
- 创建 / 更新接口必须使用专用 Request VO 作为 `@RequestBody`；资源 Response VO 不作为写接口请求体，避免 OpenAPI 文档把只读字段展示给调用方。
- Request VO 转换到 Command 时仍需显式选择字段，不能把请求对象无脑透传到 application 层。
- `@RequestBody` 对应的 Request VO 不使用 `@NotBlank`、`@NotNull`、`@Size`、`@Valid` 等 Bean Validation 注解；这些校验统一标注在 Command / Query，由 application service 边界触发。
- 创建和更新接口的 HTTP JSON 请求体直接使用资源对象或动作请求对象，不要额外包一层资源字段；例如使用 `{ "displayName": "..." }`，不要使用 `{ "resource": { ... } }`。
- 创建接口不允许信任客户端传入的 `name`、`id`、`status`、`createTime`、`updateTime`、`revision`、`createdBy` 等服务端维护字段。

### 6.2 OpenAPI 注解

每个 HTTP 接口都必须使用 OpenAPI 注解，以便后续自动生成接口文档、前端类型和联调说明。

Controller 注解规则：

- 每个 Controller 类必须使用 `@Tag` 标注接口分组名称和说明。
- `@Tag.name` 应稳定、简洁，通常使用资源名或业务域名。
- `@Tag.description` 应说明该 Controller 管理的资源或能力。

接口方法注解规则：

- 每个公开 HTTP handler 方法必须使用 `@Operation`。
- `@Operation.summary` 用一句话说明接口用途。
- `@Operation.description` 必须准确描述接口功能、业务行为、关键约束和副作用，不能只写类似 `POST /api/xxx`、`GET /api/xxx` 的 HTTP 方法和路径。
- HTTP 方法和路径由 `@GetMapping`、`@PostMapping` 等映射注解表达；如确需在 `description` 中补充路径，也必须同时说明接口做什么、影响什么资源、支持哪些查询能力或状态迁移约束。
- 对复杂请求体、路径参数、查询参数、响应体，按项目需要补充 `@Parameter`、`@RequestBody`、`@ApiResponse`、`@Schema` 等注解。
- HTTP 请求体和响应体 VO 必须使用 `@Schema` 标注类和属性，确保生成的 OpenAPI 文档能够展示字段含义、必填性、示例值、只读/只写属性、枚举范围和格式约束。
- VO 类级别 `@Schema` 应说明该对象是请求体、响应体还是资源对象；字段级别 `@Schema` 应至少包含 `description`，关键字段补充 `example`、`requiredMode`、`accessMode`、`allowableValues`、`format`。
- 服务端生成或只读字段，例如 `id`、`name`、`createTime`、`updateTime`、`revision`，应使用 `accessMode = Schema.AccessMode.READ_ONLY` 或在描述中明确创建接口不会信任客户端传入值。
- 创建 / 更新请求必须使用专用 Request VO，并通过 `@Schema` 明确可写字段、必填性和示例；资源 Response VO 中的只读字段应通过 `@Schema(accessMode = READ_ONLY)` 标注。
- OpenAPI 注解描述必须与真实路径、HTTP 方法、请求体、响应体保持一致；修改接口时必须同步更新注解。
- 注解只描述 HTTP 契约，不承载业务逻辑；业务规则仍应在 domain / application 中实现。

推荐示例：

```java
@Tag(name = "LessonCategory", description = "Lessons Learned category APIs")
@RestController
public class LessonCategoryController {

  @Operation(summary = "查询分类", description = "分页查询 Lessons Learned 分类列表，支持过滤、排序和视图参数。")
  @GetMapping(path = "/lessonCategories", produces = MediaType.APPLICATION_JSON_VALUE)
  public Mono<PageableDTO<LessonCategory>> listLessonCategories() {
    // ...
  }
}
```

### 6.3 分页与排序

列表接口统一支持以下查询参数：

| 参数 | 说明 |
|---|---|
| `page` | 页码，从 1 开始，默认 1 |
| `size` | 每页大小，默认 20，建议最大 100 |
| `filter` | 过滤条件；具体可过滤字段必须有白名单。多个条件可使用 `AND` 连接，例如 `status = PUBLISHED AND lessonType = FAILURE` |
| `orderBy` | 排序条件，例如 `publishedAt desc, viewCount desc`；字段必须有白名单 |
| `view` | 返回视图，用于区分列表摘要、详情或其他投影视图 |

过滤与排序规则：

- `filter` 和 `orderBy` 是外部表达式，不能直接拼接 SQL。
- 每个列表接口必须声明可过滤字段白名单和可排序字段白名单。
- 不支持的过滤字段、操作符或排序字段应返回参数错误。
- 默认排序必须稳定，避免分页时数据重复或遗漏。
- `view` 只控制返回字段视图，不应绕过权限或返回敏感字段。

支持分页的查询接口必须统一返回 `PageableDTO<T>`，并设置明确的泛型返回类型，其中 `T` 必须是 adapter 层 `vo` 命名空间中的响应对象。

推荐 Controller 返回类型：

```text
Mono<PageableDTO<ResourceVO>>
```

推荐构造方式：

```text
PageableDTO.<ResourceVO>builder()
  .list(dtoPage.getList().stream().map(converter::fromDTO).toList())
  .pagination(dtoPage.getPagination())
  .build()
```

统一分页结构：

```text
list: T[]
pagination:
  page: number
  totalPage: number
  pageSize: number
  total: number
```

规则：

- 页码统一从 1 开始。
- 默认 pageSize 要有限制。
- 后端必须校验最大 pageSize。
- 排序字段不能直接信任前端，应做白名单。
- `pagination.page` 表示当前页码，`pagination.pageSize` 表示实际生效页大小，`pagination.total` 表示符合过滤条件的资源总数，`pagination.totalPage` 表示总页数。
- 不要在 Controller 中返回裸 `PageableDTO`、裸 `Map` 或自定义重复分页响应。
- application / client 层分页查询必须返回 `PageableDTO<DTO>`；adapter 层必须转换为 `PageableDTO<VO>` 后再作为 HTTP 响应体返回。
- 当响应对象只有列表数据和分页信息时，禁止新增 `ListXxxResponse`、`XxxPageResponse` 等自定义壳类型，应直接使用 `PageableDTO<T>`；只有需要承载列表和分页之外的额外业务字段时，才允许定义专用响应对象。

### 6.4 枚举与时间

枚举：

- 对外使用稳定 code，数据库使用稳定 value。
- 前端使用 TypeScript union type 或 enum 表达。
- 后端 domain enum 提供 `fromCode(String)`、`getValue()` 和 `fromValue(Integer)`。
- 数据库枚举字段使用 `TINYINT`/`INT` 存储 enum value；转换必须集中在 infra converter 和 gateway 查询条件中，禁止散落 `Enum.name()` 持久化逻辑。

时间：

- API 使用 ISO 8601 格式。
- 明确时区策略。
- 前端展示再做本地化格式化。
- 时间区间必须校验开始小于结束。

### 6.5 幂等与并发

写接口需要评估：

- 是否可能重复提交？
- 是否需要 idempotency key？
- 是否需要 revision / version 乐观锁？
- 是否需要唯一索引兜底？
- 是否需要分布式锁？

状态迁移接口尤其要校验当前状态和版本。

更新接口规则：

- 更新资源优先使用 `PATCH`，而不是用 `PUT` 覆盖整个资源。
- `PATCH` 请求必须携带 `updateMask`，明确需要更新的字段，例如 `displayName,description,enabled`。
- `updateMask` 字段必须白名单校验，只允许更新当前接口支持的可写字段。
- 资源响应对象必须返回 `revision`。
- 编辑类接口必须在请求体中携带当前资源的 `revision` 作为编辑冲突检查依据。
- 当请求体中的 `revision` 与服务端当前资源 `revision` 不一致时，应返回并发冲突错误。
- 已发布、归档或受状态约束保护的资源，不允许直接覆盖修改，应通过状态迁移、自定义方法、创建修订版本或受控流程完成。

### 6.6 错误处理状态

错误响应必须统一，并映射到稳定的错误状态。可参考 Google API 错误模型：

```json
{
  "error": {
    "code": 400,
    "message": "displayName is required",
    "status": "INVALID_ARGUMENT",
    "details": []
  }
}
```

如果项目已有统一业务错误结构，也应保留等价的稳定错误状态或错误码，不要只返回临时字符串消息。

常用错误状态：

| 状态 | 说明 |
|---|---|
| `INVALID_ARGUMENT` | 请求参数错误或业务校验失败 |
| `UNAUTHENTICATED` | 未认证 |
| `PERMISSION_DENIED` | 无权限 |
| `NOT_FOUND` | 资源不存在 |
| `FAILED_PRECONDITION` | 当前状态不允许执行该操作 |
| `ALREADY_EXISTS` | 资源已存在 |
| `ABORTED` | 并发冲突 |
| `INTERNAL` | 系统内部错误 |

## 7. 前端工程规范

### 7.1 前端分层

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

### 7.2 页面职责

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

### 7.3 API Service

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

### 7.4 权限与路由

前端权限用于提升体验，不是最终安全边界。

规则：

- 路由权限和按钮权限应使用统一 access 规则。
- 后端必须再次校验权限。
- 菜单文案走国际化或统一文案配置。
- 未授权页面、登录跳转、401 处理要统一。

### 7.5 表单与交互

- 表单字段名尽量与 API request 一致。
- 必填、长度、格式、时间区间在前端先校验。
- 提交成功后刷新数据或跳转要明确。
- 删除、归档、发布等危险操作需要确认。
- loading 状态防止重复提交。
- 错误消息使用统一错误处理，不在每个页面散落重复逻辑。

### 7.6 Ant Design Pro UI 设计

前端页面默认遵循 Ant Design Pro 的 UI 设计最佳实践，优先使用项目已有的 Pro Components 和 Ant Design 组件体系承载页面结构、查询、表格、详情、表单、统计和操作反馈。

规则：

- 页面外层优先使用 `PageContainer`，复杂表单使用 `ProForm`，数据列表使用 `ProTable`，信息分组使用 `ProCard` / `Card` / `Descriptions`，履历、流程、审计记录优先使用 `Timeline`。
- 查询项、分页、排序、表格操作、空状态、loading、modal、drawer、message 等交互应使用 Ant Design Pro / Ant Design 的内建能力，不重复造自定义控件。
- 布局优先使用 `Space`、`Flex`、`Row`、`Col` 等 Ant Design 布局组件；避免大量裸 `div` 和临时 CSS 拼出组件已有能力。
- 颜色、圆角、边框、阴影、间距等视觉值优先使用 `theme.useToken()` 或组件 token，不硬编码主题色。
- 管理后台页面保持信息密度、对齐、搜索表单、操作列、按钮样式与 Ant Design Pro 一致；不要做营销页式 hero、装饰性渐变或脱离后台体系的视觉风格。
- 新增或修改页面时，应对照 Ant Design Pro 最佳实践检查页面结构、组件选择、主题 token、响应式布局和空 / 加载 / 错误状态。

## 8. 认证、授权与安全规范

### 8.1 认证

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

### 8.2 授权

权限应分层：

- 前端：控制菜单、按钮、路由可见性。
- 后端：强制校验接口访问权限。
- 领域 / 应用层：校验业务归属、操作者是否允许执行该业务动作。

规则：

- 角色码或权限码使用稳定常量。
- 高危操作必须后端校验。
- 不能只靠前端隐藏按钮。
- 审计日志记录操作者和关键动作。

### 8.3 配置与密钥

- 所有环境差异通过配置或环境变量注入。
- 不提交真实密钥、个人账号密码、生产连接串。
- 默认配置只能用于本地开发。
- CI/CD 中使用 secret manager 或受保护变量。
- 文档中的示例密钥必须明显标注为示例。
- 调用外部 HTTP 接口必须使用 Spring HTTP Interface，即使用 `@HttpExchange`、`@GetExchange`、`@PostExchange` 等注解标注 interface，并通过 Spring `HttpServiceProxyFactory` 创建代理；禁止在业务代码中直接使用 OkHttp、Apache HttpClient、JDK `HttpClient`、`RestTemplate` 或手写 HTTP 请求样板调用外部服务。
- 外部 HTTP interface 的 API Key、Token、Base URL、超时等必须由服务端配置注入；密钥只能作为请求头或认证配置在服务端使用，不得返回给前端、写入日志或进入 DTO / VO。

## 9. 错误处理与可观测性

### 9.1 后端错误处理

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

### 9.2 前端错误处理

- 统一 request error handler。
- 401 统一清理登录态并跳转。
- 业务错误按 showType 展示 message / notification。
- 页面不重复实现通用错误处理。

### 9.3 日志与监控

- 关键业务动作记录 info 日志。
- 异常记录 error 日志并包含上下文 ID。
- 不打印密码、token、身份证、个人隐私等敏感信息。
- 暴露健康检查和指标端点。
- 对外部依赖调用记录耗时和失败情况。

## 10. 测试规范

### 10.1 前端测试

前端测试关注用户可见行为、前后端契约和关键交互结果，不应绑定组件内部 state、私有方法或实现层级。

#### 10.1.1 需要测试的对象

以下对象新增或修改行为时，应同步新增或更新测试：

1. **纯函数与数据转换函数**：格式化、枚举映射、表单值归一化、查询参数转换、权限判断、排序和过滤逻辑。
2. **API Service**：请求 URL、HTTP 方法、查询参数、请求体、身份或操作者请求头，以及响应数据的转换和兜底逻辑。
3. **通用组件**：关键内容渲染、用户操作、条件显示、禁用状态、空状态、加载状态和错误状态。
4. **表单组件**：初始值和数据回填、必填项与业务校验、字段联动、提交数据转换、防重复提交和失败后的状态恢复。
5. **页面组件**：加载数据、列表查询与分页、搜索筛选、详情展示、增删改和状态操作的完整交互链路。
6. **路由、认证与权限边界**：未登录跳转、无权限时的页面或按钮控制、不同角色可执行的操作。
7. **关键回归流程**：登录、创建、编辑、提交、审批、错误处理等对业务交付有直接影响的主流程。

纯展示、无条件分支且已被上层页面覆盖的薄封装组件，可以不单独建测试；可复用业务逻辑仍应抽成纯函数并直接测试。

#### 10.1.2 测试类型与覆盖策略

- **纯函数单元测试**：直接输入和断言输出，覆盖正常值、空值、边界值和非法值。
- **API Service 单元测试**：mock `request`，验证请求契约；不得发起真实网络请求。
- **组件渲染测试**：使用 Jest、jsdom 和 Testing Library，从用户视角查询元素并验证可见结果。
- **页面交互测试**：mock API Service 或框架边界，覆盖“加载 → 操作 → 请求 → 成功或失败反馈”的关键链路。
- **回归测试**：对登录、权限、错误处理和关键业务主流程保留稳定用例；具备端到端测试环境时，可补充少量 E2E 测试，但不能用 E2E 替代纯函数、Service 和组件级测试。

#### 10.1.3 文件组织与命名

- 测试文件与被测文件就近放置，命名为 `{被测文件名}.test.ts` 或 `{被测文件名}.test.tsx`；目录入口可使用 `index.test.tsx`。
- 使用 Jest 的 `describe` 按被测对象或功能分组，使用 `it` / `test` 描述单一行为。
- 测试名称统一使用 BDD 风格：`should{预期行为}[When{条件}]`，例如 `shouldSubmitNormalizedValuesWhenFormIsValid`。
- 一个测试只验证一个业务场景；同一场景可以包含渲染结果、请求入参和反馈状态等相互关联的多个断言。
- 测试数据应在测试文件内声明，命名表达业务含义；不得依赖其他测试产生的数据或执行顺序。

#### 10.1.4 Mock 与测试隔离

- 只 mock 外部边界，例如 API Service、`request`、路由、登录用户模型、时间、浏览器 API 和难以稳定运行的第三方组件。
- 页面测试优先 mock API Service，不重复 mock Service 内部的 `request`；API Service 测试则直接 mock `request` 并验证传参。
- 使用 `jest.fn()`、`jest.mock()` 和 `jest.spyOn()`；每个测试前使用 `mockReset()`、`mockClear()` 或统一的测试初始化恢复状态，避免调用记录和返回值泄漏。
- 不 mock 被测对象自身的业务函数，不为了让断言通过而复刻一份生产逻辑。
- 不访问真实网络、真实后端或开发人员本机数据；异步请求必须显式设置成功、空数据和失败返回。
- 对日期、随机数、定时器等不稳定输入使用固定值；使用 fake timer 后必须在测试结束时恢复真实 timer。

#### 10.1.5 纯函数与 API Service 详细规范

纯函数测试应覆盖：

- 典型输入的完整输出，而不只断言单个字段。
- `null`、`undefined`、空字符串、空集合、边界数值等函数声明允许接收的边界输入。
- 枚举、状态和类型的所有业务分支；非法输入有明确兜底时，验证兜底结果。
- 输入不可变性：函数约定不修改入参时，验证原对象或集合未被篡改。

API Service 测试应覆盖：

- URL 和资源 ID 拼接正确，GET、POST、PATCH、DELETE 等 HTTP 方法正确。
- `params`、`data`、分页排序参数、`updateMask` 和自定义请求头正确传递；可选值不应被误传为错误默认值。
- 创建、更新、删除、状态操作等不同方法不会误用其他资源端点。
- 存在响应转换或显示兜底时，覆盖正常响应、字段缺失、空列表和约定的异常传播。
- 使用 `toHaveBeenCalledWith`、`toHaveBeenNthCalledWith` 或检查 `mock.calls` 验证完整请求契约；不能只断言“调用过”。

#### 10.1.6 组件、表单与页面详细规范

- 优先通过角色、可访问名称、文本、label 或 placeholder 查询元素；仅在没有稳定用户语义时使用 `data-testid`。
- 使用 Testing Library 驱动点击、输入、选择、提交等用户行为；不要直接调用组件实例方法或断言内部 state。
- 异步渲染和状态变化使用 `findBy*`、`waitFor` 等待结果，不使用任意时长的 sleep，也不在未等待时直接断言 Promise 后的 UI。
- 组件至少覆盖主要渲染、关键交互、条件分支和异常或空状态；有加载过程时验证 loading 被正确展示和结束。
- 表单至少覆盖完整字段提交、仅必填字段提交、前端校验失败不发请求、数据回填、字段联动和提交失败后的错误反馈。
- 提交测试必须断言归一化后的完整请求数据及关键上下文（例如当前用户）；不能只断言回调被调用。
- 列表页面至少覆盖首次查询、搜索或筛选、分页、空列表，以及操作成功后刷新或本地状态更新。
- 权限测试应验证用户实际看到和能够执行的行为；隐藏按钮之外，还应验证绕过 UI 时受保护操作不会由页面错误触发。
- 错误测试应验证用户可见的错误提示、页面状态可恢复，并确保失败后不会错误展示成功反馈。
- 快照测试只适合稳定、展示型结构，可作为补充；关键业务行为必须使用语义断言，不能只依赖快照。

#### 10.1.7 断言与反模式

- 优先断言可见文本、控件状态、页面跳转、请求参数和回调结果；断言应能说明业务结果是否正确。
- 集合和请求对象优先比较完整结构；只关注部分字段时可使用 `toMatchObject`，但关键字段不得遗漏。
- 异常或校验路径必须额外断言 API、提交回调或导航没有被调用。
- 不断言 CSS 类名、组件内部层级、hook 调用顺序等易变实现细节，除非该细节本身就是对外契约。
- 不滥用 `waitFor` 掩盖未正确处理的异步逻辑，不使用只为延长等待时间的 timer。
- 不随意更新快照来消除失败；必须先确认变化符合需求。
- 不编写没有有效断言、只渲染不验证，或只验证 mock 返回值本身的测试。

### 10.2 后端测试

#### 10.2.1 需要测试的对象与测试类型

以下后端对象新增或修改行为时，应同步新增或更新测试：

1. **Domain unit test**：领域实体的创建与状态迁移、值对象校验和计算、领域服务及核心不变量；不依赖 Spring 和数据库。
2. **Application unit test**：Command / Query Executor 的业务校验、用例编排、Gateway 调用和返回转换；Service Facade 的委托关系。
3. **Converter unit test**：复杂字段映射、枚举和时间转换、关联对象存在或缺失时的兜底逻辑。
4. **Gateway / Repository unit test**：基础设施实现对 Mapper、DAO、Converter 或外部 SDK 的编排、条件构造和调用方式。
5. **Infrastructure integration test**：Mapper、SQL、数据库约束、分页排序和外部适配器集成；应使用与目标数据库兼容的测试环境。
6. **API / Spring integration test**：Controller 参数绑定、JSR-303 校验、认证授权、错误码与 HTTP 状态、响应结构。

抽象基类、无业务分支的纯工具型 support 类可以不单独建测试，但其行为必须通过具体类测试覆盖。不能用 Service、API 或端到端测试替代 Executor 和 Domain 的直接单元测试。

#### 10.2.2 后端单元测试通用规范

基于项目实践中沉淀的经验，后端单元测试应遵循以下规范。

##### 10.2.2.1 测试框架与工具

- 测试框架统一使用 **JUnit 5**（`org.junit.jupiter.api`），不使用 JUnit 4。
- Mock 框架统一使用 **Mockito**（当前版本 5.14.2，通过 `athena-component-test` 传递引入）。
- 后端单元测试不使用 `@SpringBootTest` 或 Spring 上下文加载；需要验证容器行为时应单独编写集成测试。
- 测试依赖通过项目 BOM 统一管理，不单独引入 Mockito 版本。

##### 10.2.2.2 类结构规范

- 测试类使用 **package-private**（省略 `public` 修饰符），与项目现有风格一致。
- 测试类命名：`{被测类名}Test`，例如 `LessonEntryCreateExecutorTest`。
- 测试类放在与被测类相同的包路径下，位于 `src/test/java` 目录。
- 每个测试方法使用 `@Test` 注解（JUnit 5）。

##### 10.2.2.3 Mock 规范

- 外部依赖（Gateway、Service 等）统一使用 `mock()` 创建 Mock 实例，不使用手写桩实现（Stub）。
- Mock 对象通过构造器注入目标类，不依赖 Spring DI。
- 使用 `ArgumentCaptor` 捕获方法入参进行验证，确保调用方传入的参数正确。
- 使用 `verify()` 验证方法调用次数和入参，使用 `verify(never())` 验证异常路径下特定方法未被调用。
- 对于无法 Mock 的框架类（如 MapStruct 转换器），允许使用 `Mappers.getMapper()` 获取真实实例，并在需要时注入必要的 Mock 依赖为其字段赋值。

##### 10.2.2.4 测试场景覆盖

根据被测对象实际职责覆盖以下场景；Executor 应完整覆盖，透明委托的 Service 按 10.2.4 执行：

1. **成功路径（Happy Path）**：完整字段输入，验证所有输出字段正确，验证 Mock 调用入参正确。
2. **最小字段路径（Minimal Input）**：仅输入必需字段，验证非必需字段为 null 或默认值。
3. **无效参数路径（Invalid Input）**：传入非法枚举值、格式错误等，验证抛出特定业务异常。
4. **边界条件**：空集合、null 值、极端值等。

对于异常路径（Invalid Input），必须额外验证 Mock 对象中与被测方法相关的业务方法**未被调用**，以确保异常在早期阶段被正确拦截。

##### 10.2.2.5 断言规范

- 使用 JUnit 5 的 `org.junit.jupiter.api.Assertions` 静态方法（`assertEquals`、`assertNotNull`、`assertThrows`、`assertNull` 等）。
- 使用 Mockito 的 `verify()` 系列方法验证 Mock 交互。
- 断言信息应清晰表达验证意图。
- 集合字段使用 `assertEquals` 比较完整列表，不逐元素断言。

##### 10.2.2.6 Javadoc 规范

每个测试方法都必须编写 Javadoc，说明：

- 测试的场景描述
- 验证的断言要点（可用 `<ul>` 列表列举）
- 异常路径应说明预期异常类型

示例：

```java
/**
 * 测试成功创建一条完整的经验教训草稿。
 *
 * <p>验证场景：传入包含所有可选字段的创建命令，断言：</p>
 * <ul>
 *   <li>{@code gateway.save()} 的入参包含全部字段的正确值，以及默认值</li>
 *   <li>{@code gateway.getById()} 的入参为 save 返回的 ID</li>
 *   <li>返回的 DTO 字段与 command 数据一致</li>
 * </ul>
 */
@Test
void shouldCreateLessonEntryDraftSuccessfully() {
    // ...
}
```

##### 10.2.2.7 测试方法命名

统一使用 BDD 风格命名：`should{预期行为}[When{条件}]`。

- 成功路径：`shouldCreateEntrySuccessfully`、`shouldSaveEntryAndReload`
- 异常路径：`shouldRejectInvalidType`、`shouldThrowExceptionWhenStatusInvalid`

其他示例：

```text
shouldPublishWhenStatusIsDraft
shouldRejectStartWhenStatusIsDraft
shouldCalculateAverageScoreWhenSubmitted
```

##### 10.2.2.8 测试初始化

- 使用 `@BeforeEach` 方法统一初始化 Mock 对象、转换器和被测对象。
- 对于 MapStruct 转换器，在 `@BeforeEach` 中通过 `Mappers.getMapper()` 获取实例并注入必要的 Mock 依赖。

##### 10.2.2.9 避免反模式

- 不要手写 Stub 实现类来替代 Mockito Mock。
- 单体测试中，被测对象的构造器注入、setter 注入或字段注入依赖必须使用 Mockito Mock；除被测对象本身外，不要创建真实 Gateway、Mapper、DAO、Executor、Service、Converter 等协作者实例来参与行为验证。
- 不要在测试中加载 Spring 上下文。
- 不要依赖测试执行顺序。
- 不要在一个测试方法中验证多个无关的行为。
- 不要使用 `System.out` 或日志输出替代断言。
- 不要将测试数据硬编码在业务逻辑可访问的公共常量中。
- 不要在 client 模块中测试 JSR-303 Bean Validation 注解（`@NotBlank`、`@NotNull` 等）。这些注解的校验由 Spring 容器在接口层通过 `@Validated` 触发，属于集成测试范畴；Executor 级别不验证 JSR-303 注解，因此 executor 测试中不应引入 `jakarta.validation.Validator`。
- 不要为只做委托转发的 Service Facade 类编写复杂的集成测试。Service 层若仅为透明委托，只需 Mock 所有 Executor 依赖，验证每个方法正确调用对应 Executor 并透传参数和返回值即可。

#### 10.2.3 Executor 测试规范

Executor 是单体测试的核心对象。每个 Executor 的测试应遵循以下分层覆盖策略：

**0. 覆盖硬性要求：**

- 所有 Command Executor 和 Query Executor 都必须编写同名单体测试类，测试类命名为 `{Executor类名}Test`。
- 新增 Executor 时必须同步新增测试；修改 Executor 行为时必须同步更新对应测试。
- 不允许只通过 Service Facade 测试间接覆盖 Executor。Service 测试只验证委托关系，Executor 自身的业务规则、参数解析、gateway 调用和返回转换必须在 Executor 测试中直接覆盖。
- 只有抽象基类、无业务分支的纯工具型 support 类可以不单独建测试；其行为必须通过具体 Executor 测试覆盖。

**1. Executor 内部显式业务校验必须覆盖：**

- `checkRevision()` 校验 — revision 不匹配时抛 `LESSON_ENTRY_REVISION_MISMATCH`
- `require()` 校验 — entry 不存在时抛 `LESSON_ENTRY_NOT_FOUND`
- 状态校验 — 不允许的状态下操作抛 `LESSON_ENTRY_INVALID_STATUS`
- 乐观锁冲突 — `gateway.update()` 返回 0 时抛 `LESSON_ENTRY_REVISION_MISMATCH`
- 参数显式校验 — 枚举值非法、updateMask 无效、资源名格式非法、跨字段业务规则不满足等
- `parseMask()` 校验 — mask 为空或包含白名单外字段时抛 `INVALID_UPDATE_MASK`
- 不覆盖 Command / Query 上已经通过 JSR-303 表达的字段级约束，例如 `@NotBlank`、`@NotNull`、`@Size`。

**2. 成功路径验证要点：**

- 使用 `ArgumentCaptor` 捕获 gateway 调用入参，验证字段值正确
- 验证 gateway 调用次数（`getById` 调用 1 次还是 2 次取决于是否 `reload()`）
- 验证返回的 DTO 字段值与预期一致
- 验证状态字段、操作者字段、版本号等关键业务字段

**3. 异常路径验证要点：**

- 使用 `assertThrows` 断言特定异常类型
- 使用 `exception.getCode()` 断言错误码（如 `assertEquals("LESSON_ENTRY_INVALID_STATUS", exception.getCode())`）
- 使用 `verify(gateway, never()).update(any())` 验证异常路径下 gateway 写方法未被调用
- 对于在参数解析阶段（如 `parseEntryId`）就抛出的异常，还需验证 `getById` 也未被调用

**4. 状态校验测试要求：**

对于涉及状态迁移的 Executor，必须覆盖：
- 所有允许的状态下的成功路径（每个允许状态至少一个测试）
- 所有不允许的状态下的异常路径（每种不允许状态至少一个测试，或使用参数化测试覆盖）

**5. 副作用验证：**

- 验证 `updatedBy` 被正确设置为操作者
- 验证状态正确变更（`archive → ARCHIVED`、`reject → REJECTED` 等）
- 验证 `submit` 时 `markEditedAsDraft` 的正确行为（REJECTED/NEED_MORE_INFO → DRAFT）

#### 10.2.4 Service Facade 测试规范

Application Service（如 `XxxServiceImpl`）通常只做事务注解和委托转发，其测试策略：

**1. Mock 策略：**
- Mock 所有注入的 Executor 依赖，不创建真实 Executor 实例
- 不使用真实 Gateway 或 Converter

**2. 覆盖内容：**
- 每个方法至少一个成功路径测试，验证委托调用正确
- 每个方法验证返回值与 Executor 返回值一致（使用 `assertSame`）
- 每个方法验证参数被原样透传给 Executor（使用 `verify()` 或 `ArgumentCaptor`）

**3. 不需要覆盖的路径：**
- Service 不做业务校验、不做数据转换、不做 Gateway 直调，因此不需要覆盖校验异常、DAO 异常等
- Executor 层的错误会自然传播到 Service 层，不需要在 Service 测试中重复覆盖

#### 10.2.5 Command / Query 校验测试规范

Command 和 Query 对象的字段校验分两层，测试各层职责：

**1. JSR-303 注解的校验（`@NotBlank`、`@NotNull` 等）：**
- 这些校验由 Spring 容器通过 `@Validated` + `@Valid` 在接口层触发
- 在纯单元测试（无 Spring 上下文）中不需要测试 JSR-303 注解
- 禁止在 client 模块中引入 `jakarta.validation.Validator` 为 Command 编写独立的 validation 测试

**2. 业务层显式校验（Executor / Domain 内部业务规则判断）：**
- 这是 Executor 或 Domain 测试必须覆盖的校验
- 例如资源名格式解析、`updateMask` 白名单、状态流转、版本一致性、资源存在性、操作者角色、跨字段业务规则等
- 如果某个字段级约束已经由 `@NotBlank`、`@NotNull`、`@Size` 等 Bean Validation 注解表达，不要在 Executor 中重复手写判断，也不要在 Executor 测试中覆盖 validation 框架行为

#### 10.2.6 Domain 与 Converter 测试规范

**Domain 测试：**

- 领域实体的创建、状态迁移、业务计算和不变量必须直接测试，不通过 Executor 间接覆盖。
- 每个状态迁移覆盖所有允许状态和不允许状态；不允许状态应断言业务异常和错误码，并确认对象未产生部分修改。
- 值对象覆盖合法值、边界值、非法值、相等性和格式化行为；测试不依赖 Spring、数据库或系统当前时间。
- 涉及时间、操作者或序列号时，通过参数传入或固定测试值控制，避免依赖运行环境。

**Converter 测试：**

- 将 Converter 作为被测对象时可以使用真实实例；它注入的 Gateway、Mapper 或其他协作者仍必须 mock。
- 覆盖正向和反向映射、`null`、枚举、时间、集合、默认值，以及新增字段是否完整映射。
- 涉及关联数据回填时，覆盖关联对象存在、缺失和关联键为空的兜底行为。
- 不为 MapStruct 自动生成的无分支同名字段复制编写低价值断言；优先覆盖自定义表达式、字段改名、类型转换和忽略字段。

#### 10.2.7 Gateway / Repository 测试规范

Infrastructure Gateway / Repository 实现的单体测试应只验证本类对依赖的编排、转换和调用方式：

- Mock 所有注入的 Mapper、DAO、Converter、外部 SDK Client 等依赖。
- 不使用动态代理、手写 Stub 或真实数据库访问对象替代 Mock。
- 需要验证查询条件或更新条件时，使用 `ArgumentCaptor` 捕获 Wrapper / Criteria / Command 对象后断言关键字段。
- Gateway / Repository 单元测试不验证数据库或 ORM 框架本身；SQL 正确性、数据库约束和 Mapper 映射应由基础设施集成测试覆盖。

#### 10.2.8 基础设施与 API 集成测试规范

- Mapper / SQL 测试应覆盖新增或修改的查询、写入、分页、排序、空结果、数据库约束和方言相关逻辑；测试数据必须隔离并可重复执行。
- 列表查询应覆盖多条记录和重复关联键，验证批量查询只执行一次，并且每条记录按关联键正确回填。
- 外部适配器集成测试应在可控测试服务或契约桩上运行，覆盖请求转换、响应转换、超时和约定的错误映射；不能调用生产服务。
- Controller / API 测试应覆盖参数绑定、JSR-303 字段校验、认证与授权、成功响应结构、业务异常对应的错误码和 HTTP 状态。
- 如果需要证明方法级 Bean Validation 生效，应通过 Spring 集成测试覆盖 App Service 或接口边界，不在 Executor 测试中重复验证框架行为。
- 集成测试应与纯单元测试分组或按项目约定命名，确保本地和 CI 可以分别执行；不得依赖执行顺序或开发人员本机状态。

#### 10.2.9 覆盖率目标

- 每个 Executor 类的指令覆盖率目标：**100%**
- 每个 Executor 类的分支覆盖率目标：**100%**（switch 表达式中的字节码隐式分支除外）
- 公共父类（如 `ExecutorSupport`）的指令覆盖率目标：**≥ 95%**
- Service Facade 类的覆盖率目标：**100%**
- Converter 等映射类的覆盖率目标：**≥ 90%**

## 11. 代码风格规范

### 11.1 Java / 后端

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

### 11.2 TypeScript / 前端

- API 类型要准确，避免无意义 `any`。
- 组件 props 明确定义类型。
- 枚举字段使用 union type。
- 请求函数返回 Promise 的明确泛型。
- hook 只处理可复用逻辑，不混入页面文案。
- 日期、金额、状态展示使用统一格式化函数。
- 不在组件中硬编码后端 host。

### 11.3 SQL

- SQL 格式清晰，字段显式列出。
- 动态 SQL 处理 null 和空集合。
- 排序字段白名单。
- 大查询关注索引和分页。
- 删除优先软删除，物理删除需有明确理由。

### 11.4 文档与注释

注释用于解释“为什么”，不是重复“做什么”。

应写文档的场景：

- 新模块架构决策。
- 复杂业务状态机。
- 重要接口契约。
- 数据库迁移说明。
- 安全和部署配置。

不要让文档与代码长期不一致；变更代码时同步更新文档。

## 12. 新项目启动清单

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

## 13. 新功能开发清单

### 13.1 开发前

- [ ] 明确业务目标和非目标。
- [ ] 找到所属业务域。
- [ ] 确认是否新增状态、枚举、角色、权限。
- [ ] 确认是否需要数据库变更。
- [ ] 确认 API 契约与前端页面影响。
- [ ] 阅读同类功能实现，复用现有模式。

### 13.2 后端开发

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

### 13.3 前端开发

- [ ] 在 service 层新增 API 函数和类型。
- [ ] 新增页面或组件。
- [ ] 配置路由、菜单、权限。
- [ ] 页面 UI 符合 Ant Design Pro 最佳实践，优先使用 Pro Components / Ant Design 组件和主题 token。
- [ ] 处理 loading、empty、error。
- [ ] 添加表单校验和危险操作确认。
- [ ] 同步枚举、状态文案、国际化文案。
- [ ] 添加必要测试。

### 13.4 联调前检查

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

### 13.5 完成前

- [ ] 运行后端测试或最小模块编译。
- [ ] 运行前端类型检查、lint、测试。
- [ ] 检查是否引入敏感信息。
- [ ] 检查是否有临时代码、console、mock 数据残留。
- [ ] 更新相关文档。
- [ ] 总结验证结果和风险。

## 14. Coding Agent 工作准则

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

## 15. 可复用架构模板

### 15.1 后端目录模板

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

### 15.2 前端目录模板

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

### 15.3 单个功能落地模板

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

## 16. 反模式清单

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

## 17. 一句话总结

好的工程代码应该让新功能沿着固定路径自然落位：

```text
业务意图 → 用例 → 领域规则 → 契约 → 适配器 → 持久化 → 页面 → 测试 → 交付
```

只要持续保持清晰边界、稳定契约、集中转换、可测试规则和可验证交付，新项目和新功能就能在复杂度增长时仍然保持可维护。
