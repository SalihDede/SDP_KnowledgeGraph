"""
LLM Knowledge Graph Benchmark - Karşılaştırma Arayüzü
Çalıştırma: streamlit run Benchmark/LLMPerformanceBenchmarkUI/app.py
"""

import json
import os
import glob
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="LLM KG Benchmark", layout="wide", page_icon="📊")

BENCHMARK_DIR = os.path.join(os.path.dirname(__file__), "..")

TASK_LABELS = {
    1: "Task 1 — Tail Entity",
    2: "Task 2 — Relation",
    3: "Task 3 — True Verify",
    4: "Task 4 — False Verify",
}


# ─── Veri yükleme ─────────────────────────────────────────────────────────────

@st.cache_data
def load_results() -> pd.DataFrame:
    pattern = os.path.join(BENCHMARK_DIR, "results_*.jsonl")
    files = glob.glob(pattern)
    if not files:
        return pd.DataFrame()

    rows = []
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("type") == "metadata":
                    continue
                rows.append(rec)

    df = pd.DataFrame(rows)
    df = df[df["score"] >= 0]  # belirsiz cevapları dışla
    df["task_label"] = df["task"].map(TASK_LABELS)
    return df


# ─── Sidebar ──────────────────────────────────────────────────────────────────

st.sidebar.title("🔧 Filtreler")

df_all = load_results()

if df_all.empty:
    st.error("Hiç sonuç dosyası bulunamadı. Önce benchmark'ı çalıştırın.")
    st.stop()

st.sidebar.caption(f"**{df_all['model'].nunique()}** model · **{len(df_all)}** kayıt")

all_models  = sorted(df_all["model"].unique())
all_sources = sorted(df_all["source"].unique())

sel_models  = st.sidebar.multiselect("Model", all_models, default=all_models)
sel_sources = st.sidebar.multiselect("Veri Kaynağı", all_sources, default=all_sources)
sel_tasks   = st.sidebar.multiselect("Task", list(TASK_LABELS.keys()),
                                     default=list(TASK_LABELS.keys()),
                                     format_func=lambda x: TASK_LABELS[x])

df = df_all[
    df_all["model"].isin(sel_models) &
    df_all["source"].isin(sel_sources) &
    df_all["task"].isin(sel_tasks)
].copy()

if df.empty:
    st.warning("Seçilen filtrelere uygun veri yok.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.button("🔄 Yenile", on_click=load_results.clear)


# ─── Tabs ─────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Genel Skorlar",
    "🎯 Task Karşılaştırması",
    "⏱️ Latency",
    "🔤 Token Kullanımı",
    "🔍 Detay",
])


# ── Tab 1: Genel Skorlar ──────────────────────────────────────────────────────

