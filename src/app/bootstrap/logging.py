import sys

from loguru import logger


def configure_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        # 예외의 SQL·입력값 대신 메시지에 명시한 에러 종류만 출력한다.
        format=lambda record: (
            "{time:YYYY-MM-DD HH:mm:ss.SSS Z} | {level} | "
            "{name}:{function}:{line} | {message}\n"
        ),
        backtrace=False,
        diagnose=False,
    )
