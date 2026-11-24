def merge(intervals: list[list[int]]) -> list[list[int]]:
    out: list[list[int]] = []
    for start, end in intervals:
        if out and start < out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out
