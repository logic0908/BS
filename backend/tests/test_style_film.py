import torch

from app.models_svc.style_film import StyleFiLMAdapter


def test_style_film_keeps_shape_and_dtype():
    adapter = StyleFiLMAdapter(style_dim=256, hidden_channels=32, strength=0.1)
    h = torch.randn(2, 32, 48, dtype=torch.float32)
    style_emb = torch.randn(2, 256, dtype=torch.float32)

    out = adapter(h, style_emb)

    assert out.shape == h.shape
    assert out.dtype == h.dtype
    assert torch.isfinite(out).all()


def test_style_film_returns_input_when_style_is_none():
    adapter = StyleFiLMAdapter(style_dim=256, hidden_channels=16, strength=0.1)
    h = torch.randn(1, 16, 12)

    out = adapter(h, None)

    assert torch.equal(out, h)


def test_style_film_returns_input_when_strength_zero():
    adapter = StyleFiLMAdapter(style_dim=256, hidden_channels=16, strength=0.0)
    h = torch.randn(1, 16, 12)
    style_emb = torch.randn(1, 256)

    out = adapter(h, style_emb)

    assert torch.equal(out, h)


def test_style_film_changes_hidden_representation_when_enabled():
    torch.manual_seed(0)
    adapter = StyleFiLMAdapter(style_dim=256, hidden_channels=16, strength=0.1)
    h = torch.randn(1, 16, 12)
    style_emb = torch.randn(1, 256)

    out = adapter(h, style_emb)

    assert not torch.allclose(out, h)
    assert torch.isfinite(out).all()
