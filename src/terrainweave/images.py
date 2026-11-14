"""Reference-image discovery, masking, and statistics extraction."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from .configuration import (
    IMAGE_EXTENSIONS,
    SEMANTIC_EXCLUDE_LABELS,
)
from .metrics import luminance_histogram, rgb_histogram, texture_signature
from .models import ImageStats


class SemanticSegmenter:
    """Optional SegFormer inference wrapper for semantic input masks."""

    def __init__(self, model_name: str, device_name: str = "auto") -> None:
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
        except ImportError as error:
            raise RuntimeError(
                "Semantic segmentation requires optional dependencies. "
                "Install them with: python -m pip install -e '.[ml]'"
            ) from error

        self.torch = torch
        try:
            self.processor = AutoImageProcessor.from_pretrained(model_name)
            self.model = AutoModelForSemanticSegmentation.from_pretrained(model_name)
        except Exception as error:
            raise RuntimeError(f"Cannot load semantic model {model_name!r}: {error}") from error
        if device_name == "auto":
            if torch.backends.mps.is_available():
                device_name = "mps"
            elif torch.cuda.is_available():
                device_name = "cuda"
            else:
                device_name = "cpu"
        if device_name not in {"cpu", "mps", "cuda"}:
            raise ValueError("Device must be auto, cpu, mps, or cuda.")
        if device_name == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is not available.")
        if device_name == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("MPS was requested but is not available.")
        self.device = torch.device(device_name)
        self.model.to(self.device)
        self.model.eval()
        self.id_to_label = {
            int(index): str(label).lower() for index, label in self.model.config.id2label.items()
        }

    def predict(self, image: np.ndarray) -> tuple[np.ndarray, list[str], float, list[str]]:
        """Return a valid mask, labels present, and excluded-label diagnostics."""
        pil_image = Image.fromarray(image, mode="RGB")
        inputs = self.processor(images=pil_image, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with self.torch.no_grad():
            logits = self.model(**inputs).logits
        logits = self.torch.nn.functional.interpolate(
            logits,
            size=image.shape[:2],
            mode="bilinear",
            align_corners=False,
        )
        class_map = logits.argmax(dim=1)[0].detach().cpu().numpy()
        labels = sorted(
            {self.id_to_label.get(int(index), str(index)) for index in np.unique(class_map)}
        )
        excluded_ids = {
            index for index, label in self.id_to_label.items() if label in SEMANTIC_EXCLUDE_LABELS
        }
        valid = ~np.isin(class_map, list(excluded_ids))
        excluded_labels = sorted(
            self.id_to_label[index] for index in excluded_ids if np.any(class_map == index)
        )
        return valid, labels, float((~valid).mean()), excluded_labels


def automatic_valid_mask(image: np.ndarray) -> np.ndarray:
    """Return pixels likely to belong to ground, vegetation, or rocks.

    This is a fallback, not a semantic segmentation model. It removes strongly
    blue pixels and bright blue sky near the top of the image. A manual mask can
    override it when a photo contains unusual lighting or blue vegetation.
    """
    image_float = image.astype(np.float32)
    red, green, blue = image_float[..., 0], image_float[..., 1], image_float[..., 2]
    saturation = (image_float.max(axis=2) - image_float.min(axis=2)) / np.maximum(
        image_float.max(axis=2), 1
    )
    blue_dominant = (blue > red * 1.15) & (blue > green * 1.08) & (saturation > 0.12)
    height = image.shape[0]
    top_sky = np.zeros(image.shape[:2], dtype=bool)
    top_sky[: max(1, int(height * 0.18)), :] = True
    bright_sky = top_sky & (blue > red * 1.05) & (blue > green * 1.02) & (blue > 105)
    valid = ~(blue_dominant | bright_sky)
    # Do not fail on a mostly blue image: retain enough evidence to generate output.
    if valid.mean() < 0.35:
        return np.ones(image.shape[:2], dtype=bool)
    return valid


def discover_reference_paths(input_dir: Path, manifest: Path | None = None) -> list[Path]:
    """Discover reference images, or use only the files in an explicit split."""
    if manifest is None:
        return sorted(
            path
            for path in input_dir.rglob("*")
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
            and not path.name.endswith("_mask.png")
        )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError(f"Reference manifest must contain a list of records: {manifest}")
    paths = sorted({Path(record["file"]).resolve() for record in records})
    for path in paths:
        if not path.is_relative_to(input_dir.resolve()):
            raise ValueError(f"Reference image is outside {input_dir}: {path}")
        if not path.is_file():
            raise ValueError(f"Reference image not found: {path}")
    return [
        path
        for path in paths
        if path.suffix.lower() in IMAGE_EXTENSIONS and not path.name.endswith("_mask.png")
    ]


def load_images(
    input_dir: Path,
    sample_size: int = 20_000,
    use_auto_mask: bool = True,
    paths: list[Path] | None = None,
    segmenter: SemanticSegmenter | None = None,
    save_segmentation_masks: bool = False,
    segmentation_mask_dir: Path | None = None,
) -> list[ImageStats]:
    if paths is None:
        paths = sorted(
            path
            for path in input_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
    if not paths:
        raise ValueError(f"No images found in {input_dir}")

    images: list[ImageStats] = []
    for path in paths:
        with Image.open(path) as source:
            image = source.convert("RGB")
            # A common working size makes the statistics comparable and fast.
            image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            image_array = np.asarray(image, dtype=np.uint8)
            mask_path = path.with_name(f"{path.stem}_mask.png")
            semantic_excluded_fraction = 0.0
            semantic_excluded_labels: list[str] = []
            if mask_path.exists():
                with Image.open(mask_path) as mask_source:
                    mask = (
                        np.asarray(
                            mask_source.convert("L").resize(image.size, Image.Resampling.NEAREST)
                        )
                        > 127
                    )
                mask_source_name = "manual"
                semantic_labels: list[str] = []
            elif segmenter is not None:
                (
                    semantic_mask,
                    semantic_labels,
                    semantic_excluded_fraction,
                    semantic_excluded_labels,
                ) = segmenter.predict(image_array)
                color_mask = (
                    automatic_valid_mask(image_array)
                    if use_auto_mask
                    else np.ones(image_array.shape[:2], dtype=bool)
                )
                mask = semantic_mask & color_mask
                if mask.mean() < 0.35:
                    mask = semantic_mask
                mask_source_name = "semantic"
                if save_segmentation_masks and segmentation_mask_dir is not None:
                    relative_path = path.relative_to(input_dir).with_suffix(".png")
                    destination = segmentation_mask_dir / relative_path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    Image.fromarray((mask * 255).astype(np.uint8), mode="L").save(destination)
            elif use_auto_mask:
                mask = automatic_valid_mask(image_array)
                mask_source_name = "automatic"
                semantic_labels = []
            else:
                mask = np.ones(image_array.shape[:2], dtype=bool)
                mask_source_name = "none"
                semantic_labels = []
            if not mask.any():
                mask = np.ones(image_array.shape[:2], dtype=bool)
                mask_source_name = "fallback_all"
            pixels = image_array[mask].astype(np.float32)
            if len(pixels) > sample_size:
                indices = np.linspace(0, len(pixels) - 1, sample_size).astype(int)
                pixels = pixels[indices]
            # Replace excluded areas before measuring texture, so water/sky edges
            # do not become artificial texture targets.
            texture_image = image_array.copy()
            replacement = np.median(pixels, axis=0).astype(np.uint8)
            texture_image[~mask] = replacement
        images.append(
            ImageStats(
                path=f"{path} [{mask_source_name}]",
                group=classify_group(path, input_dir),
                pixels=pixels,
                rgb_histogram=rgb_histogram(pixels),
                luminance_histogram=luminance_histogram(pixels),
                texture_signature=texture_signature(texture_image),
                valid_fraction=float(mask.mean()),
                mask_source=mask_source_name,
                semantic_labels=semantic_labels,
                semantic_excluded_fraction=semantic_excluded_fraction,
                semantic_excluded_labels=semantic_excluded_labels,
            )
        )
    return images


def classify_group(path: Path, input_dir: Path) -> str:
    """Use an explicit subfolder first, then conservative filename keywords."""
    if path.parent != input_dir:
        return path.parent.name.lower()
    name = path.stem.lower()
    if any(token in name for token in ("desert", "deserto", "sahara", "marocco", "tamerice")):
        return "desert"
    if any(token in name for token in ("mountain", "montagna")):
        return "mountain"
    if any(
        token in name
        for token in (
            "urban",
            "urbano",
            "city",
            "street",
            "road",
            "building",
            "concrete",
            "asphalt",
        )
    ):
        return "urban"
    if any(
        token in name
        for token in ("snow", "neve", "snowy", "winter", "inverno", "glacier", "ghiaccio", "alpine")
    ):
        return "snow"
    if any(token in name for token in ("tundra", "arctic", "artico", "permafrost")):
        return "tundra"
    if any(token in name for token in ("taiga", "boreal", "boreale", "conifer", "conifera")):
        return "taiga"
    if any(
        token in name
        for token in ("jungle", "selva", "rainforest", "tropical", "tropics", "amazon", "monsoon")
    ):
        return "jungle"
    if any(token in name for token in ("forest", "foresta", "orman", "bosco", "castagno")):
        return "forest"
    return "other"


__all__ = [
    "ImageStats",
    "SemanticSegmenter",
    "automatic_valid_mask",
    "classify_group",
    "discover_reference_paths",
    "load_images",
]
