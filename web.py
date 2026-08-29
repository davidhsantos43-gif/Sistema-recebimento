from flask import Flask, request, redirect, render_template_string, session, url_for
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

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
            hora TEXT NOT NULL
        )
    """)
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
                placeholder="Nome do funcionário"
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

        if (
            usuario == os.environ.get("LOGIN_USER")
            and senha == os.environ.get("LOGIN_PASSWORD")
        ):
            session["logado"] = True
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
    funcionario = request.form["funcionario"].strip()
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
