# Pi 项目架构文档

## 概述

Pi 是一个用于构建 AI 代理和管理 LLM 部署的工具集，采用单体仓库（monorepo）结构，包含多个相互依赖的包。

## 核心理念

- **最小化设计**：提供核心功能，通过扩展机制实现定制化
- **统一接口**：为不同 LLM 提供者提供一致的 API 接口
- **可扩展性**：支持插件、技能、主题等自定义功能
- **多平台支持**：终端、Web、Slack 等多种交互方式

## 包结构概览

```
pi-mono/
├── packages/
│   ├── ai/              # 统一的 LLM API 库
│   ├── agent/           # 代理运行时框架
│   ├── coding-agent/    # 交互式编码代理 CLI
│   ├── tui/             # 终端用户界面组件库
│   ├── web-ui/          # Web 用户界面组件库
│   ├── mom/             # Slack 机器人
│   └── pods/            # GPU 容器部署管理工具
```

## 核心包详解

### 1. @mariozechner/pi-ai (核心 LLM 接口)

**职责**：为各种 LLM 提供商提供统一的接口

**主要特性**：
- 支持 20+ 个 LLM 提供商（OpenAI、Anthropic、Google、Mistral 等）
- 工具调用（函数调用）支持
- 图像输入支持
- 思维/推理能力支持
- 流式传输和非流式传输 API
- 跨提供商上下文传递
- 成本跟踪和令牌计数
- OAuth 认证支持

**核心概念**：
- `Model<TApi>`：模型配置接口
- `Context`：对话上下文（系统提示、消息历史、工具）
- `Message`：消息类型（用户、助手、工具结果）
- `Tool`：工具定义（使用 TypeBox 进行类型安全验证）
- `AssistantMessageEventStream`：事件流接口

**架构模式**：
```
API 注册表 → 提供商实现 → 流处理函数 → 事件发射器
```

### 2. @mariozechner/pi-agent-core (代理框架)

**职责**：状态管理代理，支持工具执行和事件流

**核心组件**：
- `Agent`：主代理类，管理会话状态
- `AgentLoop`：代理循环逻辑
- 事件系统：实时更新 UI 的事件流
- 工具管理系统：动态工具注册和执行

**关键特性**：
- 声明式状态管理
- 实时事件订阅
- 工具执行生命周期管理
- 会话持久化
- 扩展点支持

### 3. @mariozechner/pi-coding-agent (编码代理 CLI)

**职责**：面向开发者的交互式编码助手

**主要功能**：
- 交互式终端界面
- 文件操作工具（读取、写入、编辑、搜索）
- 会话管理和分支
- 上下文压缩
- 扩展系统（插件、技能、主题）
- 包管理（npm、git 包安装）

**运行模式**：
- 交互模式：完整的 TUI 体验
- 打印模式：一次性响应输出
- JSON 模型：结构化事件输出
- RPC 模式：进程间通信

### 4. @mariozechner/pi-tui (终端 UI 库)

**职责**：高性能终端用户界面组件

**核心技术**：
- 差分渲染：只更新变化的部分
- 同步输出：使用 CSI 2026 避免闪烁
- 组件系统：可组合的 UI 组件
- 输入处理：键盘事件和自动完成

**主要组件**：
- `Editor`：多行文本编辑器
- `Input`：单行输入框
- `SelectList`：选择列表
- `SettingsList`：设置面板
- `Markdown`：Markdown 渲染
- `Image`：内联图像显示

### 5. @mariozechner/pi-web-ui (Web UI 组件)

**职责**：基于 Web Components 的聊天界面

**技术栈**：
- mini-lit Web Components
- Tailwind CSS v4
- IndexedDB 存储

**核心功能**：
- 聊天面板组件
- 附件处理（PDF、DOCX、图片等）
- 工件系统（HTML、SVG、Markdown）
- 存储管理
- CORS 代理支持

### 6. @mariozechner/pi-mom (Slack 机器人)

**职责**：在 Slack 中运行的自主代理

**特色功能**：
- 自主环境管理（自动安装工具）
- 多通道隔离
- 事件调度系统
- 技能系统（CLI 工具包装）
- 内存系统（全局和通道特定）

**安全考虑**：
- Docker 沙箱模式
- 凭据隔离
- 访问控制

### 7. @mariozechner/pi (GPU 部署工具)

**职责**：在 GPU 容器上部署和管理 LLM

**主要功能**：
- vLLM 自动配置
- 多模型管理
- GPU 分配优化
- OpenAI 兼容 API
- 预定义模型配置

**支持的提供商**：
- DataCrunch（推荐，支持 NFS 共享存储）
- RunPod（良好的持久存储）
- Vast.ai、AWS EC2 等

## 数据模型

### 消息系统

