from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from types import MethodType

import soundfile
import torch

logging.getLogger("numba").setLevel(logging.WARNING)

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[3]
BACKEND_ROOT = SCRIPT_PATH.parents[2]
REPO_ROOT = Path.cwd()

for candidate in (str(PROJECT_ROOT), str(BACKEND_ROOT), str(REPO_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.models_svc.style_film import StyleFiLMAdapter
from inference import infer_tool
from inference.infer_tool import Svc
from modules import commons
from spkmix import spk_mix_map
import utils
from utils import f0_to_coarse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="So-VITS-SVC conditioned inference")

    parser.add_argument("-m", "--model_path", type=str, required=True, help="model path")
    parser.add_argument("-c", "--config_path", type=str, required=True, help="config path")
    parser.add_argument("-cl", "--clip", type=float, default=0, help="forced clip seconds")
    parser.add_argument("-n", "--clean_names", type=str, nargs="+", required=True, help="raw wav file names under raw/")
    parser.add_argument("-t", "--trans", type=int, nargs="+", required=True, help="transpose in semitones")
    parser.add_argument("-s", "--spk_list", type=str, nargs="+", required=True, help="target speaker name list")

    parser.add_argument("-a", "--auto_predict_f0", action="store_true", default=False, help="enable automatic f0 prediction")
    parser.add_argument("-cm", "--cluster_model_path", type=str, default="", help="cluster or retrieval index path")
    parser.add_argument("-cr", "--cluster_infer_ratio", type=float, default=0, help="cluster/retrieval mix ratio")
    parser.add_argument("-lg", "--linear_gradient", type=float, default=0, help="crossfade seconds")
    parser.add_argument("-f0p", "--f0_predictor", type=str, default="pm", help="f0 predictor")
    parser.add_argument("-eh", "--enhance", action="store_true", default=False, help="use nsf-hifigan enhancer")
    parser.add_argument("-shd", "--shallow_diffusion", action="store_true", default=False, help="use shallow diffusion")
    parser.add_argument("-usm", "--use_spk_mix", action="store_true", default=False, help="use speaker mix")
    parser.add_argument("-lea", "--loudness_envelope_adjustment", type=float, default=1, help="loudness envelope adjustment")
    parser.add_argument("-fr", "--feature_retrieval", action="store_true", default=False, help="use feature retrieval")

    parser.add_argument("-dm", "--diffusion_model_path", type=str, default="logs/44k/diffusion/model_0.pt")
    parser.add_argument("-dc", "--diffusion_config_path", type=str, default="configs/diffusion.yaml")
    parser.add_argument("-ks", "--k_step", type=int, default=100)
    parser.add_argument("-se", "--second_encoding", action="store_true", default=False)
    parser.add_argument("-od", "--only_diffusion", action="store_true", default=False)

    parser.add_argument("-sd", "--slice_db", type=int, default=-40)
    parser.add_argument("-d", "--device", type=str, default=None)
    parser.add_argument("-ns", "--noice_scale", type=float, default=0.4)
    parser.add_argument("-p", "--pad_seconds", type=float, default=0.5)
    parser.add_argument("-wf", "--wav_format", type=str, default="wav")
    parser.add_argument("-lgr", "--linear_gradient_retain", type=float, default=0.75)
    parser.add_argument("-eak", "--enhancer_adaptive_key", type=int, default=0)
    parser.add_argument("-ft", "--f0_filter_threshold", type=float, default=0.05)

    parser.add_argument("--style-emb-path", type=str, default="", help="path to saved style embedding (.pt/.npy/.json)")
    parser.add_argument("--style-emb-format", type=str, default="pt", help="style embedding format")
    parser.add_argument("--condition-mode", type=str, default="internal_film", choices=["internal_film", "none"])
    parser.add_argument("--film-strength", type=float, default=0.1, help="FiLM gamma/beta clamp strength")
    parser.add_argument("--film-target", type=str, default="pre_decoder", help="internal FiLM injection target")
    parser.add_argument("--conditioning-report-path", type=str, default="", help="optional JSON report output path")
    return parser.parse_args()


def load_style_embedding(style_emb_path: str, style_emb_format: str, device: torch.device) -> torch.Tensor:
    path = Path(style_emb_path)
    if not path.exists():
        raise FileNotFoundError(f"style embedding not found: {path}")

    normalized_format = (style_emb_format or path.suffix.lstrip(".") or "pt").strip().lower()
    if normalized_format == "pt":
        payload = torch.load(path, map_location=device)
        if isinstance(payload, dict):
            tensor = payload.get("style_emb")
        else:
            tensor = payload
        if tensor is None:
            raise ValueError(f"style embedding payload missing 'style_emb': {path}")
        style_emb = torch.as_tensor(tensor, dtype=torch.float32, device=device)
    elif normalized_format == "npy":
        import numpy as np

        style_emb = torch.from_numpy(np.load(path)).to(device=device, dtype=torch.float32)
    elif normalized_format == "json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = payload.get("embedding")
        if values is None:
            raise ValueError(f"style embedding json missing 'embedding': {path}")
        style_emb = torch.tensor(values, dtype=torch.float32, device=device)
    else:
        raise ValueError(f"unsupported style embedding format: {normalized_format}")

    if style_emb.dim() == 1:
        style_emb = style_emb.unsqueeze(0)
    if style_emb.dim() != 2:
        raise ValueError(f"expected style embedding with shape [B, D] or [D], got {tuple(style_emb.shape)}")
    return style_emb


def apply_internal_film_patch(
    svc_model: Svc,
    style_emb: torch.Tensor,
    film_strength: float,
    film_target: str,
) -> dict[str, object]:
    if film_target != "pre_decoder":
        raise ValueError(f"unsupported film target: {film_target}")

    net_g = svc_model.net_g_ms
    if net_g is None:
        raise RuntimeError("So-VITS model was not loaded")

    target_device = net_g.pre.weight.device
    target_dtype = net_g.pre.weight.dtype
    style_emb = style_emb.to(device=target_device, dtype=target_dtype)
    adapter = StyleFiLMAdapter(
        style_dim=int(style_emb.shape[-1]),
        hidden_channels=int(net_g.inter_channels),
        strength=float(film_strength),
    ).to(device=target_device, dtype=target_dtype)
    net_g.text_style_film_adapter = adapter
    net_g.text_style_film_style_emb = style_emb
    net_g.text_style_film_target = film_target
    net_g.text_style_film_strength = float(film_strength)
    net_g.executed_internal_film = False

    @torch.no_grad()
    def conditioned_infer(self, c, f0, uv, g=None, noice_scale=0.35, seed=52468, predict_f0=False, vol=None):
        if c.device == torch.device("cuda"):
            torch.cuda.manual_seed_all(seed)
        else:
            torch.manual_seed(seed)

        c_lengths = (torch.ones(c.size(0)) * c.size(-1)).to(c.device)

        if self.character_mix and len(g) > 1:
            g = g.reshape((g.shape[0], g.shape[1], 1, 1, 1))
            g = g * self.speaker_map
            g = torch.sum(g, dim=1)
            g = g.transpose(0, -1).transpose(0, -2).squeeze(0)
        else:
            if g.dim() == 1:
                g = g.unsqueeze(0)
            g = self.emb_g(g).transpose(1, 2)

        x_mask = torch.unsqueeze(commons.sequence_mask(c_lengths, c.size(2)), 1).to(c.dtype)
        vol = self.emb_vol(vol[:, :, None]).transpose(1, 2) if vol is not None and self.vol_embedding else 0
        x = self.pre(c) * x_mask + self.emb_uv(uv.long()).transpose(1, 2) + vol

        if self.use_automatic_f0_prediction and predict_f0:
            lf0 = 2595.0 * torch.log10(1.0 + f0.unsqueeze(1) / 700.0) / 500.0
            norm_lf0 = utils.normalize_f0(lf0, x_mask, uv, random_scale=False)
            pred_lf0 = self.f0_decoder(x, norm_lf0, x_mask, spk_emb=g)
            f0 = (700 * (torch.pow(10, pred_lf0 * 500 / 2595) - 1)).squeeze(1)

        z_p, _m_p, _logs_p, c_mask = self.enc_p(x, x_mask, f0=f0_to_coarse(f0), noice_scale=noice_scale)
        z = self.flow(z_p, c_mask, g=g, reverse=True)

        # Text-conditioned internal Bias/Scale injection point.
        # This applies FiLM-style gamma/beta modulation to the hidden representation
        # before the decoder/generator consumes it.
        z = self.text_style_film_adapter(z, self.text_style_film_style_emb)
        self.executed_internal_film = True

        o = self.dec(z * c_mask, g=g, f0=f0)
        return o, f0

    net_g.infer = MethodType(conditioned_infer, net_g)
    return {
        "executed_internal_film": True,
        "film_target": film_target,
        "injection_target": film_target,
        "film_strength": float(film_strength),
        "style_dim": int(style_emb.shape[-1]),
        "hidden_channels": int(net_g.inter_channels),
    }


def write_report(args: argparse.Namespace, payload: dict[str, object]) -> None:
    if not args.conditioning_report_path:
        return
    report_path = Path(args.conditioning_report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()

    cluster_model_path = args.cluster_model_path
    if args.cluster_infer_ratio != 0:
        if cluster_model_path == "":
            cluster_model_path = "logs/44k/feature_and_index.pkl" if args.feature_retrieval else "logs/44k/kmeans_10000.pt"
    else:
        cluster_model_path = ""

    svc_model = Svc(
        args.model_path,
        args.config_path,
        args.device,
        cluster_model_path,
        args.enhance,
        args.diffusion_model_path,
        args.diffusion_config_path,
        args.shallow_diffusion,
        args.only_diffusion,
        args.use_spk_mix,
        args.feature_retrieval,
    )

    conditioning_payload: dict[str, object] = {
        "condition_mode": args.condition_mode,
        "style_emb_path": args.style_emb_path or None,
        "style_emb_format": args.style_emb_format,
        "film_strength": float(args.film_strength),
        "film_target": args.film_target,
        "injection_target": args.film_target,
        "executed_internal_film": False,
    }
    if args.condition_mode == "internal_film":
        if not args.style_emb_path:
            raise ValueError("--style-emb-path is required when --condition-mode=internal_film")
        style_emb = load_style_embedding(args.style_emb_path, args.style_emb_format, svc_model.dev)
        conditioning_payload.update(
            apply_internal_film_patch(
                svc_model=svc_model,
                style_emb=style_emb,
                film_strength=args.film_strength,
                film_target=args.film_target,
            )
        )

    infer_tool.mkdir(["raw", "results"])

    clean_names = args.clean_names
    trans = args.trans
    spk_list = args.spk_list
    if len(spk_mix_map) <= 1:
        args.use_spk_mix = False
    if args.use_spk_mix:
        spk_list = [spk_mix_map]

    infer_tool.fill_a_to_b(trans, clean_names)
    for clean_name, tran in zip(clean_names, trans):
        raw_audio_path = f"raw/{clean_name}"
        if "." not in raw_audio_path:
            raw_audio_path += ".wav"
        infer_tool.format_wav(raw_audio_path)
        for spk in spk_list:
            kwargs = {
                "raw_audio_path": raw_audio_path,
                "spk": spk,
                "tran": tran,
                "slice_db": args.slice_db,
                "cluster_infer_ratio": args.cluster_infer_ratio,
                "auto_predict_f0": args.auto_predict_f0,
                "noice_scale": args.noice_scale,
                "pad_seconds": args.pad_seconds,
                "clip_seconds": args.clip,
                "lg_num": args.linear_gradient,
                "lgr_num": args.linear_gradient_retain,
                "f0_predictor": args.f0_predictor,
                "enhancer_adaptive_key": args.enhancer_adaptive_key,
                "cr_threshold": args.f0_filter_threshold,
                "k_step": args.k_step,
                "use_spk_mix": args.use_spk_mix,
                "second_encoding": args.second_encoding,
                "loudness_envelope_adjustment": args.loudness_envelope_adjustment,
            }
            audio = svc_model.slice_inference(**kwargs)
            key = "auto" if args.auto_predict_f0 else f"{tran}key"
            cluster_name = "" if args.cluster_infer_ratio == 0 else f"_{args.cluster_infer_ratio}"
            suffix = "internal_film" if args.condition_mode == "internal_film" else "sovits"
            if args.use_spk_mix:
                spk = "spk_mix"
            res_path = f"results/{clean_name}_{key}_{spk}{cluster_name}_{suffix}_{args.f0_predictor}.{args.wav_format}"
            soundfile.write(res_path, audio, svc_model.target_sample, format=args.wav_format)
            svc_model.clear_empty()
            conditioning_payload["selected_output"] = res_path

    write_report(args, conditioning_payload)


if __name__ == "__main__":
    main()
