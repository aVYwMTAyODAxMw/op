"""Interface (Streamlit). Rode com:  streamlit run app.py"""
import csv, io, json
import streamlit as st
import config, generator

st.set_page_config(page_title="Gerador de Ideias de Ebook", page_icon="💡", layout="centered")
st.title("💡 Gerador de Ideias de Ebook")
st.caption("Micro-nichos com problema específico, público específico e desejo forte.")

if config.PROVIDER == "demo":
    st.info("Modo DEMO (offline): 6 ideias de exemplo. Configure uma API no arquivo .env para gerar ideias reais.")
else:
    st.success(f"IA conectada: {config.PROVIDER} · {config.MODEL}")

with st.container(border=True):
    market = st.text_input("Quero explorar este mercado (opcional):", placeholder="ex.: beleza  (vazio = busca livre)")
    c1, c2 = st.columns(2)
    count = c1.number_input("Quantidade de ideias", 1, config.MAX_IDEAS, 10)
    spec = c2.select_slider("Nível de especificidade", options=[1, 2, 3, 4, 5], value=3)
    potential = st.select_slider("Potencial comercial", options=["baixo", "médio", "alto"], value="médio")
    best = st.checkbox(f"🏆 Modo MELHORES OPORTUNIDADES (gera {config.BEST_MODE_POOL}, filtra e mostra as melhores)")
    v1, v2 = st.columns(2)
    use_demand = v1.checkbox("📈 Validar demanda no Google", value=True)
    use_critic = v2.checkbox("🧐 Crítico (2ª revisão por IA)", value=True, disabled=config.PROVIDER == "demo")
    go = st.button("GERAR IDEIAS", type="primary", use_container_width=True)

if go:
    bar = st.progress(0.0, text="Gerando ideias...")
    try:
        ideas, report = generator.generate(int(count), spec, potential, market, best, validate_demand=use_demand, critic=use_critic,
                                            on_progress=lambda p: bar.progress(p))
        st.session_state["result"] = (ideas, report)
    except Exception as e:
        st.error(f"Erro ao gerar: {e}")
    bar.empty()

if "result" in st.session_state:
    ideas, report = st.session_state["result"]
    rem = ", ".join(f"{k}: {v}" for k, v in report["removidas"].items()) or "nenhuma"
    st.caption(f"Geradas: {report['geradas']} · Demanda verificada: {report['demanda_verificada']} · Mostrando: {len(ideas)} · Descartadas → {rem}")
    if not ideas:
        st.warning("Nenhuma ideia passou nos filtros. Reduza o potencial comercial ou gere novamente.")
    for n, i in enumerate(ideas, 1):
        with st.container(border=True):
            st.markdown(f"**IDEIA #{n}** · 🎯 **{i['pontuacao']}/100** (nota {i['nota_0_10']}/10)")
            st.subheader(i["titulo"])
            st.progress(i["pontuacao"] / 100)
            st.write(i["explicacao"])
            for label, key in [("Nicho", "nicho"), ("Micro-nicho", "micro_nicho"), ("Público", "publico"),
                               ("Problema", "problema"), ("Desejo", "desejo"), ("O que ensina", "o_que_ensina"),
                               ("Diferencial", "diferencial"), ("Ângulo de venda", "angulo_venda")]:
                st.markdown(f"**{label}:** {i[key]}")
            a, b, c = st.columns(3)
            a.metric("Preço", i["preco"]); b.metric("Concorrência", i["concorrencia"]); c.metric("Produção IA", i["producao_ia"])
            st.markdown(f"**Por que pode vender (potencial):** {i['justificativa']}")
            d = i.get("demanda", {})
            if d.get("sinal") is not None:
                st.markdown(f"**📈 Sinal de demanda (Google):** {d['sinal']}/100")
            else:
                st.caption("📈 Demanda não verificada (desativada ou sem internet).")
            cr = i.get("critico")
            if cr:
                st.markdown(f"**🧐 Crítico:** {cr['nota']:.0f}/10 — {cr['objecao']}")
            if i.get("teste_rapido"):
                st.markdown(f"**🧪 Teste rápido de mercado:** {i['teste_rapido']}")
            with st.expander("Detalhe da pontuação e buscas"):
                for k, (lab, mx) in config.SCORING.items():
                    st.write(f"{lab}: {i['notas'].get(k, 0)}/{mx}")
                for t, sg in d.get("termos", {}).items():
                    st.write(f"🔎 {t}: " + (" · ".join(sg[:3]) or "sem sugestões"))
    if ideas:
        st.download_button("⬇️ Baixar ideias (JSON)", json.dumps(ideas, ensure_ascii=False, indent=2),
                           "ideias_ebook.json", "application/json", use_container_width=True)
        cols = ["pontuacao", "titulo", "nicho", "micro_nicho", "publico", "problema", "desejo",
                "angulo_venda", "preco", "concorrencia", "producao_ia", "teste_rapido"]
        buf = io.StringIO()
        w = csv.DictWriter(buf, cols, extrasaction="ignore"); w.writeheader(); w.writerows(ideas)
        st.download_button("⬇️ Baixar planilha (CSV)", buf.getvalue().encode("utf-8-sig"),
                           "ideias_ebook.csv", "text/csv", use_container_width=True)
