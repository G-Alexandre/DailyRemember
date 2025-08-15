# reuniao_suporte.py (corrigido)
# Requisitos: pip install customtkinter
import os
import sqlite3
import csv
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk

APP_TITLE = "Reunião Suporte 08:30 - SIMUS"
DB_FILE = "reuniao_suporte.db"

STATUS_OPCOES = [
    "Atendido",
    "Encaminhado p/ Frente de Loja",
    "Concluído",
    "Dei uma olhada",
    "Com dúvida",
]

def hoje_str():
    return datetime.now().strftime("%Y-%m-%d")

def br_data(d):
    return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")

def iso_data(d):
    return datetime.strptime(d, "%d/%m/%Y").strftime("%Y-%m-%d")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Mantém colunas antigas por compatibilidade; a UI só usa as necessárias
    c.execute("""
        CREATE TABLE IF NOT EXISTS processos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,                 -- YYYY-MM-DD
            processo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            cliente TEXT,
            responsavel TEXT,
            canal TEXT,
            prioridade TEXT,
            status TEXT NOT NULL,
            observacoes TEXT,
            minutos_gastos INTEGER DEFAULT 0
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_proc_data ON processos(data)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_proc_status ON processos(status)")
    conn.commit()
    conn.close()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x680")
        ctk.set_default_color_theme("dark-blue")
        self._build_ui()
        init_db()
        self._load_table()

    # ---------------- UI ----------------
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top bar
        top = ctk.CTkFrame(self, corner_radius=12)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top.grid_columnconfigure(7, weight=1)

        ctk.CTkLabel(top, text="Data:").grid(row=0, column=0, padx=(10,5), pady=8)
        self.entry_data = ctk.CTkEntry(top, width=110)
        self.entry_data.grid(row=0, column=1, padx=5, pady=8)
        self.entry_data.insert(0, datetime.now().strftime("%d/%m/%Y"))

        self.btn_prev = ctk.CTkButton(top, text="◀ Ontem", width=90, command=self._go_prev_day)
        self.btn_prev.grid(row=0, column=2, padx=5, pady=8)
        self.btn_next = ctk.CTkButton(top, text="Amanhã ▶", width=110, command=self._go_next_day)
        self.btn_next.grid(row=0, column=3, padx=5, pady=8)
        self.btn_hoje = ctk.CTkButton(top, text="Hoje", width=70, command=self._go_today)
        self.btn_hoje.grid(row=0, column=4, padx=5, pady=8)

        ctk.CTkLabel(top, text="Status:").grid(row=0, column=5, padx=(20,5), pady=8)
        self.combo_status_filtro = ctk.CTkComboBox(top, values=["(Todos)"] + STATUS_OPCOES, width=220)
        self.combo_status_filtro.grid(row=0, column=6, padx=5, pady=8)
        self.combo_status_filtro.set("(Todos)")

        self.entry_busca = ctk.CTkEntry(top, placeholder_text="Buscar por processo, título, cliente ou responsável…")
        self.entry_busca.grid(row=0, column=7, padx=10, pady=8, sticky="ew")

        self.btn_atualizar = ctk.CTkButton(top, text="Atualizar", command=self._load_table)
        self.btn_atualizar.grid(row=0, column=8, padx=5, pady=8)

        self.btn_resumo = ctk.CTkButton(top, text="Copiar Resumo 08:30", command=self._copiar_resumo)
        self.btn_resumo.grid(row=0, column=9, padx=5, pady=8)

        self.btn_export = ctk.CTkButton(top, text="Exportar CSV", command=self._exportar_csv)
        self.btn_export.grid(row=0, column=10, padx=10, pady=8)

        # Middle: tabela + painel lateral de status
        mid = ctk.CTkFrame(self, corner_radius=12)
        mid.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))
        mid.grid_columnconfigure(0, weight=1)
        mid.grid_rowconfigure(0, weight=1)

        # Tabela (colunas simplificadas)
        self.tree = ttk.Treeview(
            mid,
            columns=("data","processo","titulo","cliente","responsavel","status","observacoes"),
            show="headings", height=12
        )
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10,5), pady=10)

        vsb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(mid, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=0, column=1, sticky="ns", pady=10)
        hsb.grid(row=1, column=0, sticky="ew", padx=(10,5))

        heads = {
            "data":"Data", "processo":"Processo", "titulo":"Título", "cliente":"Cliente",
            "responsavel":"Responsável", "status":"Status", "observacoes":"Observações"
        }
        widths = {"data":90,"processo":120,"titulo":280,"cliente":180,"responsavel":160,"status":190,"observacoes":120}
        for col in heads:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=widths[col], anchor="w")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-1>", self._on_click)  # identifica coluna clicada

        # Painel lateral: mudança rápida de status
        side = ctk.CTkFrame(mid, corner_radius=12)
        side.grid(row=0, column=2, sticky="ns", padx=(5,10), pady=10)
        ctk.CTkLabel(side, text="Mover Status", font=ctk.CTkFont(size=14, weight="bold")).pack(padx=10, pady=(12,6))
        for s in STATUS_OPCOES:
            ctk.CTkButton(side, text=s, width=210, command=lambda st=s: self._mover_status_selecionados(st)).pack(padx=10, pady=4)
        ctk.CTkButton(side, text="Excluir Selecionados", fg_color="#8a1c1c", hover_color="#6f1515",
                      command=self._excluir_selecionados).pack(padx=10, pady=(18,8))

        # Bottom: formulário (sem canal/prioridade/minutos)
        form = ctk.CTkFrame(self, corner_radius=12)
        form.grid(row=2, column=0, sticky="ew", padx=10, pady=(0,10))
        for i in range(8):
            form.grid_columnconfigure(i, weight=1)

        # Linha 1
        self.e_processo = ctk.CTkEntry(form, placeholder_text="Nº do processo/chamado *")
        self.e_titulo = ctk.CTkEntry(form, placeholder_text="Título *")
        self.e_cliente = ctk.CTkEntry(form, placeholder_text="Cliente")
        self.e_responsavel = ctk.CTkEntry(form, placeholder_text="Responsável")
        self.e_status = ctk.CTkComboBox(form, values=STATUS_OPCOES, width=220)
        self.e_status.set("Atendido")

        self.e_processo.grid(row=0, column=0, padx=6, pady=8, sticky="ew")
        self.e_titulo.grid(row=0, column=1, padx=6, pady=8, sticky="ew")
        self.e_cliente.grid(row=0, column=2, padx=6, pady=8, sticky="ew")
        self.e_responsavel.grid(row=0, column=3, padx=6, pady=8, sticky="ew")
        self.e_status.grid(row=0, column=4, padx=6, pady=8, sticky="ew")

        # Linha 2
        self.e_obs = ctk.CTkEntry(form, placeholder_text="Observações")
        self.e_obs.grid(row=1, column=0, columnspan=4, padx=6, pady=8, sticky="ew")

        self.btn_novo = ctk.CTkButton(form, text="Adicionar", command=self._adicionar)
        self.btn_salvar = ctk.CTkButton(form, text="Salvar Edição", command=self._salvar_edicao, state="disabled")
        self.btn_limpar = ctk.CTkButton(form, text="Limpar Formulário", command=self._limpar_form)
        self.btn_duplicar_ontem = ctk.CTkButton(form, text="Duplicar de Ontem (mesmo responsável)", command=self._duplicar_de_ontem)

        self.btn_novo.grid(row=1, column=4, padx=6, pady=8, sticky="ew")
        self.btn_salvar.grid(row=1, column=5, padx=6, pady=8, sticky="ew")
        self.btn_limpar.grid(row=1, column=6, padx=6, pady=8, sticky="ew")
        self.btn_duplicar_ontem.grid(row=1, column=7, padx=6, pady=8, sticky="ew")

        # Estado de edição
        self._edit_id = None
        self._clicked_col = None  # coluna clicada (para abrir popup nas "…")

    # ---------------- Data Ops ----------------
    def _conn(self):
        return sqlite3.connect(DB_FILE)

    def _filtro_params(self):
        try:
            data_iso = iso_data(self.entry_data.get().strip())
        except Exception:
            messagebox.showerror("Data inválida", "Use o formato DD/MM/AAAA.")
            raise
        st = self.combo_status_filtro.get()
        status = None if st == "(Todos)" else st
        busca = self.entry_busca.get().strip()
        return data_iso, status, busca

    def _load_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            data_iso, status, busca = self._filtro_params()
        except Exception:
            return

        conn = self._conn()
        c = conn.cursor()
        query = """SELECT id, data, processo, titulo, cliente, responsavel, status, observacoes
                   FROM processos
                   WHERE data = ?"""
        params = [data_iso]
        if status:
            query += " AND status = ?"; params.append(status)
        if busca:
            query += """ AND (
                processo LIKE ? OR titulo LIKE ? OR cliente LIKE ? OR responsavel LIKE ?
            )"""
            like = f"%{busca}%"; params += [like, like, like, like]
        query += " ORDER BY id DESC"

        for row in c.execute(query, params):
            _id, data, processo, titulo, cliente, responsavel, status, obs = row
            # Observações mostram "..." se houver conteúdo
            obs_short = "..." if (obs and obs.strip()) else ""
            self.tree.insert("", "end", iid=str(_id), values=(
                br_data(data), processo, titulo, cliente or "", responsavel or "", status, obs_short
            ))
        conn.close()

    def _insert(self, reg):
        """
        reg: (data, processo, titulo, cliente, responsavel, status, observacoes)
        Mapeia para as colunas completas (com canal/prioridade/minutos default).
        """
        data, processo, titulo, cliente, responsavel, status, observacoes = reg
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            """INSERT INTO processos
               (data, processo, titulo, cliente, responsavel, canal, prioridade, status, observacoes, minutos_gastos)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (data, processo, titulo, cliente, responsavel, None, None, status, observacoes, 0)
        )
        conn.commit()
        conn.close()

    def _update(self, registro, _id):
        conn = self._conn()
        c = conn.cursor()
        c.execute("""UPDATE processos
                     SET data=?, processo=?, titulo=?, cliente=?, responsavel=?, status=?, observacoes=?
                     WHERE id=?""", (*registro, _id))
        conn.commit()
        conn.close()

    def _delete_many(self, ids):
        if not ids:
            return
        conn = self._conn()
        c = conn.cursor()
        q = f"DELETE FROM processos WHERE id IN ({','.join('?'*len(ids))})"
        c.execute(q, ids)
        conn.commit()
        conn.close()

    def _mover_status_selecionados(self, novo_status):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Seleção vazia", "Selecione um ou mais registros na tabela.")
            return
        conn = self._conn()
        c = conn.cursor()
        for iid in sel:
            c.execute("UPDATE processos SET status=? WHERE id=?", (novo_status, int(iid)))
        conn.commit()
        conn.close()
        self._load_table()

    # ---------------- Handlers ----------------
    def _go_prev_day(self):
        self._shift_day(-1)

    def _go_next_day(self):
        self._shift_day(1)

    def _go_today(self):
        self.entry_data.delete(0, "end")
        self.entry_data.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self._load_table()

    def _shift_day(self, delta):
        try:
            cur = datetime.strptime(self.entry_data.get().strip(), "%d/%m/%Y")
        except Exception:
            messagebox.showerror("Data inválida", "Use o formato DD/MM/AAAA.")
            return
        newd = cur + timedelta(days=delta)
        self.entry_data.delete(0, "end")
        self.entry_data.insert(0, newd.strftime("%d/%m/%Y"))
        self._load_table()

    def _adicionar(self):
        processo = self.e_processo.get().strip()
        titulo = self.e_titulo.get().strip()
        if not processo or not titulo:
            messagebox.showwarning("Campos obrigatórios", "Preencha Processo e Título.")
            return
        cliente = self.e_cliente.get().strip() or None
        responsavel = self.e_responsavel.get().strip() or None
        status = self.e_status.get().strip() or STATUS_OPCOES[0]
        obs = self.e_obs.get().strip() or None

        try:
            data_iso = iso_data(self.entry_data.get().strip())
        except Exception:
            messagebox.showerror("Data inválida", "Use o formato DD/MM/AAAA.")
            return

        # Registro na ordem: data, processo, titulo, cliente, responsavel, status, observacoes
        self._insert((data_iso, processo, titulo, cliente, responsavel, status, obs))
        # Limpa TUDO do formulário após adicionar (como você pediu)
        self._limpar_form()
        self._load_table()

    def _on_click(self, event):
        # guarda coluna clicada para usar no double-click
        self._clicked_col = self.tree.identify_column(event.x)

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if len(sel) == 1:
            iid = sel[0]
            vals = self.tree.item(iid, "values")
            # vals: data_br, processo, titulo, cliente, responsavel, status, observacoes("..." ou "")
            self.e_processo.delete(0, "end"); self.e_processo.insert(0, vals[1])
            self.e_titulo.delete(0, "end"); self.e_titulo.insert(0, vals[2])
            self.e_cliente.delete(0, "end"); self.e_cliente.insert(0, vals[3])
            self.e_responsavel.delete(0, "end"); self.e_responsavel.insert(0, vals[4])
            self.e_status.set(vals[5])
            # Não carrego obs no form automaticamente para evitar sobrescrever sem querer
            self.e_obs.delete(0, "end")
            self._edit_id = int(iid)
            self.btn_salvar.configure(state="normal")
        else:
            self._edit_id = None
            self.btn_salvar.configure(state="disabled")

    def _on_double_click(self, event=None):
        # Detecta a coluna no próprio evento (funciona mesmo sem clique simples antes)
        col = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        # Coluna 7 é "observacoes"
        if col == "#7":
            self._abrir_observacoes_popup(int(row_id))
        else:
            if self._edit_id:
                self.btn_salvar.focus_set()

    def _abrir_observacoes_popup(self, _id: int):
        # Busca observações completas no banco
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT processo, titulo, observacoes FROM processos WHERE id=?", (_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return
        processo, titulo, obs = row
        obs = obs or ""

        # Janela popup (só leitura; tem botão Copiar e Fechar)
        popup = ctk.CTkToplevel(self)
        popup.title(f"Observações — #{processo}")
        popup.geometry("700x450")
        popup.grid_columnconfigure(0, weight=1)
        popup.grid_rowconfigure(1, weight=1)

        header = ctk.CTkLabel(popup, text=f"#{processo} — {titulo}", font=ctk.CTkFont(size=14, weight="bold"))
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12,6))

        txt = ctk.CTkTextbox(popup, wrap="word")
        txt.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)
        txt.insert("1.0", obs)
        txt.configure(state="disabled")

        btns = ctk.CTkFrame(popup)
        btns.grid(row=2, column=0, sticky="ew", padx=12, pady=(6,12))
        btns.grid_columnconfigure(1, weight=1)

        def copiar():
            self.clipboard_clear()
            self.clipboard_append(obs)
            messagebox.showinfo("Copiado", "Observações copiadas para a área de transferência.")
        ctk.CTkButton(btns, text="Copiar", command=copiar).grid(row=0, column=0, padx=4)
        ctk.CTkButton(btns, text="Fechar", command=popup.destroy).grid(row=0, column=2, padx=4)

    def _salvar_edicao(self):
        if not self._edit_id:
            return
        processo = self.e_processo.get().strip()
        titulo = self.e_titulo.get().strip()
        if not processo or not titulo:
            messagebox.showwarning("Campos obrigatórios", "Preencha Processo e Título.")
            return
        cliente = self.e_cliente.get().strip() or None
        responsavel = self.e_responsavel.get().strip() or None
        status = self.e_status.get().strip() or STATUS_OPCOES[0]
        obs_text = self.e_obs.get().strip() or None

        try:
            data_iso = iso_data(self.entry_data.get().strip())
        except Exception:
            messagebox.showerror("Data inválida", "Use o formato DD/MM/AAAA.")
            return

        self._update((data_iso, processo, titulo, cliente, responsavel, status, obs_text), self._edit_id)
        self._limpar_form()
        self._load_table()

    def _limpar_form(self):
        for e in (self.e_processo, self.e_titulo, self.e_cliente, self.e_responsavel, self.e_obs):
            e.delete(0, "end")
        self.e_status.set(STATUS_OPCOES[0])
        self._edit_id = None
        self.btn_salvar.configure(state="disabled")

    def _excluir_selecionados(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Seleção vazia", "Selecione ao menos um registro.")
            return
        if not messagebox.askyesno("Confirmar exclusão", f"Excluir {len(sel)} registro(s) selecionado(s)?"):
            return
        ids = [int(i) for i in sel]
        self._delete_many(ids)
        self._load_table()

    def _duplicar_de_ontem(self):
        try:
            data_atual = iso_data(self.entry_data.get().strip())
        except Exception:
            messagebox.showerror("Data inválida", "Use o formato DD/MM/AAAA.")
            return
        d = datetime.strptime(data_atual, "%Y-%m-%d")
        ontem_iso = (d - timedelta(days=1)).strftime("%Y-%m-%d")
        conn = self._conn()
        c = conn.cursor()
        c.execute("""SELECT processo, titulo, cliente, responsavel, status, observacoes
                     FROM processos WHERE data = ?""", (ontem_iso,))
        rows = c.fetchall()
        if not rows:
            conn.close()
            messagebox.showinfo("Nada para duplicar", "Nenhum registro encontrado em ontem.")
            return
        for (proc, tit, cli, resp, st, obs) in rows:
            self._insert((data_atual, proc, tit, cli, resp, st, obs))
        conn.close()
        self._load_table()
        messagebox.showinfo("Duplicado", f"{len(rows)} registro(s) duplicado(s) de {br_data(ontem_iso)}.")

    # ---------------- Resumo / Exportação ----------------
    def _resumo_texto(self, data_iso):
        conn = self._conn()
        c = conn.cursor()
        resumo = []
        total = 0
        for st in STATUS_OPCOES:
            c.execute("""SELECT processo, titulo, cliente, responsavel
                         FROM processos WHERE data=? AND status=?
                         ORDER BY id DESC""", (data_iso, st))
            rows = c.fetchall()
            total += len(rows)
            resumo.append((st, rows))
        conn.close()

        data_br = br_data(data_iso)
        linhas = [f"Resumo {data_br} — Reunião 08:30 (SIMUS)"]
        linhas.append(f"Total de processos: {total}")
        linhas.append("")
        for st, rows in resumo:
            linhas.append(f"• {st}: {len(rows)}")
            for (proc, tit, cli, resp) in rows:
                tag_cli = f" | Cliente: {cli}" if cli else ""
                tag_resp = f" | Resp.: {resp}" if resp else ""
                linhas.append(f"   - #{proc} — {tit}{tag_cli}{tag_resp}")
            linhas.append("")
        return "\n".join(linhas).rstrip()

    def _copiar_resumo(self):
        try:
            data_iso = iso_data(self.entry_data.get().strip())
        except Exception:
            messagebox.showerror("Data inválida", "Use o formato DD/MM/AAAA.")
            return
        texto = self._resumo_texto(data_iso)
        self.clipboard_clear()
        self.clipboard_append(texto)
        messagebox.showinfo("Resumo copiado", "Resumo gerado e copiado para a área de transferência.")

    def _exportar_csv(self):
        try:
            data_iso, status, busca = self._filtro_params()
        except Exception:
            return

        conn = self._conn()
        c = conn.cursor()
        query = """SELECT data, processo, titulo, cliente, responsavel, status, observacoes
                   FROM processos WHERE data=?"""
        params = [data_iso]
        if status:
            query += " AND status=?"; params.append(status)
        if busca:
            query += " AND (processo LIKE ? OR titulo LIKE ? OR cliente LIKE ? OR responsavel LIKE ?)"
            like = f"%{busca}%"; params += [like, like, like, like]
        query += " ORDER BY id DESC"
        rows = c.execute(query, params).fetchall()
        conn.close()

        if not rows:
            messagebox.showinfo("Sem dados", "Nenhum registro para exportar com os filtros atuais.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"reuniao_{data_iso}.csv"
        )
        if not filename:
            return

        with open(filename, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["data","processo","titulo","cliente","responsavel","status","observacoes"])
            for r in rows:
                r_list = list(r)
                r_list[0] = br_data(r_list[0])  # data em BR
                w.writerow(r_list)

        messagebox.showinfo("Exportado", f"Arquivo salvo em:\n{filename}")

if __name__ == "__main__":
    App().mainloop()
