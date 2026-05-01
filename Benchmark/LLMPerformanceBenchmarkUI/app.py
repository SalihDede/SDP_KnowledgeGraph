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
        # Dosya judge edilmiş mi tespit et
        fname = os.path.basename(path)
        is_judged = "_judged_" in fname
        # Judge model adını dosya isminden çıkar (sadece görsel etiket için)
        judge_tag = ""
        if is_judged:
            judge_part = fname.split("_judged_", 1)[1].replace(".jsonl", "")
            judge_tag = f" [judge: {judge_part}]"

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("type") == "metadata":
                    continue
                # Judge edilmiş dosyada model ismine etiket ekle
                if is_judged:
                    rec["model"] = rec["model"] + judge_tag
                rows.append(rec)

    df = pd.DataFrame(rows)
    df = df[df["score"] >= 0]
    df["task_label"] = df["task"].map(TASK_LABELS)
    return df


@st.cache_data
def load_test_dataset_results() -> pd.DataFrame:
    """Load results from test datasets (Wikipedia, KG-Gen, PromptOpt)."""
    test_files = [
        os.path.join(BENCHMARK_DIR, "datasetPerformance", "results_Wikipediatest.jsonl"),
        os.path.join(BENCHMARK_DIR, "datasetPerformance", "results_KG-Gentest.jsonl"),
        os.path.join(BENCHMARK_DIR, "datasetPerformance", "results_PromptOpttest.jsonl"),
    ]

    rows = []
    for path in test_files:
        if not os.path.exists(path):
            continue

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("type") == "metadata":
                    continue
                if rec.get("score", -1) >= 0:
                    rows.append(rec)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
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

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 Genel Skorlar",
    "🎯 Task Karşılaştırması",
    "⏱️ Latency",
    "🔤 Token Kullanımı",
    "🔍 Detay",
    "📈 Test Veri Setleri",
    "🚀 Optimizasyon Analizi",
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


# ── Tab 6: Test Veri Setleri ──────────────────────────────────────────────────

