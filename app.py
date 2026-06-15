"""Extrator de Cortes da NF  (system-tray app, Windows).

Fica na bandeja. Abrir a janela: clicar no ícone. Cole os números de
contrato OU arraste/selecione um xlsx (contratos na coluna A); o app lê os XML
das NF nas pastas do SharePoint e gera um xlsx com cortes + container, booking,
caixas e peso bruto (+ TOTAIS/Média e Status por contrato).

PRINCÍPIO: campo não encontrado fica EM BRANCO e é marcado no Status. Nada é
inventado/estimado.

Rodar:  pythonw app.py   (ou o EXE)
"""
import os
import sys
import threading
import datetime as dt
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageDraw
import pystray

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES, DND_TEXT
    _DND = True
except Exception:  # pragma: no cover
    _DND = False

from extrator import core, config, autostart
from extrator.xlsx_out import write_xlsx

APP_TITLE = "Extrator de Cortes da NF"
ROW_COLORS = {"ok": "#e8f5e9", "warn": "#fff3cd", "err": "#f8d7da"}
DARK = "#305496"


def _resource(rel):
    """Caminho de um recurso, funcionando empacotado (PyInstaller) e em dev."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def _icon_image():
    """Ícone da bandeja: usa assets/icon.png; cai num desenho simples se faltar."""
    try:
        return Image.open(_resource(os.path.join("assets", "icon.png")))
    except Exception:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([4, 4, 60, 60], radius=12, fill=DARK)
        d.rectangle([14, 24, 50, 52], outline="white", width=3)
        d.line([14, 32, 50, 32], fill="white", width=2)
        d.polygon([(14, 24), (32, 14), (50, 24)], fill="#DDEBF7")
        return img


class App:
    def __init__(self):
        self.root = TkinterDnD.Tk() if _DND else tk.Tk()
        try:
            ttk.Style().theme_use("vista")
        except Exception:
            pass
        self.busy = False
        self.last_results = None
        self.root.title(APP_TITLE)
        self.root.geometry("860x640")
        self.root.minsize(740, 560)
        try:
            self.root.iconbitmap(_resource(os.path.join("assets", "icon.ico")))
        except Exception:
            pass

        self._build_root_bar()
        self._build_input()
        self._build_actions()
        self._build_results()

        self.root_dir = config.get_root()
        self._refresh_root_label()

        self.root.protocol("WM_DELETE_WINDOW", self._hide)
        self.icon = pystray.Icon(
            "nfe_extrator", _icon_image(), APP_TITLE,
            menu=pystray.Menu(
                pystray.MenuItem("Mostrar janela", self._show_from_tray, default=True),
                pystray.MenuItem("Iniciar com o Windows", self._toggle_autostart,
                                 checked=lambda i: autostart.is_enabled()),
                pystray.MenuItem("Sair", self._quit_from_tray),
            ))
        threading.Thread(target=self.icon.run, daemon=True).start()

    # ---------- pasta raiz ----------
    def _build_root_bar(self):
        bar = ttk.Frame(self.root, padding=(10, 8))
        bar.pack(fill="x")
        ttk.Label(bar, text="Pasta dos contratos:").pack(side="left")
        self.root_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.root_var, state="readonly").pack(
            side="left", fill="x", expand=True, padx=6)
        ttk.Button(bar, text="Alterar…", command=self._change_root).pack(side="left")

    def _refresh_root_label(self):
        self.root_var.set(self.root_dir or "(não encontrada — clique em Alterar…)")

    def _change_root(self):
        start = self.root_dir or os.path.expanduser("~")
        path = filedialog.askdirectory(title="Selecione a pasta de contratos", initialdir=start)
        if not path:
            return
        if not config.looks_like_root(path):
            if not messagebox.askyesno(
                "Confirmar pasta",
                "Não encontrei pastas de contrato (26xxxx) aqui.\n\nUsar mesmo assim?"):
                return
        self.root_dir = os.path.normpath(path)
        config.set_root(self.root_dir)
        self._refresh_root_label()

    # ---------- entrada ----------
    def _build_input(self):
        frm = ttk.LabelFrame(
            self.root,
            text="Contratos — cole os números (um por linha) ou arraste/selecione um xlsx",
            padding=8)
        frm.pack(fill="both", expand=False, padx=10, pady=(4, 6))
        self.txt = tk.Text(frm, height=6, wrap="word")
        self.txt.pack(fill="both", expand=True)
        if _DND:
            self.txt.drop_target_register(DND_FILES, DND_TEXT)
            self.txt.dnd_bind("<<Drop>>", self._on_drop)
        else:
            ttk.Label(frm, text="(arrastar-e-soltar indisponível — use 'Selecionar xlsx…')",
                      foreground="#888").pack(anchor="w", pady=(4, 0))

    def _on_drop(self, event):
        data = event.data.strip()
        paths = self.root.tk.splitlist(data)
        xlsx = [p for p in paths if p.lower().endswith((".xlsx", ".xlsm", ".xls"))]
        if xlsx:
            self._load_xlsx(xlsx[0])
        else:
            self.txt.insert("end", ("\n" if self.txt.get("1.0", "end").strip() else "") + data)

    # ---------- ações ----------
    def _build_actions(self):
        bar = ttk.Frame(self.root, padding=(10, 0))
        bar.pack(fill="x")
        ttk.Button(bar, text="Selecionar xlsx…", command=self._pick_xlsx).pack(side="left")
        ttk.Button(bar, text="Limpar", command=lambda: self.txt.delete("1.0", "end")).pack(side="left", padx=6)
        self.go_btn = ttk.Button(bar, text="Gerar planilha  ▶", command=self._generate)
        self.go_btn.pack(side="right")
        self.prog = ttk.Progressbar(bar, mode="determinate", length=200)
        self.prog.pack(side="right", padx=8)
        ttk.Label(self.root,
                  text="Campos não encontrados ficam em branco e marcados no Status — nada é inventado.",
                  padding=(12, 0), foreground="#888").pack(fill="x")
        self.status = ttk.Label(self.root, text="", padding=(12, 2), foreground="#444")
        self.status.pack(fill="x")

    def _pick_xlsx(self):
        path = filedialog.askopenfilename(
            title="Selecione o xlsx com os contratos (coluna A)",
            filetypes=[("Excel", "*.xlsx *.xlsm *.xls"), ("Todos", "*.*")])
        if path:
            self._load_xlsx(path)

    def _load_xlsx(self, path):
        try:
            contracts = core.parse_contracts_from_xlsx(path)
        except Exception as exc:
            messagebox.showerror("Erro ao ler xlsx", str(exc))
            return
        if not contracts:
            messagebox.showwarning("Nada encontrado",
                                   "Não achei contratos (26xxxx) na coluna A desse arquivo.")
            return
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", "\n".join(contracts))
        self._set_status(f"{len(contracts)} contratos carregados de {os.path.basename(path)}")

    # ---------- geração ----------
    def _generate(self):
        if self.busy:
            return
        if not self.root_dir or not config.looks_like_root(self.root_dir):
            messagebox.showerror("Pasta inválida", "Defina a pasta dos contratos (botão Alterar…).")
            return
        contracts = core.parse_contracts_from_text(self.txt.get("1.0", "end"))
        if not contracts:
            messagebox.showwarning("Sem contratos", "Cole ou carregue ao menos um contrato (26xxxx).")
            return
        self.busy = True
        self.go_btn.config(state="disabled")
        self.prog.config(maximum=len(contracts), value=0)
        threading.Thread(target=self._worker, args=(contracts,), daemon=True).start()

    def _worker(self, contracts):
        def prog(i, total, c):
            self.root.after(0, self._on_progress, i, total, c)
        results = core.extract_all(self.root_dir, contracts, progress=prog)
        self.root.after(0, self._on_done, results)

    def _on_progress(self, i, total, c):
        self.prog.config(value=i)
        self._set_status(f"Lendo {i}/{total}: contrato {c}…")

    def _on_done(self, results):
        self.last_results = results
        self.busy = False
        self.go_btn.config(state="normal")
        self._fill_table(results)
        ok = sum(1 for r in results if r["vals"] is not None)
        prob = len(results) - ok
        self._set_status(f"{ok} OK, {prob} com pendência. Escolha onde salvar…")
        self._save(results)

    def _save(self, results):
        default = "Cortes_NF_%s.xlsx" % dt.datetime.now().strftime("%Y%m%d_%H%M")
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        out = filedialog.asksaveasfilename(
            title="Salvar planilha", defaultextension=".xlsx", initialfile=default,
            initialdir=desktop if os.path.isdir(desktop) else os.path.expanduser("~"),
            filetypes=[("Excel", "*.xlsx")])
        if not out:
            self._set_status("Geração concluída (não salvo).")
            return
        try:
            n_ok, n_prob = write_xlsx(results, out)
        except Exception as exc:
            messagebox.showerror("Erro ao salvar", str(exc))
            return
        self._set_status(f"Salvo: {out}  ({n_ok} OK, {n_prob} pendências)")
        if messagebox.askyesno("Pronto", "Planilha gerada!\n\nAbrir agora?"):
            try:
                os.startfile(out)  # noqa: Windows
            except Exception:
                pass

    # ---------- tabela ----------
    def _build_results(self):
        frm = ttk.LabelFrame(self.root, text="Resultado", padding=6)
        frm.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("contrato", "nf", "container", "booking", "boxes", "net", "status")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings")
        for c, t, w in (("contrato", "Contrato", 80), ("nf", "NF", 80),
                        ("container", "Container", 100), ("booking", "Booking", 110),
                        ("boxes", "Caixas", 60), ("net", "Peso Líq", 90),
                        ("status", "Status", 300)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="center" if c != "status" else "w")
        vs = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for tag, color in ROW_COLORS.items():
            self.tree.tag_configure(tag, background=color)

    def _fill_table(self, results):
        self.tree.delete(*self.tree.get_children())
        for r in results:
            if r["vals"] is None:
                tag = "err" if "ENCONTRADA" in r["status"] or "ERRO" in r["status"] else "warn"
                net = boxes = ""
            else:
                tag = "ok" if r["status"] == "OK" else "warn"
                net = f"{r['net']:,.3f}"
                boxes = r["boxes"] if r["boxes"] is not None else ""
            self.tree.insert("", "end", tags=(tag,), values=(
                r["contrato"], r["nf"], r["container"], r["booking"],
                boxes, net, r["status"]))

    def _set_status(self, txt):
        self.status.config(text=txt)

    # ---------- bandeja / ciclo de vida ----------
    def _hide(self):
        self.root.withdraw()

    def _show_from_tray(self, *_a):
        self.root.after(0, self._show)

    def _show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(300, lambda: self.root.attributes("-topmost", False))

    def _toggle_autostart(self, _icon=None, _item=None):
        try:
            autostart.disable() if autostart.is_enabled() else autostart.enable()
        except OSError:
            pass

    def _quit_from_tray(self, *_a):
        self.root.after(0, self._quit)

    def _quit(self):
        try:
            self.icon.stop()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def _selftest():
    """Diagnóstico do empacotamento: importa tudo, confere assets embutidos, faz
    uma extração real e escreve um xlsx. Grava relatório (o exe é --windowed, sem
    console). Uso: "Extrator Cortes NF.exe" --selftest  →  %TEMP%\\nfe_extrator_selftest.txt"""
    import tempfile, traceback
    report = os.path.join(tempfile.gettempdir(), "nfe_extrator_selftest.txt")
    lines, ok = [], True
    try:
        import openpyxl, tkinterdnd2, pystray, PIL  # noqa: F401
        from extrator import core, config  # noqa: F401
        from extrator.xlsx_out import write_xlsx
        lines.append("imports OK (openpyxl, tkinterdnd2, pystray, PIL, extrator)")
        lines.append("frozen=%s" % getattr(sys, "frozen", False))
        lines.append("icon.png embutido: %s" % os.path.exists(_resource(os.path.join("assets", "icon.png"))))
        lines.append("icon.ico embutido: %s" % os.path.exists(_resource(os.path.join("assets", "icon.ico"))))
        root = config.get_root()
        lines.append("pasta detectada: %r" % root)
        if root:
            # Substitua pelo número de um contrato válido na sua pasta para testar
            test_contract = "260000"
            res = core.extract_all(root, [test_contract])
            r = res[0]
            lines.append("extração %s: net=%s bruto=%s caixas=%s cont=%s book=%s status=%r"
                         % (test_contract, r["net"], r["gross"], r["boxes"],
                            r["container"], r["booking"], r["status"]))
            tmp = os.path.join(tempfile.gettempdir(), "nfe_extrator_selftest.xlsx")
            write_xlsx(res, tmp)
            lines.append("xlsx escrito: %s" % os.path.exists(tmp))
        else:
            lines.append("(sem pasta detectada aqui — normal se este PC não tem o SharePoint)")
    except Exception:
        ok = False
        lines.append("FALHA:\n" + traceback.format_exc())
    lines.append("RESULTADO: %s" % ("OK" if ok else "FALHA"))
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    sys.exit(0 if ok else 1)


def main():
    if "--selftest" in sys.argv:
        _selftest()
    App().run()


if __name__ == "__main__":
    main()
