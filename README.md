# Extrator de Quantidades da NF

Windows tray app que lê os **XML das NF-e** por pasta de contrato e gera uma
planilha com **quantidades por produto**, dados de embarque (container, booking,
caixas, peso bruto) e status de cada contrato.

Útil para empresas que precisam consolidar quantidades por produto a partir de
NFs fiscais eletrônicas armazenadas no SharePoint (ou qualquer pasta local/rede).

É um **app de bandeja** (system tray): fica ao lado do relógio. Clique no ícone
para abrir a janela; fechar a janela **esconde** na bandeja (não encerra).
Menu do ícone: *Mostrar janela* · *Iniciar com o Windows* · *Sair*.

> **Nada é inventado.** Todo campo que não for encontrado no XML fica **em branco**
> e é **marcado na coluna Status** (`sem container`, `sem booking`, `SEM NF`, etc.).

## Uso

1. Abra o app (ícone na bandeja → **Mostrar janela**).
2. Confira a **Pasta dos contratos** no topo. Na 1ª vez o app tenta auto-detectar;
   se não achar, clique **Alterar…** e aponte para a pasta que contém as subpastas
   `26xxxx` (escolha fica salva).
3. Informe os contratos:
   - **cole** os números na caixa (um por linha), ou
   - **arraste** um `.xlsx` ou clique **Selecionar xlsx…** (contratos na coluna A).
4. Clique **Gerar planilha ▶**, escolha onde salvar.

Status por contrato:
- **OK** — extraído normalmente.
- **OK (N NFs somadas)** — mais de uma NF válida encontrada (conferir).
- **produtos fora do mapa** — código `cProd` não cadastrado em `CUTS`.
- **SEM NF** / **PASTA NÃO ENCONTRADA** — amarelo/vermelho; fora dos totais.

## Colunas geradas

Contrato · NF · Container · Booking · *produtos mapeados* · Peso Líquido ·
Peso Bruto · Caixas · Status (+ linhas TOTAIS/Média).

## Configuração do mapa de produtos

Edite `extrator/core.py` → `CUTS` para mapear os códigos `cProd` da NF-e aos
nomes de produto da sua empresa:

```python
CUTS = [
    ("1001", "Produto Alpha"),
    ("1002", "Produto Beta"),
    # ...
]
```

Produtos com `cProd` fora do mapa aparecem na coluna **Status** como
`produtos fora do mapa: <código>` e não entram nos totais.

## Regras de extração

- Pasta do contrato = a que **começa** com o número (ex.: `260001`).
- NF válida = arquivo **`*procNFe.xml`**. XML em subpastas de cancelamento
  (`CANCELADA`, `ANTIGA`, `OLD`, …) são **ignorados**.
- **Quantidades, peso líquido/bruto e caixas** vêm do `procNFe`
  (`transp/vol` → `qVol`, `pesoB`; `qCom` por item).
- **Container e booking** vêm das observações (`infCpl`) do **DANFE**
  (formato `RESERVA: … / CONTAINER: …`); fallback para o `procNFe` quando não
  há DANFE ou o valor está indefinido (`A DEFINIR`/`TBN`).

## Auto-detecção da pasta

O app tenta localizar a pasta de contratos automaticamente. Se a estrutura de
pastas da sua empresa for diferente, edite os padrões em
`extrator/config.py` → `auto_detect()`. A pasta escolhida fica salva em
`%APPDATA%\NFExtrator\config.json`.

## Desenvolvimento

```
extrator/core.py      — leitura dos XML e regras (sem UI; testável)
extrator/xlsx_out.py  — escrita do xlsx (Output + TOTAIS/Média + Status)
extrator/config.py    — auto-detecção e persistência da pasta raiz
app.py                — interface (tkinter + tkinterdnd2)
```

```bash
pip install -r requirements.txt
python app.py          # rodar em dev
build_exe.bat          # gerar dist\Extrator Cortes NF.exe
```

Diagnóstico do EXE empacotado:
```
"Extrator Cortes NF.exe" --selftest
# grava relatório em %TEMP%\nfe_extrator_selftest.txt
```
