# Logging

The SDK installs a `NullHandler` on import and does not change application
logging output by default.

Use `configure_logging_console(level)` to enable SDK console logs and
`configure_logging_file(path, level)` to write SDK logs to a file. Calling
`configure_logging_file()` repeatedly replaces the previous SDK file handler
instead of appending duplicate handlers.

High-frequency success paths such as movement commands, polling reads, and
subscription frame dispatch must not emit INFO logs. Use INFO for low-frequency
lifecycle events, WARNING for recoverable abnormal states, and ERROR for failed
operations.
