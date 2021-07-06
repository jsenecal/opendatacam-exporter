from datetime import datetime


def datetime_from_string(string: str) -> datetime:
    date_format = "%Y-%m-%dT%H:%M:%S.%fZ"
    return datetime.strptime(string, date_format)


def elapsed_seconds_from_strings(start: str, finish: str) -> float:
    if start is not None and finish is not None:
        dt_start = datetime_from_string(start)
        dt_finish = datetime_from_string(finish)
        return (dt_finish - dt_start).total_seconds()
    return 0
