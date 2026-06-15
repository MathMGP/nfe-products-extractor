"""Núcleo de extração: lê os XML de NF-e por contrato e devolve quantidades por
corte + dados de embarque. Sem dependência de UI — usado pelo app e pelos testes.

Regras:
- A pasta do contrato é a que COMEÇA com o número do contrato (ex.: 260001).
- A NF fiscal válida é o arquivo ``*procNFe.xml``. Arquivos em subpastas de
  cancelamento (CANCELADA/ANTIGA/OLD/...) são IGNORADOS.
- Cortes, peso líquido/bruto e nº de caixas (volumes) vêm do procNFe.
- Container e booking vêm das observações (infCpl) do **DANFE** (formato
  estruturado "RESERVA: … / CONTAINER: …"); fallback para o procNFe se não houver
  DANFE ou se o valor estiver indefinido ("A DEFINIR"/"TBN").
- Mais de uma NF válida no contrato → quantidades somadas e status sinaliza.
"""
import os
import re
import glob
import xml.etree.ElementTree as ET

# Mapa cProd (código do produto na NF-e) -> nome do produto (col. da Output)
# Personalize para os códigos e nomes usados na sua empresa.
CUTS = [
    ("2502", "Product A"),
    ("2508", "Product B"),
    ("2540", "Product C"),
    ("2504", "Product D"),
    ("2505", "Product E"),
    ("2506", "Product F"),
    ("2507", "Product G"),
    ("2510", "Product H"),
]
CODES = [c for c, _ in CUTS]
CUT_NAMES = [n for _, n in CUTS]

# Subpastas a ignorar (NF cancelada / substituída / arquivada)
EXCLUDE = re.compile(r"CANCELAD|ANTIG|\bOLD\b|NAO USAR|NÃO USAR|SUBSTITU", re.I)

CONTRACT_RE = re.compile(r"\b(26\d{4})\b")


def find_folder(root, contract):
    """Retorna o caminho da pasta cujo nome começa com o número do contrato."""
    try:
        for d in os.listdir(root):
            if d.strip().startswith(contract) and os.path.isdir(os.path.join(root, d)):
                return os.path.join(root, d)
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return None
    return None


def _glob_xml(folder, pattern):
    """XMLs de um padrão, excluindo subpastas de cancelamento."""
    out = []
    for f in glob.glob(os.path.join(folder, "**", pattern), recursive=True):
        if not EXCLUDE.search(os.path.relpath(f, folder)):
            out.append(f)
    return sorted(out)


def valid_procnfe(folder):
    return _glob_xml(folder, "*procNFe.xml")


def _read_xml(path):
    """Lê o XML removendo namespaces (simplifica o XPath). Pode lançar."""
    raw = open(path, encoding="utf-8").read()
    return ET.fromstring(re.sub(r'xmlns="[^"]+"', "", raw))


def _infcpl(root):
    try:
        return next(root.iter("infCpl")).text or ""
    except StopIteration:
        return ""


def _field(text, *keys):
    """Valor de um campo "CHAVE: valor" no infCpl, até '/' ou '|'.
    O lookbehind evita confundir 'CONTAINER' com 'LACRE CONTAINER'."""
    for k in keys:
        m = re.search(r"(?<!LACRE )\b" + k + r"\s*[:\-]\s*([^/|]+)", text, re.I)
        if m:
            return m.group(1).strip()
    return None


def _norm_container(v):
    """Normaliza p/ ISO (4 letras + 7 dígitos). None se não parecer container."""
    if not v:
        return None
    c = re.sub(r"[^A-Za-z0-9]", "", v).upper()
    m = re.match(r"^([A-Z]{4}\d{6,7})", c)
    return m.group(1) if m else None


def _clean_booking(v):
    if not v:
        return None
    v = v.strip().upper()
    if "DEFINIR" in v or v.startswith("TBN"):
        return None
    m = re.match(r"^([A-Z0-9]{6,})", v.replace(" ", ""))
    return m.group(1) if m else None


def parse_nfe(path):
    """Lê um procNFe.xml -> dict com nf, qty por corte, extras, caixas, pesos, infCpl."""
    root = _read_xml(path)
    nNF = next(root.iter("nNF")).text
    qty, extras = {}, {}
    for prod in root.findall(".//det/prod"):
        c = (prod.findtext("cProd") or "").strip()
        q = float(prod.findtext("qCom") or 0)
        if c in CODES:
            qty[c] = qty.get(c, 0.0) + q
        else:
            label = (prod.findtext("xProd") or c).strip()
            extras[label] = extras.get(label, 0.0) + q
    vol = root.find(".//transp/vol")
    qvol = pesoB = None
    if vol is not None:
        try:
            qvol = int(float(vol.findtext("qVol")))
        except (TypeError, ValueError):
            qvol = None
        try:
            pesoB = float(vol.findtext("pesoB"))
        except (TypeError, ValueError):
            pesoB = None
    return {"nf": nNF, "qty": qty, "extras": extras,
            "qvol": qvol, "pesoB": pesoB, "infcpl": _infcpl(root)}


