"""Sample application entrypoint."""


class Greeter:
    """Greets callers."""

    def __init__(self, name: str) -> None:
        self.name = name

    def greet(self) -> str:
        return f"Hello, {self.name}!"


def main() -> None:
    greeter = Greeter("DocForge")
    print(greeter.greet())


if __name__ == "__main__":
    main()
