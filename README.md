# AI 方案助手

AI 方案助手是一个面向普通用户的 AI 应用方案生成工具。用户只需要选择一个场景，写下自己的需求，系统就会生成清晰的 AI 应用方案，包括功能设计、落地步骤、风险提醒和参考依据。

## 适合展示的能力

- RAG：根据内置资料和用户补充资料检索参考依据。
- Agent 工作流：用“理解需求、查找资料、组织方案、检查风险、输出结果”五步展示处理过程。
- 安全护栏：提示隐私、凭证、高风险行业和提示词注入等风险。
- 评测指标：用普通人能看懂的“依据充分、回答相关、覆盖完整、风险较低”展示可信度。
- 动态效果：Canvas 数据流背景、步骤进度动画、方案打字机输出。
- 后端工程：FastAPI + Pydantic，提供状态查询、资料注入和方案生成接口。

## 页面怎么用

1. 选择一个场景模板，例如“简历教练”“客服助手”“学习顾问”“代码评审”。
2. 在输入框里写下你想做的 AI 应用需求。
3. 点击“生成 AI 方案”。
4. 查看系统生成的方案说明、下一步计划、风险提醒和参考资料。
5. 如果有额外资料，可以粘贴到“补充资料”区域并点击“加入资料”，之后再次生成。

## 本地运行

如果要接入 DeepSeek，请先设置环境变量。不要把 API Key 写进代码。

PowerShell 临时设置：

```powershell
$env:DEEPSEEK_API_KEY="你的新 DeepSeek API Key"
$env:DEEPSEEK_MODEL="deepseek-v4-flash"
```

也可以参考 `.env.example` 自己配置环境变量。注意：当前项目不会自动读取 `.env` 文件，如果想用 `.env`，需要你在启动前手动加载或后续安装 `python-dotenv`。

```powershell
cd D:\OneDrive\桌面\codex\ai-command-center
.\.venv\Scripts\python.exe backend\main.py
```

或者：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8010
```

打开：

```text
http://127.0.0.1:8010
```

## 简历描述

AI 方案助手 | Python · FastAPI · RAG · Agent Workflow · Guardrails

独立设计并开发面向普通用户的 AI 应用方案生成工具，用户输入业务想法后，系统自动完成需求理解、知识检索、方案组织、风险检查和结构化输出。后端基于 FastAPI 实现资料注入、Top-K 检索、Agent 工作流运行和多维可信度评估；前端使用 HTML/CSS/JavaScript 构建清晰易用的交互页面，提供场景模板、三步引导、动态进度、打字机输出、风险提醒和引用来源展示。项目覆盖 RAG、Agent 编排、模型安全护栏、AI 评测指标、前后端交互和产品化体验设计。

## DeepSeek 接入说明

项目会读取 `DEEPSEEK_API_KEY`。如果配置了 Key，生成方案时会调用 DeepSeek API；如果没有配置，系统会自动使用本地规则生成，方便无网络或无 Key 时演示。

DeepSeek 官方文档说明其 OpenAI 兼容接口 base URL 为 `https://api.deepseek.com`，当前推荐模型包括 `deepseek-v4-flash` 和 `deepseek-v4-pro`。本项目默认使用 `deepseek-v4-flash`，可通过 `DEEPSEEK_MODEL` 修改。
