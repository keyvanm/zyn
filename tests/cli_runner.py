import sys
from dataclasses import dataclass
from io import StringIO


@dataclass
class Result:
    exit_code: int
    output: str
    exception: Exception | None = None


class CliRunner:
    def invoke(self, fn, args=None, catch_exceptions=True):
        buf = StringIO()
        exit_code = 0
        exception = None
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = buf
        try:
            fn(list(args) if args else [])
        except SystemExit as e:
            exit_code = e.code if isinstance(e.code, int) else (1 if e.code else 0)
        except Exception as e:
            exception = e
            exit_code = 1
            if not catch_exceptions:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                raise
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        return Result(exit_code=exit_code, output=buf.getvalue(), exception=exception)
