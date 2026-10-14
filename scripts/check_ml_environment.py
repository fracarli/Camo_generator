"""Check whether the optional neural segmentation environment is usable."""

from __future__ import annotations

import importlib
import sys


def main() -> int:
    print(f"Python: {sys.version.split()[0]}")
    packages = ("torch", "torchvision", "transformers")
    modules = {}
    failed = False
    for name in packages:
        try:
            module = importlib.import_module(name)
            modules[name] = module
            print(f"{name}: {getattr(module, '__version__', 'installed')}")
        except Exception as error:
            failed = True
            print(f"{name}: ERROR - {type(error).__name__}: {error}")

    if failed:
        print("\nInstall or repair the optional ML environment with:")
        print("python -m pip install --timeout 600 --retries 10 -r requirements-ml.txt")
        return 1

    torch = modules["torch"]
    print(f"torch CPU available: {torch.backends.cpu.get_cpu_capability()}")
    print(f"MPS available: {bool(torch.backends.mps.is_available())}")
    print("\nOptional ML environment looks importable.")
    print("The first semantic run may still download the Hugging Face model weights.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
