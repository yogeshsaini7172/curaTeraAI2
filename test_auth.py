import requests

data = {
    "email": "test@example.com",
    "password": "password123",
    "full_name": "Test User"
}
response = requests.post("http://localhost:5000/api/auth/signup", json=data)
print("SIGNUP:", response.status_code, response.text)
