from flask import Flask, request, redirect, render_template_string, session, url_for
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from zoneinfo import ZoneInfo
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


def registrar_log(usuario, acao, entidade=None, entidade_id=None, detalhes=None):
    try:
        banco = conectar()
        banco.execute(
            """
            INSERT INTO logs (usuario, acao, entidade, entidade_id, detalhes, data_hora)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                usuario,
                acao,
                entidade,
                entidade_id,
                detalhes,
                datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S"),
            ),
        )
        banco.commit()
        banco.close()
    except Exception as e:
        print("ERRO_LOG:", e)

def criar_banco():
    banco = conectar()

    banco.execute("""
        CREATE TABLE IF NOT EXISTS recebimentos (
            id SERIAL PRIMARY KEY,
            fornecedor TEXT NOT NULL,
            nota_fiscal TEXT,
        data_nf TEXT,
            volumes INTEGER,
            funcionario TEXT,
            observacao TEXT,
            data TEXT NOT NULL,
            nota TEXT NOT NULL,
            conferido INTEGER NOT NULL DEFAULT 0,
            conferido_por TEXT,
            conferido_em TEXT
        )
    """)
    banco.execute("ALTER TABLE recebimentos ADD COLUMN IF NOT EXISTS data_nf TEXT")
    banco.execute("ALTER TABLE recebimentos ADD COLUMN IF NOT EXISTS conferido INTEGER NOT NULL DEFAULT 0")
    banco.execute("ALTER TABLE recebimentos ADD COLUMN IF NOT EXISTS conferido_por TEXT")
    banco.execute("ALTER TABLE recebimentos ADD COLUMN IF NOT EXISTS conferido_em TEXT")
    banco.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            nivel TEXT NOT NULL DEFAULT 'funcionario'
        )
    """)

    banco.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS pode_ver_logs INTEGER NOT NULL DEFAULT 0")
    banco.execute("UPDATE usuarios SET pode_ver_logs = 1 WHERE usuario = 'ADMIN'")

    banco.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            usuario TEXT,
            acao TEXT NOT NULL,
            entidade TEXT,
            entidade_id INTEGER,
            detalhes TEXT,
            data_hora TEXT NOT NULL
        )
    """)

    banco.execute("""
        CREATE TABLE IF NOT EXISTS sugestoes_observacao (
            id SERIAL PRIMARY KEY,
            texto TEXT UNIQUE NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1
        )
    """)

    sugestoes_padrao = [
        "Tudo certo",
        "Faltaram peças",
        "Vieram peças a mais",
        "Produto avariado",
        "Produto quebrado",
        "Produto amassado",
        "Produto riscado",
        "Produto molhado",
        "Produto errado",
        "Quantidade divergente",
        "Item faltando",
        "Item duplicado",
        "Volume faltante",
        "Volume excedente",
        "Entrega parcial",
        "Embalagem danificada",
        "Embalagem aberta",
        "Caixa amassada",
        "Caixa rasgada",
        "Caixa molhada",
        "Caixa violada",
        "Lacre violado",
        "Nota fiscal divergente",
        "Sem nota fiscal",
        "Nota fiscal não encontrada",
        "Lote divergente",
        "Validade curta",
        "Validade vencida",
        "Mercadoria recusada",
        "Mercadoria devolvida",
        "Aguardando conferência",
        "Aguardando reposição",
        "Aguardando contato com fornecedor",
        "Recebimento com ressalva"
    ]

    for sugestao in sugestoes_padrao:
        banco.execute(
            """
            INSERT INTO sugestoes_observacao (texto, ativo)
            VALUES (?, 1)
            ON CONFLICT (texto) DO NOTHING
            """,
            (sugestao,)
        )

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

.sugestoes-bloco {margin:12px 0;border:1px solid #d1d5db;border-radius:9px;background:#f9fafb;overflow:hidden}.sugestoes-bloco summary {padding:13px 15px;color:#111827;font-size:14px;font-weight:bold;cursor:pointer;user-select:none}.sugestoes-bloco[open] summary {border-bottom:1px solid #d1d5db;background:#f3f4f6}.sugestoes-lista {display:flex;flex-wrap:wrap;gap:8px;padding:12px}

.historico-card {
    padding: 0;
    overflow: hidden;
}

.historico-titulo {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 20px;
    border-bottom: 1px solid #e5e7eb;
}

.historico-titulo h2 {
    margin: 0;
}

.total-registros {
    padding: 6px 10px;
    border-radius: 999px;
    background: #e5e7eb;
    color: #374151;
    font-size: 13px;
    font-weight: bold;
}

.historico-grade {
    width: 100%;
    overflow-x: auto;
}

.historico-tabela {
    width: 100%;
    min-width: 1180px;
    border-collapse: collapse;
    background: white;
}

.historico-tabela th,
.historico-tabela td {
    padding: 13px 12px;
    border-right: 1px solid #e5e7eb;
    border-bottom: 1px solid #e5e7eb;
    text-align: left;
    vertical-align: top;
    font-size: 14px;
}

.historico-tabela th:last-child,
.historico-tabela td:last-child {
    border-right: 0;
}

.historico-tabela th {
    background: #111827;
    color: white;
    font-size: 12px;
    letter-spacing: .03em;
    text-transform: uppercase;
    white-space: nowrap;
}

.historico-tabela tbody tr:nth-child(even) {
    background: #f8fafc;
}

.historico-tabela tbody tr:hover {
    background: #eef2ff;
}

.historico-tabela .col-fornecedor {
    min-width: 150px;
    font-weight: bold;
}

.historico-tabela .col-observacao {
    min-width: 210px;
    max-width: 280px;
    white-space: normal;
}

.data-hora {
    white-space: nowrap;
}

.data-hora span,
.conferencia-detalhes {
    display: block;
    margin-top: 4px;
    color: #6b7280;
    font-size: 12px;
}

.status {
    display: inline-block;
    padding: 5px 9px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: bold;
    white-space: nowrap;
}

.status-conferido {
    background: #dcfce7;
    color: #166534;
}

.status-pendente {
    background: #fef3c7;
    color: #92400e;
}

.acoes {
    min-width: 150px;
}

.acoes a,
.acoes button {
    display: block;
    width: 100%;
    min-height: 36px;
    margin: 0 0 7px;
    padding: 8px 10px;
    border: 1px solid #d1d5db;
    border-radius: 7px;
    background: white;
    color: #111827;
    font: inherit;
    font-size: 12px;
    font-weight: bold;
    line-height: 18px;
    text-align: center;
    text-decoration: none;
    cursor: pointer;
}

.acoes form {
    margin: 0;
}

.acoes .acao-conferir {
    background: #111827;
    border-color: #111827;
    color: white;
}

.acoes .acao-excluir,
.acoes .acao-desfazer {
    color: #b91c1c;
    border-color: #fecaca;
}

.historico-vazio {
    margin: 0;
    padding: 24px 20px;
    color: #6b7280;
}

.dica-rolagem {
    display: none;
    margin: 0;
    padding: 10px 20px;
    background: #f8fafc;
    color: #6b7280;
    font-size: 12px;
    border-bottom: 1px solid #e5e7eb;
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

{% if session.get("usuario") == "ADMIN" %}
<a href="/configuracoes"
   style="display:flex;align-items:center;justify-content:center;
   width:100%;min-height:54px;background:#111827;color:white;
   padding:14px 18px;border-radius:9px;text-decoration:none;
   margin:0 0 22px;font-weight:bold;font-size:16px;">
    ⚙️ CONFIGURAÇÕES
</a>
{% endif %}

<a href="/logs"
   style="display:flex;align-items:center;justify-content:center;
   width:100%;min-height:54px;
   background:#111827;color:white;
   padding:14px 18px;border-radius:9px;
   text-decoration:none;margin:0 0 22px;
   font-weight:bold;font-size:16px;
   border:1px solid rgba(255,255,255,.18);
   box-shadow:0 3px 0 rgba(0,0,0,.30),0 6px 14px rgba(0,0,0,.16);">
    LOGS DO SISTEMA
</a>

<a href="/observacoes"
   style="display:flex;align-items:center;justify-content:center;
   width:100%;min-height:54px;
   background:#111827;color:white;
   padding:14px 18px;border-radius:9px;
   text-decoration:none;margin:0 0 22px;
   font-weight:bold;font-size:16px;
   border:1px solid rgba(255,255,255,.18);
   box-shadow:0 3px 0 rgba(0,0,0,.30),0 6px 14px rgba(0,0,0,.16);">
    GERENCIAR OBSERVAÇÕES
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
                    inputmode="numeric"
                    pattern="[0-9]*"
                        placeholder="Ex: 123456"
                    >
                </div>

                <div>
                    <label>Data da NF</label>
                    <input type="date" name="data_nf" required>

                    <label>Quantidade de volumes</label>
                    <input
                        type="number"
                        name="volumes"
                    inputmode="numeric"
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

            <details class="sugestoes-bloco">
                <summary>Selecionar sugestões rápidas</summary>

                <div class="sugestoes-lista">
                    {% for sugestao in sugestoes %}
                    <button
                        type="button"
                        onclick="adicionarObservacao(this.dataset.texto)"
                        data-texto="{{ sugestao['texto'] }}"
                        style="
                            width:auto;
                            min-height:38px;
                            padding:8px 12px;
                            margin:0;
                            border-radius:20px;
                            border:1px solid #d1d5db;
                            background:#f3f4f6;
                            color:#111827;
                            font-size:13px;
                            font-weight:600;
                            box-shadow:none;
                        "
                    >
                        {{ sugestao["texto"] }}
                    </button>
                    {% endfor %}
                </div>
            </details>

            <script>
            function adicionarObservacao(texto) {
                const campo = document.querySelector('textarea[name="observacao"]');
                if (!campo) return;

                const atual = campo.value.trim();

                if (!atual) {
                    campo.value = texto;
                } else if (!atual.includes(texto)) {
                    campo.value = atual + "; " + texto;
                }
            }
            </script>

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

    <div class="card historico-card">
        <div class="historico-titulo">
            <h2>Histórico</h2>
            <span class="total-registros">
                {{ registros|length }} registro{% if registros|length != 1 %}s{% endif %}
            </span>
        </div>

        {% if registros %}
        <p class="dica-rolagem">Deslize a grade para o lado para ver todas as colunas.</p>

        <div class="historico-grade">
            <table class="historico-tabela">
                <thead>
                    <tr>
                        <th>Fornecedor</th>
                        <th>Recebimento</th>
                        <th>NF</th>
                        <th>Data da NF</th>
                        <th>Volumes</th>
                        <th>Recebido por</th>
                        <th>Observação</th>
                        <th>Conferência</th>
                        <th>Ações</th>
                    </tr>
                </thead>
                <tbody>
                    {% for r in registros %}
                    <tr>
                        <td class="col-fornecedor">{{ r["fornecedor"] }}</td>

                        <td class="data-hora">
                            {{ r["data"] }}
                            <span>{{ r["hora"] }}</span>
                        </td>

                        <td>{{ r["nota_fiscal"] or "—" }}</td>

                        <td class="data-hora">
                            {% if r["data_nf"] %}
                                {{ r["data_nf"][8:10] }}/{{ r["data_nf"][5:7] }}/{{ r["data_nf"][0:4] }}
                            {% else %}
                                —
                            {% endif %}
                        </td>

                        <td>{{ r["volumes"] if r["volumes"] is not none else "—" }}</td>
                        <td>{{ r["funcionario"] or "—" }}</td>
                        <td class="col-observacao">{{ r["observacao"] or "—" }}</td>

                        <td>
                            {% if r["conferido"] %}
                                <span class="status status-conferido">Conferido</span>
                                <span class="conferencia-detalhes">
                                    Por: {{ r["conferido_por"] or "—" }}<br>
                                    Em: {{ r["conferido_em"] or "—" }}
                                </span>
                            {% else %}
                                <span class="status status-pendente">Pendente</span>
                            {% endif %}
                        </td>

                        <td class="acoes">
                            {% if not r["conferido"] %}
                            <form method="POST" action="/conferir/{{ r['id'] }}">
                                <button class="acao-conferir" type="submit">Marcar conferido</button>
                            </form>
                            {% elif session.get("nivel") == "admin" %}
                            <form method="POST" action="/desfazer-conferencia/{{ r['id'] }}" onsubmit="return confirm('Tem certeza que deseja desfazer esta conferência?');">
                                <button class="acao-desfazer" type="submit">Desfazer conferência</button>
                            </form>
                            {% endif %}

                            {% if session.get("nivel") == "admin" %}
                            <a href="/editar/{{ r['id'] }}">Editar</a>
                            <a
                                class="acao-excluir"
                                href="/excluir/{{ r['id'] }}"
                                onclick="return confirm('Excluir este recebimento?')"
                            >Excluir</a>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
            <p class="historico-vazio">Nenhum recebimento encontrado.</p>
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
            registrar_log(
                registro["usuario"],
                "LOGIN",
                "sessao",
                registro["id"],
                "Login realizado com sucesso"
            )
            return redirect(url_for("inicio"))

        erro = "Usuário ou senha inválidos."

    return render_template_string(LOGIN_HTML, erro=erro)


@app.route("/logout")
def logout():
    usuario = session.get("usuario", "desconhecido")
    usuario_id = session.get("usuario_id")
    registrar_log(
        usuario,
        "LOGOUT",
        "sessao",
        usuario_id,
        "Logout realizado"
    )
    session.clear()
    return redirect(url_for("login"))


@app.before_request
def exigir_login():
    if request.endpoint not in ("login", "static") and not session.get("logado"):
        return redirect(url_for("login"))




LOGS_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Logs do sistema</title>
<style>
* { box-sizing: border-box; }
body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f3f5f7;
    color: #222;
}
.container {
    max-width: 1100px;
    margin: 30px auto;
    padding: 20px;
}
.card {
    background: white;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 2px 10px rgba(0,0,0,.08);
}
h1 {
    margin-top: 0;
}
.tabela-wrap {
    overflow-x: auto;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 20px;
}
th, td {
    padding: 12px 10px;
    border-bottom: 1px solid #ddd;
    text-align: left;
    vertical-align: top;
}
th {
    background: #111827;
    color: white;
}
tr:hover {
    background: #f8fafc;
}
.detalhes {
    min-width: 300px;
    word-break: break-word;
}
.voltar {
    display: inline-block;
    margin-top: 20px;
    color: #111827;
    font-weight: bold;
}
.vazio {
    padding: 25px 0;
    color: #666;
}
</style>
</head>
<body>
<div class="container">
<div class="card">
<h1>Logs do sistema</h1>
<p>Registro das principais ações realizadas no sistema.</p>

{% if logs %}
<div class="tabela-wrap">
<table>
<thead>
<tr>
    <th>Data/Hora</th>
    <th>Usuário</th>
    <th>Ação</th>
    <th>Tipo</th>
    <th>ID</th>
    <th>Detalhes</th>
</tr>
</thead>
<tbody>
{% for log in logs %}
<tr>
    <td>{{ log["data_hora"] }}</td>
    <td>{{ log["usuario"] or "-" }}</td>
    <td>{{ log["acao"] }}</td>
    <td>{{ log["entidade"] or "-" }}</td>
    <td>{{ log["entidade_id"] or "-" }}</td>
    <td class="detalhes">{{ log["detalhes"] or "-" }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
{% else %}
<p class="vazio">Nenhum log registrado ainda.</p>
{% endif %}

<a class="voltar" href="/">Voltar ao sistema</a>
</div>
</div>
</body>
</html>
"""