with tab6:
    st.header("Test Veri Setleri — Performans ve Kalite")

    df_test = load_test_dataset_results()

    if df_test.empty:
        st.warning("Test veri seti sonuçları bulunamadı. Önce evaluator.py'yi çalıştırın.")
    else:
        st.caption(f"**{len(df_test)}** test kaydı · **{df_test['dataset'].nunique()}** dataset · **{df_test['model'].nunique()}** model")

        # ─── Dataset Özeti ────────────────────────────────────────────────
        st.subheader("📊 Dataset Özeti")

        col1, col2, col3 = st.columns(3)
        cols = [col1, col2, col3]
        for idx, dataset in enumerate(sorted(df_test['dataset'].unique())):
            dataset_df = df_test[df_test['dataset'] == dataset]
            count = len(dataset_df)
            accuracy = (dataset_df['score'].sum() / count * 100) if count > 0 else 0
            with cols[idx % 3]:
                st.metric(
                    dataset.replace('test', ''),
                    f"{count} örnek",
                    delta=f"{accuracy:.1f}% accuracy"
                )

        st.markdown("---")

        # ─── Dataset × Model × Task ───────────────────────────────────────
        st.subheader("🎯 Dataset × Model × Task Performansı")

        dataset_model_task = (
            df_test.groupby(["dataset", "model", "task_label"])["score"]
            .agg(['mean', 'count'])
            .mul(100)
            .round(2)
            .reset_index()
            .rename(columns={'mean': 'accuracy_pct'})
        )

        pivot_display = dataset_model_task.pivot_table(
            index=['dataset', 'model'],
            columns='task_label',
            values='accuracy_pct',
            aggfunc='first'
        ).reset_index()

        # Ortalama ekle
        task_labels = [TASK_LABELS[i] for i in range(1, 5)]
        pivot_display['Ortalama'] = pivot_display[task_labels].mean(axis=1).round(2)
        pivot_display = pivot_display.sort_values(['dataset', 'Ortalama'], ascending=[True, False])
        pivot_display.index = range(1, len(pivot_display) + 1)

        st.dataframe(
            pivot_display.style.background_gradient(cmap="RdYlGn", vmin=0, vmax=100,
                                                     subset=task_labels + ['Ortalama']),
            use_container_width=True,
        )

        st.markdown("---")

        # ─── Dataset Bazında Karşılaştırma ───────────────────────────────
        st.subheader("📈 Dataset Bazında Model Performansı")

        dataset_acc = (
            df_test.groupby(["dataset", "model"])["score"]
            .mean().mul(100).round(2).reset_index()
            .rename(columns={"score": "accuracy_pct"})
            .sort_values(["dataset", "accuracy_pct"], ascending=[True, False])
        )

        fig_dataset = px.bar(
            dataset_acc, x="dataset", y="accuracy_pct", color="model",
            barmode="group", text="accuracy_pct",
            labels={"accuracy_pct": "Accuracy (%)", "dataset": ""},
            title="Test Veri Setleri — Model Başına Accuracy",
        )
        fig_dataset.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        st.plotly_chart(fig_dataset, use_container_width=True)

        st.markdown("---")

        # ─── Task Bazında Dataset Analizi ─────────────────────────────────
        st.subheader("🎯 Task Bazında Dataset Performansı")

        task_dataset = (
            df_test.groupby(["task_label", "dataset"])["score"]
            .mean().mul(100).round(2).reset_index()
            .rename(columns={"score": "accuracy_pct"})
        )

        fig_task_dataset = px.bar(
            task_dataset, x="task_label", y="accuracy_pct", color="dataset",
            barmode="group", text="accuracy_pct",
            labels={"accuracy_pct": "Accuracy (%)", "task_label": ""},
            title="Task Başına Dataset Performansı",
        )
        fig_task_dataset.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        st.plotly_chart(fig_task_dataset, use_container_width=True)

        st.markdown("---")

        # ─── Dataset Detayı ───────────────────────────────────────────────
        st.subheader("🔍 Dataset Detayı")

        col1, col2, col3 = st.columns(3)
        with col1:
            sel_dataset = st.selectbox("Dataset Seç", sorted(df_test['dataset'].unique()), key="ds_select")
        with col2:
            sel_model_test = st.selectbox("Model Seç", sorted(df_test['model'].unique()), key="model_test_select")
        with col3:
            sel_task_test = st.selectbox("Task Seç", list(TASK_LABELS.keys()), format_func=lambda x: TASK_LABELS[x], key="task_test_select")

        det_df_test = df_test[
            (df_test['dataset'] == sel_dataset) &
            (df_test['model'] == sel_model_test) &
            (df_test['task'] == sel_task_test)
        ].copy()

        st.caption(f"{len(det_df_test)} kayıt · Accuracy: {(det_df_test['score'].mean() * 100):.1f}%")

        show_cols_test = ["triple", "task_input", "llm_predictions", "ground_truth", "score"]
        if "latency_s" in det_df_test.columns:
            show_cols_test.append("latency_s")
        if "input_tokens" in det_df_test.columns:
            show_cols_test += ["input_tokens", "output_tokens"]
        if "source" in det_df_test.columns:
            show_cols_test.insert(0, "source")

        st.dataframe(
            det_df_test[show_cols_test].reset_index(drop=True),
            use_container_width=True,
            height=500,
        )


# ── Tab 7: Optimizasyon Analizi ───────────────────────────────────────────────

