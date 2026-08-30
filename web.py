from flask import Flask, request, redirect, render_template_string, session, url_for
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

class Banco:
    def __init__(self):
        self.conn = psycopg2.connect(os.environ["DATABASE_URL"])
        self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)

    def execute(self, sql, params=()):
        self.cursor.execute(sql.replace("?", "%s"), params)
        return self.cursor

    def commit(self):
        self.conn.commit()

    def close(self):
        self.cursor.close()
        self.conn.close()

def conectar():
    return Banco()

def criar_banco():
    banco = conectar()

    banco.execute("""
        CREATE TABLE IF NOT EXISTS recebimentos (
            id SERIAL PRIMARY KEY,
            fornecedor TEXT NOT NULL,
            nota_fiscal TEXT,
            volumes INTEGER,
            funcionario TEXT,
            observacao TEXT,
            data TEXT NOT NULL,
            nota TEXT NOT NULL
        )
    """)

    banco.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            nivel TEXT NOT NULL DEFAULT 'funcionario'
        )
    """)

    admin_user = os.environ.get("LOGIN_USER")
    admin_password = os.environ.get("LOGIN_PASSWORD")

    if admin_user and admin_password:
        existente = banco.execute(
            "SELECT id FROM usuarios WHERE usuario = ?",
            (admin_user,)
        ).fetchone()

        if not existente:
            banco.execute(
                "INSERT INTO usuarios (usuario, senha, nivel) VALUES (?, ?, ?)",
                (
                    admin_user,
                    generate_password_hash(admin_password),
                    "admin"
                )
            )

    banco.commit()
    banco.close()


HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Controle de Recebimentos</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f3f5f7;
    color: #222;
}

.topo {
    background: #111827;
    color: white;
    padding: 20px;
}

.container {
    max-width: 900px;
    margin: auto;
    padding: 20px;
}

.card {
    background: white;
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}

input, textarea {
    width: 100%;
    padding: 13px;
    margin-top: 6px;
    margin-bottom: 12px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 16px;
}

textarea {
    min-height: 80px;
}

label {
    font-weight: bold;
}

.grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
}

.botao {
    width: 100%;
    padding: 15px;
    border: 0;
    border-radius: 9px;
    background: #111827;
    color: white;
    font-size: 16px;
    font-weight: bold;
    min-height: 54px;
    border: 1px solid rgba(255,255,255,.18);
    box-shadow: 0 3px 0 rgba(0,0,0,.30), 0 6px 14px rgba(0,0,0,.16);
}

.registro {
    padding: 15px 0;
    border-bottom: 1px solid #ddd;
}

.fornecedor {
    font-size: 18px;
    font-weight: bold;
}

.data {
    color: #6b7280;
    font-size: 14px;
}

.excluir {
    color: #dc2626;
    text-decoration: none;
}

@media (max-width: 650px) {
    .grid {
        grid-template-columns: 1fr;
    }
}
</style>

</head>
<body>

<div class="topo">
    <div class="container">
        <h1>Controle de Recebimentos</h1>

{% if session.get("nivel") == "admin" %}
<a href="/usuarios"
   style="display:flex;align-items:center;justify-content:center;
   width:100%;min-height:54px;
   background:#111827;color:white;
   padding:14px 18px;border-radius:9px;
   text-decoration:none;margin:18px 0 22px;
   font-weight:bold;font-size:16px;
   border:1px solid rgba(255,255,255,.18);
   box-shadow:0 3px 0 rgba(0,0,0,.30),0 6px 14px rgba(0,0,0,.16);">
    GERENCIAR USUÁRIOS
</a>
{% endif %}

        <p>Registro e acompanhamento de entregas</p>
    </div>
</div>

<div class="container">

    <div class="card">
        <h2>Novo recebimento</h2>

        <form method="POST" action="/registrar">

            <label>Fornecedor</label>
            <input
                name="fornecedor"
                placeholder="Ex: Elgin"
                required
            >

            <div class="grid">
                <div>
                    <label>Nota fiscal</label>
                    <input
                        name="nota_fiscal"
                        placeholder="Ex: 123456"
                    >
                </div>

                <div>
                    <label>Quantidade de volumes</label>
                    <input
                        type="number"
                        name="volumes"
                        min="0"
                        placeholder="Ex: 5"
                    >
                </div>
            </div>

            <label>Funcionário que recebeu</label>
            <input
                name="funcionario"
                        value="{{ session.get('usuario', '') }}"
                        readonly
                    >

            <label>Observação</label>
            <textarea
                name="observacao"
                placeholder="Avarias, falta de volumes ou observações..."
            ></textarea>

            <button class="botao" type="submit">
                REGISTRAR RECEBIMENTO
            </button>
        </form>
    </div>

    <div class="card">
        <h2>Pesquisar</h2>

        <form method="GET" action="/">
            <input
                name="q"
                value="{{ pesquisa }}"
                placeholder="Fornecedor ou nota fiscal"
            >

            <button class="botao" type="submit">
                Buscar
            </button>
        </form>
    </div>

    <div class="card">
        <h2>Histórico</h2>

        {% if registros %}

            {% for r in registros %}

                <div class="registro">

                    <div class="fornecedor">
                        {{ r["fornecedor"] }}
                    </div>

                    <div class="data">
                        {{ r["data"] }} às {{ r["hora"] }}
                    </div>

                    {% if r["nota_fiscal"] %}
                        <div>
                            <strong>NF:</strong>
                            {{ r["nota_fiscal"] }}
                        </div>
                    {% endif %}

                    {% if r["volumes"] %}
                        <div>
                            <strong>Volumes:</strong>
                            {{ r["volumes"] }}
                        </div>
                    {% endif %}

                    {% if r["funcionario"] %}
                        <div>
                            <strong>Recebido por:</strong>
                            {{ r["funcionario"] }}
                        </div>
                    {% endif %}

                    {% if r["observacao"] %}
                        <div>
                            <strong>Observação:</strong>
                            {{ r["observacao"] }}
                        </div>
                    {% endif %}

                    <br>

                    <a
                        class="excluir"
                        href="/excluir/{{ r['id'] }}"
                        onclick="return confirm('Excluir este recebimento?')"
                    >
                        Excluir registro
                    </a>

                </div>

            {% endfor %}

        {% else %}

            <p>Nenhum recebimento encontrado.</p>

        {% endif %}
    </div>

</div>


<div style="max-width:900px;margin:28px auto 40px;padding:0 20px;">
    <a href="/logout"
       style="display:flex;align-items:center;justify-content:center;
       width:100%;min-height:54px;
       background:#111827;color:white;
       padding:14px 18px;border-radius:9px;
       text-decoration:none;font-weight:bold;font-size:16px;
       box-sizing:border-box;
       border:1px solid rgba(255,255,255,.18);
       box-shadow:0 3px 0 rgba(0,0,0,.30),0 6px 14px rgba(0,0,0,.16);">
        SAIR
    </a>
</div>

</body>
</html>
"""


