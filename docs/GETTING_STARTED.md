# OmniChat 快速上手指南

Clone 本仓库后，按本文从安装到体验四个 Phase 功能。更完整的架构说明见根目录 [README.md](../README.md)。

## 环境要求

| 依赖 | 版本 / 说明 |
|------|-------------|
| Python | 3.10+（推荐 3.11 / 3.12） |
| Node.js | 18+ |
| pnpm | 推荐（亦可用 npm） |
| DeepSeek API Key | **必填**，否则无法对话 |
| 浏览器 | Chrome / Edge（语音输入需支持 Web Speech API） |

> **磁盘与网络：** Phase 2 首次使用 RAG 时会下载 BGE-M3 嵌入模型（约 2GB+），请预留空间；国内可在 `server/.env` 设置 `HF_ENDPOINT=https://hf-mirror.com` 加速。

---

## 1. 获取代码

```bash
git clone https://github.com/zzdream/OmniChat.git
cd OmniChat
```

SSH 方式：

```bash
git clone git@github.com:zzdream/OmniChat.git
cd OmniChat
```

---

## 2. 后端初始化

```bash
cd server
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `server/.env`，填入你的 DeepSeek 密钥：

```env
DEEPSEEK_API_KEY=sk-你的真实密钥
```

可选：开发阶段若频繁触发限流，可设置 `RATE_LIMIT_ENABLED=false`。

验证后端能否启动：

```bash
uvicorn main:app --reload --port 8000
```

浏览器打开 <http://localhost:8000/health>，应返回 `{"status":"ok"}`。确认后 `Ctrl+C` 停止。

---

## 3. 前端初始化

新开终端：

```bash
cd web
pnpm install
```

---

## 4. 启动项目

在**项目根目录**执行（推荐）：

```bash
pnpm dev
# 或
bash scripts/dev.sh
```

| 服务 | 地址 |
|------|------|
| 前端 | <http://localhost:5173> |
| 后端 API 文档 | <http://localhost:8000/docs> |

按 `Ctrl+C` 可同时停止前后端。

### 分别启动（可选）

```bash
# 终端 1
cd server && source venv/bin/activate && uvicorn main:app --reload --port 8000