@app.route("/logs")
def logs_sistema():
    if session.get("nivel") != "admin":
        return redirect(url_for("inicio"))

    banco = conectar()
    logs = banco.execute(
        """
        SELECT id, usuario, acao, entidade, entidade_id, detalhes, data_hora
        FROM logs
        ORDER BY id DESC
        LIMIT 500
        """
    ).fetchall()
    banco.close()

    return render_template_string(LOGS_HTML, logs=logs)



CONFIGURACOES_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Configurações</title>
<style>
body {
    font-family: Arial, sans-serif;
    background:#f3f4f6;
    margin:0;
    padding:20px;
}
.caixa {
    max-width:700px;
    margin:30px auto;
    background:white;
    padding:25px;
    border-radius:12px;
}
.opcao {
    display:block;
    padding:16px;
    margin:12px 0;
    background:#111827;
    color:white;
    text-decoration:none;
    border-radius:9px;
    font-weight:bold;
}
</style>
</head>
<body>
<div class="caixa">
<h1>⚙️ Configurações</h1>

<a class="opcao" href="/usuarios">Gerenciar usuários</a>
<a class="opcao" href="/observacoes">Gerenciar observações</a>
<a class="opcao" href="/logs">Logs do sistema</a>

<h2>Acesso aos logs</h2>

