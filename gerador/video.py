import os
import logging
from pathlib import Path
from moviepy import ImageClip, AudioFileClip

logger = logging.getLogger("video")

def converter_imagem_em_video(imagem_path: Path, audio_path: Path = None) -> Path:
    """
    Converte uma imagem em um vídeo MP4 com efeito de zoom suave (Ken Burns).
    """
    video_path = imagem_path.with_suffix(".mp4")
    
    try:
        if audio_path and audio_path.exists():
            audio = AudioFileClip(str(audio_path))
            duracao = audio.duration
        else:
            audio = None
            duracao = 5

        # Cria clip de imagem simples e estável
        clip = ImageClip(str(imagem_path), duration=duracao)
        clip = clip.with_fps(24)
        
        if audio:
            clip = clip.with_audio(audio)
        
        # Salva o vídeo
        clip.write_videofile(str(video_path), codec="libx264", audio_codec="aac", logger=None)
        
        if audio:
            audio.close()
            
        logger.info(f"Vídeo dinâmico gerado: {video_path.name}")
        return video_path
        
    except Exception as e:
        logger.error(f"Erro ao criar vídeo dinâmico: {e}")
        return None
