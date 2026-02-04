import time
import requests
from pathlib import Path
from typing import TypedDict

# LangGraph 必要元件
from langgraph.graph import StateGraph, END

# LangChain 元件
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ============================================
# 🔧 設定區域（請根據需要修改）
# ============================================

# 音檔路徑（請修改為你的音檔位置）
AUDIO_PATH = "./audio/Podcast_EP14_30s.wav"

# LLM 設定
LLM_BASE_URL = "https://ws-02.wade0426.me/v1"
LLM_API_KEY = ""  # KEY 留空
LLM_MODEL = "google/gemma-3-27b-it"

# ASR API 設定
ASR_BASE = "https://3090api.huannago.com"
ASR_CREATE_URL = f"{ASR_BASE}/api/v1/subtitle/tasks"
ASR_AUTH = ("nutc2504", "nutc2504")

# ============================================
# 1. 初始化 LLM
# ============================================
llm = ChatOpenAI(
    base_url=LLM_BASE_URL,
    api_key=LLM_API_KEY,
    model=LLM_MODEL,
    temperature=0
)

# ============================================
# 2. 定義 State（共享狀態）
# ============================================
class MeetingState(TypedDict):
    """
    State 是 LangGraph 中所有節點共享的「黑板」
    每個節點都可以讀取和更新這些資料
    """
    audio_path: str           # 輸入：音檔路徑
    txt_content: str          # ASR 結果：純文字
    srt_content: str          # ASR 結果：SRT 格式（含時間軸）
    detailed_minutes: str     # 輸出：詳細逐字稿
    summary: str              # 輸出：重點摘要
    final_report: str         # 輸出：最終報告

# ============================================
# 3. 定義 Nodes（節點函數）
# ============================================

def asr_node(state: MeetingState) -> dict:
    """
    🎙️ ASR 節點：語音轉文字
    
    功能：
    - 上傳音檔到 ASR API
    - 等待轉錄完成
    - 取得 TXT（純文字）和 SRT（含時間軸）格式
    
    輸入：state["audio_path"]
    輸出：txt_content, srt_content
    """
    print("\n" + "="*50)
    print("🎙️ [ASR 節點] 開始語音轉文字...")
    print("="*50)
    
    audio_path = state["audio_path"]
    print(f"   📁 音檔路徑: {audio_path}")
    
    # 建立輸出目錄
    out_dir = Path("./out")
    out_dir.mkdir(exist_ok=True)
    
    # -------- 步驟 1: 建立 ASR 任務 --------
    print("   📤 上傳音檔到 ASR 服務...")
    try:
        with open(audio_path, "rb") as f:
            response = requests.post(
                ASR_CREATE_URL, 
                files={"audio": f}, 
                timeout=60, 
                auth=ASR_AUTH
            )
        response.raise_for_status()
        task_id = response.json()["id"]
        print(f"   ✅ 任務建立成功！任務 ID: {task_id}")
    except FileNotFoundError:
        print(f"   ❌ 錯誤：找不到音檔 {audio_path}")
        raise
    except Exception as e:
        print(f"   ❌ 上傳失敗: {e}")
        raise
    
    # -------- 步驟 2: 等待轉錄完成 --------
    txt_url = f"{ASR_BASE}/api/v1/subtitle/tasks/{task_id}/subtitle?type=TXT"
    srt_url = f"{ASR_BASE}/api/v1/subtitle/tasks/{task_id}/subtitle?type=SRT"
    
    def wait_download(url: str, file_type: str, max_tries: int = 300) -> str:
        """等待 ASR 處理完成並下載結果"""
        print(f"   🔄 等待 {file_type} 轉錄結果...")
        for i in range(max_tries):
            try:
                resp = requests.get(url, timeout=(5, 60), auth=ASR_AUTH)
                if resp.status_code == 200:
                    print(f"   ✅ {file_type} 轉錄完成！")
                    return resp.text
            except requests.exceptions.ReadTimeout:
                pass
            except Exception as e:
                print(f"   ⚠️ 請求錯誤: {e}")
            
            if i % 15 == 0 and i > 0:
                print(f"   ⏳ 仍在處理中... ({i}/{max_tries})")
            time.sleep(2)
        
        print(f"   ⚠️ {file_type} 轉錄超時")
        return ""
    
    # 取得 TXT 結果
    txt_text = wait_download(txt_url, "TXT", max_tries=300)
    if not txt_text:
        raise TimeoutError("TXT 轉錄逾時或失敗")
    
    # 取得 SRT 結果（有時間軸）
    srt_text = wait_download(srt_url, "SRT", max_tries=300)
    
    # -------- 步驟 3: 儲存結果 --------
    txt_path = out_dir / f"{task_id}.txt"
    txt_path.write_text(txt_text, encoding="utf-8")
    print(f"   💾 TXT 已儲存: {txt_path}")
    
    if srt_text:
        srt_path = out_dir / f"{task_id}.srt"
        srt_path.write_text(srt_text, encoding="utf-8")
        print(f"   💾 SRT 已儲存: {srt_path}")
    
    # 預覽內容
    print(f"\n   📄 轉錄內容預覽（前 200 字）：")
    print(f"   {txt_text[:200]}...")
    
    return {
        "txt_content": txt_text,
        "srt_content": srt_text or ""
    }