{% for a in admins %}
<div style="padding:12px 0;border-bottom:1px solid #ddd;">
    <strong>{{ a["usuario"] }}</strong>

    {% if a["pode_ver_logs"] %}
        <span> — ✅ Permitido</span>
        {% if a["usuario"] != "ADMIN" %}
        <form method="POST" action="/configuracoes/logs/{{ a['id'] }}/0" style="display:inline;">
            <button type="submit">Bloquear</button>
        </form>
        {% endif %}
    {% else %}
        <span> — ❌ Bloqueado</span>
        <form method="POST" action="/configuracoes/logs/{{ a['id'] }}/1" style="display:inline;">
            <button type="submit">Permitir</button>
        </form>
    {% endif %}
</div>
{% endfor %}


<a href="/">Voltar ao sistema</a>
</div>
</body>
</html>
"""

@app.route("/configuracoes")
def configuracoes():
    if session.get("usuario") != "ADMIN":
        return redirect(url_for("inicio"))

    banco = conectar()
    admins = banco.execute(
        """
        SELECT id, usuario, pode_ver_logs
        FROM usuarios
        WHERE nivel = 'admin'
        ORDER BY usuario
        """
    ).fetchall()
    banco.close()

    return render_template_string(
        CONFIGURACOES_HTML,
        admins=admins
    )


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

   <form method="POST" action="/usuarios/excluir/{{ u['id'] }}" onsubmit="return confirm('Tem certeza que deseja excluir este usuC!rio?');">
    <button type="submit" style="width:auto; padding:6px 12px; display:inline-block;">Excluir</button>
</form>
        {% if session.get("usuario") == "ADMIN" %}
        <form method="POST" action="/usuarios/senha/{{ u['id'] }}" style="margin-top:8px;">
            <input type="password" name="senha_admin" placeholder="Senha atual do ADMIN" required style="width:auto;padding:6px 12px;margin-right:6px;">
            <input type="password" name="senha" placeholder="Nova senha" required style="width:auto;padding:6px 12px;margin-right:6px;">
            <button type="submit" style="width:auto;padding:6px 12px;">Alterar senha</button>
        </form>
        {% endif %}
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

            registrar_log(
                session.get("usuario"),
                "CRIOU USUARIO",
                "usuario",
                None,
                f"Usuário criado: {usuario} | nível: {nivel}"
            )

    lista = banco.execute(
        "SELECT id, usuario, nivel FROM usuarios ORDER BY usuario"
    ).fetchall()

    banco.close()

    return render_template_string(USUARIOS_HTML, usuarios=lista)
   
@app.route("/usuarios/excluir/<int:id_usuario>", methods=["POST"])
def excluir_usuario(id_usuario):
    if session.get("nivel") != "admin":
        return redirect(url_for("inicio"))

    if id_usuario == session.get("usuario_id"):
        return redirect(url_for("usuarios"))

    banco = conectar()

    usuario_excluido = banco.execute(
        "SELECT usuario, nivel FROM usuarios WHERE id = ?",
        (id_usuario,)
    ).fetchone()

    banco.execute(
        "DELETE FROM usuarios WHERE id = ?",
        (id_usuario,)
    )
    banco.commit()
    banco.close()

    if usuario_excluido:
        registrar_log(
            session.get("usuario"),
            "EXCLUIU USUARIO",
            "usuario",
            id_usuario,
            f"Usuário excluído: {usuario_excluido['usuario']} | nível: {usuario_excluido['nivel']}"
        )

    return redirect(url_for("usuarios"))

@app.route("/usuarios/senha/<int:id_usuario>", methods=["POST"])
def alterar_senha_usuario(id_usuario):
    if session.get("usuario") != "ADMIN":
        return redirect(url_for("inicio"))

    senha_admin = request.form.get("senha_admin", "")
    nova_senha = request.form.get("senha", "")

    banco = conectar()

    admin = banco.execute(
        "SELECT senha FROM usuarios WHERE usuario = ?",
        ("ADMIN",)
    ).fetchone()

    if not admin or not check_password_hash(admin["senha"], senha_admin):
        banco.close()
        return redirect(url_for("usuarios"))

    if not nova_senha:
        banco.close()
        return redirect(url_for("usuarios"))

    banco.execute(
        "UPDATE usuarios SET senha = ? WHERE id = ?",
        (generate_password_hash(nova_senha), id_usuario)
    )
    banco.commit()
    banco.close()

    registrar_log(
        "ADMIN",
        "ALTEROU SENHA",
        "usuario",
        id_usuario,
        "Senha alterada pelo ADMIN"
    )

    return redirect(url_for("usuarios"))


@app.route("/conferir/<int:id_recebimento>", methods=["POST"])
def conferir_recebimento(id_recebimento):
    if "usuario" not in session:
        return redirect(url_for("login"))

    banco = conectar()
    banco.execute(
        """UPDATE recebimentos
        SET conferido = 1,
        conferido_por = ?,
        conferido_em = ?
        WHERE id = ?""",
        (session["usuario"], datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M"), id_recebimento)
    )
    banco.commit()
    banco.close()

    registrar_log(
        session.get("usuario"),
        "CONFERENCIA",
        "recebimento",
        id_recebimento,
        "Recebimento marcado como conferido"
    )

    return redirect(url_for("inicio"))

@app.route("/desfazer-conferencia/<int:id_recebimento>", methods=["POST"])
def desfazer_conferencia(id_recebimento):
    if session.get("nivel") != "admin":
        return redirect(url_for("inicio"))

    banco = conectar()
    banco.execute(
        """UPDATE recebimentos
        SET conferido = 0,
            conferido_por = NULL,
            conferido_em = NULL
        WHERE id = ?""",
        (id_recebimento,)
    )
    banco.commit()
    banco.close()

    registrar_log(
        session.get("usuario"),
        "DESFEZ CONFERENCIA",
        "recebimento",
        id_recebimento,
        "Conferência do recebimento removida"
    )

    return redirect(url_for("inicio"))


OBSERVACOES_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Gerenciar observações</title>
<style>
* { box-sizing: border-box; }

body {
    margin: 0;
    padding: 20px;
    background: #f3f4f6;
    font-family: Arial, sans-serif;
    color: #111827;
}

.caixa {
    max-width: 750px;
    margin: auto;
    background: white;
    padding: 24px;
    border-radius: 14px;
}

.item {
    padding: 14px 0;
    border-bottom: 1px solid #ddd;
}

.inativo {
    opacity: .45;
}

a {
    color: #111827;
}
</style>
</head>
<body>

<div class="caixa">
    <h1>Gerenciar observações</h1>

    <h2>Nova sugestão</h2>

    <form method="POST" action="/observacoes/adicionar">
        <input
            name="texto"
            placeholder="Digite uma nova sugestão"
            required
            style="width:100%;padding:13px;border:1px solid #d1d5db;
            border-radius:9px;font-size:16px;margin-bottom:10px;"
        >

        <button
            type="submit"
            style="width:100%;padding:13px;border:0;border-radius:9px;
            background:#111827;color:white;font-weight:bold;font-size:15px;"
        >
            ADICIONAR SUGESTÃO
        </button>
    </form>

    <h2 style="margin-top:30px;">Sugestões cadastradas</h2>

    {% for s in sugestoes_observacao %}
    <div class="item {% if not s['ativo'] %}inativo{% endif %}">

        <form method="POST" action="/observacoes/editar/{{ s['id'] }}">
            <input
                name="texto"
                value="{{ s['texto'] }}"
                required
                style="width:100%;padding:12px;border:1px solid #d1d5db;
                border-radius:9px;font-size:15px;margin-bottom:8px;"
            >

            <button
                type="submit"
                style="width:100%;padding:11px;border:0;border-radius:9px;
                background:#111827;color:white;font-weight:bold;"
            >
                SALVAR ALTERAÇÃO
            </button>
        </form>

        <form
            method="POST"
            action="/observacoes/toggle/{{ s['id'] }}"
            style="margin-top:8px;"
        >
            <button
                type="submit"
                style="width:100%;padding:11px;border:1px solid #111827;
                border-radius:9px;background:white;color:#111827;
                font-weight:bold;"
            >
                {% if s["ativo"] %}
                    DESATIVAR
                {% else %}
                    ATIVAR
                {% endif %}
            </button>
        </form>

    </div>
    {% endfor %}

    <p style="margin-top:25px;">
        <a href="/">Voltar ao sistema</a>
    </p>
</div>

</body>
</html>
"""