with tab7:
    st.header("🚀 Optimizasyon Tekniklerinin Performans Analizi")

    df_opt = load_test_dataset_results()
    df_opt = df_opt[df_opt['dataset'] == 'PromptOpttest'].copy()

    if df_opt.empty:
        st.warning("PromptOpt test sonuçları bulunamadı.")
    else:
        all_optimizations = sorted(df_opt['source'].unique())

        st.caption(f"**{len(all_optimizations)}** optimizasyon · **{len(df_opt)}** test kaydı")

        # ─── Optimizasyon Seçimi ──────────────────────────────────────
        st.markdown("### 📊 Optimizasyon Karşılaştırması")

        sel_opts = st.multiselect(
            "Karşılaştırılacak Optimizasyonları Seç",
            all_optimizations,
            default=all_optimizations,
            key="opt_select"
        )

        df_opt_filtered = df_opt[df_opt['source'].isin(sel_opts)].copy()

        if df_opt_filtered.empty:
            st.warning("Seçilen optimizasyonlar için veri yok.")
        else:
            # ─── Genel Accuracy Karşılaştırması ───────────────────────
            st.subheader("Genel Accuracy")

            opt_overall = (
                df_opt_filtered.groupby('source')['score']
                .agg(['sum', 'count'])
                .reset_index()
            )
            opt_overall.columns = ['source', 'correct', 'total']
            opt_overall['accuracy_pct'] = (opt_overall['correct'] / opt_overall['total'] * 100).round(2)
            opt_overall = opt_overall.sort_values('accuracy_pct', ascending=False)

            col1, col2 = st.columns([1, 2])

            with col1:
                display_opt = opt_overall[['source', 'accuracy_pct', 'total']].copy()
                display_opt.columns = ['Optimizasyon', 'Accuracy (%)', 'Test Sayısı']
                display_opt.index = range(1, len(display_opt) + 1)
                st.dataframe(display_opt, use_container_width=True)

            with col2:
                fig_opt = px.bar(
                    opt_overall, x="accuracy_pct", y="source", orientation="h",
                    text="accuracy_pct", color="accuracy_pct",
                    color_continuous_scale="RdYlGn", range_color=[0, 100],
                    labels={"accuracy_pct": "Accuracy (%)", "source": ""},
                    title="Optimizasyon Teknikleri — Accuracy Karşılaştırması",
                )
                fig_opt.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                fig_opt.update_layout(coloraxis_showscale=False, yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig_opt, use_container_width=True)

            st.markdown("---")

            # ─── Task Bazında Optimizasyon Performansı ────────────────
            st.subheader("Task Bazında Optimizasyon Performansı")

            opt_task = (
                df_opt_filtered.groupby(['source', 'task_label'])['score']
                .mean().mul(100).round(2).reset_index()
                .rename(columns={'score': 'accuracy_pct'})
            )

            fig_opt_task = px.bar(
                opt_task, x="task_label", y="accuracy_pct", color="source",
                barmode="group", text="accuracy_pct",
                labels={"accuracy_pct": "Accuracy (%)", "task_label": ""},
                title="Her Task için Optimizasyon Karşılaştırması",
            )
            fig_opt_task.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            st.plotly_chart(fig_opt_task, use_container_width=True)

            st.markdown("---")

            # ─── Pivot Tablo: Optimizasyon × Task ──────────────────────
            st.subheader("Pivot Tablo — Optimizasyon × Task")

            opt_pivot = (
                df_opt_filtered.groupby(['source', 'task_label'])['score']
                .mean().mul(100).round(2)
                .unstack('task_label')
                .reset_index()
            )
            task_labels = [TASK_LABELS[i] for i in range(1, 5)]
            opt_pivot['Ortalama'] = opt_pivot[task_labels].mean(axis=1).round(2)
            opt_pivot = opt_pivot.sort_values('Ortalama', ascending=False)
            opt_pivot.columns = ['Optimizasyon'] + task_labels + ['Ortalama']
            opt_pivot.index = range(1, len(opt_pivot) + 1)

            st.dataframe(
                opt_pivot.style.background_gradient(cmap="RdYlGn", vmin=0, vmax=100,
                                                    subset=task_labels + ['Ortalama']),
                use_container_width=True,
            )

            st.markdown("---")

            # ─── Model Bazında Optimizasyon Performansı ────────────────
            st.subheader("Model Bazında Optimizasyon Performansı")

            opt_model = (
                df_opt_filtered.groupby(['source', 'model'])['score']
                .mean().mul(100).round(2).reset_index()
                .rename(columns={'score': 'accuracy_pct'})
            )

            fig_opt_model = px.bar(
                opt_model, x="model", y="accuracy_pct", color="source",
                barmode="group", text="accuracy_pct",
                labels={"accuracy_pct": "Accuracy (%)", "model": ""},
                title="Model Başına Optimizasyon Karşılaştırması",
            )
            fig_opt_model.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_opt_model.update_layout(xaxis_tickangle=45)
            st.plotly_chart(fig_opt_model, use_container_width=True)

            st.markdown("---")

            # ─── Performance Metrikleri ────────────────────────────────
            st.subheader("📈 Detaylı Performance Metrikleri")

            metrics_cols = st.columns(len(sel_opts))

            for idx, opt in enumerate(sel_opts):
                opt_data = df_opt_filtered[df_opt_filtered['source'] == opt]
                accuracy = (opt_data['score'].sum() / len(opt_data) * 100) if len(opt_data) > 0 else 0

                with metrics_cols[idx]:
                    st.metric(
                        f"**{opt.upper()}**",
                        f"{accuracy:.1f}%",
                        delta=f"{len(opt_data)} test"
                    )
