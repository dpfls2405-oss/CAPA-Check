
def judge_ratio(r, low_th, high_th, over_th):
    if r < low_th:
        return "과소"
    elif r <= high_th:
        return "적정"
    elif r <= over_th:
        return "다소과다"
    else:
        return "과다"