@app.route("/observacoes")
def gerenciar_observacoes():
    if session.get("nivel") != "admin":
        return redirect(url_for("inicio"))

    banco = conectar()

    lista = banco.execute("""
        SELECT id, texto, ativo
        FROM sugestoes_observacao
        ORDER BY texto
    """).fetchall()

    banco.close()

    return render_template_string(
        OBSERVACOES_HTML,
        sugestoes_observacao=lista
    )


@app.route("/observacoes/adicionar", methods=["POST"])
def adicionar_observacao():
    if session.get("nivel") != "admin":
        return redirect(url_for("inicio"))

    texto = request.form.get("texto", "").strip()

    if texto:
        banco = conectar()
        banco.execute(
            """
            INSERT INTO sugestoes_observacao (texto, ativo)
            VALUES (?, 1)
            ON CONFLICT (texto) DO UPDATE SET ativo = 1
            """,
            (texto,)
        )
        banco.commit()
        banco.close()

    return redirect(url_for("gerenciar_observacoes"))


@app.route("/observacoes/editar/<int:id>", methods=["POST"])
def editar_observacao(id):
    if session.get("nivel") != "admin":
        return redirect(url_for("inicio"))

    texto = request.form.get("texto", "").strip()

    if texto:
        banco = conectar()
        banco.execute(
            "UPDATE sugestoes_observacao SET texto = ? WHERE id = ?",
            (texto, id)
        )
        banco.commit()
        banco.close()

    return redirect(url_for("gerenciar_observacoes"))


