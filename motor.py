import os
import time
import logging
import threading
import schedule
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# â”€â”€ Configura logging â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s â€“ %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, "shopeebot.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("motor")

# â”€â”€ Importa mÃ³dulos do bot â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from scraper.shopee   import buscar_ofertas_api
from gerador.imagem   import gerar_imagem, gerar_legenda_gemini, gerar_roteiro_gemini
from gerador.audio    import gerar_audio_sync
from gerador.video    import converter_imagem_em_video
from tiktok.poster    import postar_video
from banco.db         import inicializar, salvar_oferta, marcar_postado, marcar_erro, registrar_log, listar_pendentes

# â”€â”€ Estado global â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_running   = False
_lock      = threading.Lock()
_stats     = {"buscas": 0, "gerados": 0, "postados": 0, "erros": 0, "ultima_execucao": "â€”"}


def ciclo_completo():
    """Executa um ciclo: busca â†’ gera â†’ posta."""
    global _stats
    logger.info("=" * 50)
    logger.info("Iniciando ciclo completo")

    with _lock:
        _stats["buscas"] += 1
        _stats["ultima_execucao"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # 1) Buscar ofertas
    try:
        ofertas = buscar_ofertas_api()
        logger.info(f"{len(ofertas)} ofertas encontradas")
        registrar_log("BUSCA", f"{len(ofertas)} ofertas")
    except Exception as e:
        logger.error(f"Erro na busca: {e}")
        with _lock:
            _stats["erros"] += 1
        return

    # 2) Para cada oferta, gerar imagem e salvar no banco
    for produto in ofertas[:5]:  # MÃ¡ximo 5 por ciclo pra nÃ£o spammar
        try:
            legenda      = gerar_legenda_gemini(produto)
            imagem_path  = gerar_imagem(produto, legenda)
            oferta_id    = salvar_oferta(produto, imagem_path, legenda)

            if oferta_id is None:
                logger.info(f"Oferta jÃ¡ existente, ignorando: {produto['nome'][:40]}")
                continue

            with _lock:
                _stats["gerados"] += 1

            logger.info(f"Imagem gerada para: {produto['nome'][:40]}")

        except Exception as e:
            logger.error(f"Erro ao gerar: {e}")
            with _lock:
                _stats["erros"] += 1

    # 3) Postar no TikTok os pendentes
    pendentes = listar_pendentes()
    logger.info(f"{len(pendentes)} ofertas pendentes para postar")

    for oferta in pendentes[:3]:  # MÃ¡ximo 3 posts por ciclo
        try:
            from pathlib import Path
            imagem_path = Path(oferta["imagem_path"])
            
            # 1) Gera Roteiro de fala com Gemini
            roteiro = gerar_roteiro_gemini(oferta)
            
            # 2) Gera Ãudio com voz humana (edge-tts)
            nome_limpo = oferta["nome"][:20].replace(" ", "_").replace("/", "")
            audio_path = gerar_audio_sync(roteiro, nome_limpo)
            
            # 3) Converte imagem em vÃ­deo com narraÃ§Ã£o
            video_path = converter_imagem_em_video(imagem_path, audio_path)
            
            if not video_path:
                logger.error(f"Falha ao criar vÃ­deo para: {oferta['nome']}")
                continue

            resultado = postar_video(video_path, oferta["legenda"])

            if resultado["sucesso"]:
                marcar_postado(oferta["id"], resultado.get("publish_id", ""), "PUBLICADO")
                with _lock:
                    _stats["postados"] += 1
                logger.info(f"Postado no TikTok: {oferta['nome'][:40]}")
                registrar_log("POST_OK", oferta["nome"])
                time.sleep(30)  # Aguarda entre posts
            else:
                logger.warning(f"Falha ao postar: {resultado.get('motivo')}")
                marcar_erro(oferta["id"], resultado.get("motivo", ""))
                registrar_log("POST_ERRO", resultado.get("motivo", ""))
                with _lock:
                    _stats["erros"] += 1

        except Exception as e:
            logger.error(f"Erro ao postar: {e}")
            with _lock:
                _stats["erros"] += 1

    logger.info("Ciclo concluÃ­do")


def iniciar():
    global _running
    _running = True

    inicializar()
    logger.info("ShopeeBot iniciado!")
    registrar_log("INICIO", "Bot iniciado")

    # Agendamento
    horarios = os.getenv("HORARIOS_POST", "08:00,12:00,18:00,21:00").split(",")
    for h in horarios:
        schedule.every().day.at(h.strip()).do(ciclo_completo)
        logger.info(f"Agendado para: {h.strip()}")

    # Executa imediatamente ao iniciar
    threading.Thread(target=ciclo_completo, daemon=True).start()

    # Loop do scheduler
    while _running:
        schedule.run_pending()
        time.sleep(30)


def parar():
    global _running
    _running = False
    registrar_log("PARADA", "Bot parado pelo usuÃ¡rio")
    logger.info("ShopeeBot parado.")


def get_stats() -> dict:
    from banco.db import get_estatisticas_reais
    db_stats = get_estatisticas_reais()
    
    with _lock:
        return {
            "buscas": _stats["buscas"],
            "gerados": db_stats["gerados"],
            "postados": db_stats["postados"],
            "erros": db_stats["erros"],
            "ultima_execucao": db_stats["ultima"]
        }


if __name__ == "__main__":
    iniciar()