LOGIN_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Login - Sistema de Recebimento</title>
<style>
* { box-sizing: border-box; }
body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f3f4f6;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
}
.login {
    background: white;
    width: 90%;
    max-width: 400px;
    padding: 30px;
    border-radius: 14px;
    box-shadow: 0 5px 25px rgba(0,0,0,.10);
}
h1 {
    margin-top: 0;
    text-align: center;
    color: #111827;
}
p {
    text-align: center;
    color: #6b7280;
}
input {
    width: 100%;
    padding: 14px;
    margin: 8px 0;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 16px;
}
button {
    width: 100%;
    padding: 14px;
    margin-top: 10px;
    border: 0;
    border-radius: 8px;
    background: #111827;
    color: white;
    font-size: 16px;
    font-weight: bold;
}
.erro {
    color: #dc2626;
    font-weight: bold;
}
</style>
</head>
<body>
<div class="login">
    <h1>Sistema de Recebimento</h1>
    <p>Entre para continuar</p>

    {% if erro %}
    <p class="erro">{{ erro }}</p>
    {% endif %}

    <form method="POST">
        <input name="usuario" placeholder="Usuário" required>
        <input name="senha" type="password" placeholder="Senha" required>
        <button type="submit">ENTRAR</button>
    </form>
</div>
</body>
</html>
"""

@app.route("/login", methods=["GET", "POST"])
def login():
    erro = None

    if request.method == "POST":
        usuario = request.form.get("usuario", "")
        senha = request.form.get("senha", "")

        banco = conectar()
        registro = banco.execute(
            "SELECT id, usuario, senha, nivel FROM usuarios WHERE usuario = ?",
            (usuario,)
        ).fetchone()
        banco.close()

        if registro and check_password_hash(registro["senha"], senha):
            session["logado"] = True
            session["usuario_id"] = registro["id"]
            session["usuario"] = registro["usuario"]
            session["nivel"] = registro["nivel"]
            return redirect(url_for("inicio"))

        erro = "Usuário ou senha inválidos."

    return render_template_string(LOGIN_HTML, erro=erro)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.before_request
def exigir_login():
    if request.endpoint not in ("login", "static") and not session.get("logado"):
        return redirect(url_for("login"))



USUARIOS_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Gerenciar usuários</title>
<style>
body {
    font-family: Arial, sans-serif;
    background: #f3f4f6;
    margin: 0;
    padding: 20px;
}
.caixa {
    max-width: 700px;
    margin: auto;
    background: white;
    padding: 24px;
    border-radius: 14px;
}
input, select, button {
    width: 100%;
    padding: 12px;
    margin: 7px 0;
    box-sizing: border-box;
}
button {
    background: #111827;
    color: white;
    border: 0;
    border-radius: 8px;
    font-weight: bold;
}
.usuario {
    border-top: 1px solid #ddd;
    padding: 12px 0;
}
a {
    color: #111827;
}
</style>
</head>
<body>
<div class="caixa">
    <h1>Gerenciar usuários</h1>

    <form method="POST">
        <input name="usuario" placeholder="Novo usuário" required>
        <input name="senha" type="password" placeholder="Senha" required>

        <select name="nivel">
            <option value="funcionario">Funcionário</option>
            <option value="admin">Administrador</option>
        </select>

        <button type="submit">CRIAR USUÁRIO</button>
    </form>

    <h2>Usuários cadastrados</h2>

    {% for u in usuarios %}
    <div class="usuario">
        <strong>{{ u["usuario"] }}</strong>
        — {{ u["nivel"] }}
    </div>
    {% endfor %}

    <p><a href="/">Voltar ao sistema</a></p>
</div>
</body>
</html>
"""

