"""Validação de demanda com Google Autocomplete (grátis). Se as pessoas digitam algo
parecido com o problema, há um sinal real de busca. Sinal baixo NÃO prova ausência de demanda."""
import json, re, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import config

STOP = {"para", "como", "com", "sem", "uma", "que", "dos", "das", "por", "seu", "sua", "mais", "pra"}

@lru_cache(maxsize=2048)
def suggestions(term: str):
    url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(
        {"client": "firefox", "hl": "pt-BR", "gl": "br", "q": term})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT) as r:
        return tuple(json.loads(r.read().decode("utf-8", "ignore"))[1])

def _tokens(t):
    return {w for w in re.findall(r"\w+", t.lower()) if len(w) > 3 and w not in STOP}

def _relevant(term, sugs):
    tk = _tokens(term)
    if not tk:
        return []
    need = max(1, len(tk) // 2)
    return [s for s in sugs if len(tk & _tokens(s)) >= need]

def check_idea(idea):
    terms = idea.get("termos_busca") or [idea.get("micro_nicho", "")]
    per_term, scores, errors = {}, [], 0
    for term in [t for t in terms if t][:3]:
        try:
            full = _relevant(term, suggestions(term))
            head_q = " ".join(term.split()[:3])
            head = full if head_q == term else _relevant(term, suggestions(head_q))
        except Exception:
            errors += 1
            continue
        per_term[term] = full[:5]
        scores.append(min(1.0, (2 * len(full) + len(head)) / 10))
    idea["demanda"] = {"sinal": round(100 * sum(scores) / len(scores)) if scores else None,
                       "termos": per_term}
    return idea

def check_all(ideas):
    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(check_idea, ideas))
