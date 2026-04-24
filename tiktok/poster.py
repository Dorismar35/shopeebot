import os
import time
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("tiktok")

CLIENT_KEY     = os.getenv("TIKTOK_CLIENT_KEY", "")
CLIENT_SECRET  = os.getenv("TIKTOK_CLIENT_SECRET", "")
ACCESS_TOKEN   = os.getenv("TIKTOK_ACCESS_TOKEN", "")

BASE_URL = "https://open.tiktokapis.com/v2"


def _headers(token=None) -> dict:
    return {
        "Authorization": f"Bearer {token if token else ACCESS_TOKEN}",
        "Content-Type":  "application/json; charset=UTF-8",
    }


def renovar_token():
    """Renova o access_token usando o refresh_token."""
    global ACCESS_TOKEN
    refresh_token = os.getenv("TIKTOK_REFRESH_TOKEN", "")
    if not refresh_token:
        logger.error("TIKTOK_REFRESH_TOKEN não encontrado no .env")
        return False

    logger.info("Tentando renovar o token do TikTok...")
    try:
        resp = requests.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": CLIENT_KEY,
                "client_secret": CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        
        new_access = data.get("access_token")
        new_refresh = data.get("refresh_token")
        
        if new_access:
            env_path = Path(__file__).parent.parent / ".env"
            if env_path.exists():
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                with open(env_path, "w", encoding="utf-8") as f:
                    for line in lines:
                        if line.startswith("TIKTOK_ACCESS_TOKEN="):
                            f.write(f"TIKTOK_ACCESS_TOKEN={new_access}\n")
                        elif line.startswith("TIKTOK_REFRESH_TOKEN=") and new_refresh:
                            f.write(f"TIKTOK_REFRESH_TOKEN={new_refresh}\n")
                        else:
                            f.write(line)
            
            ACCESS_TOKEN = new_access
            logger.info("Token do TikTok renovado com sucesso!")
            return True
            
    except Exception as e:
        logger.error(f"Erro ao renovar token: {e}")
    return False


def postar_video(video_path: Path, legenda: str, retry_on_401=True) -> dict:
    """
    Posta um vídeo no TikTok usando o endpoint /v2/post/publish/video/init/.
    """
    if not ACCESS_TOKEN:
        logger.warning("TIKTOK_ACCESS_TOKEN não configurado.")
        return {"sucesso": False, "motivo": "Token não configurado"}

    try:
        video_size = os.path.getsize(video_path)
        
        # 1) Inicializa o upload de vídeo
        init_payload = {
            "post_info": {
                "description":      legenda[:4000],
                "privacy_level":    "PUBLIC_TO_EVERYONE", # Tenta público primeiro
                "disable_duet":     False,
                "disable_comment":  False,
                "disable_stitch":   False,
            },
            "source_info": {
                "source":             "FILE_UPLOAD",
                "video_size":         video_size,
                "chunk_size":         video_size,
                "total_chunk_count":  1
            }
        }

        init_resp = requests.post(
            f"{BASE_URL}/post/publish/video/init/",
            headers=_headers(),
            json=init_payload,
            timeout=15,
        )
        
        # Fallback: Se der erro de parâmetros ou permissão (por causa da privacidade pública não autorizada)
        if init_resp.status_code in [400, 403]:
            logger.warning(f"Falha ao postar como Público (Erro {init_resp.status_code}). Tentando como Privado (SELF_ONLY)...")
            init_payload["post_info"]["privacy_level"] = "SELF_ONLY"
            init_resp = requests.post(
                f"{BASE_URL}/post/publish/video/init/",
                headers=_headers(),
                json=init_payload,
                timeout=15,
            )

        init_resp.raise_for_status()
        data        = init_resp.json().get("data", {})
        publish_id  = data.get("publish_id")
        upload_url  = data.get("upload_url")

        if not upload_url:
            logger.error(f"TikTok não retornou upload_url: {init_resp.text}")
            return {"sucesso": False, "motivo": "Sem upload_url"}

        # 2) Faz upload do vídeo
        with open(video_path, "rb") as f:
            video_bytes = f.read()

        upload_resp = requests.put(
            upload_url,
            data=video_bytes,
            headers={
                "Content-Type": "video/mp4", 
                "Content-Length": str(video_size),
                "Content-Range": f"bytes 0-{video_size-1}/{video_size}"
            },
            timeout=60,
        )
        upload_resp.raise_for_status()

        logger.info(f"Vídeo enviado ao TikTok. publish_id={publish_id}")
        
        # Chama o comentário automático
        chamar_comentario(publish_id, ACCESS_TOKEN)
        
        return {"sucesso": True, "publish_id": publish_id}

    except requests.HTTPError as e:
        if e.response.status_code == 401 and retry_on_401:
            logger.warning("Erro 401 detectado. Tentando renovar token...")
            if renovar_token():
                return postar_video(video_path, legenda, retry_on_401=False)
        
        logger.error(f"Erro HTTP TikTok: {e.response.status_code} - {e.response.text}")
        return {"sucesso": False, "motivo": str(e)}
    except Exception as e:
        logger.error(f"Erro inesperado TikTok: {e}")
        return {"sucesso": False, "motivo": str(e)}


def chamar_comentario(publish_id: str, access_token: str):
    """
    Aguarda o post ser publicado e insere um comentário automático.
    """
    logger.info(f"Aguardando publicação do post {publish_id} para comentar...")
    
    # 1) Loop para aguardar o status 'PUBLISHED' e pegar o video_id
    video_id = None
    for attempt in range(10):
        try:
            time.sleep(10) # Aguarda processamento do TikTok
            resp = requests.post(
                f"{BASE_URL}/post/publish/status/fetch/",
                headers=_headers(access_token),
                json={"publish_id": publish_id},
                timeout=10,
            )
            data = resp.json().get("data", {})
            status = data.get("status")
            
            if status == "PUBLISHED" or status == "SUCCESS" or status == "PUBLISH_COMPLETE":
                video_id = data.get("public_id") or data.get("video_id")
                break
            elif status == "FAILED":
                logger.error(f"Falha na publicação: {data.get('fail_reason')}")
                return
        except Exception as e:
            logger.error(f"Erro ao verificar status para comentário: {e}")
            
    if not video_id:
        logger.warning(f"Não foi possível obter o video_id para o post {publish_id}")
        return

    # 2) Publica o comentário
    try:
        url_comm = f"{BASE_URL}/comment/publish/"
        link_afiliado = os.getenv("SHOPEE_AFFILIATE_LINK", "https://shopee.com.br")
        texto = (
            "🔥 LINK DA OFERTA AQUI 👇\n"
            f"{link_afiliado}\n"
            "✅ Clica e aproveita antes de acabar!"
        )
        
        comm_resp = requests.post(
            url_comm,
            headers=_headers(access_token),
            json={
                "video_id": video_id,
                "text": texto
            },
            timeout=15
        )
        if comm_resp.status_code == 200:
            logger.info(f"Comentário publicado com sucesso no vídeo {video_id}")
        else:
            logger.warning(f"Falha ao publicar comentário: {comm_resp.text}")
            
    except Exception as e:
        logger.error(f"Erro ao chamar API de comentário: {e}")


def verificar_status(publish_id: str) -> str:
    """Verifica o status de um post enviado."""
    try:
        resp = requests.post(
            f"{BASE_URL}/post/publish/status/fetch/",
            headers=_headers(),
            json={"publish_id": publish_id},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("status", "DESCONHECIDO")
    except Exception as e:
        logger.error(f"Erro ao verificar status: {e}")
        return "ERRO"
