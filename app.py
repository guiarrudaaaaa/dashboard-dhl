from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from functools import wraps
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dhl-dashboard-2026")

# ── CONFIGURAÇÕES ────────────────────────────────────────
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "dhl2026")
DB_PATH    = os.environ.get("DB_PATH", "/data/dashboard.db")

STATUSES = ["Pátio", "Doca", "Separado", "Separando", "Liberado", "Trânsito", "Descarregado", "Carregando"]
TIPOS    = ["Entrada", "Saída"]

# ── BANCO DE DADOS ───────────────────────────────────────
def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS registros (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            data_operacao  TEXT NOT NULL,
            status         TEXT NOT NULL,
            tipo           TEXT NOT NULL,
            destino        TEXT NOT NULL,
            transportadora TEXT NOT NULL,
            tons           REAL NOT NULL DEFAULT 0,
            criado_em      TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    # Seed de exemplo apenas se banco estiver vazio
    if conn.execute("SELECT COUNT(*) FROM registros").fetchone()[0] == 0:
        seed = [
            ("02/06/2026","Separado", "Entrada","PORTO BELO - SC",        "COOCATRANS S.A",           4.0),
            ("07/06/2026","Doca",     "Entrada","FOZ DO IGUACU - PR",     "BBT TRANSPORTES LTDA",     7.0),
            ("09/06/2026","Doca",     "Entrada","FOZ DO IGUACU - PR",     "BBT TRANSPORTES LTDA",     4.0),
            ("13/06/2026","Trânsito", "Entrada","CURITIBA - PR",           "TRANSP EXEMPLO",           10.0),
            ("19/06/2026","Pátio",    "Entrada","ICARA - SC",              "MEATIMPEX LOGISTICA LTDA", 12.0),
            ("21/06/2026","Pátio",    "Entrada","ICARA - SC",              "MEATIMPEX LOGISTICA LTDA", 7.0),
            ("25/06/2026","Liberado", "Entrada","CASCAVEL - PR",           "TRANSP RAPIDO",            11.0),
            ("04/07/2026","Separando","Entrada","PORTO BELO - SC",         "COOCATRANS S.A",           5.0),
            ("06/07/2026","Separando","Entrada","PORTO BELO - SC",         "COOCATRANS S.A",           6.0),
            ("04/06/2026","Separando","Saída",  "PORTO BELO - SC",         "COOCATRANS S.A",           5.0),
            ("10/06/2026","Doca",     "Saída",  "FOZ DO IGUACU - PR",     "BBT TRANSPORTES LTDA",     7.0),
            ("12/06/2026","Liberado", "Saída",  "FOZ DO IGUACU - PR",     "BBT TRANSPORTES LTDA",     4.0),
            ("16/06/2026","Trânsito", "Saída",  "CURITIBA - PR",           "TRANSP EXEMPLO",           10.0),
            ("22/06/2026","Pátio",    "Saída",  "ICARA - SC",              "MEATIMPEX LOGISTICA LTDA", 12.0),
            ("24/06/2026","Doca",     "Saída",  "ICARA - SC",              "MEATIMPEX LOGISTICA LTDA", 7.0),
            ("28/06/2026","Liberado", "Saída",  "CASCAVEL - PR",           "TRANSP RAPIDO",            9.0),
            ("01/07/2026","Separado", "Saída",  "PORTO BELO - SC",         "COOCATRANS S.A",           5.0),
            ("03/07/2026","Separado", "Saída",  "PORTO BELO - SC",         "COOCATRANS S.A",           6.0),
        ]
        conn.executemany(
            "INSERT INTO registros (data_operacao,status,tipo,destino,transportadora,tons) VALUES (?,?,?,?,?,?)",
            seed
        )
    conn.commit()
    conn.close()

# ── DECORATOR DE AUTENTICAÇÃO ────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ── DASHBOARD (público) ──────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/status")
def status():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM registros ORDER BY data_operacao DESC, id DESC"
    ).fetchall()
    conn.close()
    return jsonify([{
        "data_operacao":       r["data_operacao"],
        "status_carregamento": r["status"],
        "tipo_de_carga":       r["tipo"],
        "destino":             r["destino"],
        "transportadora":      r["transportadora"],
        "tons":                r["tons"],
    } for r in rows])

