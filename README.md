# 🎙️ 智慧會議記錄助手

使用 **LangGraph** 實作的智慧會議記錄系統，可自動將語音轉換為：
1. 📝 **詳細逐字稿**（含時間軸）
2. 🎯 **重點摘要**

---

## 📊 系統架構圖

```
    +-----------+
    | __start__ |
    +-----------+
          |
          v
    +-----------+
    |    asr    |  ← 語音轉文字（呼叫 ASR API）
    +-----------+
          |
          v
+------------------+
|  minutes_taker   |  ← 產生詳細逐字稿
+------------------+
          |
          v
+------------------+
|   summarizer     |  ← 產生重點摘要
+------------------+
          |
          v
    +-----------+
    |   writer  |  ← 整合最終報告
    +-----------+
          |
          v
    +-----------+
    |  __end__  |
    +-----------+
```

---

## 🛠️ 安裝步驟

### 1. 建立虛擬環境（建議）
```bash
conda create -n langgraph-env python=3.11 -y
conda activate langgraph-env
```

### 2. 安裝套件
```bash
pip install -r requirements.txt
```

或手動安裝：
```bash
pip install langchain langchain-openai langgraph grandalf requests
```

---

## 📁 檔案結構

```
project/
├── meeting_assistant.py   # 主程式
├── requirements.txt       # 套件清單
├── README.md             # 說明文件
├── audio/                # 放置音檔
│   └── Podcast_EP14_30s.wav
└── out/                  # 輸出目錄（自動建立）
    ├── {task_id}.txt     # ASR 純文字結果
    ├── {task_id}.srt     # ASR SRT 結果
    └── meeting_report.md # 最終報告
```

---

## 🚀 使用方式

### 1. 準備音檔
將你的音檔放到 `./audio/` 資料夾

### 2. 修改設定（如需要）
編輯 `meeting_assistant.py` 中的設定：
```python
# 音檔路徑
AUDIO_PATH = "./audio/Podcast_EP14_30s.wav"

# LLM 設定
LLM_BASE_URL = "https://ws-02.wade0426.me/v1"
LLM_MODEL = "google/gemma-3-27b-it"
```

### 3. 執行程式
```bash
python meeting_assistant.py
```

---

## 📋 輸出範例

### 重點摘要
```markdown
## 🎯 重點摘要（Executive Summary）
### 主題：《努力但不費力》Podcast 導讀

本次會議重點討論了葛瑞格麥乞昂的《努力但不費力》一書。

**決策結論：**
* 鼓勵團隊成員重新審視「努力」的定義

**待辦事項（Action Items）：**
* 學習「不費力」的三個階段：狀態、行動、成果
```

### 詳細逐字稿
```markdown
## 📋 詳細記錄（Detailed Minutes）
### 會議發言紀錄

| **時間** | **發言內容** |
|----------|-------------|
| 00:00:00 - 00:00:03 | 歡迎來到天下文化 podcast |
| 00:00:03 - 00:00:10 | 今天要介紹一本非常棒的書 |
```

---

## 🔧 核心概念說明

### LangGraph 三大元件

| 元件 | 說明 | 本專案對應 |
|------|------|-----------|
| **State** | 共享的資料結構 | `MeetingState` |
| **Nodes** | 執行函式 | `asr_node`, `minutes_taker_node`, `summarizer_node`, `writer_node` |
| **Edges** | 控制流向 | `add_edge()` 定義節點間連結 |

### 流程說明

1. **ASR 節點**：上傳音檔 → 等待轉錄 → 取得 TXT/SRT
2. **逐字稿節點**：讀取 SRT → LLM 整理成表格
3. **摘要節點**：讀取 TXT → LLM 歸納重點
4. **寫作節點**：合併結果 → 輸出報告

---

## ⚠️ 注意事項

1. ASR API 處理時間約 30-60 秒，請耐心等待
2. 確保網路連線正常
3. 音檔格式建議使用 WAV
4. LLM 回應可能因模型不同而有差異

---

## 📚 參考資料

- [LangGraph 官方文件](https://langchain-ai.github.io/langgraph/)
- [LangChain 官方文件](https://python.langchain.com/)
- day3.pdf 課程講義

---

*課後練習 - AI/LLM 技術工作坊*