with tab1:
    st.header("Genel Model Skorları")

    overall = (
        df.groupby("model")["score"]
        .agg(accuracy=lambda s: s.mean(), count="count")
        .reset_index()
        .sort_values("accuracy", ascending=False)
    )
    overall["accuracy_pct"] = (overall["accuracy"] * 100).round(2)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Sıralama")
        display = overall[["model", "accuracy_pct", "count"]].copy()
        display.columns = ["Model", "Accuracy (%)", "Kayıt"]
        display.index = range(1, len(display) + 1)
        st.dataframe(display, use_container_width=True)

    with col2:
        fig = px.bar(
            overall, x="accuracy_pct", y="model", orientation="h",
            text="accuracy_pct", color="accuracy_pct",
            color_continuous_scale="RdYlGn", range_color=[0, 100],
            labels={"accuracy_pct": "Accuracy (%)", "model": ""},
            title="Genel Accuracy — Model Karşılaştırması",
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(coloraxis_showscale=False, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Model × Kaynak")
    pivot_src = (
        df.groupby(["model", "source"])["score"]
        .mean().mul(100).round(2).reset_index()
        .rename(columns={"score": "accuracy_pct"})
    )
    fig2 = px.bar(
        pivot_src, x="model", y="accuracy_pct", color="source", barmode="group",
        text="accuracy_pct", labels={"accuracy_pct": "Accuracy (%)", "model": ""},
        title="Kepler vs Codex — Model Bazında",
    )
    fig2.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    st.plotly_chart(fig2, use_container_width=True)


# ── Tab 2: Task Karşılaştırması ───────────────────────────────────────────────

with tab2:
    st.header("Task Bazında Model Performansı")

    task_model = (
        df.groupby(["model", "task", "task_label"])["score"]
        .mean().mul(100).round(2).reset_index()
        .rename(columns={"score": "accuracy_pct"})
        .sort_values("task")
    )

    fig3 = px.bar(
        task_model, x="task_label", y="accuracy_pct", color="model",
        barmode="group", text="accuracy_pct",
        labels={"accuracy_pct": "Accuracy (%)", "task_label": ""},
        title="Her Task için Model Karşılaştırması",
    )
    fig3.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig3.update_layout(xaxis_tickangle=0)
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown("---")
    st.subheader("Pivot Tablo — Model × Task")
    pivot = (
        df.groupby(["model", "task_label"])["score"]
        .mean().mul(100).round(2)
        .unstack("task_label")
        .reset_index()
    )
    pivot["Ortalama"] = pivot.iloc[:, 1:].mean(axis=1).round(2)
    pivot = pivot.sort_values("Ortalama", ascending=False)
    pivot.index = range(1, len(pivot) + 1)
    st.dataframe(
        pivot.style.background_gradient(cmap="RdYlGn", vmin=0, vmax=100,
                                         subset=pivot.columns[1:]),
        use_container_width=True,
    )


# ── Tab 3: Latency ────────────────────────────────────────────────────────────

with tab3:
    st.header("Latency Analizi")

    if "latency_s" not in df.columns:
        st.info("Latency verisi bulunamadı.")
    else:
        lat = df.groupby(["model", "task_label"])["latency_s"].mean().round(3).reset_index()

        fig4 = px.bar(
            lat, x="task_label", y="latency_s", color="model", barmode="group",
            text="latency_s",
            labels={"latency_s": "Ort. Süre (s)", "task_label": ""},
            title="Task Başına Ortalama Latency",
        )
        fig4.update_traces(texttemplate="%{text:.2f}s", textposition="outside")
        st.plotly_chart(fig4, use_container_width=True)

        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("1 Triple için Toplam Süre (4 Task)")
            total_lat = df.groupby(["model", "triple_index"])["latency_s"].sum().reset_index()
            total_avg = total_lat.groupby("model")["latency_s"].mean().round(3).reset_index()
            total_avg.columns = ["Model", "Ort. Toplam Süre (s)"]
            total_avg = total_avg.sort_values("Ort. Toplam Süre (s)")
            total_avg.index = range(1, len(total_avg) + 1)
            st.dataframe(total_avg, use_container_width=True)

        with col2:
            st.subheader("Latency Dağılımı (Box)")
            fig5 = px.box(
                df, x="model", y="latency_s", color="task_label",
                labels={"latency_s": "Süre (s)", "model": ""},
                title="Latency Dağılımı",
            )
            st.plotly_chart(fig5, use_container_width=True)


# ── Tab 4: Token Kullanımı ────────────────────────────────────────────────────

with tab4:
    st.header("Token Kullanımı")

    if "input_tokens" not in df.columns:
        st.info("Token verisi bulunamadı.")
    else:
        col1, col2 = st.columns(2)

        # Task başına ortalama token
        tok_task = df.groupby(["model", "task_label"])[["input_tokens", "output_tokens"]].mean().round(1).reset_index()

        with col1:
            fig6 = px.bar(
                tok_task, x="task_label", y="input_tokens", color="model",
                barmode="group", text="input_tokens",
                labels={"input_tokens": "Ort. Input Token", "task_label": ""},
                title="Task Başına Ortalama Input Token",
            )
            fig6.update_traces(texttemplate="%{text:.0f}", textposition="outside")
            st.plotly_chart(fig6, use_container_width=True)

        with col2:
            fig7 = px.bar(
                tok_task, x="task_label", y="output_tokens", color="model",
                barmode="group", text="output_tokens",
                labels={"output_tokens": "Ort. Output Token", "task_label": ""},
                title="Task Başına Ortalama Output Token",
            )
            fig7.update_traces(texttemplate="%{text:.0f}", textposition="outside")
            st.plotly_chart(fig7, use_container_width=True)

        st.markdown("---")
        st.subheader("Toplam Token Kullanımı (Tüm Tripleler)")

        tok_total = (
            df.groupby("model")[["input_tokens", "output_tokens"]]
            .sum().reset_index()
        )
        tok_total["total_tokens"] = tok_total["input_tokens"] + tok_total["output_tokens"]
        tok_total = tok_total.sort_values("total_tokens", ascending=False)
        tok_total.index = range(1, len(tok_total) + 1)
        tok_total.columns = ["Model", "Input Token", "Output Token", "Toplam Token"]
        st.dataframe(tok_total, use_container_width=True)

        fig8 = px.bar(
            tok_total, x="Model", y=["Input Token", "Output Token"],
            barmode="stack", title="Toplam Token — Input vs Output",
            labels={"value": "Token", "variable": ""},
        )
        st.plotly_chart(fig8, use_container_width=True)

        st.markdown("---")
        st.subheader("1 Triple için Ortalama Token (4 Task Toplamı)")
        tok_per_triple = (
            df.groupby(["model", "triple_index"])[["input_tokens", "output_tokens"]]
            .sum().reset_index()
            .groupby("model")[["input_tokens", "output_tokens"]]
            .mean().round(1).reset_index()
        )
        tok_per_triple["total"] = (tok_per_triple["input_tokens"] + tok_per_triple["output_tokens"]).round(1)
        tok_per_triple.columns = ["Model", "Ort. Input", "Ort. Output", "Ort. Toplam"]
        tok_per_triple.index = range(1, len(tok_per_triple) + 1)
        st.dataframe(tok_per_triple, use_container_width=True)


# ── Tab 5: Detay ──────────────────────────────────────────────────────────────

with tab5:
    st.header("Kayıt Detayı")

    col1, col2, col3 = st.columns(3)
    with col1:
        det_model  = st.selectbox("Model", sorted(df["model"].unique()))
    with col2:
        det_task   = st.selectbox("Task", list(TASK_LABELS.keys()), format_func=lambda x: TASK_LABELS[x])
    with col3:
        det_score  = st.selectbox("Sonuç", ["Tümü", "Doğru (1)", "Yanlış (0)"])

    det_df = df[(df["model"] == det_model) & (df["task"] == det_task)].copy()
    if det_score == "Doğru (1)":
        det_df = det_df[det_df["score"] == 1]
    elif det_score == "Yanlış (0)":
        det_df = det_df[det_df["score"] == 0]

    st.caption(f"{len(det_df)} kayıt")

    show_cols = ["triple", "task_input", "llm_predictions", "ground_truth", "score"]
    if "latency_s"    in det_df.columns: show_cols.append("latency_s")
    if "input_tokens" in det_df.columns: show_cols += ["input_tokens", "output_tokens"]
    if "source"       in det_df.columns: show_cols.insert(0, "source")

    st.dataframe(
        det_df[show_cols].reset_index(drop=True),
        use_container_width=True,
        height=500,
    )
