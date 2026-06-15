"""Descoberta automática e persistência da pasta raiz no PC do usuário.

A raiz é a pasta que contém as pastas de contrato (26xxxx). Como o caminho do
SharePoint varia de máquina para máquina, tentamos auto-detectar e guardamos a
escolha em %APPDATA%\\NFExtrator\\config.json.

Personalize os padrões em ``auto_detect()`` para o nome de pasta usado na sua
organização (ex.: "ANO 2026", "CONTRATOS", etc.)."""
import os
import re
import json
import glob

APP_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "NFExtrator"
)
CFG_PATH = os.path.join(APP_DIR, "config.json")

_CONTRACT_DIR = re.compile(r"^26\d{4}")


def load():
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save(cfg):
    os.makedirs(APP_DIR, exist_ok=True)
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def looks_like_root(path):
    """True se a pasta contém ao menos uma subpasta de contrato (26xxxx)."""
    if not path or not os.path.isdir(path):
        return False
    try:
        for d in os.listdir(path):
            if _CONTRACT_DIR.match(d.strip()):
                return True
    except (PermissionError, OSError):
        pass
    return False


def auto_detect():
    """Procura a pasta de contratos em locais prováveis. Retorna lista de candidatos.

    Os padrões baratos (profundidade fixa) rodam primeiro; o glob recursivo (lento
    em SharePoint grande/online-only) só é usado se nada for achado — assim a
    abertura do app não trava.

    Personalize os padrões abaixo para o nome de pasta usado na sua organização."""
    home = os.path.expanduser("~")
    # Padrões baratos — ajuste para o nome da pasta de contratos da sua empresa
    cheap = [
        os.path.join(home, "*", "ANO 2026"),
        os.path.join(home, "*", "*", "ANO 2026"),
        os.path.join(home, "OneDrive*", "*", "ANO 2026"),
        os.path.join(home, "OneDrive*", "*", "*", "ANO 2026"),
    ]
    fallback = [os.path.join(home, "**", "ANO 2026")]

    def scan(patterns):
        out = []
        for pat in patterns:
            try:
                for p in glob.glob(pat, recursive="**" in pat):
                    p = os.path.normpath(p)
                    if p not in out and looks_like_root(p):
                        out.append(p)
            except Exception:
                continue
        return out

    found = scan(cheap)
    return found or scan(fallback)


def get_root():
    """Raiz salva (se ainda válida), senão tenta auto-detectar e salva a 1ª."""
    cfg = load()
    saved = cfg.get("root")
    if looks_like_root(saved):
        return saved
    cands = auto_detect()
    if cands:
        set_root(cands[0])
        return cands[0]
    return None


def set_root(path):
    cfg = load()
    cfg["root"] = os.path.normpath(path)
    save(cfg)