@app.route("/observacoes/toggle/<int:id>", methods=["POST"])
def toggle_observacao(id):
    if session.get("nivel") != "admin":
        return redirect(url_for("inicio"))

    banco = conectar()
    banco.execute(
        """
        UPDATE sugestoes_observacao
        SET ativo = CASE WHEN ativo = 1 THEN 0 ELSE 1 END
        WHERE id = ?
        """,
        (id,)
    )
    banco.commit()
    banco.close()

    return redirect(url_for("gerenciar_observacoes"))


@app.route("/")
def inicio():
    pesquisa = request.args.get("q", "").strip()

    banco = conectar()

    sugestoes = banco.execute("""
        SELECT id, texto
        FROM sugestoes_observacao
        WHERE ativo = 1
        ORDER BY texto
    """).fetchall()

    if pesquisa:
        registros = banco.execute("""
            SELECT *
            FROM recebimentos
            WHERE fornecedor ILIKE ?
               OR nota_fiscal ILIKE ?
            ORDER BY
                CASE WHEN nota_fiscal = ? THEN 0 ELSE 1 END,
                id DESC
        """, (
            f"%{pesquisa}%",
            f"%{pesquisa}%",
            pesquisa
        )).fetchall()
    else:
        registros = banco.execute("""
            SELECT *
            FROM recebimentos
            ORDER BY id DESC
            LIMIT 100
        """).fetchall()

    hoje = datetime.now(ZoneInfo("America/Sao_Paulo"))

    inicio_semana = hoje.date().fromordinal(
        hoje.date().toordinal() - hoje.weekday()
    )

    total_hoje = banco.execute(
        "SELECT COUNT(*) AS total FROM recebimentos WHERE data = ?",
        (hoje.strftime("%d/%m/%Y"),)
    ).fetchone()["total"]

    total_semana = banco.execute(
        """
        SELECT COUNT(*) AS total
        FROM recebimentos
        WHERE TO_DATE(data, 'DD/MM/YYYY') BETWEEN ?::date AND ?::date
        """,
        (inicio_semana.isoformat(), hoje.date().isoformat())
    ).fetchone()["total"]

    total_pendentes = banco.execute(
        "SELECT COUNT(*) AS total FROM recebimentos WHERE conferido = 0"
    ).fetchone()["total"]

    total_conferidos = banco.execute(
        "SELECT COUNT(*) AS total FROM recebimentos WHERE conferido = 1"
    ).fetchone()["total"]

    banco.close()

    return render_template_string(
        HTML,
        registros=registros,
        pesquisa=pesquisa,
        sugestoes=sugestoes,
        total_hoje=total_hoje,
        total_semana=total_semana,
        total_pendentes=total_pendentes,
        total_conferidos=total_conferidos
    )


