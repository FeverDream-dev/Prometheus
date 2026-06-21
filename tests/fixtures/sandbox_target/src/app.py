"""Sandbox target fixture app — a trivial module for sandbox test verification."""


def add(a: int, b: int) -> int:
    return a + b


def main() -> None:
    print(f"2 + 3 = {add(2, 3)}")


if __name__ == "__main__":
    main()
