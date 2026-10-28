"""Launcher for AuraFit - Adaptive Nutrition & Fitness App."""
import socket
import uvicorn

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8000
    print("\n" + "="*60)
    print("🚀 AuraFit App is starting!")
    print(f"💻 On your computer:  http://127.0.0.1:{port}")
    print(f"📱 On your phone:     http://{local_ip}:{port}")
    print("="*60)
    print("To install on iPhone: Open Safari -> Share -> Add to Home Screen")
    print("To install on Android: Open Chrome -> Tap menu -> Install App")
    print("="*60 + "\n")

    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)