```
Message (基类型)
├── UserMessage: 用户输入
├── AssistantMessage: 助手响应（含工具调用）
└── ToolResultMessage: 工具执行结果

Content Blocks:
├── TextContent: 文本内容
├── ThinkingContent: 思维/推理内容
├── ImageContent: 图像内容
└── ToolCall: 工具调用
```

### 会话管理

```
Session
├── SessionEntry (JSONL 条目)
│   ├── SessionMessageEntry: 消息条目
│   ├── CompactionEntry: 压缩摘要
│   ├── ModelChangeEntry: 模型变更
│   └── CustomEntry: 自定义条目
└── Context: 当前 LLM 上下文
```

### 工具系统

```
Tool (定义)
└── AgentTool (可执行工具)
    ├── name: 工具名称
    ├── description: 描述
    ├── parameters: TypeBox 模式
    └── execute: 执行函数
```

## 扩展系统

### 插件架构

```
Extension System
├── ExtensionAPI: 插件接口
├── ExtensionRuntime: 运行时环境
├── Tool Registration: 工具注册
├── Command Registration: 命令注册
└── Event Handlers: 事件处理器
```

### 技能系统

```
Skill
├── SKILL.md: 技能描述文件（含 frontmatter）
├── 脚本文件: 可执行脚本
└── 依赖项: npm 包或其他资源
```

## 存储架构

### 本地存储

```
~/.pi/
├── agent/           # 编码代理配置
│   ├── sessions/    # 会话文件（JSONL）
│   ├── extensions/  # 插件
│   ├── skills/      # 技能
│   ├── prompts/     # 提示模板
│   └── themes/      # 主题
├── mom/             # Slack 机器人数据
└── pods/            # GPU 部署配置
```

### Web 存储

```
IndexedDB
├── settings: 键值对设置
├── providerKeys: 提供商 API 密钥
├── sessions: 聊天会话
└── customProviders: 自定义提供商
```

## 事件驱动架构

### 代理事件流

```
AgentEvent
├── agent_start/agent_end: 代理生命周期
├── turn_start/turn_end: 回合生命周期
├── message_start/message_update/message_end: 消息生命周期
└── tool_execution_start/tool_execution_update/tool_execution_end: 工具执行
```

### LLM 事件流

```
AssistantMessageEvent
├── start: 流开始
├── text_start/text_delta/text_end: 文本块
├── thinking_start/thinking_delta/thinking_end: 思维块
├── toolcall_start/toolcall_delta/toolcall_end: 工具调用
├── done: 完成
└── error: 错误
```

## 认证与安全

### API 密钥管理

```
认证方式
├── 环境变量: OPENAI_API_KEY, ANTHROPIC_API_KEY 等
├── OAuth 登录: /login 命令
└── 动态解析: getApiKey 回调函数
```

### 安全实践

1. **凭据隔离**：每个环境独立存储
2. **沙箱执行**：Docker 容器隔离
3. **权限控制**：最小权限原则
4. **审计日志**：完整操作记录
5. **访问控制**：团队级别的实例隔离

## 部署架构

### 开发环境

```
本地开发
├── npm run dev: 监视模式构建
├── 单元测试: npm test
└── 类型检查: npm run check
```

### 生产部署

```
发布流程
├── 版本同步: 所有包共享相同版本号
├── 变更日志: 自动生成更新日志
├── npm 发布: 自动发布到 npm
└── Git 标签: 版本标记
```

## 性能优化

### 内存管理

1. **上下文压缩**：自动压缩旧消息
2. **差分渲染**：只重绘变化部分
3. **缓存策略**：智能缓存机制
4. **流式处理**：实时数据流处理

### 并发控制

1. **工具执行队列**：有序工具调用
2. **请求批处理**：合并相似请求
3. **连接池**：HTTP 连接复用
4. **超时管理**：合理的超时设置

## 监控与调试

### 日志系统

```
日志级别
├── error: 错误信息
├── warn: 警告信息
├── info: 一般信息
└── debug: 调试信息
```

### 性能监控

1. **令牌使用统计**：输入/输出令牌计数
2. **成本跟踪**：实时成本计算
3. **响应时间**：API 响应延迟
4. **错误率**：失败请求统计

## 最佳实践

### 开发规范

1. **类型安全**：避免使用 `any` 类型
2. **错误处理**：完善的错误处理机制
3. **测试覆盖**：充分的单元测试
4. **文档完善**：详细的 API 文档

### 扩展开发

1. **声明合并**：使用 TypeScript 声明合并扩展类型
2. **事件驱动**：通过事件系统集成
3. **工具注册**：标准化工具定义
4. **配置管理**：清晰的配置接口

## 未来发展方向

1. **更多提供商支持**：持续增加新的 LLM 提供商
2. **增强扩展系统**：更强大的插件能力
3. **性能优化**：进一步提升响应速度
4. **用户体验改进**：更好的交互设计
5. **企业级功能**：RBAC、审计等企业需求

---

*本文档基于 pi-mono 项目版本 0.51.6 生成*