@app.route("/usuarios", methods=["GET", "POST"])
def usuarios():
    if session.get("nivel") != "admin":
        return redirect(url_for("inicio"))

    banco = conectar()

    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        nivel = request.form.get("nivel", "funcionario")

        if usuario and senha and nivel in ("admin", "funcionario"):
            existente = banco.execute(
                "SELECT id FROM usuarios WHERE usuario = ?",
                (usuario,)
            ).fetchone()

            if not existente:
                banco.execute(
                    "INSERT INTO usuarios (usuario, senha, nivel) VALUES (?, ?, ?)",
                    (
                        usuario,
                        generate_password_hash(senha),
                        nivel
                    )
                )
                banco.commit()

    lista = banco.execute(
        "SELECT id, usuario, nivel FROM usuarios ORDER BY usuario"
    ).fetchall()

    banco.close()

    return render_template_string(USUARIOS_HTML, usuarios=lista)


@app.route("/")
def inicio():
    pesquisa = request.args.get("q", "").strip()

    banco = conectar()

    if pesquisa:
        registros = banco.execute("""
            SELECT *
            FROM recebimentos
            WHERE fornecedor LIKE ?
               OR nota_fiscal LIKE ?
            ORDER BY id DESC
        """, (
            f"%{pesquisa}%",
            f"%{pesquisa}%"
        )).fetchall()
    else:
        registros = banco.execute("""
            SELECT *
            FROM recebimentos
            ORDER BY id DESC
            LIMIT 100
        """).fetchall()

    banco.close()

    return render_template_string(
        HTML,
        registros=registros,
        pesquisa=pesquisa
    )


@app.route("/registrar", methods=["POST"])
def registrar():
    fornecedor = request.form["fornecedor"].strip()
    nota_fiscal = request.form["nota_fiscal"].strip()
    funcionario = session.get("usuario", "")
    observacao = request.form["observacao"].strip()

    volumes = request.form["volumes"].strip()

    if volumes:
        volumes = int(volumes)
    else:
        volumes = None

    agora = datetime.now()

    data = agora.strftime("%d/%m/%Y")
    hora = agora.strftime("%H:%M:%S")

    banco = conectar()

    banco.execute("""
        INSERT INTO recebimentos
        (
            fornecedor,
            nota_fiscal,
            volumes,
            funcionario,
            observacao,
            data,
            hora
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        fornecedor,
        nota_fiscal,
        volumes,
        funcionario,
        observacao,
        data,
        hora
    ))

    banco.commit()
    banco.close()

    return redirect("/")


@app.route("/excluir/<int:id>")
def excluir(id):
    banco = conectar()

    banco.execute(
        "DELETE FROM recebimentos WHERE id = ?",
        (id,)
    )

    banco.commit()
    banco.close()

    return redirect("/")


criar_banco()

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
