"""
Budget plan generator using Google Gemini API.
Generates A/B/C proposals with evidence binding (根拠拘束).
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Optional

from src.config import GEMINI_API_KEY, GEMINI_MODEL

genai = None


def _get_genai():
    """Lazy-load and configure google.generativeai."""
    global genai
    if genai is None:
        import google.generativeai as _genai
        if GEMINI_API_KEY:
            _genai.configure(api_key=GEMINI_API_KEY)
        genai = _genai
    return genai


@dataclass
class EvidenceItem:
    """A piece of evidence backing a claim."""
    evidence_id: str
    evidence_type: str  # "data" or "document"
    source: str         # e.g. "e-Stat 国勢調査 2020"
    query: str          # The query or reference used
    summary: str        # Brief description


@dataclass
class PolicyProposal:
    """A single policy proposal (A, B, or C plan)."""
    plan_id: str        # "A", "B", "C"
    title: str
    objective: str
    scheme: str
    cost_range: str
    kpi: list[str]
    implementation_structure: str
    risks_and_mitigations: list[dict]
    evidence_ids: list[str]


@dataclass
class BudgetDraftResult:
    """Complete budget draft output."""
    request_id: str
    prompt: str
    proposals: list[PolicyProposal]
    evidences: list[EvidenceItem]
    hypotheses: list[str]  # Claims without evidence (isolated)
    job_log: list[dict]


SYSTEM_PROMPT = """あなたは日本の自治体向けEBPM（根拠に基づく政策立案）支援AIです。
以下の制約を厳守してください：

1. 必ずA案・B案・C案の3つの施策案を提案する
2. 各施策案には以下を含める：
   - タイトル、狙い（目的）
   - 事業スキーム（実施方法）
   - 概算費用レンジ
   - KPI（3〜5個）
   - 実施体制
   - リスクと対策（2〜3個）
3. 全ての主張には必ず根拠（エビデンス）を紐づける
   - 根拠がない主張は「仮説」として明示する
4. 根拠は以下の形式で記載：
   [E-001] データソース名 | クエリ/参照 | 要約
5. 出力はJSON形式で返す

