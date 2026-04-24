import os
import subprocess
import logging

logger = logging.getLogger(__name__)

class AudioProcessor:
    @staticmethod
    def separate_vocals(input_path: str, output_dir: str) -> str:
        """
        使用 Demucs 分离音频中的人声。
        :param input_path: 带伴奏的音频文件路径
        :param output_dir: 分离结果的输出目录
        :return: 提取出的 vocals.wav 的绝对路径
        """
        os.makedirs(output_dir, exist_ok=True)
        
        cmd = [
            "demucs",
            "--two-stems", "vocals",
            "-n", "htdemucs",
            "-o", output_dir,
            input_path
        ]
        
        logger.info(f"Starting Demucs separation: {' '.join(cmd)}")
        
        try:
            # 运行 demucs
            result = subprocess.run(
                cmd, 
                check=True, 
                capture_output=True, 
                text=True
            )
            logger.info("Demucs separation completed.")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.error(f"Demucs failed with error: {error_msg}")
            raise RuntimeError(f"Demucs separation failed: {error_msg}")
            
        # demucs 的默认输出结构为: <output_dir>/htdemucs/<filename_without_ext>/vocals.wav
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        vocals_path = os.path.join(output_dir, "htdemucs", base_name, "vocals.wav")
        
        if not os.path.exists(vocals_path):
            raise FileNotFoundError(f"Vocals file not found at expected path: {vocals_path}")
            
        return vocals_path