def minutes_taker_node(state: MeetingState) -> dict:
    """
    📝 逐字稿節點：產生詳細的時間軸逐字稿
    
    功能：
    - 讀取 SRT 內容（含時間軸）
    - 使用 LLM 整理成表格格式
    
    輸入：state["srt_content"] 或 state["txt_content"]
    輸出：detailed_minutes
    """
    print("\n" + "="*50)
    print("📝 [逐字稿節點] 產生詳細逐字稿...")
    print("="*50)
    
    srt_content = state.get("srt_content", "")
    txt_content = state.get("txt_content", "")
    
    # 優先使用 SRT（有時間軸）
    content_to_process = srt_content if srt_content else txt_content
    
    # 定義 Prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一位專業的會議記錄員。請將以下語音轉錄內容整理成詳細的逐字稿。

## 輸出要求：
1. 使用 Markdown 表格格式
2. 按時間順序列出每一句話
3. 保留時間戳（如果有的話）
4. 不要省略任何內容
5. 使用繁體中文

## 輸出格式範例：
## 📋 詳細記錄（Detailed Minutes）
### 會議發言紀錄 — Podcast

| **時間** | **發言內容** |
|----------|-------------|
| 00:00:00 - 00:00:03 | 歡迎來到天下文化 podcast，我是阿布阿哥。 |
| 00:00:03 - 00:00:10 | 今天要介紹一本非常棒的書... |
"""),
        ("user", "{content}")
    ])
    
    # 建立 Chain 並執行
    chain = prompt | llm | StrOutputParser()
    result = chain.invoke({"content": content_to_process})
    
    print("   ✅ 詳細逐字稿產生完成！")
    
    return {"detailed_minutes": result}


def summarizer_node(state: MeetingState) -> dict:
    """
    📊 摘要節點：產生重點摘要
    
    功能：
    - 讀取純文字內容
    - 使用 LLM 歸納重點
    
    輸入：state["txt_content"]
    輸出：summary
    """
    print("\n" + "="*50)
    print("📊 [摘要節點] 產生重點摘要...")
    print("="*50)
    
    txt_content = state.get("txt_content", "")
    
    # 定義 Prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一位專業的內容分析師。請閱讀以下語音轉錄內容，並產生一份重點摘要。

## 輸出要求：
1. 開頭標題：## 🎯 重點摘要（Executive Summary）
2. 列出主題名稱
3. 歸納 3-5 個關鍵重點
4. 如果有結論或建議，請標註
5. 如果有待辦事項，請列出
6. 使用繁體中文，條列式呈現

## 輸出格式範例：
## 🎯 重點摘要（Executive Summary）
### 主題：《努力但不費力》Podcast 導讀

本次會議重點討論了葛瑞格麥乞昂的《努力但不費力》一書。

**決策結論：**
* 鼓勵團隊成員重新審視「努力」的定義...

**待辦事項（Action Items）：**
* 學習「不費力」的三個階段：狀態、行動、成果
* 反思自身工作模式...
"""),
        ("user", "{content}")
    ])
    
    # 建立 Chain 並執行
    chain = prompt | llm | StrOutputParser()
    result = chain.invoke({"content": txt_content})
    
    print("   ✅ 重點摘要產生完成！")
    
    return {"summary": result}


