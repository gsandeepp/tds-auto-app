from fastapi import FastAPI, Request

app = FastAPI()

MY_SECRET = "YOLO"  # <--- Replace with your actual secret!

@app.post("/")
async def receive_request(request: Request):
    data = await request.json()
    print("Received JSON:", data)
    # Extract all important fields safely
    email = data.get("email")
    secret = data.get("secret")
    brief = data.get("brief")
    task = data.get("task")
    round_num = data.get("round")
    nonce = data.get("nonce")
    attachments = data.get("attachments")
    checks = data.get("checks")
    evaluation_url = data.get("evaluation_url")
    # Print all fields for debug
    print(f"Email: {email}")
    print(f"Secret: {secret}")
    print(f"Brief: {brief}")
    print(f"Task: {task}")
    print(f"Round: {round_num}")
    print(f"Nonce: {nonce}")
    print(f"Attachments: {attachments}")
    print(f"Checks: {checks}")
    print(f"Evaluation URL: {evaluation_url}")
    # Secret check!
    if secret != MY_SECRET:
        return {"status": "error", "reason": "Invalid secret"}
    return {
        "status": "ok",
        "email": email,
        "brief": brief,
        "task": task,
        "round": round_num,
        "nonce": nonce,
        "attachments": attachments,
        "checks": checks,
        "evaluation_url": evaluation_url
    }