# ── LOGIN ────────────────────────────────────────────────
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        user  = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "").strip()
        if user == ADMIN_USER and senha == ADMIN_PASS:
            session["logged_in"] = True
            session["usuario"]   = user
            return redirect(url_for("admin"))
        error = "Usuário ou senha incorretos."
    return render_template("login.html", error=error)

@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ── ADMIN — LISTAR ───────────────────────────────────────
@app.route("/admin")
@login_required
def admin():
    conn  = get_db()
    rows  = conn.execute(
        "SELECT * FROM registros ORDER BY data_operacao DESC, id DESC"
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM registros").fetchone()[0]
    conn.close()
    return render_template("admin.html",
        rows=rows, total=total,
        statuses=STATUSES, tipos=TIPOS,
        msg=request.args.get("msg")
    )

# ── ADMIN — ADICIONAR ────────────────────────────────────
@app.route("/admin/add", methods=["POST"])
@login_required
def admin_add():
    erros = []
    data   = request.form.get("data_operacao", "").strip()
    status = request.form.get("status", "").strip()
    tipo   = request.form.get("tipo", "").strip()
    dest   = request.form.get("destino", "").strip().upper()
    transp = request.form.get("transportadora", "").strip().upper()
    tons_s = request.form.get("tons", "0").strip()

    if not data:   erros.append("Data obrigatória")
    if not status: erros.append("Status obrigatório")
    if not tipo:   erros.append("Tipo obrigatório")
    if not dest:   erros.append("Destino obrigatório")
    if not transp: erros.append("Transportadora obrigatória")

    try:
        tons = float(tons_s)
    except ValueError:
        tons = 0.0
        erros.append("TONS inválido")

    if erros:
        return redirect(url_for("admin", msg="ERRO: " + " | ".join(erros)))

    conn = get_db()
    conn.execute(
        "INSERT INTO registros (data_operacao,status,tipo,destino,transportadora,tons) VALUES (?,?,?,?,?,?)",
        (data, status, tipo, dest, transp, tons)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin", msg="Registro adicionado com sucesso!"))

# ── ADMIN — EDITAR ───────────────────────────────────────
@app.route("/admin/edit/<int:rid>", methods=["GET", "POST"])
@login_required
def admin_edit(rid):
    conn = get_db()
    row  = conn.execute("SELECT * FROM registros WHERE id=?", (rid,)).fetchone()
    if not row:
        conn.close()
        return redirect(url_for("admin", msg="Registro não encontrado."))

    if request.method == "POST":
        data   = request.form.get("data_operacao", "").strip()
        status = request.form.get("status", "").strip()
        tipo   = request.form.get("tipo", "").strip()
        dest   = request.form.get("destino", "").strip().upper()
        transp = request.form.get("transportadora", "").strip().upper()
        try:
            tons = float(request.form.get("tons", 0))
        except ValueError:
            tons = 0.0

        conn.execute(
            "UPDATE registros SET data_operacao=?,status=?,tipo=?,destino=?,transportadora=?,tons=? WHERE id=?",
            (data, status, tipo, dest, transp, tons, rid)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin", msg="Registro #" + str(rid) + " atualizado!"))

    conn.close()
    return render_template("edit.html", row=row, statuses=STATUSES, tipos=TIPOS)

# ── ADMIN — APAGAR ───────────────────────────────────────
@app.route("/admin/delete/<int:rid>", methods=["POST"])
@login_required
def admin_delete(rid):
    conn = get_db()
    conn.execute("DELETE FROM registros WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin", msg="Registro removido."))

# ── BOOT ─────────────────────────────────────────────────
init_db()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
