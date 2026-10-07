# Gerador de Ideias de Ebook

**Stack:** Python + Streamlit. Uma interface web bonita em ~60 linhas, sem HTML/CSS/JS, e a lógica fica separada da tela.

## Arquivos
- `app.py` – interface (cards, controles, botão)
- `generator.py` – geração, pontuação, filtros, modo MELHORES OPORTUNIDADES, provedores de IA
- `prompts.py` – prompt do gerador (edite à vontade)
- `config.py` – quantidades, critérios de pontuação, provedor/modelo
- `.env.example` – modelo de configuração · `requirements.txt` – dependências

## Instalação
1. Instale Python 3.10+ (python.org).
2. Na pasta do projeto: `pip install -r requirements.txt`

## Executar
`streamlit run app.py` (abre no navegador). Sem configurar nada ele roda em **modo DEMO** (6 ideias de exemplo, sem custo).

## Conectar uma API de IA
1. Copie `.env.example` para `.env`.
2. Anthropic: `EBOOK_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=sua_chave`, `EBOOK_MODEL=claude-sonnet-5-5`
   OpenAI: `EBOOK_PROVIDER=openai`, `OPENAI_API_KEY=sua_chave`, `EBOOK_MODEL=gpt-4o`
3. Reinicie o app. Para trocar de modelo, só mude `EBOOK_MODEL`.
4. Outro provedor? Adicione um `if` na função `call_llm` em `generator.py` (ela só recebe texto e devolve texto).

## Alterar o prompt
Edite `prompts.py`: `SYSTEM_PROMPT` (regras e postura da IA), `USER_TEMPLATE` (pedido por lote) e `SPECIFICITY` (o que cada nível 1-5 significa).

## Configurar pontuação e quantidades
Em `config.py`: `SCORING` (critérios e pontos máximos), `MIN_SCORE` (corte por potencial), `BEST_MODE_POOL` (ex.: 50), `BATCH_SIZE`, `MAX_IDEAS`, `GENERIC_NICHES`.

## Modo MELHORES OPORTUNIDADES
Gera `BEST_MODE_POOL` ideias → descarta incompletas/genéricas → sem motivo de compra → difíceis de produzir com IA → abaixo do potencial → ordena por pontuação → mostra as melhores. Custa mais chamadas de API.

## Validação e crítico (novo)
- **Demanda (Google Autocomplete):** `validator.py` confere se as pessoas digitam frases parecidas com o problema (`termos_busca`). O sinal 0-100 soma/subtrai até `DEMAND_MAX_POINTS` pontos. Sinal baixo não prova que não há demanda (buscas muito específicas rendem poucas sugestões). Grátis e sem chave, mas precisa de internet.
- **Crítico:** segunda chamada de IA que tenta "matar" cada ideia (nota 0-10 e objeção). No modo MELHORES, descarta as que uma busca grátis resolve. Só funciona com API conectada.
- **Teste rápido de mercado:** cada ideia traz uma forma de validar em 48h com gasto mínimo. Teste as 3-5 melhores antes de produzir.
- **CSV:** botão para baixar as ideias em planilha.
