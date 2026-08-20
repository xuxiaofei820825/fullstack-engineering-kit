# 后端架构、领域、持久化与 API 规范

> 从仓库根目录 `coding-standards.md` 提取；源文档是最终依据。

## 目录

- 推荐后端架构
- 用例、CQRS、Validation 与事务
- 领域模型
- 数据模型、持久化与 Liquibase
- REST、OpenAPI、分页、枚举、幂等与错误状态

## 推荐后端架构

### 分层模型

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

### 依赖方向

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

### 请求处理链路

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

## 用例与 CQRS 规范

### 一个用例一个执行器

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

### Command / Query 设计

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

### Validation 职责边界

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

### 事务边界

事务应放在 application service 层：

- 写操作：开启事务，异常回滚。
- 查询操作：只读事务。
- 跨聚合写操作：明确一致性要求，必要时使用事件或补偿。
- 外部系统调用：避免长事务包裹远程调用；必要时拆分流程。

## 领域模型规范

### 领域对象承载核心规则

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

### 创建与状态流转

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

### 值对象

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

### 错误码

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

## 数据模型与持久化规范

### 区分领域模型与持久化对象

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

### 数据库通用字段

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

### SQL 与 Mapper

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

#### 列表查询中的关联数据回填

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

### Liquibase 数据库迁移

所有数据库结构和基础数据变更必须通过 Liquibase 管理，禁止只修改数据库、PO 或 Mapper 而不提供迁移脚本。

#### 版本与目录组织

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

#### SQL 文件拆分与命名

- 每个表的变更对应一个 SQL 文件；同一发布版本内，同一张表的建表、加列、索引、约束等变更集中在该表文件中。
- SQL 文件名必须直接使用表名并采用小写下划线形式，例如 `tb_lesson_review.sql`。
- 文件名不得添加动作前缀或描述性后缀，例如不得使用 `alter_tb_lesson_review.sql`、`create_lesson_review_table.sql`。
- 一个 SQL 文件只允许修改其文件名对应的主表，不得在同一文件中顺带修改其他表。

#### changeset 规范

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

#### 迁移设计与审查

- 新增表应同步设计主键、业务唯一约束、必要索引、逻辑关联字段、乐观锁、逻辑删除和审计字段，并与项目通用字段规范保持一致；禁止创建外键约束。
- 索引和约束必须显式命名，名称应稳定且能表达表内用途，避免数据库自动生成不可预测名称。
- 新增非空字段必须评估历史数据；需要回填时，应先提供兼容默认值或分阶段迁移，禁止直接导致存量数据迁移失败。
- 删除列、修改类型、收紧约束等破坏性变更必须说明数据迁移和回滚策略，并验证应用版本的前后向兼容窗口。
- 提交前至少检查：changelog include 链完整、版本归属正确、每表一文件、文件名等于表名、changeset 格式正确、执行顺序合理、rollback 可用、目标数据库方言兼容。

### 多存储一致性

当同时使用 MySQL、MongoDB、Redis、对象存储时：

- 明确哪个存储是主数据源。
- 明确快照、缓存、索引数据的更新时机。
- 对文件上传、对象存储写入要考虑失败清理。
- 对缓存使用要有失效策略。
- 对发布版本、历史版本建议使用不可变快照。

## 接口设计规范

### REST API

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

### OpenAPI 注解

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

### 分页与排序

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

### 枚举与时间

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

### 幂等与并发

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

### 错误处理状态

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