JSON出力形式:
{
  "proposals": [
    {
      "plan_id": "A",
      "title": "...",
      "objective": "...",
      "scheme": "...",
      "cost_range": "...",
      "kpi": ["..."],
      "implementation_structure": "...",
      "risks_and_mitigations": [{"risk": "...", "mitigation": "..."}],
      "evidence_ids": ["E-001", "E-002"]
    }
  ],
  "evidences": [
    {
      "evidence_id": "E-001",
      "evidence_type": "data",
      "source": "...",
      "query": "...",
      "summary": "..."
    }
  ],
  "hypotheses": ["根拠なしの主張がある場合ここに記載"]
}
"""


def generate_budget_draft(
    prompt: str,
    context_data: Optional[str] = None,
    rag_results: Optional[list[dict]] = None,
) -> BudgetDraftResult:
    """
    Generate a budget draft with A/B/C proposals.

    Args:
        prompt: User's budget request
        context_data: Additional statistical context
        rag_results: Retrieved documents from RAG pipeline

    Returns:
        BudgetDraftResult with proposals, evidences, and hypotheses
    """
    request_id = str(uuid.uuid4())[:8]
    job_log = [{"step": "generate", "request_id": request_id, "prompt": prompt}]

    if not GEMINI_API_KEY:
        return _mock_budget_result(request_id, prompt)

    # Build context
    user_message = f"## 予算案作成リクエスト\n\n{prompt}\n"
    if context_data:
        user_message += f"\n## 利用可能な統計データ\n\n{context_data}\n"
    if rag_results:
        user_message += "\n## 関連資料（RAG検索結果）\n\n"
        for doc in rag_results:
            user_message += f"- {doc.get('title', '')}: {doc.get('content', '')[:500]}\n"

    user_message += "\n\n上記に基づいて、JSON形式で3案の予算案を作成してください。"

    try:
        _genai = _get_genai()
        model = _genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(
            [
                {"role": "user", "parts": [{"text": SYSTEM_PROMPT}]},
                {"role": "model", "parts": [{"text": "承知しました。JSON形式でEBPMに基づく予算案を作成します。"}]},
                {"role": "user", "parts": [{"text": user_message}]},
            ],
            generation_config=_genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=8192,
            ),
        )

        raw_text = response.text
        job_log.append({"step": "llm_response", "length": len(raw_text)})

        # Parse JSON from response
        result = _parse_llm_response(raw_text, request_id, prompt, job_log)
        return result

    except Exception as e:
        job_log.append({"step": "error", "message": str(e)})
        return _mock_budget_result(request_id, prompt, error=str(e))


def _parse_llm_response(
    raw_text: str,
    request_id: str,
    prompt: str,
    job_log: list,
) -> BudgetDraftResult:
    """Parse LLM response and validate evidence binding."""
    # Extract JSON from response
    json_match = re.search(r'\{[\s\S]*\}', raw_text)
    if not json_match:
        job_log.append({"step": "parse_error", "message": "No JSON found in response"})
        return _mock_budget_result(request_id, prompt, error="JSON parse failed")

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        job_log.append({"step": "json_error", "message": str(e)})
        return _mock_budget_result(request_id, prompt, error=str(e))

    # Build evidence items
    evidences = []
    for ev in data.get("evidences", []):
        evidences.append(EvidenceItem(
            evidence_id=ev.get("evidence_id", ""),
            evidence_type=ev.get("evidence_type", "data"),
            source=ev.get("source", ""),
            query=ev.get("query", ""),
            summary=ev.get("summary", ""),
        ))

    evidence_ids_set = {e.evidence_id for e in evidences}

    # Build proposals with evidence validation
    proposals = []
    hypotheses = list(data.get("hypotheses", []))

    for p in data.get("proposals", []):
        bound_ids = [eid for eid in p.get("evidence_ids", []) if eid in evidence_ids_set]
        unbound_ids = [eid for eid in p.get("evidence_ids", []) if eid not in evidence_ids_set]

        if unbound_ids:
            hypotheses.append(f"[{p.get('plan_id', '?')}案] 根拠ID {unbound_ids} は未定義です")

        proposals.append(PolicyProposal(
            plan_id=p.get("plan_id", "?"),
            title=p.get("title", ""),
            objective=p.get("objective", ""),
            scheme=p.get("scheme", ""),
            cost_range=p.get("cost_range", ""),
            kpi=p.get("kpi", []),
            implementation_structure=p.get("implementation_structure", ""),
            risks_and_mitigations=p.get("risks_and_mitigations", []),
            evidence_ids=bound_ids,
        ))

    job_log.append({"step": "validated", "proposals": len(proposals), "evidences": len(evidences)})

    return BudgetDraftResult(
        request_id=request_id,
        prompt=prompt,
        proposals=proposals,
        evidences=evidences,
        hypotheses=hypotheses,
        job_log=job_log,
    )


def _mock_budget_result(
    request_id: str,
    prompt: str,
    error: str = "",
) -> BudgetDraftResult:
    """Generate a mock result for testing without API key."""
    evidences = [
        EvidenceItem("E-001", "data", "e-Stat 国勢調査 2020", "人口総数", "対象地域の人口動態データ"),
        EvidenceItem("E-002", "data", "e-Stat 経済センサス", "事業所数", "地域の産業構造データ"),
        EvidenceItem("E-003", "document", "総合計画 第5次", "基本構想", "自治体の中長期ビジョン"),
    ]
    proposals = [
        PolicyProposal("A", "積極投資型プラン", "地域活性化と人口増加を目指す",
                       "大規模施設整備＋交通インフラ改善", "50〜80億円",
                       ["定住人口+5%", "交流人口+20%", "新規事業所+30件"],
                       "官民連携PFI", [{"risk": "財政負担", "mitigation": "国庫補助金の活用"}],
                       ["E-001", "E-002"]),
        PolicyProposal("B", "段階的整備型プラン", "既存資源を活用しつつ段階的に整備",
                       "既存施設改修＋ソフト事業", "20〜40億円",
                       ["住民満足度+10pt", "施設利用率+15%", "イベント参加者+50%"],
                       "直営＋業務委託", [{"risk": "効果の発現が遅い", "mitigation": "短期KPIの設定"}],
                       ["E-001", "E-003"]),
        PolicyProposal("C", "最小投資型プラン", "最小限の投資でソフト施策を中心に実施",
                       "デジタル化＋コミュニティ支援", "5〜15億円",
                       ["デジタル利用率+30%", "コミュニティ活動参加+20%"],
                       "直営", [{"risk": "変化が小さい", "mitigation": "成功事例の横展開"}],
                       ["E-002", "E-003"]),
    ]
    hypotheses = []
    if error:
        hypotheses.append(f"[システム] API呼び出しエラー: {error}")

    return BudgetDraftResult(
        request_id=request_id,
        prompt=prompt,
        proposals=proposals,
        evidences=evidences,
        hypotheses=hypotheses if hypotheses else ["（仮説なし — 全主張に根拠が紐づいています）"],
        job_log=[{"step": "mock", "reason": error or "no_api_key"}],
    )
