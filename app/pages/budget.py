"""
Budget Draft page — EBPM budget proposal generator.
Generates A/B/C proposals with evidence binding using Gemini.
"""

import json

import streamlit as st
import pandas as pd

from app.components.stats_card import evidence_tag, hypothesis_box


def render_budget():
    """Render the Budget Draft page."""
    st.markdown("## 📋 Budget Draft — EBPM予算案生成")
    st.markdown(
        "プロンプトを入力して、根拠データ付きの予算案（A/B/C案）を自動生成します。"
    )

    # --- Input Form ---
    with st.form("budget_form"):
        st.markdown("### 📝 予算案リクエスト")

        col1, col2 = st.columns(2)
        with col1:
            target_area = st.text_input("対象地域", "東京都千代田区")
            period = st.text_input("対象期間", "令和8年〜令和10年")
        with col2:
            budget_limit = st.text_input("予算上限", "50億円")
            purpose = st.text_input("目的キーワード", "地域活性化、少子高齢化対策")

        prompt = st.text_area(
            "予算案リクエスト（自由記述）",
            value="子育て支援と高齢者福祉の充実に関する新規予算案を作成してください。"
                  "特に、公共交通空白地域における移動支援と、子育て世帯の定住促進策を重視してください。",
            height=120,
        )

        submitted = st.form_submit_button("🚀 予算案を生成", type="primary", use_container_width=True)

    # --- Generate ---
    if submitted:
        with st.spinner("🤖 Gemini APIで予算案を生成中..."):
            _generate_and_display(prompt, target_area, period, budget_limit, purpose)


def _generate_and_display(
    prompt: str,
    target_area: str,
    period: str,
    budget_limit: str,
    purpose: str,
):
    """Generate budget draft and display in 3 tabs."""
    try:
        from src.llm.budget_generator import generate_budget_draft
        from src.rag.retriever import search_documents, add_sample_documents, get_all_documents

        # Ensure sample docs
        if not get_all_documents():
            add_sample_documents()

        # Build full prompt
        full_prompt = prompt
        if target_area:
            full_prompt += f"\n対象地域: {target_area}"
        if period:
            full_prompt += f"\n期間: {period}"
        if budget_limit:
            full_prompt += f"\n予算上限: {budget_limit}"
        if purpose:
            full_prompt += f"\n目的: {purpose}"

        # RAG search
        rag_results = search_documents(prompt)

        # Generate
        result = generate_budget_draft(
            prompt=full_prompt,
            rag_results=rag_results,
        )

        # === Display in 3 tabs ===
        st.markdown("---")
        st.markdown(f"### 📄 生成結果 (Request ID: `{result.request_id}`)")

        tab1, tab2, tab3 = st.tabs(["💡 施策案", "📎 根拠", "🔄 再現性"])

        # --- Tab 1: Proposals ---
        with tab1:
            _render_proposals_tab(result)

        # --- Tab 2: Evidence ---
        with tab2:
            _render_evidence_tab(result)

        # --- Tab 3: Reproducibility ---
        with tab3:
            _render_reproducibility_tab(result)

    except Exception as e:
        st.error(f"❌ 生成エラー: {e}")
        st.exception(e)


