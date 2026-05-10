# Zhongkao-Zhong-Navigator 🚀

**Zhongkao-Zhong-Navigator** 是一款基于 Streamlit 和 DeepSeek AI 构建的中考语文基础知识冲刺 MVP 工具。它能够根据本地素材库，利用大模型的推理能力，实时生成符合中考风格的模拟题，并提供深度的逻辑关联解析。

## ✨ 核心功能

- **AI 动态命题**：基于 `chinese_assets.json` 素材，模拟中考真题第一大题风格。
- **三种挑战模式**：
  - **字音挑战**：专注考查多音字、形声字、易错字读音。
  - **成语辨析**：考查成语含义及在语境中的实际运用。
  - **随机乱斗**：综合考查字音、字形及文学常识。
- **深度解析**：AI 提供“逻辑关联记忆法”解析，拒绝死记硬背。
- **进度追踪**：实时统计答题正确率，激励学生持续练习。

## 🛠️ 技术栈

- **Frontend**: Streamlit
- **AI Engine**: DeepSeek (OpenAI Compatible API)
- **Data**: JSON based local assets
- **Styling**: Vanilla CSS within Streamlit

## 🚀 快速开始

1. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

2. **配置 API Key**：
   在项目根目录创建 `.env` 文件，或在启动后的侧边栏手动输入：
   ```env
   DEEPSEEK_API_KEY=your_api_key_here
   ```

3. **运行应用**：
   ```bash
   streamlit run app.py
   ```

## 📂 项目结构

- `app.py`: 主程序入口，负责 UI 渲染与状态管理。
- `utils.py`: 核心逻辑组件，包括数据加载与 AI 接口调用。
- `chinese_assets.json`: 本地素材数据库。
- `requirements.txt`: Python 依赖清单。

## 📝 免责声明
本项目生成的题目仅供参考，建议结合正式教材进行复习。

---
Built with ❤️ for every Zhongkao candidate.
