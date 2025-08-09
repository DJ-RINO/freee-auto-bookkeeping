import os
import yaml


DEFAULTS = {
    "thresholds": {"auto": 85, "assist_min": 65, "assist_max": 84},
    "tolerances": {"amount_jpy": 1, "days": 3},
    "weights": {"amount": 0.4, "date": 0.25, "name": 0.3, "tax_rate": 0.05},
    "similarity": {"name_algo": "jaro_winkler", "high_mark": 0.85, "min_candidate": 0.6},
    "ng_words": ["振込", "入金", "出金"],
}


def load_linking_config() -> dict:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "linking.yml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return DEFAULTS

    # shallow merge defaults
    merged = dict(DEFAULTS)
    for k, v in (cfg or {}).items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            mv = dict(merged[k])
            mv.update(v)
            merged[k] = mv
        else:
            merged[k] = v
    return merged


