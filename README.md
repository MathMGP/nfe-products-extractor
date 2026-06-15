# Extrator de Cortes da NF

App de mesa (Windows) para gerar a planilha de **quantidades por corte** a partir
dos **XML das NF-e** que ficam nas pastas de contrato do SharePoint
(`.../ANO 2026/26xxxx/`).

É um **app de bandeja** (system tray): fica rodando ao lado do relógio. Clique no
ícone (caixa) para abrir a janela; fechar a janela **esconde** na bandeja (não sai).
Menu do ícone: *Mostrar janela* · *Iniciar com o Windows* · *Sair*.

> **Nada é inventado.** Todo campo que não for encontrado no XML fica **em branco** e
> é **marcado na coluna Status** (`sem container`, `sem booking`, `SEM NF`, etc.).
> O app nunca estima nem preenche valor que não esteja no documento.

## Uso

1. Abra o app (ícone na bandeja → **Mostrar janela**).
2. Confira a **Pasta dos contratos** no topo. Na 1ª vez o app tenta achar a pasta
   de contratos sozinho; se não achar (ou achar errado), clique **Alterar…** e
   aponte para a pasta que contém as subpastas `26xxxx` (a escolha fica salva).
3. Informe os contratos de um destes jeitos:
   - **cole** os números na caixa (um por linha), ou
   - **arraste** um `.xlsx` para a caixa, ou clique **Selecionar xlsx…**
     (os contratos saem da **coluna A**).
4. Clique **Gerar planilha ▶**, escolha onde salvar e pronto.

A tabela na tela mostra o status de cada contrato:
- **OK** — extraído normalmente.
- **OK (N NFs somadas)** — o contrato tinha mais de uma NF válida (conferir).
- **cortes fora do padrão** — apareceu produto além dos 8 cortes esperados.
- **SEM NF** / **PASTA NÃO ENCONTRADA** — pintado de amarelo/vermelho; fica fora dos totais.

## Colunas geradas

Contrato · NF · **Container** · **Booking** · 8 cortes · Peso Líquido · **Peso Bruto** ·
**Caixas** · Status (+ linhas TOTAIS/Média).

## Regras de extração

- Pasta do contrato = a que **começa** com o número (ex.: `260398`).
- NF válida = arquivo **`*procNFe.xml`**. XML em subpastas de cancelamento
  (`CANCELADA`, `ANTIGA`, `OLD`, …) são **ignorados**.
- **Cortes, peso líquido/bruto e caixas (volumes)** vêm do procNFe
  (`transp/vol` → `qVol`, `pesoB`).
- **Container e booking** vêm das observações (`infCpl`) do **DANFE**
  (`RESERVA: … / CONTAINER: …`); fallback para o procNFe quando não há DANFE ou o
  valor está indefinido (`A DEFINIR`/`TBN`). O procNFe sozinho não é confiável p/
  esses dois (pode trazer lacre ou "A DEFINIR").
- Quantidade = `qCom` por item; corte mapeado pelo código `cProd`:

  | cProd | Corte (NF, PT) | Coluna (EN) |
  |------|----------------|-------------|
  | 2502 | ACEM (MIOLO) | Chuck Roll |
  | 2508 | ACEM (RAMA) | Chuck Ribs |
  | 2540 | PALETA | Shoulder |
  | 2504 | PEITO | Brisket |
  | 2505 | PEIXINHO | Chuck Tender |
  | 2506 | PESCOCO | Neck |
  | 2507 | RAQUETE | Oyster Blade |
  | 2510 | MUSCULO DO DIANTEIRO | Shin |

  > Se a numeração de `cProd` mudar, ajuste o mapa em `extrator/core.py` (`CUTS`).

## Auto-detecção da pasta

O app tenta achar a pasta de contratos automaticamente. Se a estrutura de pastas
da sua empresa for diferente, edite os padrões em `extrator/config.py` → `auto_detect()`.
A pasta escolhida fica salva em `%APPDATA%\NFExtrator\config.json`.

## Desenvolvimento

```
extrator/core.py      — leitura dos XML e regras (sem UI; testável)
extrator/xlsx_out.py  — escrita do xlsx (formato Output + TOTAIS/Média + Status)
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
