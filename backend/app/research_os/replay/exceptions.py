class TemporalLeakageError(Exception):
    """
    Raised whenever any code attempt is made to access, query, or infer 
    historical data at timestamps greater than the current Replay Clock time.
    """
    def __init__(self, requested_time, current_time, message=None):
        self.requested_time = requested_time
        self.current_time = current_time
        if message is None:
            message = (
                f"TEMPORAL LEAKAGE VIOLATION: Requested time {requested_time} "
                f"is strictly in the future relative to Replay Clock current_time {current_time}."
            )
        super().__init__(message)
