import requests

def notify_line_with_image(token, msg, image_path):
    headers = {"Authorization": f"Bearer " + token}
    payload = {"message": msg}
    files = {"imageFile": open(image_path, "rb")}
    r = requests.post("https://notify-api.line.me/api/notify", headers=headers, data=payload, files=files)
    print("📤 LINE 通知送出：", r.status_code)
