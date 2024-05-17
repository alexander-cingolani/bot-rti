from datetime import timedelta, datetime
from itertools import zip_longest


def _create_timedelta_from_str(string: str) -> timedelta:
    colons = string.count(":")

    if colons > 2:
        print("Invalid time/times.")
        raise ValueError
    if colons == 2:
        hours, minutes, seconds = string.split(":")
        milliseconds = "0"
    elif colons == 1:
        hours = "0"
        minutes, seconds = string.split(":")
    else:
        hours = "0"
        minutes = "0"
        seconds = string

    milliseconds = "0"
    if "." in seconds:
        seconds, milliseconds = seconds.split(".")

    return timedelta(
        hours=int(hours),
        minutes=int(minutes),
        seconds=int(seconds),
        milliseconds=int(milliseconds),
    )


def calculate_gaps():
    times_input = input("Paste times here: ")
    times_str = times_input.split()

    drivers = []
    if not times_str[0][0].isnumeric():
        drivers = times_str[0::2]
        times_str = times_str[1::2]

    best_time: timedelta
    for i, (time_str, driver) in enumerate(zip_longest(times_str, drivers)):
        td = _create_timedelta_from_str(time_str)
        if i == 0:
            best_time = td
            t = (datetime.min + best_time).time()
        else:
            delta = td - best_time  # type: ignore
            t = (datetime.min + delta).time()

        if not driver:
            driver = ""
        else:
            driver += " "
        if t.hour:
            print(driver + t.strftime("%X")[:-3])
        elif t.minute:
            print(driver + t.strftime("%-M:%S.%f")[:-3])
        else:
            print(driver + t.strftime("%-S.%f")[:-3])


if __name__ == "__main__":
    calculate_gaps()