def writer_node(state: MeetingState) -> dict:
    """
    📄 寫作節點：整合最終報告
    
    功能：
    - 合併逐字稿和摘要
    - 產生完整的會議報告
    
    輸入：state["detailed_minutes"], state["summary"]
    輸出：final_report
    """
    print("\n" + "="*50)
    print("📄 [寫作節點] 整合最終報告...")
    print("="*50)
    
    detailed_minutes = state.get("detailed_minutes", "")
    summary = state.get("summary", "")
    
    # 組合最終報告
    final_report = f"""# 📑 智慧會議紀錄報告

---

{summary}

---

{detailed_minutes}

---

*本報告由 LangGraph 智慧會議記錄助手自動產生*
*產生時間：{time.strftime("%Y-%m-%d %H:%M:%S")}*
"""
    
    print("   ✅ 最終報告整合完成！")
    
    return {"final_report": final_report}


# ============================================
# 4. 組裝 Graph
# ============================================
def build_meeting_graph():
    """
    建立會議記錄助手的 LangGraph
    
    圖結構說明：
    - asr: 語音轉文字
    - minutes_taker: 產生逐字稿
    - summarizer: 產生摘要
    - writer: 整合報告
    
    執行流程：asr -> minutes_taker -> summarizer -> writer -> END
    """
    print("\n🔧 建立 LangGraph 工作流程...")
    
    # 初始化 StateGraph
    workflow = StateGraph(MeetingState)
    
    # 加入節點
    workflow.add_node("asr", asr_node)
    workflow.add_node("minutes_taker", minutes_taker_node)
    workflow.add_node("summarizer", summarizer_node)
    workflow.add_node("writer", writer_node)
    
    # 設定入口點
    workflow.set_entry_point("asr")
    
    # 設定邊（Edge）- 定義節點間的流向
    workflow.add_edge("asr", "minutes_taker")
    workflow.add_edge("minutes_taker", "summarizer")
    workflow.add_edge("summarizer", "writer")
    workflow.add_edge("writer", END)
    
    # 編譯 Graph
    app = workflow.compile()
    
    print("   ✅ Graph 建立完成！")
    
    return app


# ============================================
# 5. 主程式
# ============================================
def main():
    """主程式進入點"""
    
    print("\n" + "="*60)
    print("🚀 智慧會議記錄助手 - LangGraph 版本")
    print("="*60)
    
    # 建立 Graph
    app = build_meeting_graph()
    
    # 顯示 Graph 結構
    try:
        print("\n📊 Graph 結構圖：")
        print(app.get_graph().draw_ascii())
    except Exception:
        print("（提示：安裝 grandalf 套件可顯示 ASCII 圖形）")
        print("   pip install grandalf")
    
    # 檢查音檔是否存在
    audio_path = Path(AUDIO_PATH)
    if not audio_path.exists():
        print(f"\n❌ 錯誤：找不到音檔 {AUDIO_PATH}")
        print("請確認音檔路徑是否正確，或修改 AUDIO_PATH 變數")
        return
    
    print(f"\n📁 音檔路徑: {AUDIO_PATH}")
    print(f"📁 輸出目錄: ./out/")
    
    # 初始化狀態
    initial_state: MeetingState = {
        "audio_path": str(audio_path),
        "txt_content": "",
        "srt_content": "",
        "detailed_minutes": "",
        "summary": "",
        "final_report": ""
    }
    
    # 執行 Graph
    print("\n" + "-"*60)
    print("🎬 開始執行工作流程...")
    print("-"*60)
    
    # 使用 stream 觀察每個節點的執行
    for event in app.stream(initial_state):
        for node_name in event.keys():
            print(f"\n✅ 節點 [{node_name}] 執行完成")
    
    # 取得最終結果
    final_state = app.invoke(initial_state)
    
    # 顯示最終報告
    print("\n" + "="*60)
    print("📋 最終報告")
    print("="*60)
    final_report = final_state.get("final_report", "無報告")
    print(final_report)
    
    # 儲存報告
    out_dir = Path("./out")
    out_dir.mkdir(exist_ok=True)
    report_path = out_dir / "meeting_report.md"
    report_path.write_text(final_report, encoding="utf-8")
    
    print("\n" + "="*60)
    print(f"✅ 報告已儲存至: {report_path}")
    print("="*60)


if __name__ == "__main__":
    main()


