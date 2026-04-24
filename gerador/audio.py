import asyncio
import edge_tts
import logging
from pathlib import Path

logger = logging.getLogger("audio")

OUTPUT_DIR = Path(__file__).parent.parent / "banco" / "audios"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VOICE = "pt-BR-AntonioNeural" # Voz masculina brasileira muito boa

async def gerar_audio(texto: str, nome_base: str) -> Path:
    """Transforma texto em áudio MP3."""
    caminho_audio = OUTPUT_DIR / f"{nome_base}.mp3"
    
    try:
        logger.info(f"Gerando áudio para: {nome_base}")
        communicate = edge_tts.Communicate(texto, VOICE)
        await communicate.save(str(caminho_audio))
        
        if caminho_audio.exists():
            return caminho_audio
    except Exception as e:
        logger.error(f"Erro ao gerar áudio: {e}")
    return None

def gerar_audio_sync(texto: str, nome_base: str) -> Path:
    """Versão síncrona para facilitar uso no motor."""
    return asyncio.run(gerar_audio(texto, nome_base))
