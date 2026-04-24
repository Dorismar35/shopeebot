import os
import threading
import logging
import sqlite3
from flask import Flask, render_template_string, jsonify, redirect, url_for, send_from_directory, send_file
from dotenv import load_dotenv
import motor
from banco.db import listar_todos, resetar, inicializar

load_dotenv()

IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "banco", "imagens")

logger = logging.getLogger("painel")
app    = Flask(__name__)

# Rota definitiva para servir a imagem pelo ID da oferta
@app.route("/imagem_produto/<int:oid>")
def servir_imagem_por_id(oid):
    from flask import Response
    from banco.db import DB_PATH
    try:
        with sqlite3.connect(str(DB_PATH), timeout=10) as con:
            con.row_factory = sqlite3.Row
            res = con.execute("SELECT imagem_path FROM ofertas WHERE id=?", (oid,)).fetchone()
            if res and res["imagem_path"] and os.path.exists(res["imagem_path"]):
                with open(res["imagem_path"], "rb") as f:
                    return Response(f.read(), mimetype="image/jpeg")
    except Exception as e:
        logger.error(f"Erro ao servir imagem ID {oid}: {e}")
    return "Imagem não encontrada", 404

_bot_thread = None

# ── HTML do painel ──────────────────────────────────────────────────────────────
TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ShopeeBot Mission Control</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="icon" href="data:,">
<style>
:root{--orange:#ff5722;--cyan:#00e5ff;--green:#00ff88;--red:#ff1744;--yellow:#ffd600;--bg:#050810;--bg2:#0a0f1e;--border:rgba(0,229,255,0.12);--text:#c8d6f0;--dim:#3a5070;}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;min-height:100vh;}
body::before{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(0,229,255,0.025) 1px,transparent 1px),linear-gradient(90deg,rgba(0,229,255,0.025) 1px,transparent 1px);background-size:40px 40px;pointer-events:none;z-index:0;}
.wrap{position:relative;z-index:1;max-width:1400px;margin:0 auto;padding:0 24px 40px;}
header{display:flex;align-items:center;justify-content:space-between;padding:18px 0 16px;border-bottom:1px solid var(--border);margin-bottom:24px;}
.logo{display:flex;align-items:center;gap:14px;}
.logo-icon{width:44px;height:44px;background:linear-gradient(135deg,#ff5722,#ff8c42);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:22px;box-shadow:0 0 18px rgba(255,87,34,0.35);}
.logo h1{font-family:'Orbitron',monospace;font-size:18px;font-weight:900;color:#fff;letter-spacing:2px;}
.logo p{font-family:'Share Tech Mono',monospace;font-size:10px;color:var(--cyan);letter-spacing:3px;margin-top:2px;}
.hright{display:flex;align-items:center;gap:16px;}
.online{display:flex;align-items:center;gap:7px;background:rgba(0,255,136,0.07);border:1px solid rgba(0,255,136,0.18);border-radius:20px;padding:5px 13px;font-family:'Share Tech Mono',monospace;font-size:11px;color:var(--green);}
.dot{width:7px;height:7px;background:var(--green);border-radius:50%;animation:pulse 2s infinite;}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(0,255,136,0.4);}50%{box-shadow:0 0 0 5px rgba(0,255,136,0);}}
.clk{font-family:'Share Tech Mono',monospace;font-size:13px;color:var(--dim);}

.stats-container{display: flex; gap: 12px; margin-bottom: 20px;}
.stats{flex: 3; display:grid; grid-template-columns:repeat(4,1fr); gap:12px;}
.sc{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:18px 14px;position:relative;overflow:hidden;}
.sc::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--ac,var(--cyan));box-shadow:0 0 10px var(--ac,var(--cyan));}
.sc-label{font-family:'Share Tech Mono',monospace;font-size:9px;letter-spacing:2px;color:var(--dim);text-transform:uppercase;margin-bottom:8px;}
.sc-val{font-family:'Orbitron',monospace;font-size:30px;font-weight:700;color:var(--ac,var(--cyan));text-shadow:0 0 15px var(--ac,var(--cyan));}
.sc-sub{font-size:11px;color:var(--dim);margin-top:4px;}
.c1{--ac:var(--cyan);}.c2{--ac:var(--orange);}.c3{--ac:var(--green);}.c4{--ac:var(--red);}.c5{--ac:var(--yellow);}

