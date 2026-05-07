import requests

URL = "http://113.141.72.253:38000/api/v1/tasks/148/samples"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MTIsInVzZXJuYW1lIjoiZGVuZ2d1b2p1bkBnbWFpbC5jb20iLCJleHAiOjE3NzY5MjYyMjl9.yGtFInDyKWhwEVp9EEyvI1Y78j_16rQVlhoqF23IodM",
    "Connection": "keep-alive",
    "Content-Type": "application/json",
    "Origin": "http://113.141.72.253:38000",
    "Referer": "http://113.141.72.253:38000/tasks/148?page=10&size=10",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    ),
}


def delete_sample(sample_id: int) -> requests.Response:
    payload = {"sample_ids": [sample_id]}
    return requests.delete(URL, headers=HEADERS, json=payload, timeout=15)


def main(sample_id: int = 6551) -> None:
    response = delete_sample(sample_id)
    print(f"sample_id={sample_id}, status_code={response.status_code}")
    print(response.text)


if __name__ == "__main__":
    main(6552)
