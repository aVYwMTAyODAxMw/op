"""Configurações centrais. Edite aqui sem mexer na lógica."""
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Provedor de IA: "demo" (offline, sem custo) | "anthropic" | "openai" ---
PROVIDER = os.getenv("EBOOK_PROVIDER", "demo").lower()
MODEL = os.getenv("EBOOK_MODEL", "claude-sonnet-5-5")  # para openai ex.: gpt-4o
MAX_TOKENS = 8000

# --- Quantidades ---
BATCH_SIZE = 10          # ideias pedidas por chamada à IA
BEST_MODE_POOL = 50      # ideias geradas no modo MELHORES OPORTUNIDADES
MAX_IDEAS = 30           # limite do campo "quantidade" na interface

# --- Pontuação (0-100): chave -> (rótulo, pontos máximos). Deve somar 100. ---
SCORING = {
    "intensidade_problema": ("Intensidade do problema", 20),
    "clareza_publico": ("Clareza do público", 15),
    "intencao_compra": ("Intenção de compra", 20),
    "diferenciacao": ("Diferenciação", 15),
    "transformacao": ("Potencial de transformação", 10),
    "producao_ia": ("Facilidade de produção com IA", 10),
    "concorrencia_oportunidade": ("Concorrência/oportunidade", 10),
}

# Pontuação mínima por nível de "potencial comercial"
MIN_SCORE = {"baixo": 0, "médio": 60, "alto": 75}

# Micro-nichos genéricos que são descartados no modo MELHORES OPORTUNIDADES
GENERIC_NICHES = {
    "emagrecimento", "relacionamentos", "dinheiro", "produtividade", "treino",
    "ansiedade", "marketing", "saúde", "finanças", "beleza", "negócios",
}

# --- Validação de demanda (Google Autocomplete, grátis, sem chave) ---
DEMAND_MAX_POINTS = 10   # o sinal de demanda soma/subtrai até ±10 pontos
DEMAND_TOP_N = 30        # só valida as N melhores (evita excesso de requisições)
HTTP_TIMEOUT = 6

# --- Crítico: 2ª passada de IA que tenta "matar" cada ideia ---
CRITIC_MAX_POINTS = 10   # nota do crítico soma/subtrai até ±10 pontos
CRITIC_BATCH = 15
