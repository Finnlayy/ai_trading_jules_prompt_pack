# custom exceptions
class RiskGateException(Exception):
    def __init__(self, message: str, reason_code: str):
        super().__init__(message)
        self.reason_code = reason_code
