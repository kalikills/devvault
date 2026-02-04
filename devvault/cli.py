from __future__ import annotations

def main() -> int:
    # Temporary delegation: keep scanner as the engine for now.
    from scanner.main import main as scanner_main
    return scanner_main()
