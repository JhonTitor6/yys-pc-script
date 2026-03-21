import datetime
import time

import requests

URL = "https://push-producter-ehfztureyc.us-east-1.fcapp.run/push/batch"

AUTH_TOKEN = "tokenData-a3c058g9g9989i8dc75d2cjc12gg"

HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
    "Connection": "close"
}

# 每个应用配置
APPS = [
    {
        "appId": 187,
        "account": "Native",
        "platform": "android",
        "clickUrl": "purecolor://com.colorstudio.purecolor?type=color&id=a977a156-b32a-4d9c-aa74-f0947cbc6f70&test_name=color",
        "fcmTokens": [
            # "dGdRDjGCS_2_P-XK1KJPQZ:APA91bFl49S4UHF8_m55LEo3QlA-SN9ivZQYiLTRtAvhifGKEOZPbQqebF1RkeBTfAWbU4SHAbz8B5ZeDai-sDwRXRP1FIt_hMwrs1GOPk1KZSFCM5O8YFo",
            # "e5QFbUgVRP2cHAI80gP3Uh:APA91bF7Qg61aA_I0JtaV_Dv89J33BpJ7mKSMzkhAdT5yqaBTJ5NLSLjpD9vCmS-N478jpUaMBwGWjMwYO0Rxy5_cRsko5ZeCAFGqFvZ8Dqa3nlE-CUZlxU",
            "fGj6coQ1SUqDJQkERlLb58:APA91bFKo6moHVJ3Vo46F6wrmaZKcCx5NrtOEO2PhSxO83rgrI1Ywjv6RQvSaOFDlrX6Gd2aWzYpkUyulLamaKWQDrOVm36T06xErRC8fUYY_CzcDqOv4U4"
        ]
    },
    {
        "appId": 108,
        "account": "Unity",
        "platform": "ios",
        "clickUrl": "vividcolor://com.colorstudio.vividcolor?type=color&id=5c876ca9-12b1-4670-a2b0-bc6f9f5edf66",
        "fcmTokens": [
            "fbJKsQjmSU3hn8MRIdbk7R:APA91bHCufenCI24X6MbDS-lEcaBkNR2IPAfQ6INuJdzy-dr0ZgLSG2LpCSzUT2UgcH_l_Tl1rkh9WUA9ol1zf5mFszd3NUBS3UhFxTnJLns9j_Q0GzkITo",
            "cX316qmONEiNqtWyq31iCF:APA91bEuOcKwkaj8mPx2-Q4Nvx2Cbt9gG9bZEgQCDa1akfg2IJ7IF0SXm9_ZUdyPe_12wvTUjg2qwT8nYkLgyEZF1sacnQDI6N5_C5tpcchHMWp6wUrWZug"
        ]
    }
]


IMAGE_URL = "https://d14caigaxudzuk.cloudfront.net/push_message_image/204cfea4d38e036137a3c4d62ad65670.jpg"


def send_push(app):
    body = {
        "messages": [
            {
                "fcmTokens": app["fcmTokens"],
                "title": "sent from python close app",
                "content": "sent from python close app",
                "appId": app["appId"],
                "platform": app["platform"],
                "account": app["account"],
                "imageUrl": IMAGE_URL,
                "clickUrl": app["clickUrl"],
                "delaySeconds": 0
            }
        ],
        "mode": "fcm"
    }

    try:
        r = requests.post(URL, json=body, headers=HEADERS, timeout=60)
        print(f"[{datetime.datetime.now()}] appId={app['appId']} status={r.status_code}")
        print(r.text)
    except Exception as e:
        print("send error", e)


def job():
    for app in APPS:
        send_push(app)


def wait_until_next_hour():
    now = datetime.datetime.now()
    next_hour = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    seconds = (next_hour - now).total_seconds()
    time.sleep(seconds)


def is_within_allowed_hours():
    """检查当前时间是否在允许的时间范围内（早上8点到晚上12点）"""
    now = datetime.datetime.now()
    current_hour = now.hour
    return 8 <= current_hour < 24  # 8点到24点（晚上12点）


if __name__ == "__main__":
    # 首次执行测试
    send_push(APPS[0])

    # while True:
    #     wait_until_next_hour()
    #
    #     # 每小时执行前检查时间
    #     if is_within_allowed_hours():
    #         job()
    #     else:
    #         print(f"跳过执行：当前时间 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 不在允许的时间范围内")