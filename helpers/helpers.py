RED = "\033[31m"
GREEN = "\033[32m"
WHITE = "\033[37m"


def print_error(msg: str | Exception) -> None:
    print(f"{RED}ERROR: {msg}{WHITE}")


def print_success(msg: str) -> None:
    print(f"{GREEN}SUCCESS: {msg}{WHITE}")