def parse_logistics(folder, proc_infcpl=""):
    """Container e booking, preferindo o DANFE (infCpl estruturado)."""
    cont = book = None
    for f in _glob_xml(folder, "DANFE*.xml"):
        try:
            t = _infcpl(_read_xml(f))
        except Exception:
            continue
        cont = cont or _norm_container(_field(t, "CONTAINER"))
        book = book or _clean_booking(_field(t, "RESERVA", "BOOKING"))
        if cont and book:
            break
    if not cont:
        cont = _norm_container(_field(proc_infcpl, "CONTAINER"))
    if not book:
        book = _clean_booking(_field(proc_infcpl, "BOOKING", "RESERVA"))
    return cont or "", book or ""


def extract_one(root, contract):
    """Processa um contrato. Sempre devolve um dict (nunca lança)."""
    res = {"contrato": contract, "nf": "", "container": "", "booking": "",
           "vals": None, "net": None, "gross": None, "boxes": None,
           "extras": {}, "status": ""}
    folder = find_folder(root, contract)
    if not folder:
        res["status"] = "PASTA NÃO ENCONTRADA"
        return res
    xmls = valid_procnfe(folder)
    if not xmls:
        res["status"] = "SEM NF"
        return res

    nfs, qty, extras = set(), {}, {}
    qvol_sum, pesoB_sum, last_infcpl = 0, 0.0, ""
    have_vol = have_gross = False
    for x in xmls:
        try:
            p = parse_nfe(x)
        except Exception as exc:  # XML corrompido / não baixado
            res["status"] = "ERRO AO LER XML (%s)" % exc.__class__.__name__
            return res
        nfs.add(p["nf"])
        for k, v in p["qty"].items():
            qty[k] = qty.get(k, 0.0) + v
        for k, v in p["extras"].items():
            extras[k] = extras.get(k, 0.0) + v
        if p["qvol"] is not None:
            qvol_sum += p["qvol"]; have_vol = True
        if p["pesoB"] is not None:
            pesoB_sum += p["pesoB"]; have_gross = True
        last_infcpl = p["infcpl"]

    res["nf"] = " / ".join(sorted(nfs))
    res["vals"] = [round(qty.get(c, 0.0), 3) for c in CODES]
    res["net"] = round(sum(res["vals"]), 3)
    res["gross"] = round(pesoB_sum, 3) if have_gross else None
    res["boxes"] = qvol_sum if have_vol else None
    res["extras"] = extras
    res["container"], res["booking"] = parse_logistics(folder, last_infcpl)

    parts = ["OK"]
    if len(xmls) > 1:
        parts = ["OK (%d NFs somadas)" % len(xmls)]
    flags = []
    if extras:
        flags.append("cortes fora do padrão: " + ", ".join(extras))
    if not res["container"]:
        flags.append("sem container")
    if not res["booking"]:
        flags.append("sem booking")
    if res["gross"] is None:
        flags.append("sem peso bruto")
    if res["boxes"] is None:
        flags.append("sem caixas")
    res["status"] = " — ".join(parts + flags)
    return res


def extract_all(root, contracts, progress=None):
    """Processa a lista de contratos. ``progress(i, total, contrato)`` opcional."""
    results = []
    total = len(contracts)
    for i, c in enumerate(contracts, 1):
        if progress:
            progress(i, total, c)
        results.append(extract_one(root, c))
    return results


def parse_contracts_from_text(text):
    """Extrai números de contrato (26xxxx) de texto colado, sem duplicar."""
    seen, out = set(), []
    for m in CONTRACT_RE.findall(text or ""):
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def parse_contracts_from_xlsx(path):
    """Lê a coluna A de um xlsx e devolve os contratos (26xxxx), sem duplicar."""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb.active
    seen, out = set(), []
    for (cell,) in ws.iter_rows(min_col=1, max_col=1, values_only=True):
        if cell is None:
            continue
        m = CONTRACT_RE.search(str(cell))
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            out.append(m.group(1))
    wb.close()
    return out
