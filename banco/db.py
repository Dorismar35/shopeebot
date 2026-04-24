import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("banco")

DB_PATH = Path(__file__).parent / "shopeebot.db"


def conectar():
    con = sqlite3.connect(str(DB_PATH), timeout=10, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=10000")
    return con


def inicializar():
    """Cria as tabelas se não existirem."""
    with conectar() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS ofertas (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nome        TEXT,
            loja        TEXT,
            preco       REAL,
            desconto    INTEGER,
            avaliacao   REAL,
            vendas      INTEGER,
            link        TEXT UNIQUE,
            imagem_path TEXT,
            legenda     TEXT,
            postado     INTEGER DEFAULT 0,
            publish_id  TEXT,
            status_tt   TEXT DEFAULT 'PENDENTE',
            criado_em   TEXT DEFAULT (datetime('now','localtime')),
            postado_em  TEXT
        );

        CREATE TABLE IF NOT EXISTS log_execucao (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            evento      TEXT,
            detalhes    TEXT,
            criado_em   TEXT DEFAULT (datetime('now','localtime'))
        );
        """)
    logger.info("Banco inicializado.")


def salvar_oferta(produto: dict, imagem_path: str, legenda: str) -> int | None:
    """Salva oferta no banco. Retorna o ID ou None se já existir."""
    try:
        with conectar() as con:
            cur = con.execute(
                """INSERT OR IGNORE INTO ofertas
                   (nome, loja, preco, desconto, avaliacao, vendas, link, imagem_path, legenda)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (produto["nome"], produto["loja"], produto["preco"], produto["desconto"],
                 produto["avaliacao"], produto["vendas"], produto["link"],
                 str(imagem_path), legenda),
            )
            return cur.lastrowid if cur.rowcount else None
    except Exception as e:
        logger.error(f"Erro ao salvar oferta: {e}")
        return None


def marcar_postado(oferta_id: int, publish_id: str, status: str):
    with conectar() as con:
        con.execute(
            """UPDATE ofertas SET postado=1, publish_id=?, status_tt=?, postado_em=datetime('now','localtime')
               WHERE id=?""",
            (publish_id, status, oferta_id),
        )


def marcar_erro(oferta_id: int, motivo: str):
    """Marca uma oferta como erro para não ficar travada em PENDENTE."""
    with conectar() as con:
        con.execute(
            "UPDATE ofertas SET status_tt='ERRO', postado=0 WHERE id=?",
            (oferta_id,)
        )


def listar_pendentes() -> list[dict]:
    with conectar() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM ofertas WHERE postado=0 ORDER BY desconto DESC").fetchall()
        return [dict(r) for r in rows]


def listar_todos(limite: int = 50) -> list[dict]:
    with conectar() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT * FROM ofertas ORDER BY criado_em DESC LIMIT ?", (limite,)
        ).fetchall()
        return [dict(r) for r in rows]


def registrar_log(evento: str, detalhes: str = ""):
    try:
        with conectar() as con:
            con.execute(
                "INSERT INTO log_execucao (evento, detalhes) VALUES (?,?)",
                (evento, detalhes),
            )
    except Exception:
        pass


def resetar():
    """Apaga todos os dados (equivalente ao reset_db dos outros bots)."""
    with conectar() as con:
        con.executescript("DELETE FROM ofertas; DELETE FROM log_execucao;")
    logger.info("Banco resetado.")


def get_estatisticas_reais() -> dict:
    """Retorna o total de registros reais do banco de dados."""
    try:
        with conectar() as con:
            con.row_factory = sqlite3.Row
            
            total_ofertas = con.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0]
            total_postados = con.execute("SELECT COUNT(*) FROM ofertas WHERE postado=1").fetchone()[0]
            total_erros = con.execute("SELECT COUNT(*) FROM ofertas WHERE status_tt='ERRO'").fetchone()[0]
            ultima = con.execute("SELECT criado_em FROM ofertas ORDER BY id DESC LIMIT 1").fetchone()
            
            return {
                "gerados": total_ofertas,
                "postados": total_postados,
                "erros": total_erros,
                "ultima": ultima[0] if ultima else "—"
            }
    except Exception as e:
        logger.error(f"Erro ao buscar stats reais: {e}")
        return {"gerados": 0, "postados": 0, "erros": 0, "ultima": "—"}
