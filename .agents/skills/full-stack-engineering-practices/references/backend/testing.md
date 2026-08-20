# 后端测试规范

> 从仓库根目录 `coding-standards.md` 提取；源文档是最终依据。

## 目录

- 测试对象与测试类型
- 单元测试通用规范
- Executor 测试
- Service Facade 测试
- Command / Query 校验测试
- Domain 与 Converter 测试
- Gateway / Repository 测试
- 基础设施与 API 集成测试
- 覆盖率目标

## 后端测试

### 需要测试的对象与测试类型

以下后端对象新增或修改行为时，应同步新增或更新测试：

1. **Domain unit test**：领域实体的创建与状态迁移、值对象校验和计算、领域服务及核心不变量；不依赖 Spring 和数据库。
2. **Application unit test**：Command / Query Executor 的业务校验、用例编排、Gateway 调用和返回转换；Service Facade 的委托关系。
3. **Converter unit test**：复杂字段映射、枚举和时间转换、关联对象存在或缺失时的兜底逻辑。
4. **Gateway / Repository unit test**：基础设施实现对 Mapper、DAO、Converter 或外部 SDK 的编排、条件构造和调用方式。
5. **Infrastructure integration test**：Mapper、SQL、数据库约束、分页排序和外部适配器集成；应使用与目标数据库兼容的测试环境。
6. **API / Spring integration test**：Controller 参数绑定、JSR-303 校验、认证授权、错误码与 HTTP 状态、响应结构。

抽象基类、无业务分支的纯工具型 support 类可以不单独建测试，但其行为必须通过具体类测试覆盖。不能用 Service、API 或端到端测试替代 Executor 和 Domain 的直接单元测试。

### 后端单元测试通用规范

基于项目实践中沉淀的经验，后端单元测试应遵循以下规范。

#### 测试框架与工具

- 测试框架统一使用 **JUnit 5**（`org.junit.jupiter.api`），不使用 JUnit 4。
- Mock 框架统一使用 **Mockito**（当前版本 5.14.2，通过 `athena-component-test` 传递引入）。
- 后端单元测试不使用 `@SpringBootTest` 或 Spring 上下文加载；需要验证容器行为时应单独编写集成测试。
- 测试依赖通过项目 BOM 统一管理，不单独引入 Mockito 版本。

#### 类结构规范

- 测试类使用 **package-private**（省略 `public` 修饰符），与项目现有风格一致。
- 测试类命名：`{被测类名}Test`，例如 `LessonEntryCreateExecutorTest`。
- 测试类放在与被测类相同的包路径下，位于 `src/test/java` 目录。
- 每个测试方法使用 `@Test` 注解（JUnit 5）。

#### Mock 规范

- 外部依赖（Gateway、Service 等）统一使用 `mock()` 创建 Mock 实例，不使用手写桩实现（Stub）。
- Mock 对象通过构造器注入目标类，不依赖 Spring DI。
- 使用 `ArgumentCaptor` 捕获方法入参进行验证，确保调用方传入的参数正确。
- 使用 `verify()` 验证方法调用次数和入参，使用 `verify(never())` 验证异常路径下特定方法未被调用。
- 对于无法 Mock 的框架类（如 MapStruct 转换器），允许使用 `Mappers.getMapper()` 获取真实实例，并在需要时注入必要的 Mock 依赖为其字段赋值。

#### 测试场景覆盖

根据被测对象实际职责覆盖以下场景；Executor 应完整覆盖，透明委托的 Service 按 Service Facade 测试规范执行：

1. **成功路径（Happy Path）**：完整字段输入，验证所有输出字段正确，验证 Mock 调用入参正确。
2. **最小字段路径（Minimal Input）**：仅输入必需字段，验证非必需字段为 null 或默认值。
3. **无效参数路径（Invalid Input）**：传入非法枚举值、格式错误等，验证抛出特定业务异常。
4. **边界条件**：空集合、null 值、极端值等。

对于异常路径（Invalid Input），必须额外验证 Mock 对象中与被测方法相关的业务方法**未被调用**，以确保异常在早期阶段被正确拦截。

#### 断言规范

- 使用 JUnit 5 的 `org.junit.jupiter.api.Assertions` 静态方法（`assertEquals`、`assertNotNull`、`assertThrows`、`assertNull` 等）。
- 使用 Mockito 的 `verify()` 系列方法验证 Mock 交互。
- 断言信息应清晰表达验证意图。
- 集合字段使用 `assertEquals` 比较完整列表，不逐元素断言。

#### Javadoc 规范

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

#### 测试方法命名

统一使用 BDD 风格命名：`should{预期行为}[When{条件}]`。

- 成功路径：`shouldCreateEntrySuccessfully`、`shouldSaveEntryAndReload`
- 异常路径：`shouldRejectInvalidType`、`shouldThrowExceptionWhenStatusInvalid`

其他示例：