def _render_proposals_tab(result):
    """Render the proposals tab."""
    if not result.proposals:
        st.warning("施策案が生成されませんでした。")
        return

    for proposal in result.proposals:
        plan_colors = {"A": "#667eea", "B": "#43e97b", "C": "#f093fb"}
        color = plan_colors.get(proposal.plan_id, "#888")

        st.markdown(f"""
        <div style="
            border-left: 4px solid {color};
            padding: 1rem 1.2rem;
            margin: 1rem 0;
            background: rgba(255,255,255,0.02);
            border-radius: 0 12px 12px 0;
        ">
            <h3 style="color: {color}; margin: 0 0 0.5rem 0;">
                {proposal.plan_id}案: {proposal.title}
            </h3>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**🎯 狙い:** {proposal.objective}")
            st.markdown(f"**📋 事業スキーム:** {proposal.scheme}")
            st.markdown(f"**💰 概算費用:** {proposal.cost_range}")
        with col2:
            st.markdown(f"**🏛 実施体制:** {proposal.implementation_structure}")
            st.markdown("**📊 KPI:**")
            for kpi in proposal.kpi:
                st.markdown(f"  - {kpi}")

        # Risks
        if proposal.risks_and_mitigations:
            with st.expander("⚠️ リスクと対策"):
                for rm in proposal.risks_and_mitigations:
                    risk = rm.get("risk", rm) if isinstance(rm, dict) else str(rm)
                    mitigation = rm.get("mitigation", "") if isinstance(rm, dict) else ""
                    st.markdown(f"- **リスク:** {risk}")
                    if mitigation:
                        st.markdown(f"  → **対策:** {mitigation}")

        # Evidence binding
        if proposal.evidence_ids:
            st.markdown("**紐づき根拠:**")
            for eid in proposal.evidence_ids:
                ev = next((e for e in result.evidences if e.evidence_id == eid), None)
                if ev:
                    evidence_tag(eid, ev.source)
        else:
            hypothesis_box(f"{proposal.plan_id}案には根拠が紐づいていません。仮説として扱ってください。")

        st.markdown("---")

    # Hypotheses
    if result.hypotheses:
        st.markdown("### ⚠️ 仮説（根拠未確認の主張）")
        for h in result.hypotheses:
            hypothesis_box(h)


def _render_evidence_tab(result):
    """Render the evidence tab."""
    if not result.evidences:
        st.info("根拠データはありません。")
        return

    st.markdown("### 📎 根拠データ一覧")

    # Evidence table
    ev_data = []
    for ev in result.evidences:
        ev_data.append({
            "ID": ev.evidence_id,
            "種別": "📊 データ" if ev.evidence_type == "data" else "📄 資料",
            "ソース": ev.source,
            "クエリ/参照": ev.query,
            "概要": ev.summary,
        })

    ev_df = pd.DataFrame(ev_data)
    st.dataframe(ev_df, use_container_width=True, hide_index=True)

    # Evidence detail cards
    st.markdown("### 根拠詳細")
    for ev in result.evidences:
        with st.expander(f"📎 {ev.evidence_id}: {ev.source}"):
            st.markdown(f"- **種別:** {ev.evidence_type}")
            st.markdown(f"- **ソース:** {ev.source}")
            st.markdown(f"- **クエリ:** `{ev.query}`")
            st.markdown(f"- **概要:** {ev.summary}")


def _render_reproducibility_tab(result):
    """Render the reproducibility tab."""
    st.markdown("### 🔄 再現性情報")
    st.markdown(f"**Request ID:** `{result.request_id}`")

    # Job log
    st.markdown("#### ジョブ実行ログ")
    for i, log_entry in enumerate(result.job_log):
        step = log_entry.get("step", "unknown")
        icon = {"generate": "🚀", "llm_response": "🤖", "validated": "✅",
                "mock": "🔧", "error": "❌"}.get(step, "📝")
        st.markdown(f"{icon} **Step {i+1}:** `{step}` — {json.dumps(log_entry, ensure_ascii=False)}")

    # Prompt
    st.markdown("#### 使用プロンプト")
    st.code(result.prompt, language="text")

    # Re-run button
    st.markdown("---")
    if st.button("🔄 同一条件で再実行"):
        st.rerun()

    # Export
    st.markdown("#### 📥 エクスポート")
    export_data = {
        "request_id": result.request_id,
        "prompt": result.prompt,
        "proposals": [
            {
                "plan_id": p.plan_id,
                "title": p.title,
                "objective": p.objective,
                "scheme": p.scheme,
                "cost_range": p.cost_range,
                "kpi": p.kpi,
                "evidence_ids": p.evidence_ids,
            }
            for p in result.proposals
        ],
        "evidences": [
            {
                "evidence_id": e.evidence_id,
                "source": e.source,
                "query": e.query,
                "summary": e.summary,
            }
            for e in result.evidences
        ],
        "hypotheses": result.hypotheses,
    }
    st.download_button(
        label="📥 JSON でダウンロード",
        data=json.dumps(export_data, ensure_ascii=False, indent=2),
        file_name=f"budget_draft_{result.request_id}.json",
        mime="application/json",
    )