@app.route("/registrar", methods=["POST"])
def registrar():
    fornecedor = request.form["fornecedor"].strip()
    nota_fiscal = request.form["nota_fiscal"].strip()
    data_nf = request.form.get("data_nf", "").strip()
    funcionario = session.get("usuario", "")
    observacao = request.form["observacao"].strip()

    volumes = request.form["volumes"].strip()

    if volumes:
        volumes = int(volumes)
    else:
        volumes = None

    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))

    data = agora.strftime("%d/%m/%Y")
    hora = agora.strftime("%H:%M:%S")

    banco = conectar()

    banco.execute("""
        INSERT INTO recebimentos
        (
            fornecedor,
            nota_fiscal,
            data_nf,
            volumes,
            funcionario,
            observacao,
            data,
            hora
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        fornecedor,
        nota_fiscal,
        data_nf,
        volumes,
        funcionario,
        observacao,
        data,
        hora
    ))

    banco.commit()
    banco.close()

    return redirect("/")




EDITAR_HTML = """

<!DOCTYPE html>

<html lang="pt-BR">

<head>

<meta charset="UTF-8">

<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Editar recebimento</title>

<style>

* { box-sizing: border-box; }

body {

    margin: 0;

    padding: 20px;

    background: #f3f4f6;

    font-family: Arial, sans-serif;

    color: #111827;

}

.caixa {

    max-width: 700px;

    margin: auto;

    background: white;

    padding: 24px;

    border-radius: 14px;

}

label {

    display: block;

    font-weight: bold;

    margin-top: 16px;

    margin-bottom: 6px;

}

input, textarea, button {

    width: 100%;

    padding: 13px;

    border-radius: 9px;

    font-size: 16px;

}

input, textarea {

    border: 1px solid #d1d5db;

}

textarea {

    min-height: 110px;

}

button {

    margin-top: 20px;

    border: 0;

    background: #111827;

    color: white;

    font-weight: bold;

}

.info {

    margin-top: 18px;

    padding: 12px;

    background: #f3f4f6;

    border-radius: 9px;

}

</style>

</head>

<body>

<div class="caixa">

    <h1>Editar recebimento</h1>

    <form method="POST">

        <label>Fornecedor</label>

        <input

            name="fornecedor"

            value="{{ registro['fornecedor'] }}"

            required

        >

        <label>Nota fiscal</label>

        <input

            name="nota_fiscal"

            value="{{ registro['nota_fiscal'] or '' }}"

            inputmode="numeric"

            pattern="[0-9]*"

        >

        <label>Data da NF</label>
        <input type="date" name="data_nf" value="{{ registro['data_nf'] or '' }}">

        <label>Quantidade de volumes</label>

        <input

            type="number"

            name="volumes"

            value="{{ registro['volumes'] or '' }}"

            min="0"

            inputmode="numeric"

        >

        <label>Observação</label>

        <textarea name="observacao">{{ registro['observacao'] or '' }}</textarea>

        <div class="info">

            <strong>Recebido por:</strong> {{ registro['funcionario'] }}<br>

            <strong>Data:</strong> {{ registro['data'] }} às {{ registro['hora'] }}

        </div>

        <button type="submit">SALVAR ALTERAÇÕES</button>

    </form>

    <p><a href="/">Voltar ao sistema</a></p>

</div>

</body>

</html>

"""

@app.route("/editar/<int:id>", methods=["GET", "POST"])

def editar_recebimento(id):

    if session.get("nivel") != "admin":

        return redirect(url_for("inicio"))

    banco = conectar()

    registro = banco.execute(

        "SELECT * FROM recebimentos WHERE id = ?",

        (id,)

    ).fetchone()

    if not registro:

        banco.close()

        return redirect(url_for("inicio"))

    if request.method == "POST":

        fornecedor = request.form.get("fornecedor", "").strip()

        nota_fiscal = request.form.get("nota_fiscal", "").strip()

        data_nf = request.form.get("data_nf", "").strip()

        observacao = request.form.get("observacao", "").strip()

        volumes_txt = request.form.get("volumes", "").strip()

        volumes = int(volumes_txt) if volumes_txt else None

        banco.execute(

            """

            UPDATE recebimentos

            SET fornecedor = ?,

                nota_fiscal = ?,

                volumes = ?,

                observacao = ?

            WHERE id = ?

            """,

            (

                fornecedor,

                nota_fiscal,

                volumes,

                observacao,

                id

            )

        )

        banco.commit()

        alteracoes = []

        if registro["fornecedor"] != fornecedor:
            alteracoes.append(f'Fornecedor: {registro["fornecedor"]} -> {fornecedor}')

        if registro["nota_fiscal"] != nota_fiscal:
            alteracoes.append(f'NF: {registro["nota_fiscal"]} -> {nota_fiscal}')

        if registro["volumes"] != volumes:
            alteracoes.append(f'Volumes: {registro["volumes"]} -> {volumes}')

        if registro["observacao"] != observacao:
            alteracoes.append(f'Observação: {registro["observacao"]} -> {observacao}')

        registrar_log(
            session.get("usuario"),
            "EDITOU RECEBIMENTO",
            "recebimento",
            id,
            " | ".join(alteracoes) if alteracoes else "Salvou sem alterações"
        )

        banco.close()

        return redirect(url_for("inicio"))

    banco.close()

    return render_template_string(

        EDITAR_HTML,

        registro=registro

    )

@app.route("/excluir/<int:id>")
def excluir(id):
    if session.get("nivel") != "admin":
        return redirect(url_for("inicio"))

    banco = conectar()

    registro = banco.execute(
        """
        SELECT fornecedor, nota_fiscal, volumes, observacao
        FROM recebimentos
        WHERE id = ?
        """,
        (id,)
    ).fetchone()

    banco.execute(
        "DELETE FROM recebimentos WHERE id = ?",
        (id,)
    )

    banco.commit()
    banco.close()

    if registro:
        registrar_log(
            session.get("usuario"),
            "EXCLUIU RECEBIMENTO",
            "recebimento",
            id,
            f'Fornecedor: {registro["fornecedor"]} | NF: {registro["nota_fiscal"]} | Volumes: {registro["volumes"]} | Observação: {registro["observacao"]}'
        )

    return redirect("/")


criar_banco()

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )

@app.route("/configuracoes/logs/<int:id_usuario>/<int:valor>", methods=["POST"])
def configurar_acesso_logs(id_usuario, valor):
    if session.get("usuario") != "ADMIN":
        return redirect(url_for("inicio"))

    valor = 1 if valor == 1 else 0

    banco = conectar()

    usuario = banco.execute(
        "SELECT usuario FROM usuarios WHERE id = ?",
        (id_usuario,)
    ).fetchone()

    if usuario and usuario["usuario"] != "ADMIN":
        banco.execute(
            "UPDATE usuarios SET pode_ver_logs = ? WHERE id = ?",
            (valor, id_usuario)
        )
        banco.commit()

    banco.close()

    return redirect(url_for("configuracoes"))