```text
shouldPublishWhenStatusIsDraft
shouldRejectStartWhenStatusIsDraft
shouldCalculateAverageScoreWhenSubmitted
```

#### 测试初始化

- 使用 `@BeforeEach` 方法统一初始化 Mock 对象、转换器和被测对象。
- 对于 MapStruct 转换器，在 `@BeforeEach` 中通过 `Mappers.getMapper()` 获取实例并注入必要的 Mock 依赖。

#### 避免反模式

- 不要手写 Stub 实现类来替代 Mockito Mock。
- 单体测试中，被测对象的构造器注入、setter 注入或字段注入依赖必须使用 Mockito Mock；除被测对象本身外，不要创建真实 Gateway、Mapper、DAO、Executor、Service、Converter 等协作者实例来参与行为验证。
- 不要在测试中加载 Spring 上下文。
- 不要依赖测试执行顺序。
- 不要在一个测试方法中验证多个无关的行为。
- 不要使用 `System.out` 或日志输出替代断言。
- 不要将测试数据硬编码在业务逻辑可访问的公共常量中。
- 不要在 client 模块中测试 JSR-303 Bean Validation 注解（`@NotBlank`、`@NotNull` 等）。这些注解的校验由 Spring 容器在接口层通过 `@Validated` 触发，属于集成测试范畴；Executor 级别不验证 JSR-303 注解，因此 executor 测试中不应引入 `jakarta.validation.Validator`。
- 不要为只做委托转发的 Service Facade 类编写复杂的集成测试。Service 层若仅为透明委托，只需 Mock 所有 Executor 依赖，验证每个方法正确调用对应 Executor 并透传参数和返回值即可。

### Executor 测试规范

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

### Service Facade 测试规范

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

### Command / Query 校验测试规范

Command 和 Query 对象的字段校验分两层，测试各层职责：

**1. JSR-303 注解的校验（`@NotBlank`、`@NotNull` 等）：**
- 这些校验由 Spring 容器通过 `@Validated` + `@Valid` 在接口层触发
- 在纯单元测试（无 Spring 上下文）中不需要测试 JSR-303 注解
- 禁止在 client 模块中引入 `jakarta.validation.Validator` 为 Command 编写独立的 validation 测试

**2. 业务层显式校验（Executor / Domain 内部业务规则判断）：**
- 这是 Executor 或 Domain 测试必须覆盖的校验
- 例如资源名格式解析、`updateMask` 白名单、状态流转、版本一致性、资源存在性、操作者角色、跨字段业务规则等
- 如果某个字段级约束已经由 `@NotBlank`、`@NotNull`、`@Size` 等 Bean Validation 注解表达，不要在 Executor 中重复手写判断，也不要在 Executor 测试中覆盖 validation 框架行为

### Domain 与 Converter 测试规范

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

### Gateway / Repository 测试规范

Infrastructure Gateway / Repository 实现的单体测试应只验证本类对依赖的编排、转换和调用方式：

- Mock 所有注入的 Mapper、DAO、Converter、外部 SDK Client 等依赖。
- 不使用动态代理、手写 Stub 或真实数据库访问对象替代 Mock。
- 需要验证查询条件或更新条件时，使用 `ArgumentCaptor` 捕获 Wrapper / Criteria / Command 对象后断言关键字段。
- Gateway / Repository 单元测试不验证数据库或 ORM 框架本身；SQL 正确性、数据库约束和 Mapper 映射应由基础设施集成测试覆盖。

### 基础设施与 API 集成测试规范

- Mapper / SQL 测试应覆盖新增或修改的查询、写入、分页、排序、空结果、数据库约束和方言相关逻辑；测试数据必须隔离并可重复执行。
- 列表查询应覆盖多条记录和重复关联键，验证批量查询只执行一次，并且每条记录按关联键正确回填。
- 外部适配器集成测试应在可控测试服务或契约桩上运行，覆盖请求转换、响应转换、超时和约定的错误映射；不能调用生产服务。
- Controller / API 测试应覆盖参数绑定、JSR-303 字段校验、认证与授权、成功响应结构、业务异常对应的错误码和 HTTP 状态。
- 如果需要证明方法级 Bean Validation 生效，应通过 Spring 集成测试覆盖 App Service 或接口边界，不在 Executor 测试中重复验证框架行为。
- 集成测试应与纯单元测试分组或按项目约定命名，确保本地和 CI 可以分别执行；不得依赖执行顺序或开发人员本机状态。

### 覆盖率目标

- 每个 Executor 类的指令覆盖率目标：**100%**
- 每个 Executor 类的分支覆盖率目标：**100%**（switch 表达式中的字节码隐式分支除外）
- 公共父类（如 `ExecutorSupport`）的指令覆盖率目标：**≥ 95%**
- Service Facade 类的覆盖率目标：**100%**
- Converter 等映射类的覆盖率目标：**≥ 90%**