.destaque-card{flex: 1.2; background: var(--bg2); border: 1px solid var(--orange); border-radius: 12px; padding: 18px; display: flex; flex-direction: column; justify-content: center; align-items: center; background: rgba(255,87,34,0.05);}
.destaque-label{font-family:'Share Tech Mono',monospace; font-size: 10px; color: var(--orange); letter-spacing: 2px; margin-bottom: 10px;}
.destaque-nome{font-size: 15px; font-weight: 700; text-align: center; color: #fff; margin-bottom: 8px; font-family: 'Rajdhani', sans-serif;}
.destaque-val{font-family:'Orbitron',monospace; font-size: 36px; color: var(--orange); text-shadow: 0 0 15px var(--orange);}

.actions{margin-bottom: 20px; display: flex; gap: 12px; align-items: center;}
.btn{display: inline-flex; align-items: center; gap: 8px; padding: 12px 24px; border-radius: 8px; font-family: 'Orbitron', sans-serif; font-size: 11px; font-weight: 700; text-decoration: none; transition: 0.3s; cursor: pointer; border: none; letter-spacing: 1px;}
.btn-primary{background: var(--green); color: #050810; box-shadow: 0 0 15px rgba(0,255,136,0.3);}
.btn-primary:hover{box-shadow: 0 0 25px rgba(0,255,136,0.5); transform: translateY(-2px);}
.ult-box{font-family:'Share Tech Mono',monospace; font-size: 11px; color: var(--dim); background: var(--bg2); border: 1px solid var(--border); padding: 12px 18px; border-radius: 8px;}

.tbox{background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;}
.thead2{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--border);}
.ttitle{font-family:'Orbitron',monospace;font-size:11px;font-weight:700;letter-spacing:2px;color:var(--cyan);}
.tcount{font-family:'Share Tech Mono',monospace;font-size:10px;color:var(--dim);}
table{width:100%;border-collapse:collapse;}
th{padding:10px 14px;text-align:left;font-family:'Share Tech Mono',monospace;font-size:9px;letter-spacing:2px;color:var(--dim);text-transform:uppercase;background:rgba(0,229,255,0.02);border-bottom:1px solid var(--border);}
td{padding:11px 14px;border-bottom:1px solid rgba(255,255,255,0.02);font-size:13px;}
tr:last-child td{border-bottom:none;}
tr:hover td{background:rgba(0,229,255,0.015);}
.pname{font-weight:600;}
.dbadge{display:inline-block;padding:2px 9px;border-radius:20px;font-family:'Orbitron',monospace;font-size:9px;font-weight:700;background:rgba(255,87,34,.12);color:var(--orange);border:1px solid rgba(255,87,34,.25);}
.price{font-family:'Share Tech Mono',monospace;font-size:12px;color:#ff8c42;}
.sb{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:20px;font-family:'Share Tech Mono',monospace;font-size:9px;}
.ok{background:rgba(0,255,136,.08);color:var(--green);border:1px solid rgba(0,255,136,.15);}
.pend{background:rgba(255,214,0,.08);color:var(--yellow);border:1px solid rgba(255,214,0,.15);}
.err{background:rgba(255,23,68,.08);color:var(--red);border:1px solid rgba(255,23,68,.15);}
.dtext{font-family:'Share Tech Mono',monospace;font-size:10px;color:var(--dim);}
.empty{text-align:center;padding:50px;color:var(--dim);}
</style>
<script>
// ATUALIZAÇÃO INTELIGENTE (30 SEGUNDOS)
setInterval(function(){
  fetch('/api/stats').then(function(r){return r.json();}).then(function(d){
    document.getElementById('v1').textContent=d.buscas;
    document.getElementById('v2').textContent=d.gerados;
    document.getElementById('v3').textContent=d.postados;
    document.getElementById('v4').textContent=d.erros;
    document.getElementById('ult').textContent='⟳ ÚLTIMA ATUALIZAÇÃO: '+d.ultima_execucao;
  });
}, 30000);

// REMOVIDO: Recarregamento automático da página removido para evitar incômodo visual
// O painel já atualiza os dados via API a cada 30 segundos.

function tick(){
  var n=new Date();
  document.getElementById('clk').textContent=
    String(n.getHours()).padStart(2,'0')+':'+
    String(n.getMinutes()).padStart(2,'0')+':'+
    String(n.getSeconds()).padStart(2,'0');
}
setInterval(tick,1000);tick();
</script>
</head>
<body>
<div class="wrap">
<header>
  <div class="logo">
    <div class="logo-icon">&#128717;</div>
    <div><h1>SHOPEEBOT</h1><p>MISSION CONTROL v2.0</p></div>
  </div>
  <div class="hright">
    <div class="online"><div class="dot"></div>SISTEMA ONLINE</div>
    <div class="clk" id="clk">00:00:00</div>
  </div>
</header>

<div class="stats-container">
  <div class="stats">
    <div class="sc c1"><div class="sc-label">Buscas</div><div class="sc-val" id="v1">{{s.buscas}}</div><div class="sc-sub">realizadas</div></div>
    <div class="sc c2"><div class="sc-label">Imagens</div><div class="sc-val" id="v2">{{s.gerados}}</div><div class="sc-sub">geradas</div></div>
    <div class="sc c3"><div class="sc-label">Posts TikTok</div><div class="sc-val" id="v3">{{s.postados}}</div><div class="sc-sub">publicados</div></div>
    <div class="sc c4"><div class="sc-label">Erros</div><div class="sc-val" id="v4">{{s.erros}}</div><div class="sc-sub">capturados</div></div>
  </div>
  
  <div class="destaque-card">
    <div class="destaque-label">MELHOR OFERTA HOJE</div>
    <div class="destaque-nome">{{ofertas[0].nome[:60] if ofertas else '---'}}</div>
    <div class="destaque-val">{{ofertas[0].desconto if ofertas else 0}}% OFF</div>
  </div>
</div>

<div class="actions">
    <a href="/ciclo" class="btn btn-primary">🚀 FORÇAR BUSCA E POSTAGEM AGORA</a>
    <div class="ult-box" id="ult">⟳ ÚLTIMA ATUALIZAÇÃO: {{s.ultima_execucao}}</div>
</div>

<div class="tbox">
  <div class="thead2">
    <div class="ttitle">◈ HISTÓRICO DE POSTAGENS TIKTOK</div>
    <div class="tcount">{{ofertas|length}} registros</div>
  </div>
  <table>
    <thead>
      <tr>
        <th>Mídia</th>
        <th>Produto</th>
        <th>Desconto</th>
        <th>Preço</th>
        <th>ID TikTok</th>
        <th>Status</th>
        <th>Data/Hora</th>
      </tr>
    </thead>
    <tbody>
    {% for o in ofertas %}
    <tr {% if o.postado %}style="background: rgba(0,255,136,0.03)"{% endif %}>
      <td>
        <div style="width:50px; height:50px; border-radius:6px; overflow:hidden; border:1px solid var(--border); background:var(--bg);">
          {% if o.imagem_path %}
            <img src="/imagem_produto/{{o.id}}" style="width:100%; height:100%; object-fit:cover;">
          {% else %}
            <div style="display:flex; align-items:center; justify-content:center; height:100%; font-size:20px;">📦</div>
          {% endif %}
        </div>
      </td>
      <td>
        <span class="pname">{% if o.postado %}📱 {% endif %}{{o.nome[:45]}}{% if o.nome|length > 45 %}...{% endif %}</span>
      </td>
      <td><span class="dbadge">-{{o.desconto}}%</span></td>
      <td><span class="price">R$ {{'{:.2f}'.format(o.preco)}}</span></td>
      <td class="dtext">{{o.publish_id if o.publish_id else '—'}}</td>
      <td>
        {% if o.postado %}
          <span class="sb ok">✓ POSTADO</span>
        {% elif o.status_tt == 'ERRO' %}
          <span class="sb err">✗ ERRO</span>
        {% else %}
          <span class="sb pend">⏳ AGUARDANDO</span>
        {% endif %}
      </td>
      <td><span class="dtext">{{o.criado_em}}</span></td>
    </tr>
    {% endfor %}
    {% if not ofertas %}
    <tr><td colspan="7"><div class="empty"><p>NENHUMA POSTAGEM ENCONTRADA - O MOTOR ESTÁ EM EXECUÇÃO</p></div></td></tr>
    {% endif %}
    </tbody>
  </table>
</div>
</div>
</body>
</html>
"""

# --- ROTAS DA LANDING PAGE (Para aprovação do TikTok) ---
@app.route("/")
def landing_page():
    # Serve o index.html da pasta landing_page
    return send_from_directory("landing_page", "index.html")

@app.route("/privacidade.html")
def privacy():
    return send_from_directory("landing_page", "privacidade.html")

@app.route("/termos.html")
def terms():
    return send_from_directory("landing_page", "termos.html")

# --- ROTA DO PAINEL DE CONTROLE (Dashboard) ---
@app.route("/dashboard")
def index():
    inicializar()
    ofertas = listar_todos(50)
    return render_template_string(
        TEMPLATE,
        s=motor.get_stats(),
        ofertas=ofertas,
    )

@app.route("/api/stats")
def api_stats():
    stats = motor.get_stats()
    logger.info(f"[API] Stats enviadas para o painel: {stats}")
    return jsonify(stats)

@app.route("/iniciar")
def iniciar():
    global _bot_thread
    if _bot_thread is None or not _bot_thread.is_alive():
        _bot_thread = threading.Thread(target=motor.iniciar, daemon=True)
        _bot_thread.start()
        logger.info("Bot iniciado pelo painel")
    return redirect(url_for("index"))

@app.route("/parar")
def parar():
    motor.parar()
    return redirect(url_for("index"))

@app.route("/ciclo")
def executar_ciclo():
    threading.Thread(target=motor.ciclo_completo, daemon=True).start()
    return redirect(url_for("index"))

@app.route("/reset")
def reset_db():
    resetar()
    return redirect(url_for("index"))

if __name__ == "__main__":
    porta = int(os.getenv("PORTA_PAINEL", 5020))
    logger.info(f"Painel rodando em http://localhost:{porta}")
    
    # Inicia o motor do bot automaticamente em segundo plano
    if _bot_thread is None or not _bot_thread.is_alive():
        _bot_thread = threading.Thread(target=motor.iniciar, daemon=True)
        _bot_thread.start()
        logger.info("Motor do bot iniciado automaticamente com o painel")

    app.run(host="0.0.0.0", port=porta, debug=False)