# 终端 2
cd web && pnpm dev
```

---

## 5. 功能体验（Phase 1 → 4）

顶部导航栏可在各页面间切换。

### Phase 1 — 自由对话 `/chat`

1. 打开 <http://localhost:5173/chat>
2. 点击欢迎页的示例问题，或自行输入
3. 观察 SSE 流式输出、Markdown 与代码高亮
4. 工具栏可切换：**模型**、**温度**（0～2）、**角色设定**（System Prompt）
5. 左侧可新建 / 切换 / 删除会话；支持导出 Markdown / JSON

**试试这些问题：**

- 「用 Python 写一个快速排序」
- 「解释什么是 SSE 流式输出」

---

### Phase 2 — 知识库 RAG

分两步：**管理知识库** → **问答**。

#### 2.1 创建知识库 `/knowledge`

1. 打开 <http://localhost:5173/knowledge>
2. 点击 **「新建知识库」**，填写名称与描述
3. 选中知识库后，点击 **上传文档**

**支持格式：** txt、md、pdf、Word、Excel、PPT、png/jpg 等（图片走 OCR）

**限制：** 单文件最大 5MB；上传后状态变为「已完成」即可检索

> 首次上传会触发 BGE-M3 模型下载，可能等待数分钟，属正常现象。

#### 2.2 知识库问答 `/rag-chat`

1. 打开 <http://localhost:5173/rag-chat>
2. 左侧选择刚创建的知识库
3. 输入问题，例如：
   - 「这份资料主要讲了什么？」
   - 「帮我总结关键要点」
4. 回答下方会展示 **引用来源**（检索到的文档片段）

---

### Phase 3 — 工具 Agent `/agent-chat`

Agent 会**自主决定**何时调用工具，与 RAG 问答页「固定先检索」不同。

1. 打开 <http://localhost:5173/agent-chat>
2. （可选）左侧绑定知识库，可检索文档再回答
3. 输入问题，观察消息中的 **工具调用步骤**

**不绑知识库时可试：**

- 「123 乘以 456 等于多少？」→ 调用 `calculator`
- 「把 hello world 转成大写」→ 调用 `text_formatter`
- 「计算 (100 + 50) * 2」

**绑定知识库后可试：**

- 「这份资料主要讲了什么？」
- 「检索内容并把标题转成大写」

---

### Phase 4 — 3D 场景 Agent `/scene-agent`

在浏览器中加载 GLB 模型，用自然语言或语音控制场景。

1. 打开 <http://localhost:5173/scene-agent>
2. 左侧点击 **上传 GLB**，选择 `.glb` / `.gltf` 文件（单文件 ≤ 50MB）
3. 在 3D 画布中 **点击模型** 选中（蓝色边框）
4. 需要讲解时，点顶栏 **「解释选中模型」**
5. 在右侧输入框用文字控制，或点 **麦克风** 语音输入（Chrome / Edge 推荐）

**示例指令：**

- 「列出场景里有哪些模型」
- 「把第一个模型绕 Y 轴转 45 度」
- 「聚焦到选中的对象」
- 「把 bus 向右移 2 米」（对象名取决于上传时的文件名）

**绑定知识库后：**

- 「这份场景文档里有哪些设备？」
- 「检索资料并解释当前选中模型」

**操作说明：**

| 操作 | 方式 |
|------|------|
| 旋转视角 | 鼠标拖拽画布 |
| 缩放 | 滚轮 |
| 选中模型 | 单击模型 |
| 删除模型 | 左侧列表点击 × |
| 停止生成 | 输入框旁停止按钮 |

> 复杂 GLB（KTX2 贴图、Draco 压缩）已内置解码器，无需额外配置。

---

## 6. 页面一览

| 路由 | 功能 |
|------|------|
| `/chat` | Phase 1 自由对话 |
| `/knowledge` | Phase 2 知识库管理 |
| `/rag-chat` | Phase 2 知识库问答 |
| `/agent-chat` | Phase 3 工具 Agent |
| `/scene-agent` | Phase 4 3D 场景 Agent |

---

## 7. 运行测试（可选）

```bash
# 后端（LLM 已 mock，不会消耗 API 额度）
cd server && source venv/bin/activate && pytest

# 前端
cd web && pnpm typecheck && pnpm test:run
```

---

## 8. 常见问题

### 启动时报「未找到后端虚拟环境」

先完成 [§2 后端初始化](#2-后端初始化)，确保存在 `server/venv/`。

### 对话报错「API Key」或 401

检查 `server/.env` 中 `DEEPSEEK_API_KEY` 是否正确，修改后需重启后端。

### RAG 上传后一直「索引中」或很慢

首次运行需下载 BGE-M3 模型。在 `server/.env` 添加：

```env
HF_ENDPOINT=https://hf-mirror.com
```

重启后端后再试。查看终端日志确认是否有下载 / 解析错误。

### 知识库问答没有引用

确认文档状态为 **「已完成」**；问题尽量与文档内容相关。

### 3D 模型加载失败

- 确认文件为 `.glb` / `.gltf`，且小于 50MB
- 打开浏览器开发者工具 Console 查看具体报错
- 可换较简单的 GLB 测试

### 语音按钮不可用

Web Speech API 需要 HTTPS 或 `localhost`，推荐使用 Chrome / Edge。

### 端口被占用

修改后端端口：

```bash
uvicorn main:app --reload --port 8001
```

并同步修改 `web/.env` 中 `VITE_BASE_API=http://localhost:8001`。

---

## 9. 下一步

- 后端接口细节：[server/README.md](../server/README.md)
- 前端目录说明：[web/README.md](../web/README.md)
- LLM 参数与原理：[server/LLM_BASICS.md](../server/LLM_BASICS.md)
- Swagger 交互式 API：<http://localhost:8000/docs>
