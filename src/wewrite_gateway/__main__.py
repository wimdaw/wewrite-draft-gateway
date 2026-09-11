"""``python -m wewrite_gateway`` —— 等价于 ``wewrite-push``。"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
