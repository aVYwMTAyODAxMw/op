"""Lógica de geração (independente da interface)."""
import json, re
import config, prompts

REQUIRED = ["titulo", "explicacao", "nicho", "micro_nicho", "publico", "problema", "desejo",
            "o_que_ensina", "diferencial", "angulo_venda", "preco", "concorrencia",
            "producao_ia", "justificativa"]

# ---------- Provedores de IA (troque/adicione aqui) ----------
def call_llm(system: str, user: str) -> str:
    if config.PROVIDER == "anthropic":
        import anthropic
        r = anthropic.Anthropic().messages.create(
            model=config.MODEL, max_tokens=config.MAX_TOKENS, system=system,
            messages=[{"role": "user", "content": user}])
        return r.content[0].text
    if config.PROVIDER == "openai":
        from openai import OpenAI
        r = OpenAI().chat.completions.create(
            model=config.MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        return r.choices[0].message.content
    raise ValueError(f"Provedor desconhecido: {config.PROVIDER}")

def parse_json(text: str) -> list:
    text = re.sub(r"```(?:json)?", "", text)
    a, b = text.find("["), text.rfind("]")
    data = json.loads(text[a:b + 1])
    return data if isinstance(data, list) else []

# ---------- Pontuação e filtros ----------
def clean(i: dict) -> dict:
    for k in REQUIRED:
        i[k] = str(i.get(k, "") or "").strip()
    i["notas"] = i.get("notas") if isinstance(i.get("notas"), dict) else {}
    t = i.get("termos_busca") or []
    t = [x.strip() for x in t.split(";")] if isinstance(t, str) else [str(x).strip() for x in t]
    i["termos_busca"] = [x for x in t if x][:3]
    i["teste_rapido"] = str(i.get("teste_rapido", "") or "").strip()
    return i

def score(i: dict) -> dict:
    total = 0.0
    for k, (_, mx) in config.SCORING.items():
        try:
            v = float(i["notas"].get(k, 0))
        except (TypeError, ValueError):
            v = 0
        total += max(0, min(v, mx))
    i["pontuacao"] = round(total)
    i["nota_0_10"] = round(total / 10, 1)
    return i

def reject_reason(i: dict):
    if any(not i[k] for k in REQUIRED):
        return "incompleta"
    if (len(i["titulo"].split()) < 5 or len(i["micro_nicho"].split()) < 3
            or i["micro_nicho"].lower() in config.GENERIC_NICHES or len(i["publico"].split()) < 6):
        return "genérica"
    if len(i["diferencial"].split()) < 6 or len(i["angulo_venda"].split()) < 4:
        return "sem motivo de compra"
    if i["producao_ia"].lower().startswith("baix"):
        return "difícil de produzir com IA"
    return None

# ---------- Etapas extras ----------
def _clamp(v):
    return max(0, min(100, round(v)))

def critique(ideas):
    """2ª passada de IA: tenta 'matar' as ideias; ajusta a pontuação e marca as que a busca grátis resolve."""
    for s in range(0, len(ideas), config.CRITIC_BATCH):
        batch = ideas[s:s + config.CRITIC_BATCH]
        try:
            res = parse_json(call_llm(prompts.CRITIC_SYSTEM, prompts.build_critic_prompt(batch)))
        except Exception:
            continue
        for r in res:
            try:
                i = batch[int(r["indice"])]
                nota = max(0.0, min(10.0, float(r.get("nota", 5))))
            except (KeyError, ValueError, IndexError, TypeError):
                continue
            i["critico"] = {"nota": nota, "resolve_gratis": bool(r.get("resolve_gratis")),
                            "objecao": str(r.get("objecao", ""))}
            i["pontuacao"] = _clamp(i["pontuacao"] + (nota - 5) / 5 * config.CRITIC_MAX_POINTS)

def _apply_demand(ideas):
    import validator
    ideas.sort(key=lambda i: -i["pontuacao"])
    top = ideas[:config.DEMAND_TOP_N]
    validator.check_all(top)
    for i in top:
        sinal = i["demanda"]["sinal"]
        if sinal is not None:
            i["pontuacao"] = _clamp(i["pontuacao"] + (sinal - 50) / 50 * config.DEMAND_MAX_POINTS)
    return sum(1 for i in top if i["demanda"]["sinal"] is not None)

# ---------- Função principal ----------
def generate(count=10, specificity=3, potential="médio", market="", best_mode=False,
             validate_demand=True, critic=False, on_progress=None):
    """Retorna (lista_de_ideias, relatorio)."""
    pool = config.BEST_MODE_POOL if best_mode else count
    raw, tries = [], 0
    if config.PROVIDER == "demo":
        raw = demo_ideas(market)
    else:
        while len(raw) < pool and tries < 8:
            tries += 1
            n = min(config.BATCH_SIZE, pool - len(raw))
            avoid = "; ".join(i.get("titulo", "") for i in raw[-60:])
            raw += parse_json(call_llm(prompts.SYSTEM_PROMPT,
                              prompts.build_user_prompt(n, specificity, potential, market, avoid)))
            if on_progress:
                on_progress(min(len(raw) / pool, 1.0))
    removed = {}
    def drop(why):
        removed[why] = removed.get(why, 0) + 1

    kept = []
    for i in [score(clean(x)) for x in raw]:
        why = reject_reason(i) if best_mode else None  # funil só no modo MELHORES
        drop(why) if why else kept.append(i)

    critic_on = critic and config.PROVIDER != "demo" and bool(kept)
    if critic_on:
        critique(kept)
        if best_mode:
            keep2 = []
            for i in kept:
                drop("pesquisa grátis resolve") if i.get("critico", {}).get("resolve_gratis") else keep2.append(i)
            kept = keep2
    verified = _apply_demand(kept) if (validate_demand and kept) else 0

    if best_mode:
        keep3 = []
        for i in kept:
            drop("abaixo do potencial pedido") if i["pontuacao"] < config.MIN_SCORE.get(potential, 0) else keep3.append(i)
        kept = keep3
    for i in kept:
        i["nota_0_10"] = round(i["pontuacao"] / 10, 1)
    kept.sort(key=lambda i: -i["pontuacao"])
    return kept[:count], {"geradas": len(raw), "removidas": removed, "provedor": config.PROVIDER,
                          "demanda_verificada": verified, "critico": critic_on}

# ---------- Modo DEMO (offline) ----------
def _s(titulo, nicho, micro, publico, problema, desejo, ensina, dif, angulo, preco, conc, prod, notas, why):
    keys = list(config.SCORING)
    return {"titulo": titulo, "explicacao": f"{problema} O ebook ensina: {ensina}", "nicho": nicho,
            "micro_nicho": micro, "publico": publico, "problema": problema, "desejo": desejo,
            "o_que_ensina": ensina, "diferencial": dif, "angulo_venda": angulo, "preco": preco,
            "concorrencia": conc, "producao_ia": prod, "justificativa": why,
            "notas": dict(zip(keys, notas))}

DEMO = [
 _s("Almoço de 15 Minutos: Marmitas para Emagrecer para Quem Trabalha em Escritório e Odeia Cozinhar",
    "Alimentação", "Marmitas de emagrecimento para rotina de escritório",
    "Mulheres de 25-35 anos que trabalham em escritório, treinam 3x por semana e têm 15 minutos para preparar o almoço",
    "Comem mal ou pedem delivery por falta de tempo e travam o emagrecimento.",
    "Emagrecer sem gastar horas na cozinha",
    "Plano semanal, lista de compras, 30 receitas rápidas e checklist de preparo no domingo.",
    "Foco em tempo máximo de 15 minutos e orçamento, não em dieta genérica.",
    "Monte a semana inteira de almoços leves em 15 minutos por dia.", "R$19,90 - R$39,90",
    "Alta", "Alta", (16, 13, 16, 9, 8, 10, 5), "Dor recorrente e diária, público claro; a concorrência é alta, então o recorte de tempo é o diferencial."),
 _s("Primeiros Clientes como Designer Freelancer Usando Instagram Sem Aparecer",
    "Carreira freelancer", "Designers iniciantes que não querem mostrar o rosto",
    "Designers gráficos de 20-30 anos, iniciantes, tímidos, sem portfólio forte e sem clientes fixos",
    "Não conseguem os primeiros clientes e evitam se expor nas redes.",
    "Fechar os primeiros projetos pagos", "Perfil de portfólio, roteiros de DM, calendário de 30 dias de posts sem rosto.",
    "Resolve o bloqueio de não aparecer, que guias de freelancer ignoram.",
    "Primeiros clientes em 30 dias sem mostrar o rosto.", "R$27,00 - R$47,00",
    "Média", "Alta", (17, 13, 17, 12, 8, 9, 6), "Dor ligada a dinheiro com intenção de compra alta; nicho menor, mas bem definido."),
 _s("Quarto Pequeno Organizado Sem Comprar Móveis: 25 Soluções para Quem Aluga",
    "Casa e organização", "Organização de quarto pequeno para inquilinos",
    "Jovens de 20-32 anos que moram de aluguel em apartamento pequeno e não podem furar paredes",
    "Quarto bagunçado e sem espaço, sem verba nem permissão para reformar.",
    "Ganhar espaço sem gastar", "Mapa do quarto, soluções sem obra, lista de itens baratos e plano de fim de semana.",
    "Restrições reais: aluguel, sem furos e orçamento baixo.",
    "Ganhe espaço no quarto em um fim de semana, sem obra e sem móveis novos.", "R$14,90 - R$29,90",
    "Média", "Alta", (13, 12, 13, 11, 7, 10, 6), "Problema irritante e concreto; ticket baixo, bom para volume."),
 _s("Treino de 30 Minutos para Quem Trabalha Sentado 8 Horas e Treina em Academia de Condomínio",
    "Fitness", "Treino curto para sedentários de escritório em academia de condomínio",
    "Homens de 28-40 anos que trabalham sentados, com dor lombar leve e acesso só a academia pequena de condomínio",
    "Pouco tempo, equipamento limitado e postura ruim.",
    "Ganhar condicionamento e aliviar a lombar", "Treinos de 4 semanas, mobilidade, progressão e planilha de cargas.",
    "Adaptado a equipamentos limitados e ao corpo de quem fica sentado.",
    "Treine 30 minutos com o que o condomínio tem e pare de sentir a lombar.", "R$24,90 - R$39,90",
    "Alta", "Alta", (14, 14, 14, 10, 8, 9, 4), "Mercado grande, mas a entrada específica ajuda; concorrência alta limita a nota."),
 _s("Comida de Homem que Mora Sozinho: 30 Refeições Baratas e Rápidas para Quem Não Sabe Cozinhar",
    "Culinária", "Cozinha básica para quem começou a morar sozinho",
    "Homens de 18-28 anos que acabaram de sair da casa dos pais, sem experiência na cozinha e com orçamento apertado",
    "Gastam com delivery e comem mal.", "Comer bem gastando pouco",
    "Equipamentos mínimos, técnicas básicas, 30 receitas e lista de compras mensal.",
    "Parte do zero absoluto e do orçamento real de quem mora sozinho.",
    "Pare de gastar com delivery: 30 refeições simples e baratas.", "R$17,90 - R$29,90",
    "Média", "Alta", (14, 14, 15, 10, 8, 10, 6), "Momento de vida claro (mudança) gera busca por solução."),
 _s("Planilhas e Roteiros para Negociar Aumento de Aluguel Sem Ter Que se Mudar",
    "Finanças pessoais", "Negociação de reajuste de aluguel para inquilinos",
    "Inquilinos de 25-45 anos que receberam aviso de reajuste acima da inflação e não querem se mudar",
    "Reajuste abusivo com medo de perder o imóvel.", "Reduzir ou evitar o aumento",
    "Pesquisa de mercado local, argumentos, modelos de mensagem e contraproposta.",
    "Foco em script e argumentação prática, não em teoria jurídica.",
    "Negocie o reajuste com argumentos e modelos prontos.", "R$27,00 - R$49,00",
    "Baixa", "Alta", (17, 13, 17, 13, 8, 8, 9), "Dor financeira urgente e pouca oferta específica; não substitui orientação jurídica."),
]

def demo_ideas(market=""):
    import copy
    m = market.strip().lower()
    hits = [i for i in DEMO if m and m in json.dumps(i, ensure_ascii=False).lower()]
    return copy.deepcopy(hits or DEMO)

_EXTRAS = [
 (["marmita para emagrecer", "almoço rápido para marmita", "marmita fit para o trabalho"], "Poste 3 fotos de marmitas da semana e ofereça o plano de 7 dias em uma lista de espera."),
 (["como conseguir clientes como designer freelancer", "designer freelancer instagram sem aparecer", "primeiros clientes designer"], "Faça um carrossel 'como consegui o 1º cliente sem mostrar o rosto' e conte quantos pedem o guia."),
 (["como organizar quarto pequeno", "organizar quarto alugado sem furar parede", "ideias quarto pequeno barato"], "Poste um antes e depois com itens baratos e meça salvamentos e pedidos do checklist."),
 (["treino rápido para quem trabalha sentado", "treino academia de condomínio", "treino de 30 minutos academia"], "Publique um treino de exemplo e ofereça o plano de 4 semanas em troca do contato."),
 (["receitas para quem mora sozinho", "o que cozinhar morando sozinho", "comida barata e fácil para iniciantes"], "Poste 3 refeições de menos de R$10 e abra uma lista de espera do ebook."),
 (["como negociar aluguel", "reajuste de aluguel abusivo o que fazer", "como pedir desconto no aluguel"], "Publique um modelo de mensagem de negociação e veja quantas pessoas pedem o pacote completo."),
]
for _d, (_t, _q) in zip(DEMO, _EXTRAS):
    _d["termos_busca"], _d["teste_rapido"] = _t, _q
